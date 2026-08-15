# -*- coding: utf-8 -*-
"""Проверки бота. Запуск: py test_bot.py

Токен не нужен: подставляем заведомо нерабочий, до сети дело не доходит.
Проверяем то, что ломается тише всего, — согласованность текстов на двух
языках и настоящий ответ /api/rates.
"""
import json
import os
import threading
import urllib.error
import urllib.request

os.environ.setdefault("BOT_TOKEN", "0:proverka")

import bot          # noqa: E402
import sovet        # noqa: E402

provereno, provalov = [], []


def proverka(imya, uslovie, podskazka=""):
    (provereno if uslovie else provalov).append(
        imya + ("" if uslovie or not podskazka else "  << " + podskazka))


# ── Тексты: два языка обязаны совпадать по составу ───────────────────

klyuchi_uz = set(bot.TEKSTY["uz"])
klyuchi_ru = set(bot.TEKSTY["ru"])
proverka("состав текстов совпадает", klyuchi_uz == klyuchi_ru,
         "разница: " + str(klyuchi_uz ^ klyuchi_ru))

for lang in ("uz", "ru"):
    for k, v in bot.TEKSTY[lang].items():
        if isinstance(v, str):
            proverka("текст %s/%s не пустой" % (lang, k), bool(v.strip()))

# Каждый вердикт советника должен иметь подпись на обоих языках, иначе
# оповещение упадёт на KeyError у живого человека.
VSE_VERDIKTY = {"otlichno", "horosho", "obychno", "nize_obychnogo", "ploho"}
for lang in ("uz", "ru"):
    proverka("вердикты покрыты на " + lang,
             set(bot.VERDIKTY[lang]) == VSE_VERDIKTY,
             "не хватает: " + str(VSE_VERDIKTY - set(bot.VERDIKTY[lang])))
    proverka("тренды покрыты на " + lang,
             set(bot.TEKSTY[lang]["trend"]) == {"rastet", "padaet", "stoit"})


# ── Подстановки в шаблонах ───────────────────────────────────────────

ocenka = sovet.analiz([{"date": "2026-08-%02d" % (i + 1), "rub_uzs": v}
                       for i, v in enumerate([140] * 9 + [150])])

for lang in ("uz", "ru"):
    try:
        gotovo = bot.TEKSTY[lang]["uvedomlenie"].format(
            verdikt=bot.VERDIKTY[lang][ocenka["verdikt"]],
            kurs=ocenka["segodnya"], srednee=ocenka["srednee_30"],
            stroka_summy=bot._stroka_summy(lang, ocenka, 50000))
        proverka("оповещение собирается на " + lang, bool(gotovo))
        proverka("в оповещении на %s есть сумма" % lang, "50 000" in gotovo,
                 gotovo[:120])
    except Exception as e:
        proverka("оповещение собирается на " + lang, False, repr(e))

proverka("без суммы строка пустая", bot._stroka_summy("ru", ocenka, None) == "")
proverka("знак плюс при выгоде", "+" in bot._stroka_summy("ru", ocenka, 50000))

ploho = sovet.analiz([{"date": "2026-08-%02d" % (i + 1), "rub_uzs": v}
                      for i, v in enumerate([150] * 9 + [140])])
proverka("при плохом курсе знака плюс нет",
         "+" not in bot._stroka_summy("ru", ploho, 50000),
         bot._stroka_summy("ru", ploho, 50000))


# ── Команды не пересекаются ──────────────────────────────────────────

vse_komandy = (bot.KOMANDY_KURS + bot.KOMANDY_SCHET + bot.KOMANDY_UVED
               + bot.KOMANDY_YAZYK + bot.KOMANDY_POMOSHCH)
proverka("команды не повторяются", len(vse_komandy) == len(set(vse_komandy)),
         "повтор в списке команд уводит вызов не туда")
proverka("все команды со слеша", all(k.startswith("/") for k in vse_komandy))


# ── Живой HTTP ───────────────────────────────────────────────────────

os.environ["PORT"] = "18081"
bot.podnyat_stranicu()

try:
    # Первый сбор без истории: тридцать запросов в тесте ждать незачем,
    # история проверяется отдельно в rates.
    snimok = bot.rates.snimok(s_istoriey=False)
    with bot._zamok:
        bot._dannye["snimok"] = snimok
        bot._dannye["obnovleno"] = __import__("time").time()

    with urllib.request.urlopen("http://127.0.0.1:18081/", timeout=10) as r:
        proverka("корень отвечает 200", r.status == 200)

    with urllib.request.urlopen("http://127.0.0.1:18081/api/rates", timeout=10) as r:
        proverka("api/rates отвечает 200", r.status == 200)
        proverka("api/rates разрешает чужой источник",
                 r.headers.get("Access-Control-Allow-Origin") == "*",
                 "без этого приложение на github.io не получит данные")
        telo = json.loads(r.read().decode("utf-8"))

    proverka("в ответе есть курс ЦБ", bool(telo.get("cbu")))
    proverka("курс рубля правдоподобен",
             telo["cbu"] and 80 < telo["cbu"]["rub_uzs"] < 250,
             str(telo.get("cbu")))
    proverka("в ответе есть сервисы", len(telo.get("services") or []) > 0)
    proverka("у сервиса посчитана наценка",
             all("nacenka_percent" in s for s in telo["services"]))
    proverka("наценка сервисов в разумных пределах",
             all(-20 < s["nacenka_percent"] < 30 for s in telo["services"]),
             str([(s["name"], s["nacenka_percent"]) for s in telo["services"]]))

    with urllib.request.urlopen("http://127.0.0.1:18081/api/stats", timeout=10) as r:
        stat = json.loads(r.read().decode("utf-8"))
        proverka("api/stats отвечает", "podpischikov" in stat)

    zapros = urllib.request.Request("http://127.0.0.1:18081/api/rates", method="HEAD")
    with urllib.request.urlopen(zapros, timeout=10) as r:
        proverka("HEAD отвечает 200", r.status == 200,
                 "UptimeRobot ходит именно HEAD")

    # ── Учёт событий ────────────────────────────────────────────────

    def poslat_sobytie(telo, syroe=None):
        dannye = syroe if syroe is not None else json.dumps(telo).encode("utf-8")
        z = urllib.request.Request(
            "http://127.0.0.1:18081/api/event", data=dannye,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(z, timeout=10) as r:
            return r.status

    proverka("событие принимается",
             poslat_sobytie({"tip": "raschet", "chat_id": 1,
                             "dannye": {"summa": "50-150k"}}) == 200)
    proverka("событие без chat_id принимается",
             poslat_sobytie({"tip": "otkryt"}) == 200,
             "человек мог открыть приложение вне Telegram")
    proverka("битое тело не роняет бота",
             poslat_sobytie(None, syroe="{ это не json".encode("utf-8")) == 200,
             "аналитика не должна ломать разговор с людьми")
    proverka("пустое событие принимается", poslat_sobytie({}) == 200)

    # Гигантское тело обязано отлетать: бесплатный тариф кладётся одним
    # запросом, если читать сколько прислали.
    proverka("огромное тело не читается целиком",
             poslat_sobytie(None, syroe=b'{"tip":"x","d":"' + b"a" * 9000 + b'"}') == 200)

    z = urllib.request.Request("http://127.0.0.1:18081/api/event",
                               method="OPTIONS")
    with urllib.request.urlopen(z, timeout=10) as r:
        proverka("OPTIONS разрешает POST",
                 "POST" in (r.headers.get("Access-Control-Allow-Methods") or ""),
                 "браузер спрашивает разрешение перед POST на чужой адрес")

    try:
        urllib.request.urlopen(urllib.request.Request(
            "http://127.0.0.1:18081/api/net-takogo", data=b"{}", method="POST"),
            timeout=10)
        proverka("неизвестный адрес отвечает 404", False, "ответил 200")
    except urllib.error.HTTPError as e:
        proverka("неизвестный адрес отвечает 404", e.code == 404, str(e.code))

except Exception as oshibka:
    proverka("живой HTTP", False, repr(oshibka)[:200])


# ── Итог ─────────────────────────────────────────────────────────────

print("Пройдено:", len(provereno))
for p in provereno:
    print("  + " + p)

if provalov:
    print("\nПРОВАЛЕНО:", len(provalov))
    for p in provalov:
        print("  - " + p)
    raise SystemExit(1)

print("\nВсе проверки зелёные.")
