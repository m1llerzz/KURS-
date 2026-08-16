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
import sys
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

PRILOZHENIE = "https://m1llerzz.github.io/KURS-/"
BOT = "https://qanchayetadi-bot.onrender.com"

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE

ZELYONY, KRASNY, ZHELTY, SBROS = "\033[32m", "\033[91m", "\033[33m", "\033[0m"
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

    data_na_stranice = re.search(r'data-zapas="data_ru">([^<]+)<', stranica)
    if data_na_stranice:
        god = re.search(r"(\d{4})", data_na_stranice.group(1))
        svezhiy = god and int(god.group(1)) >= datetime.now(timezone.utc).year
        proverka("дата на странице не из прошлого года", bool(svezhiy),
                 data_na_stranice.group(1) +
                 " — запусти bot/obnovit_zapas.py и залей заново")

kod_robots, _, _ = skachat(PRILOZHENIE + "robots.txt")
proverka("robots.txt отдаётся", kod_robots == 200, "код " + str(kod_robots))
kod_sitemap, _, _ = skachat(PRILOZHENIE + "sitemap.xml")
proverka("карта сайта отдаётся", kod_sitemap == 200, "код " + str(kod_sitemap))

# ── Бот ──────────────────────────────────────────────────────────────

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

    if "podrobnosti" in s:
        # Без ключа сказать «событий нет» нельзя: мы их просто не видим.
        # Ложное предупреждение хуже отсутствующего — оно приучает
        # пролистывать жёлтые строки.
        preduprezhdenie("события не проверены",
                        "разбивка закрыта ключом. Задай STATS_KEY в окружении "
                        "тем же значением, что на Render, и прогони снова")
    elif not (s.get("sobytiya_7d") or []):
        preduprezhdenie("событий за неделю нет",
                        "либо никто не приходил, либо не задан DATABASE_URL "
                        "и события никуда не пишутся — это разные вещи")
else:
    preduprezhdenie("учёт не отвечает", "код " + str(kod))

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
