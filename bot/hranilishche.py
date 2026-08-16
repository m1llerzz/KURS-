# -*- coding: utf-8 -*-
"""ХРАНИЛИЩЕ — подписчики и события.

Почему это отдельный файл и почему Postgres.

На бесплатном тарифе Render диск стирается при каждом перезапуске и при
каждой заливке. Список подписчиков, стёртый в среду, — это не «неудобно»,
это конец продукта: единственный канал, по которому мы возвращаем людей,
исчезает молча, и никто этого не замечает, пока не станет поздно.

Поэтому: есть DATABASE_URL — работаем с Postgres (Neon, бесплатный тариф,
у Семёна уже заведён под другой проект). Нет — падаем на файл рядом с
кодом. Файл годится для работы на своей машине и НЕ годится для хостинга.
Если бот поднялся на Render без DATABASE_URL, он кричит об этом в журнал
при каждом запуске — молчаливая деградация здесь недопустима.

Единственная зависимость проекта: psycopg2-binary. Взята сознательно —
альтернатива это потеря аудитории.
"""
import json
import os
import threading
import time
from datetime import datetime, timezone

URL_BAZY = os.environ.get("DATABASE_URL", "").strip()
PAPKA = os.path.dirname(os.path.abspath(__file__))

# Путь можно подменить переменной. Нужно проверкам: без этого они писали
# живых людей в тот же файл, что и работающий бот, и однажды тестовый
# прогон затёр бы настоящий список. Заодно файл не попадает в репозиторий.
FAYL = os.environ.get("HRANILISHCHE_FAYL") or os.path.join(PAPKA, "podpischiki.json")

_zamok = threading.Lock()
_pg = None

if URL_BAZY:
    try:
        import psycopg2
        import psycopg2.extras
        _pg = psycopg2
    except ImportError:
        print("[хранилище] DATABASE_URL задан, но psycopg2 не установлен. "
              "Работаю через файл — на хостинге данные будут теряться.", flush=True)


def _teper():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def na_postgres():
    return bool(URL_BAZY and _pg)


# ── Postgres ─────────────────────────────────────────────────────────

def _soedinenie():
    return _pg.connect(URL_BAZY, connect_timeout=10)


def _vypolnit(sql, parametry=(), vernut=False):
    try:
        with _soedinenie() as soed:
            with soed.cursor() as kursor:
                kursor.execute(sql, parametry)
                if vernut:
                    return kursor.fetchall()
        return True
    except Exception as oshibka:
        print("[хранилище] запрос не прошёл:", repr(oshibka)[:200], flush=True)
        return None


# ── Файл ─────────────────────────────────────────────────────────────

def _chitat_fayl():
    if not os.path.exists(FAYL):
        return {}
    try:
        with open(FAYL, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _pisat_fayl(dannye):
    # Пишем через временный файл: обрыв посреди записи не должен оставлять
    # покорёженный json, из которого потом не поднимется весь список.
    vremenny = FAYL + ".tmp"
    with open(vremenny, "w", encoding="utf-8") as f:
        json.dump(dannye, f, ensure_ascii=False, indent=1)
    os.replace(vremenny, FAYL)


# ── Общий вход ───────────────────────────────────────────────────────

# Схема вынесена в константу по той же причине, что и запросы: базы под
# рукой при разработке нет, и проверить её можно только разбором. А
# ошибка здесь ломает не отчёт, а весь запуск — таблицы не создадутся, и
# всё остальное будет молча падать на каждом обращении.
SQL_SHEMA = ["""
        CREATE TABLE IF NOT EXISTS podpischiki (
            chat_id        BIGINT PRIMARY KEY,
            lang           TEXT    NOT NULL DEFAULT 'uz',
            summa_rub      INTEGER,
            bank_id        TEXT,
            -- ПО УМОЛЧАНИЮ НЕТ. Раньше здесь стояло TRUE, и человек,
            -- написавший боту одно слово, автоматически попадал в рассылку.
            -- Согласие, которого не давали, — это спам, как его ни назови.
            uvedomlyat     BOOLEAN NOT NULL DEFAULT FALSE,
            -- Спрашивали ли уже. Предложение подписки показывается один
            -- раз в жизни: второй раз это давление, а не предложение.
            sprosili_podpisku BOOLEAN NOT NULL DEFAULT FALSE,
            posledniy_verdikt TEXT,
            -- Курс, при котором человек просил его разбудить. Он ставит
            -- его сам — и именно поэтому возвращается: это его решение,
            -- а не наша рассылка.
            cel_kurs       DOUBLE PRECISION,
            uvedomlen_v    TIMESTAMPTZ,
            sozdan_v       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            aktiven_v      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )""",

    # Таблица могла быть создана прошлой версией бота, без этих полей.
    # CREATE TABLE IF NOT EXISTS её не тронет, и запись цели упала бы молча.
    "ALTER TABLE podpischiki ADD COLUMN IF NOT EXISTS cel_kurs DOUBLE PRECISION",
    "ALTER TABLE podpischiki ADD COLUMN IF NOT EXISTS "
    "sprosili_podpisku BOOLEAN NOT NULL DEFAULT FALSE",

    # Таблица могла быть создана прошлой версией, где согласие было
    # включено по умолчанию. Меняем умолчание для новых записей; уже
    # накопленные не трогаем — снимать согласие у тех, кто его давал,
    # так же неправильно, как ставить тем, кто не давал.
    "ALTER TABLE podpischiki ALTER COLUMN uvedomlyat SET DEFAULT FALSE",

    """
        CREATE TABLE IF NOT EXISTS sobytiya (
            id        BIGSERIAL PRIMARY KEY,
            chat_id   BIGINT,
            tip       TEXT NOT NULL,
            dannye    TEXT,
            sozdano_v TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )""",

    # Служебная память бота: что уже опубликовано, что уже разослано.
    # Раньше это жило в переменных внутри цикла, то есть в памяти
    # процесса. На бесплатном тарифе сервис перезапускается сам по себе, и
    # после каждого перезапуска бот считал, что сегодня ещё ничего не
    # публиковал, — и публиковал заново. 16 августа так вышло семнадцать
    # копий одного поста подряд.
    """
        CREATE TABLE IF NOT EXISTS sostoyanie (
            kluch      TEXT PRIMARY KEY,
            znachenie  TEXT,
            obnovleno  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )""",
]


def podnyat():
    """Создаёт таблицы. Вызывать один раз при запуске."""
    if not na_postgres():
        if os.environ.get("RENDER"):
            print("[хранилище] ВНИМАНИЕ: на хостинге нет DATABASE_URL. "
                  "Подписчики будут стёрты при первом же перезапуске, "
                  "а посты в канал и оповещения не будут выходить вовсе.",
                  flush=True)
        else:
            print("[хранилище] файл:", FAYL, flush=True)
        return

    for zapros in SQL_SHEMA:
        _vypolnit(zapros)
    print("[хранилище] Postgres готов", flush=True)


# ── Служебная память ─────────────────────────────────────────────────

def sostoyanie(kluch, po_umolchaniyu=None):
    """Что записано под этим ключом. Нет записи — `po_umolchaniyu`."""
    if na_postgres():
        ryady = _vypolnit("SELECT znachenie FROM sostoyanie WHERE kluch = %s",
                          (kluch,), vernut=True)
        if ryady:
            return ryady[0][0]
        return po_umolchaniyu

    return (_chitat_fayl().get("sostoyanie") or {}).get(kluch, po_umolchaniyu)


def zapisat_sostoyanie(kluch, znachenie):
    """Запоминает значение под ключом. Возвращает True, если получилось.

    Ответ важен: вызывающий по нему решает, публиковать ли. Если запомнить
    не удалось, честнее промолчать, чем отправить пост, о котором мы потом
    забудем и отправим его снова.
    """
    znachenie = str(znachenie)

    if na_postgres():
        return bool(_vypolnit(
            "INSERT INTO sostoyanie (kluch, znachenie, obnovleno) "
            "VALUES (%s, %s, NOW()) "
            "ON CONFLICT (kluch) DO UPDATE SET "
            "znachenie = EXCLUDED.znachenie, obnovleno = NOW()",
            (kluch, znachenie)))

    try:
        dannye = _chitat_fayl()
        dannye.setdefault("sostoyanie", {})[kluch] = znachenie
        _pisat_fayl(dannye)
        return True
    except Exception as oshibka:
        print("[хранилище] состояние не записалось:", repr(oshibka)[:200],
              flush=True)
        return False


def zapisat_cheloveka(chat_id, **polya):
    """Создаёт или обновляет человека. Пустые поля не затирают старые."""
    chat_id = int(chat_id)
    razresheno = {"lang", "summa_rub", "bank_id", "uvedomlyat",
                  "posledniy_verdikt", "uvedomlen_v", "cel_kurs",
                  "sprosili_podpisku"}
    # Список полей — не удобство, а защита: имена колонок подставляются
    # в SQL строкой, и без белого списка сюда однажды приедет что угодно.
    # Значение при этом всегда идёт параметром, никогда не склейкой.
    #
    # Отдельно: None означает «не трогать», а сбросить цель надо уметь.
    # Поэтому для сброса есть явная строка-пустышка, см. ниже.
    polya = {k: v for k, v in polya.items() if k in razresheno and v is not None}
    # Строка «sbros» означает «стереть» для любого поля. Обычный None
    # здесь значит «не трогать», и без отдельного слова стереть однажды
    # сохранённое было бы нечем.
    for k in list(polya):
        if polya[k] == "sbros":
            polya[k] = None

    with _zamok:
        if na_postgres():
            _vypolnit("INSERT INTO podpischiki (chat_id) VALUES (%s) "
                      "ON CONFLICT (chat_id) DO NOTHING", (chat_id,))
            if polya:
                kuski = ", ".join("%s = %%s" % k for k in polya)
                _vypolnit("UPDATE podpischiki SET " + kuski +
                          ", aktiven_v = NOW() WHERE chat_id = %s",
                          tuple(polya.values()) + (chat_id,))
            else:
                _vypolnit("UPDATE podpischiki SET aktiven_v = NOW() "
                          "WHERE chat_id = %s", (chat_id,))
            return

        vse = _chitat_fayl()
        # uvedomlyat False по умолчанию — так же, как в базе. Согласие,
        # которого не давали, не должно возникать из значения по умолчанию
        # ни в одном из двух хранилищ.
        chelovek = vse.get(str(chat_id), {"chat_id": chat_id, "uvedomlyat": False,
                                          "sprosili_podpisku": False,
                                          "lang": "uz", "sozdan_v": _teper()})
        chelovek.update(polya)
        chelovek["aktiven_v"] = _teper()
        vse[str(chat_id)] = chelovek
        _pisat_fayl(vse)


def chelovek(chat_id):
    chat_id = int(chat_id)
    if na_postgres():
        stroki = _vypolnit(
            "SELECT chat_id, lang, summa_rub, bank_id, uvedomlyat, "
            "posledniy_verdikt, cel_kurs, sprosili_podpisku "
            "FROM podpischiki WHERE chat_id = %s", (chat_id,), vernut=True)
        if not stroki:
            return None
        s = stroki[0]
        return {"chat_id": s[0], "lang": s[1], "summa_rub": s[2],
                "bank_id": s[3], "uvedomlyat": s[4], "posledniy_verdikt": s[5],
                "cel_kurs": s[6], "sprosili_podpisku": s[7]}
    return _chitat_fayl().get(str(chat_id))


def podpisannye():
    """Все, кто согласен получать оповещения.

    `uvedomlen_v` отдаётся вместе с остальным: по нему решается, не писали
    ли человеку слишком недавно. Раньше поле было в таблице, но наружу не
    выходило — и правило «не чаще раза в трое суток» существовало только
    в документах.
    """
    if na_postgres():
        stroki = _vypolnit(
            "SELECT chat_id, lang, summa_rub, posledniy_verdikt, cel_kurs, "
            "uvedomlen_v FROM podpischiki WHERE uvedomlyat = TRUE", vernut=True)
        if not stroki:
            return []
        return [{"chat_id": s[0], "lang": s[1], "summa_rub": s[2],
                 "posledniy_verdikt": s[3], "cel_kurs": s[4],
                 "uvedomlen_v": s[5].isoformat() if s[5] else None}
                for s in stroki]
    return [c for c in _chitat_fayl().values() if c.get("uvedomlyat")]


def s_celyu():
    """Те, кто назначил свой курс и ждёт его.

    Отдельно от подписки намеренно: человек может не хотеть регулярных
    сообщений, но хотеть один-единственный сигнал про свой курс. Это его
    решение, и оно сильнее любой нашей рассылки.
    """
    if na_postgres():
        stroki = _vypolnit(
            "SELECT chat_id, lang, summa_rub, cel_kurs FROM podpischiki "
            "WHERE cel_kurs IS NOT NULL", vernut=True)
        if not stroki:
            return []
        return [{"chat_id": s[0], "lang": s[1], "summa_rub": s[2],
                 "cel_kurs": s[3]} for s in stroki]
    return [c for c in _chitat_fayl().values() if c.get("cel_kurs")]


def skolko_vsego():
    if na_postgres():
        stroki = _vypolnit("SELECT COUNT(*), COUNT(*) FILTER (WHERE uvedomlyat) "
                           "FROM podpischiki", vernut=True)
        return (stroki[0][0], stroki[0][1]) if stroki else (0, 0)
    vse = _chitat_fayl()
    return len(vse), sum(1 for c in vse.values() if c.get("uvedomlyat"))


def sobytie(chat_id, tip, dannye=None):
    """Учёт. Бесплатный, свой, без внешних сервисов — см. METRICS.md.

    Сбой записи события не должен ронять разговор с человеком: аналитика
    важна нам, а не ему.
    """
    try:
        stroka = json.dumps(dannye, ensure_ascii=False) if dannye else None
        if na_postgres():
            _vypolnit("INSERT INTO sobytiya (chat_id, tip, dannye) VALUES (%s, %s, %s)",
                      (chat_id, tip, stroka))
        else:
            print("[событие]", tip, chat_id, stroka or "", flush=True)
    except Exception:
        pass


def svodka_sobytiy(dney=7):
    """Что происходило за неделю. Нужна для еженедельной сверки метрик."""
    if not na_postgres():
        return []
    stroki = _vypolnit(
        "SELECT tip, COUNT(*) FROM sobytiya "
        "WHERE sozdano_v > NOW() - INTERVAL '%s days' "
        "GROUP BY tip ORDER BY COUNT(*) DESC" % int(dney), vernut=True)
    return [{"tip": s[0], "skolko": s[1]} for s in (stroki or [])]


# Запрос вынесен из функции нарочно: без базы под рукой его никак не
# проверить, а собрать строку и посмотреть на неё — можно. Проверка в
# test_bot.py следит, чтобы двойные проценты свернулись и интервал
# подставился в обе половины.
SQL_ISTOCHNIKI = (
    "SELECT otkuda, SUM(skolko) FROM ("
    "  SELECT COALESCE(NULLIF(dannye::json->>'istochnik', ''), 'напрямую')"
    "         AS otkuda, COUNT(*) AS skolko"
    "  FROM sobytiya"
    "  WHERE tip = 'otkryt' AND sozdano_v > NOW() - INTERVAL '%(d)s days'"
    # Событие без данных — это тоже «напрямую», а не повод уронить запрос.
    # Кастуем только то, что заведомо json.
    "    AND (dannye IS NULL OR dannye LIKE '{%%')"
    "  GROUP BY 1"
    "  UNION ALL"
    "  SELECT COALESCE(NULLIF(dannye::json->>'start', ''), 'напрямую')"
    "         AS otkuda, COUNT(*) AS skolko"
    "  FROM sobytiya"
    "  WHERE tip = 'novyy' AND sozdano_v > NOW() - INTERVAL '%(d)s days'"
    "    AND (dannye IS NULL OR dannye LIKE '{%%')"
    "  GROUP BY 1"
    ") AS vse GROUP BY otkuda ORDER BY SUM(skolko) DESC"
)


# Воронка по источникам: пришёл — посчитал. Метка лежит в каждом
# событии, а не только в «открыл», поэтому считать можно оба шага.
#
# Зачем именно так. По одним переходам источники не различить: чат с
# двумя сотнями заходов и нулём расчётов хуже, чем чат с двадцатью
# заходами и пятнадцатью расчётами. Первый — случайные зеваки, второй —
# люди с деньгами в руках. Ради этой разницы посев и ведётся по одному
# чату за раз, и без второго столбца весь труд насмарку.
SQL_VORONKA = (
    "SELECT COALESCE(NULLIF(dannye::json->>'istochnik', ''), 'напрямую')"
    "       AS otkuda,"
    "       COUNT(*) FILTER (WHERE tip = 'otkryt')  AS prishli,"
    "       COUNT(*) FILTER (WHERE tip = 'raschet') AS poschitali,"
    "       COUNT(*) FILTER (WHERE tip = 'share')   AS pereslali"
    "  FROM sobytiya"
    " WHERE sozdano_v > NOW() - INTERVAL '%(d)s days'"
    "   AND tip IN ('otkryt', 'raschet', 'share')"
    "   AND (dannye IS NULL OR dannye LIKE '{%%')"
    " GROUP BY 1 ORDER BY 2 DESC"
)


def voronka_istochnikov(dney=7):
    """По каждому источнику: пришли, посчитали, переслали.

    Возвращает список; **None означает «запрос не выполнился»**, и это
    не то же самое, что пустой список.

    Зачем различать. Запрос сложный, а базы под рукой при разработке
    нет — Postgres негде поднять, и синтаксис проверяется только на
    боевом. Если он однажды упадёт, `_vypolnit` поймает исключение и
    вернёт пустоту, сводка покажет «источников нет», и это прочтётся как
    «людей не было». Разница между «никто не приходил» и «мы сломались»
    — это разница между «ждём» и «чиним сегодня».
    """
    if not na_postgres():
        return []
    stroki = _vypolnit(SQL_VORONKA % {"d": int(dney)}, vernut=True)
    if stroki is None:
        return None
    return [{"otkuda": s[0], "prishli": int(s[1]),
             "poschitali": int(s[2]), "pereslali": int(s[3])}
            for s in stroki]


def svodka_istochnikov(dney=7):
    """Откуда приходили люди: канал, чат, чужая пересылка, напрямую.

    Зачем это отдельно от общей сводки. Денег на рекламу нет, значит
    каждый человек пришёл из какого-то одного места, и весь смысл посева
    в том, чтобы понять, из какого именно. Без этой разбивки видно только
    «пришло сорок человек» — и непонятно, повторять посев или бросать.

    Метка приходит из двух мест, и считать надо оба:

        otkryt.istochnik — человек открыл приложение по нашей ссылке
                           (канал, поиск, чужая пересылка);
        novyy.start      — человек написал БОТУ по ссылке с меткой.
                           Так помечаются чаты при посеве: у каждого чата
                           своя ссылка вида t.me/бот?start=chat_moskva.

    Без второго половина посева была бы не видна: в чатах ссылку дают на
    бота, а не на приложение, и эти люди не попадали в счёт вовсе.

    Пустая метка — человек пришёл сам, не по нашей ссылке.
    """
    if not na_postgres():
        return []
    stroki = _vypolnit(SQL_ISTOCHNIKI % {"d": int(dney)}, vernut=True)
    return [{"otkuda": s[0], "skolko": int(s[1])} for s in (stroki or [])]
