# -*- coding: utf-8 -*-
"""ПРОВЕРКА БОЕВОГО — того, что видит человек прямо сейчас.

    py proverit_zhivoe.py

Чем отличается от `proverit.py`. Тот проверяет код на твоей машине. Этот
ходит по настоящим адресам и смотрит, что отдаётся людям: залилось ли
приложение, поднялся ли бот с новым кодом, свежие ли курсы, не показываем
ли мы кому-то цифру недельной давности.

Зелёный `proverit.py` при красном `proverit_zhivoe.py` означает ровно одно:
код хороший, а у людей он не работает. Второе важнее.

Запускать после каждой заливки и раз в несколько дней просто так.
"""
import json
import re
import ssl
import subprocess
import sys
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

PRILOZHENIE = "https://m1llerzz.github.io/KURS-/"
BOT = "https://qanchayetadi-bot.onrender.com"

# Канал читается с его публичной страницы, без токена. Токен здесь был
# бы лишним доступом ради одной даты, а у сторожа на GitHub его нет и
# быть не должно.
KANAL = "https://t.me/rublkursi_bugun"

# Папка приложения — отсюда берётся calc.js, чтобы разбирать ответ ЦБ тем
# же кодом, что стоит у людей.
KORNI_APP = os.path.dirname(os.path.abspath(__file__))

# Правило «молчит ли канал» лежит у бота и ввозится, а не переписывается
# здесь: по нему сторож шлёт письма, и вторая его копия однажды разойдётся
# с первой. Ввоз стоит ниже обычного места для ввозов, потому что раньше
# неизвестен путь. Зависимостей `tishina` не тянет — сторож ничего не
# ставит, и ставить ему нечего.
sys.path.insert(0, os.path.join(KORNI_APP, "bot"))
import tishina  # noqa: E402

# Сегодняшнее ТАШКЕНТСКОЕ число: курс датируется днём того места, где его
# публикуют, и приложение спрашивает архив именно за него.
_SEGODNYA_UZ = (datetime.now(timezone.utc).timestamp() + 5 * 3600)
_SEGODNYA_UZ = datetime.fromtimestamp(_SEGODNYA_UZ, timezone.utc).date().isoformat()
CBU_SEGODNYA = ("https://cbu.uz/ru/arkhiv-kursov-valyut/json/all/%s/"
                % _SEGODNYA_UZ)

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE

ZELYONY, KRASNY, ZHELTY, SBROS = "\033[32m", "\033[91m", "\033[33m", "\033[0m"

# Цвет — только живому терминалу. В журнал GitHub и в файл уезжают голые
# управляющие последовательности: их читает не человек, а сторож, и
# «\033[91m- бот отвечает» он должен видеть как «- бот отвечает».
if not sys.stdout.isatty():
    ZELYONY = KRASNY = ZHELTY = SBROS = ""

if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleMode(
            ctypes.windll.kernel32.GetStdHandle(-11), 7)
    except Exception:
        ZELYONY = KRASNY = ZHELTY = SBROS = ""

proshlo, upalo, predupredit = [], [], []


def proverka(imya, uslovie, podskazka=""):
    if uslovie:
        proshlo.append(imya)
    else:
        upalo.append(imya + ("  << " + podskazka if podskazka else ""))


def preduprezhdenie(imya, podskazka=""):
    predupredit.append(imya + ("  << " + podskazka if podskazka else ""))


def skachat(url, timeout=90):
    zapros = urllib.request.Request(url, headers={"User-Agent": "qy-proverka/1"})
    try:
        with urllib.request.urlopen(zapros, timeout=timeout, context=_CTX) as o:
            # Имена заголовков приводим к нижнему регистру. Cloudflare перед
            # Render переписывает их по-своему: бот шлёт
            # Access-Control-Allow-Origin, а до нас доезжает
            # access-control-allow-origin. Точное сравнение объявляло
            # рабочий продукт сломанным.
            zagolovki = {k.lower(): v for k, v in o.headers.items()}
            return o.status, o.read().decode("utf-8", "replace"), zagolovki
    except urllib.error.HTTPError as e:
        return e.code, "", {}
    except Exception as e:
        return None, "ОШИБКА " + repr(e)[:160], {}


# Возраст запаса в data.js: считается при разборе приложения, а судится
# после ответа бота — пока бот жив, запас никто не видит.
vozrast_zapasa = None
sobran_zapas = ""
data_js = ""

print("Проверка боевого — то, что видит человек")
print("=" * 62)

# ── Приложение ───────────────────────────────────────────────────────

print("\nПриложение: " + PRILOZHENIE)
kod, html, _ = skachat(PRILOZHENIE)
proverka("приложение открывается", kod == 200, "код " + str(kod))

if kod == 200:
    proverka("это наше приложение", "Qancha yetadi" in html)
    proverka("вердикт дня есть в разметке", 'id="verdict"' in html,
             "первый экран продукта")
    proverka("быстрый выбор суммы на месте", 'id="chips"' in html)
    proverka("график курса на месте", 'id="vSpark"' in html)
    proverka("оба языка на месте",
             'data-lang="uz"' in html and 'data-lang="ru"' in html,
             "русский обязателен наравне с узбекским")

    versii = set(re.findall(r'\.js\?v=(\d+)', html))
    proverka("у всех скриптов одна версия", len(versii) == 1,
             "версии разъехались: " + str(sorted(versii)) +
             " — часть файлов приедет из кеша старой")

    # Файлы приложения должны реально отдаваться, а не только упоминаться.
    for fayl in ("i18n.js", "data.js", "calc.js", "app.js"):
        k, telo, _ = skachat(PRILOZHENIE + fayl)
        proverka("отдаётся " + fayl, k == 200 and len(telo) > 500,
                 "код " + str(k))

    k, data_js, _ = skachat(PRILOZHENIE + "data.js")
    if k == 200:
        proverka("тестовые данные выключены",
                 "window.TEST_DATA = false" in data_js,
                 "с TEST_DATA = true людям показывать нельзя")
        proverka("в запасе есть история курса", "HISTORY_ZAPAS" in data_js)

        # ── Возраст запаса у ЛЮДЕЙ ───────────────────────────────────
        #
        # Это единственная проверка возраста во всём проекте, и стоит она
        # именно здесь. В `proverit.py` привязка к календарю запрещена:
        # там проверяется код, а код от даты не зависит, и красное на
        # исправном коде обесценивает весь прогон. Здесь проверяется мир —
        # то, что человек видит прямо сейчас, — и возраст запаса это и
        # есть главный вопрос к миру.
        #
        # Зачем. С 24 по 31 августа приложение было погашено: бот
        # приостановлен, запас не пересобирался, курсы сервисов
        # перевалили за 72 часа, и правило свежести спрятало список
        # целиком. Человек открывал продукт и не видел НИ ОДНОГО способа.
        # Эта проверка тогда была зелёной от первой строки до последней:
        # приложение открывалось, файлы отдавались, история была на месте.
        # Молчаливее поломки не бывает.
        sobrano = re.findall(r'"checked_at":\s*"([^"]+)"', data_js)
        if not sobrano:
            preduprezhdenie("в запасе нет даты сбора",
                            "без неё возраст курсов не узнать")
        else:
            # Разбираем ВСЕ отметки и берём самую позднюю по времени, а не
            # по алфавиту: строки со смещением «+05:00» и «+00:00»
            # сравниваются как текст неправильно, и «свежайшей» оказалась бы
            # не та. Отметка без часового пояса считается UTC — так её и
            # пишет сборщик; молча вычесть её из времени с поясом нельзя,
            # это не ошибка значения, а ошибка типа, и она уронила бы всю
            # проверку боевого вместе со сторожем.
            kogdy = []
            for syraya in sobrano:
                try:
                    t = datetime.fromisoformat(syraya.strip().replace("Z", "+00:00"))
                except Exception:
                    continue
                if t.tzinfo is None:
                    t = t.replace(tzinfo=timezone.utc)
                kogdy.append((t, syraya))

            if not kogdy:
                chasov = None
                preduprezhdenie("не разобрал ни одной даты сбора в запасе",
                                ", ".join(sobrano[:2])[:80])
            else:
                kogda, svezhaya = max(kogdy)
                chasov = (datetime.now(timezone.utc) - kogda).total_seconds() / 3600

            # Судить о запасе будем ПОСЛЕ того, как спросим бота.
            #
            # Запас — страховка, а не то, что человек видит обычно: пока
            # бот отвечает, приложение считает по его свежим курсам, и
            # протухший запас никому не мешает. Красное здесь, когда бот
            # жив, — это красное на работающем продукте.
            vozrast_zapasa = chasov
            sobran_zapas = svezhaya[:16]

# ── Второй слой курса: ЦБ прямо из браузера ──────────────────────────
#
# Официальный курс приложение спрашивает у ЦБ само, минуя наш сервер. Всё
# это держится на двух вещах, которые нам никто не обещал: на заголовке
# `access-control-allow-origin` у cbu.uz и на том, что поля в их ответе
# называются так же, как вчера. Пропадёт первое — слой умрёт молча, у
# каждого человека в браузере и ни у кого в журналах. Изменится второе —
# разбор вернёт None, и приложение тихо откатится к запасу.
#
# Проверяем оба, на живом ответе и тем же кодом, что стоит в приложении.

razobrano_cb = None
print("\nВторой слой курса: " + CBU_SEGODNYA)
kod_cb, otvet_cb, zagolovki_cb = skachat(CBU_SEGODNYA, timeout=30)
proverka("ЦБ отвечает приложению", kod_cb == 200, "код " + str(kod_cb))

if kod_cb == 200:
    proverka("ЦБ разрешает читать себя из браузера",
             zagolovki_cb.get("access-control-allow-origin") == "*",
             "без этого заголовка приложение не сможет спросить курс само: "
             + str(zagolovki_cb.get("access-control-allow-origin")))

    # Разбираем ТЕМ ЖЕ кодом, что стоит в приложении. Своя проверка полей
    # здесь проверяла бы себя: разойтись она может ровно так же, как и
    # приложение, и молча.
    try:
        gotovo = subprocess.run(
            ["node", "-e",
             "global.window={};require(process.argv[1]);"
             "const d=JSON.parse(process.argv[2]);"
             "process.stdout.write(JSON.stringify("
             "window.CALC.razborKursaCB(d, process.argv[3])||null));",
             os.path.join(KORNI_APP, "calc.js"), otvet_cb, _SEGODNYA_UZ],
            capture_output=True, text=True, encoding="utf-8", timeout=60)
        razobrano_cb = json.loads(gotovo.stdout or "null")
    except FileNotFoundError:
        razobrano_cb = None
        preduprezhdenie("node не найден", "разбор ответа ЦБ не проверен")
    except Exception as e:
        razobrano_cb = None
        preduprezhdenie("разбор ответа ЦБ не выполнен", repr(e)[:120])
    else:
        proverka("приложение разбирает сегодняшний ответ ЦБ",
                 bool(razobrano_cb) and 50 < (razobrano_cb.get("rub_uzs") or 0) < 500,
                 "поля ответа изменились — приложение молча откатится к запасу: "
                 + (gotovo.stderr or gotovo.stdout or "")[:160])
        if razobrano_cb:
            proverka("у разобранного курса есть дата публикации",
                     bool(razobrano_cb.get("date")),
                     "цифра без даты в этом продукте не показывается")

# ── Страница под поиск ───────────────────────────────────────────────
#
# Её не открывает никто из нас, и именно поэтому она сломается молча.
# А для поиска молчаливая поломка означает выпадение из выдачи, о котором
# узнаёшь через три месяца по отсутствию людей.

print("\nСтраница поиска: " + PRILOZHENIE + "kurs.html")
kod, stranica, _ = skachat(PRILOZHENIE + "kurs.html")
proverka("страница поиска открывается", kod == 200, "код " + str(kod))

if kod == 200:
    proverka("заголовок ловит запрос про курс",
             re.search(r"<title>[^<]*[Кк]урс рубля", stranica) is not None)
    proverka("описание для выдачи на месте",
             'name="description"' in stranica)
    proverka("оба языка на странице",
             'lang="uz"' in stranica and 'lang="ru"' in stranica)
    proverka("разметка вопрос-ответ на месте",
             "FAQPage" in stranica)
    proverka("ссылка в приложение помечена источником",
             "startapp=poisk" in stranica,
             "без метки переходы из поиска не отличить от остальных")

    # Числа на странице переписывает obnovit_zapas.py. Если они застыли,
    # страница будет годами показывать позапрошлый курс, выглядя исправной.
    kurs_na_stranice = re.search(r'data-zapas="kurs">([\d,]+)<', stranica)
    proverka("курс в разметке на месте", kurs_na_stranice is not None)

    # Дату разбираем целиком, а не по году.
    #
    # Здесь стояла проверка «год не прошлый». Она пропускала страницу с
    # курсом двухмесячной давности: год тот же, а число давно чужое.
    # Страница живёт ради одного запроса — «курс рубля к суму сегодня»,
    # — и человек, пришедший из поиска на позавчерашнее число, уходит
    # молча. Порог тот же, что у совета в приложении: пять дней. ЦБ не
    # публикует по выходным и в праздники, и длинные каникулы — норма.
    MESYACY_RU_ = ["января", "февраля", "марта", "апреля", "мая", "июня",
                   "июля", "августа", "сентября", "октября", "ноября",
                   "декабря"]
    data_na_stranice = re.search(r'data-zapas="data_ru">([^<]+)<', stranica)
    if data_na_stranice:
        syraya = data_na_stranice.group(1).strip()
        razobrano = re.match(r"(\d{1,2})\s+([А-Яа-яё]+)\s+(\d{4})", syraya)
        if not razobrano or razobrano.group(2).lower() not in MESYACY_RU_:
            preduprezhdenie("дату на странице не разобрал", syraya)
        else:
            na_stranice = "%s-%02d-%02d" % (
                razobrano.group(3),
                MESYACY_RU_.index(razobrano.group(2).lower()) + 1,
                int(razobrano.group(1)))

            # Сверяем с ДАТОЙ ПУБЛИКАЦИИ ЦБ, а не с календарём.
            #
            # Календарь тут врёт: ЦБ не публикует по выходным и в
            # праздники, а с 29 августа по 1 сентября 2026 не публиковал
            # четыре дня подряд — выходные плюс День независимости. Проверка
            # «не старше пяти дней» покраснела бы на исправной странице, а
            # красное на исправном продукте обесценивает весь прогон и
            # будит сторожа зря.
            #
            # Правильный вопрос не «давно ли», а «то ли самое число, что
            # ЦБ публикует сейчас».
            if razobrano_cb and razobrano_cb.get("date"):
                proverka("на странице поиска — сегодняшний курс ЦБ",
                         na_stranice == razobrano_cb["date"],
                         "на странице %s, а ЦБ сейчас публикует %s — значит "
                         "пересборка данных не доезжает"
                         % (na_stranice, razobrano_cb["date"]))
            else:
                preduprezhdenie(
                    "дату страницы не с чем сверить",
                    "ЦБ не ответил — сравнивать с календарём здесь нельзя")

kod_robots, _, _ = skachat(PRILOZHENIE + "robots.txt")
proverka("robots.txt отдаётся", kod_robots == 200, "код " + str(kod_robots))
kod_sitemap, _, _ = skachat(PRILOZHENIE + "sitemap.xml")
proverka("карта сайта отдаётся", kod_sitemap == 200, "код " + str(kod_sitemap))

# ── Бот ──────────────────────────────────────────────────────────────

# Ответы бота заводим ДО запроса и пустыми.
#
# Раньше их заводил сам ответ, и всё, что читало их ниже, existовало
# только в мире, где бот ответил. Стоило Render пересобираться — а он
# пересобирается после каждой заливки, то есть ровно тогда, когда эту
# проверку и запускают, — как разбор ответа падал с трассировкой на
# полуслове. Проверка умирала в единственном случае, ради которого
# написана, и вместе с ней пропадало всё, что стояло после неё.
#
# Пусто — это не «ничего не задано», а «спросить не удалось», и дальше
# оно так и называется.
d = None
s = None

print("\nБот: " + BOT)
kod, telo, zagolovki = skachat(BOT + "/api/rates")
proverka("бот отвечает", kod == 200, "код " + str(kod) +
         " (бесплатный Render просыпается до минуты)")

if kod == 200 and telo.startswith("{"):
    proverka("бот отдаёт данные приложению", True)
    proverka("чужому источнику разрешено читать",
             zagolovki.get("access-control-allow-origin") == "*",
             "без этого приложение на github.io не получит курсы")

    d = json.loads(telo)
    cb = d.get("cbu") or {}
    proverka("курс ЦБ на месте", bool(cb.get("rub_uzs")))
    proverka("курс рубля правдоподобен",
             cb.get("rub_uzs") and 80 < cb["rub_uzs"] < 250, str(cb.get("rub_uzs")))
    proverka("есть хотя бы один способ", len(d.get("services") or []) > 0)
    proverka("у способов посчитана наценка",
             all("nacenka_percent" in s for s in (d.get("services") or [])))

    # Полный отказ разбора виден сразу — сервисов ноль. А когда из двух
    # нашёлся один, продукт работает как ни в чём не бывало, только
    # сравнивать ему больше не с чем. Такое пропадает молча.
    if len(d.get("services") or []) == 1:
        preduprezhdenie(
            "найден только один сервис из двух",
            "вероятно, изменилась вёрстка bank.uz — сравнивать не с чем")

    istoriya = d.get("history") or []
    proverka("истории хватает на вердикт", len(istoriya) >= 7,
             "точек: " + str(len(istoriya)))

    sovet = d.get("sovet") or {}
    proverka("вердикт дня посчитан", bool(sovet.get("verdikt")))

    # Свежесть — то, ради чего всё затевалось. Данные старше трёх суток
    # означают, что сборщик молча умер, а мы этого не заметили.
    sobrano = d.get("generated_at")
    if sobrano:
        try:
            vozrast = (datetime.now(timezone.utc)
                       - datetime.fromisoformat(sobrano)).total_seconds() / 3600
            proverka("данные собраны недавно", vozrast < 26,
                     "часов назад: %.1f" % vozrast)
        except Exception:
            preduprezhdenie("не разобрал дату сбора", str(sobrano))

    if sovet:
        print("\n  Сегодня: %s сум · среднее %s · вердикт %s (%+.2f%%)"
              % (sovet.get("segodnya"), sovet.get("srednee_30"),
                 sovet.get("verdikt"), sovet.get("otklonenie_percent") or 0))
        print("  Способы: " + ", ".join(
            "%s %s (%s%%)" % (s["name"], s["rate_rub_uzs"], s.get("nacenka_percent"))
            for s in (d.get("services") or [])))

elif kod == 200:
    upalo.append("бот отдаёт данные приложению  << работает СТАРЫЙ код: "
                 "Render не подхватил заливку. Render -> Manual Deploy")

# Учёт и живость.
#
# Разбивка событий закрыта ключом: адрес открыт всему интернету, а список
# сработавших чатов — это карта нашего посева. Ключ берём из окружения,
# как на Render:  $env:STATS_KEY = "..."  и прогнать снова.
KLUCH_STATS = os.environ.get("STATS_KEY", "").strip()
adres_stats = BOT + "/api/stats"
if KLUCH_STATS:
    adres_stats += "?key=" + urllib.parse.quote(KLUCH_STATS)

kod, telo, _ = skachat(adres_stats)
if kod == 200 and telo.startswith("{"):
    s = json.loads(telo)
    proverka("учёт отвечает", "podpischikov" in s)
    print("\n  Людей: %s · с оповещениями: %s"
          % (s.get("podpischikov"), s.get("s_uvedomleniyami")))

    # Слышит ли бот людей. Разговор и сбор курсов живут в разных потоках:
    # опрос Telegram может умереть насовсем, а всё остальное останется
    # зелёным — курсы обновляются, данные отдаются, страница живости
    # отвечает. Снаружи это выглядит как исправный продукт, который молчит
    # каждому, кто ему написал. Длинный запрос держится 50 секунд, значит
    # у здорового бота число всегда меньше минуты с небольшим запасом.
    if "opros_sekund_nazad" in s:
        davno = s.get("opros_sekund_nazad")
        if davno is None:
            preduprezhdenie("опрос Telegram ещё не отвечал",
                            "бот только что запустился — или не слышит "
                            "людей с самого старта")
        elif davno > 180:
            upalo.append(
                "БОТ НЕ СЛЫШИТ ЛЮДЕЙ: Telegram не отвечал на опрос %d с  "
                "<< курсы при этом собираются, и снаружи всё выглядит "
                "исправным" % davno)
        else:
            proverka("бот слышит людей (ответ %d с назад)" % davno, True)

    # Какой код там работает на самом деле. Без этого проверка боевого
    # отвечала на вопрос «работает ли что-то», а не «работает ли то, что
    # я только что залил»: на бесплатном тарифе заливка доезжает не
    # мгновенно, и зелёный прогон по старому коду успокаивает зря.
    if s.get("kod"):
        KORENA = os.path.dirname(os.path.abspath(__file__))

        def _git(*args):
            try:
                return subprocess.check_output(
                    ("git",) + args, cwd=KORENA,
                    stderr=subprocess.DEVNULL).decode().strip()
            except Exception:
                return None

        svoy = _git("rev-parse", "--short=7", "HEAD")
        if svoy and svoy == s["kod"]:
            proverka("на боевом тот же код, что у меня (%s)" % svoy, True)
        elif svoy:
            # Сравниваем не коммиты, а ФАЙЛЫ БОТА. Приложение и страница
            # поиска лежат на GitHub Pages и заливаются тем же push, но
            # Render на них не перезапускается — и правильно делает.
            # Проверка, кричащая после каждой правки картинки, приучает
            # пролистывать жёлтое, а вместе с ним и настоящие поломки.
            izmenilos = _git("diff", "--name-only", s["kod"] + "..HEAD",
                             "--", "bot")
            if izmenilos is None:
                preduprezhdenie(
                    "на боевом код %s, а такого коммита у меня нет"
                    % s["kod"], "проверено НЕ то, что лежит в рабочей копии")
            elif izmenilos:
                preduprezhdenie(
                    "БОТ НА БОЕВОМ СТАРЫЙ: там %s, у меня %s"
                    % (s["kod"], svoy),
                    "изменены " + ", ".join(sorted(
                        set(izmenilos.split("\n"))))[:160]
                    + " — заливка не доехала или не пошла")
            else:
                proverka("бот на боевом свежий (%s; дальше менялось только "
                         "приложение)" % s["kod"], True)

    if "podrobnosti" in s:
        # Без ключа сказать «событий нет» нельзя: мы их просто не видим.
        # Ложное предупреждение хуже отсутствующего — оно приучает
        # пролистывать жёлтые строки.
        preduprezhdenie("события не проверены",
                        "разбивка закрыта ключом. Задай STATS_KEY в окружении "
                        "тем же значением, что на Render, и прогони снова")
    elif not (s.get("sobytiya_7d") or []):
        # Раньше строка гадала: «либо никто не приходил, либо нет базы».
        # Гадать больше незачем — боевое само говорит, есть ли база. А
        # предупреждение, перечисляющее обе причины при известной одной,
        # приучает пролистывать жёлтое.
        if s.get("baza"):
            preduprezhdenie("событий за неделю нет",
                            "база на месте и пишет — значит за неделю к нам "
                            "правда никто не приходил")
        else:
            preduprezhdenie("событий за неделю нет",
                            "базы нет: события никуда не пишутся, и узнать, "
                            "приходил ли кто-нибудь, нечем")
else:
    preduprezhdenie("учёт не отвечает", "код " + str(kod))

# ── Что ещё не включено ──────────────────────────────────────────────
#
# Бот перечисляет незаданные переменные в журнал при запуске, но журнал
# лежит в кабинете Render, куда надо зайти и найти. Здесь то же самое
# видно из ответов боевого — одной командой, не выходя из терминала.
#
# Это не проверки: незаданная переменная не поломка, а невключённая
# часть продукта. Поэтому отдельный список, а не красное.

ne_vklyucheno = []

if not isinstance(d, dict):
    # «Не смогли спросить» — это не «не задано». Раньше здесь стояло
    # только второе, и молчащий бот выглядел как бот без канала.
    ne_vklyucheno.append(
        "про CHANNEL_ID сказать нечего — бот не ответил, спросить было не у кого")
elif not d.get("channel"):
    ne_vklyucheno.append(
        "CHANNEL_ID — постов в канале нет, ссылка на канал не показывается")

if "podrobnosti" in (s if isinstance(s, dict) else {}):
    ne_vklyucheno.append(
        "STATS_KEY — разбивка «откуда пришли» закрыта, посев не посчитать")

if isinstance(s, dict) and s.get("svoih") == 0:
    # Без своих команда /tekst недоступна никому, и посев пойдёт
    # текстами из файла — то есть с позапрошлым курсом. Первый же
    # человек, сверивший с cbu.uz, поймает нас на этом.
    ne_vklyucheno.append(
        "своих нет — /tekst недоступен. Проще всего: сделать Видадия "
        "администратором канала, тогда SVOI не нужен вовсе")

if isinstance(s, dict) and s.get("baza") is False:
    # Первым в списке: без базы продукт не рассылает оповещения и не
    # считает событий — это не «одна невключённая мелочь», а половина
    # того, ради чего он вообще работает без нас.
    #
    # Канал теперь отдельной строкой: пока базы нет, отметки о постах
    # лежат у Telegram, и канал может публиковать. Считать это «всё
    # хорошо» нельзя, но и писать «постов нет», когда они идут, —
    # такая же неправда.
    ne_vklyucheno.insert(0, (
        "DATABASE_URL — событий нет, подписчики стираются при перезапуске, "
        "оповещения НЕ РАССЫЛАЮТСЯ"))
    if s.get("kanal_pishet") is True:
        ne_vklyucheno.insert(1, (
            "  (канал при этом публикует — держится на запасной памяти "
            "у Telegram, см. bot/pamyat_kanala.py)"))
    else:
        ne_vklyucheno.insert(1, (
            "  ПОСТОВ В КАНАЛЕ ТОЖЕ НЕТ: запасная память у Telegram не "
            "поднялась, смотреть строки [память] в журнале Render"))
elif isinstance(s, dict) and "baza" not in s and not (s.get("sobytiya_7d") or []) \
        and "podrobnosti" not in s:
    ne_vklyucheno.append(
        "похоже, нет DATABASE_URL — события не пишутся, подписчики стираются")

if ne_vklyucheno:
    print("\n" + "─" * 62)
    print("ЕЩЁ НЕ ВКЛЮЧЕНО (см. DEYSTVIYA-SEMYONA.md):")
    for stroka in ne_vklyucheno:
        print("  · " + stroka)

# ── Запас: судим после того, как спросили бота ───────────────────────
#
# С 24 по 31 августа бот был приостановлен, запас не пересобирался, и
# приложение показывало пустой список: правило свежести прячет курсы
# старше 72 часов. Это и была настоящая поломка — та, которую никто не
# заметил восемь дней.
#
# Но когда бот отвечает, приложение считает по ЕГО курсам, а запас лежит
# страховкой. Тогда протухший запас — предупреждение: он сработает в
# следующий раз, когда бот замолчит, и лучше знать об этом заранее.

if vozrast_zapasa is not None:
    _bot_zhiv = "бот отвечает" in proshlo
    if vozrast_zapasa > 72:
        if _bot_zhiv:
            preduprezhdenie(
                "запас протух (%d ч, собран %s)" % (vozrast_zapasa, sobran_zapas),
                "сейчас его прикрывает бот, но замолчит он — и человек не "
                "увидит ни одного способа")
        else:
            proverka("люди видят способы", False,
                     "бот молчит, а запасу %d ч (собран %s) — курсы сервисов "
                     "скрыты целиком, человек не видит ни одного способа"
                     % (vozrast_zapasa, sobran_zapas))
    else:
        proverka("люди видят способы", True)
        if vozrast_zapasa > 24:
            preduprezhdenie("запасу больше суток",
                            "%d ч — способы помечены как вчерашние"
                            % vozrast_zapasa)


# ── Канал: молчит ли он ──────────────────────────────────────────────
#
# ЗАЧЕМ. Канал — единственное, что приводит людей в продукт, и до сих пор
# за ним не следил никто. С 21 по 30 августа он молчал девять дней
# подряд, пока лежал Render, и заметили это по календарю, а не по
# тревоге. Теперь у утреннего поста две двери — бот и работа GitHub, — и
# тем нужнее знать, что закрыты обе: вторая может молча не заработать
# (не тот секрет, не поднявшаяся память у Telegram), и узнали бы мы об
# этом снова через неделю по пустой ленте.
#
# КАК СУДИМ. Не по числу дней молчания: ЦБ не публикует по выходным и в
# праздники, и канал в такие дни молчит ПРАВИЛЬНО — молчание лучше
# повтора, это правило проекта. Судим по тому, освещён ли курс: берём
# даты публикаций ЦБ новее последнего поста.
#
#   ни одной  — канал в порядке, сказать ему нечего;
#   одна      — сегодня ещё успеется: бот пишет с 9:00, работа GitHub в
#               11:00 и 15:00 по Ташкенту. До четырёх дня это жёлтое;
#   две и больше — молчат обе двери, и это уже поломка.
#
# Даты курса берём из ДВУХ источников. У бота они свежее, но именно он и
# лежит в тот день, когда канал замолкает; запас приложения пересобирает
# GitHub четыре раза в сутки, и он переживает падение Render — то есть
# работает ровно тогда, когда нужен.

print("\nКанал: " + KANAL)
_kod_kanala, _stranica, _ = skachat(KANAL.replace("t.me/", "t.me/s/"))

_daty_kursa = set()
if isinstance(d, dict):
    _daty_kursa |= {str(z.get("date"))[:10] for z in (d.get("history") or [])
                    if z.get("date")}
_daty_kursa |= set(re.findall(r"date:\s*'(\d{4}-\d{2}-\d{2})'", data_js))

_posledniy_post = None
for _metka in re.findall(r'datetime="([^"]+)"', _stranica or ""):
    try:
        _moment = datetime.fromisoformat(_metka)
    except ValueError:
        continue
    if _moment.tzinfo is None:
        _moment = _moment.replace(tzinfo=timezone.utc)
    # Сутки канала считаются по Ташкенту, как и всё остальное в продукте:
    # пост, ушедший в 9 утра по Ташкенту, это 4 утра UTC, и по UTC он
    # попал бы во вчера через день на третий.
    _den_posta = (_moment.astimezone(timezone.utc) + timedelta(hours=5)).date()
    if _posledniy_post is None or _den_posta > _posledniy_post:
        _posledniy_post = _den_posta

_teper_uz = datetime.now(timezone.utc) + timedelta(hours=5)

if _kod_kanala != 200 or not _stranica:
    preduprezhdenie("канал не прочитался", "код %s — судить о нём нечем"
                    % _kod_kanala)
elif _posledniy_post is None:
    proverka("в канале есть хоть одно сообщение", False,
             "на публичной странице канала не видно ни одного поста")
elif not _daty_kursa:
    preduprezhdenie("канал не с чем сравнить",
                    "ни бот, ни запас приложения не дали дат публикаций ЦБ")
else:
    _cvet, _ne_osveshcheny = tishina.sudit(_posledniy_post.isoformat(),
                                           _daty_kursa, _teper_uz.hour)
    if _cvet == tishina.ZELYONOE:
        proverka("канал не отстал (последний пост %s)" % _posledniy_post, True)
    elif _cvet == tishina.ZHOLTOE:
        preduprezhdenie(
            "курс за %s ещё не в канале" % ", ".join(_ne_osveshcheny),
            "сегодня успеется: бот пишет с 9:00, работа GitHub в 11:00 и "
            "15:00. Сейчас в Ташкенте %s" % _teper_uz.strftime("%H:%M"))
    else:
        proverka(
            "канал не отстал", False,
            "последний пост %s, а курс публиковался после этого %d раз (%s) "
            "— молчат ОБЕ двери: и бот, и работа GitHub. Проверить секреты "
            "BOT_TOKEN и CHANNEL_ID в Actions и строки [память] в журнале "
            "Render" % (_posledniy_post, len(_ne_osveshcheny),
                        ", ".join(_ne_osveshcheny)))


# ── Итог ─────────────────────────────────────────────────────────────

print("\n" + "=" * 62)
for p in proshlo:
    print("%s+ %s%s" % (ZELYONY, p, SBROS))
for p in predupredit:
    print("%s~ %s%s" % (ZHELTY, p, SBROS))
for p in upalo:
    print("%s- %s%s" % (KRASNY, p, SBROS))

print("=" * 62)
if upalo:
    print("%sУ ЛЮДЕЙ НЕ РАБОТАЕТ: %d. Чинить сейчас.%s" % (KRASNY, len(upalo), SBROS))
    sys.exit(1)
print("%sБоевое работает. Пройдено %d.%s" % (ZELYONY, len(proshlo), SBROS))
if predupredit:
    print("%sОбратить внимание: %d.%s" % (ZHELTY, len(predupredit), SBROS))
