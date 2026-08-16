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

def podnyat():
    """Создаёт таблицы. Вызывать один раз при запуске."""
    if not na_postgres():
        if os.environ.get("RENDER"):
            print("[хранилище] ВНИМАНИЕ: на хостинге нет DATABASE_URL. "
                  "Подписчики будут стёрты при первом же перезапуске.", flush=True)
        else:
            print("[хранилище] файл:", FAYL, flush=True)
        return

    _vypolnit("""
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
        )""")
    # Таблица могла быть создана прошлой версией бота, без этого поля.
    # CREATE TABLE IF NOT EXISTS её не тронет, и запись цели упадёт молча.
    _vypolnit("ALTER TABLE podpischiki ADD COLUMN IF NOT EXISTS "
              "cel_kurs DOUBLE PRECISION")
    _vypolnit("ALTER TABLE podpischiki ADD COLUMN IF NOT EXISTS "
              "sprosili_podpisku BOOLEAN NOT NULL DEFAULT FALSE")
    # Таблица могла быть создана прошлой версией, где согласие было
    # включено по умолчанию. Меняем умолчание для новых записей; уже
    # накопленные не трогаем — снимать согласие у тех, кто его давал,
    # так же неправильно, как ставить тем, кто не давал.
    _vypolnit("ALTER TABLE podpischiki ALTER COLUMN uvedomlyat SET DEFAULT FALSE")

    _vypolnit("""
        CREATE TABLE IF NOT EXISTS sobytiya (
            id        BIGSERIAL PRIMARY KEY,
            chat_id   BIGINT,
            tip       TEXT NOT NULL,
            dannye    TEXT,
            sozdano_v TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )""")
    print("[хранилище] Postgres готов", flush=True)


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
    if polya.get("cel_kurs") == "sbros":
        polya["cel_kurs"] = None

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
    """Все, кто согласен получать оповещения."""
    if na_postgres():
        stroki = _vypolnit(
            "SELECT chat_id, lang, summa_rub, posledniy_verdikt, cel_kurs "
            "FROM podpischiki WHERE uvedomlyat = TRUE", vernut=True)
        if not stroki:
            return []
        return [{"chat_id": s[0], "lang": s[1], "summa_rub": s[2],
                 "posledniy_verdikt": s[3], "cel_kurs": s[4]} for s in stroki]
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


def svodka_istochnikov(dney=7):
    """Откуда приходили люди: канал, чат, чужая пересылка, напрямую.

    Зачем это отдельно от общей сводки. Денег на рекламу нет, значит
    каждый человек пришёл из какого-то одного места, и весь смысл посева
    в том, чтобы понять, из какого именно. Без этой разбивки видно только
    «пришло сорок человек» — и непонятно, повторять посев или бросать.

    Метку кладёт приложение в поле `istochnik` события «открыл». Пустая
    метка — человек открыл приложение сам, не по нашей ссылке.
    """
    if not na_postgres():
        return []
    stroki = _vypolnit(
        "SELECT COALESCE(dannye::json->>'istochnik', 'напрямую') AS otkuda, "
        "COUNT(*) FROM sobytiya "
        "WHERE tip = 'otkryt' AND sozdano_v > NOW() - INTERVAL '%s days' "
        # Событие без данных — это тоже «напрямую», а не повод уронить
        # запрос. Кастуем только то, что заведомо json.
        "AND (dannye IS NULL OR dannye LIKE '{%%') "
        "GROUP BY 1 ORDER BY COUNT(*) DESC" % int(dney), vernut=True)
    return [{"otkuda": s[0], "skolko": s[1]} for s in (stroki or [])]
