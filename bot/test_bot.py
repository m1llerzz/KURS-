# -*- coding: utf-8 -*-
"""Проверки бота. Запуск: py test_bot.py

Токен не нужен: подставляем заведомо нерабочий, до сети дело не доходит.
Проверяем то, что ломается тише всего, — согласованность текстов на двух
языках и настоящий ответ /api/rates.
"""
import json
import os
import tempfile
import threading
import urllib.error
import urllib.request

os.environ.setdefault("BOT_TOKEN", "0:proverka")

# Проверки не должны трогать боевой список подписчиков. Раньше трогали:
# файл писался рядом с ботом, попадал под git add -A и уезжал в публичный
# репозиторий. Данных внутри не оказалось, но полагаться на это нельзя.
_VREMENNYY = os.path.join(tempfile.gettempdir(), "qy_test_podpischiki.json")
os.environ["HRANILISHCHE_FAYL"] = _VREMENNYY
if os.path.exists(_VREMENNYY):
    os.remove(_VREMENNYY)

import bot          # noqa: E402
import sovet        # noqa: E402

provereno, provalov, predupredit = [], [], []


def proverka(imya, uslovie, podskazka=""):
    (provereno if uslovie else provalov).append(
        imya + ("" if uslovie or not podskazka else "  << " + podskazka))


def preduprezhdenie(imya, podskazka=""):
    """Не провал и не успех: проверить не удалось по чужой вине.

    Нужно, чтобы отличать «наш код сломан» от «ЦБ не ответил». Часть
    проверок ходит в интернет, и без этого разделения красное появлялось
    бы на здоровом коде каждый раз, когда чужой сервер моргнул. А тест,
    который краснеет просто так, перестают читать — и вместе с ним
    перестают замечать настоящие поломки.
    """
    predupredit.append(imya + ("  << " + podskazka if podskazka else ""))


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
# Списки берём из sovet.py, где они и порождаются. Перечисленные здесь
# отставали бы: добавят шестой вердикт — проверка о нём не узнает.
VSE_VERDIKTY = set(sovet.VSE_VERDIKTY)
for lang in ("uz", "ru"):
    _vse_sovety = set(sovet.VSE_SOVETY)
    proverka("совет покрыт на " + lang,
             set(bot.DEYSTVIYA[lang]) == _vse_sovety,
             "не хватает: " + str(_vse_sovety - set(bot.DEYSTVIYA[lang])))
    proverka("сдвиг за неделю есть на " + lang,
             "kurs_nedelya_up" in bot.TEKSTY[lang]
             and "kurs_nedelya_down" in bot.TEKSTY[lang])
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
            data=bot.data_slovom(ocenka.get("data"), lang),
            stroka_summy=bot._stroka_summy(lang, ocenka, 50000),
            sovet=bot.DEYSTVIYA[lang][ocenka["deystvie"]])
        proverka("оповещение собирается на " + lang, bool(gotovo))
        proverka("в оповещении на %s есть сумма" % lang, "50 000" in gotovo,
                 gotovo[:120])
        # Цифра без даты не показывается никому и никогда — правило
        # проекта не знает исключений, включая оповещения.
        proverka("в оповещении на %s есть дата курса" % lang,
                 any(m in gotovo for m in bot.MESYACY[lang]), gotovo[:160])
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
    # Первый сбор без истории: тридцать запросов в тесте ждать незачем.
    # Историю проверяет test_rates.py — до 16 августа 2026 эта строчка
    # ссылалась на набор, которого не существовало, и ровно в нём потом
    # нашлась треть ряда, датированная днями без публикации ЦБ.
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

    # Данные приходят от ЦБ Узбекистана и bank.uz — чужих серверов, до
    # которых нам нет никакого дела в момент проверки кода. Их молчание
    # это не поломка нашего кода, и объявлять её провалом нельзя: красное
    # на здоровом коде обесценивает все остальные строки прогона.
    if not telo.get("cbu"):
        preduprezhdenie(
            "данные не проверены: ЦБ Узбекистана не ответил",
            "это не поломка кода — прогони позже или проверь сеть")
    else:
        proverka("в ответе есть курс ЦБ", True)
        proverka("курс рубля правдоподобен",
                 80 < telo["cbu"]["rub_uzs"] < 250, str(telo.get("cbu")))

    if not (telo.get("services") or []):
        preduprezhdenie(
            "курсы сервисов не проверены: bank.uz не ответил",
            "если повторяется несколько дней — смотри разбор страницы")
    else:
        proverka("в ответе есть сервисы", True)
        proverka("у сервиса посчитана наценка",
                 all("nacenka_percent" in s for s in telo["services"]))
        proverka("наценка сервисов в разумных пределах",
                 all(-20 < s["nacenka_percent"] < 30 for s in telo["services"]),
                 str([(s["name"], s["nacenka_percent"]) for s in telo["services"]]))

    # Медленный запрос не должен вставать поперёк остальных.
    #
    # Обычный HTTPServer обрабатывает по одному: пока один человек ждёт,
    # остальные стоят в очереди. А ответ бывает долгим — если кеш курсов
    # устарел, обработчик собирает данные сам. В такую минуту встало бы
    # всё сразу, включая пинг UptimeRobot, и монитор решил бы, что
    # сервис упал.
    _medlenno = []

    def _dolgiy_zapros():
        _bylo = bot.svezhie_dannye
        # Спим долго нарочно: проверка сравнивает два времени, и чем
        # больше разрыв, тем меньше она зависит от того, чем ещё занята
        # машина в этот момент. Тест, срабатывающий через раз, хуже
        # отсутствующего — его начинают перезапускать «на удачу».
        bot.svezhie_dannye = lambda *a, **k: (
            __import__("time").sleep(3) or _bylo(*a, **k))
        try:
            with urllib.request.urlopen(
                    "http://127.0.0.1:18081/api/rates", timeout=15) as r:
                r.read()
        finally:
            bot.svezhie_dannye = _bylo
        _medlenno.append(True)

    _potok = threading.Thread(target=_dolgiy_zapros)
    _potok.start()
    __import__("time").sleep(0.3)             # даём медленному начаться

    _nachalo = __import__("time").time()
    with urllib.request.urlopen("http://127.0.0.1:18081/", timeout=10) as r:
        r.read()
    _zanyalo = __import__("time").time() - _nachalo
    _potok.join(timeout=15)

    # Порог с большим запасом: медленный спит три секунды, значит при
    # однопоточном сервере быстрый ждал бы почти столько же. Полторы —
    # это заведомо «не ждал», даже если машина в этот момент занята.
    proverka("быстрый запрос не ждёт медленного", _zanyalo < 1.5,
             "занял %.1f с — сервер обрабатывает запросы по одному, и в "
             "такую минуту встаёт всё, включая пинг монитора" % _zanyalo)

    with urllib.request.urlopen("http://127.0.0.1:18081/api/stats", timeout=10) as r:
        stat = json.loads(r.read().decode("utf-8"))
        proverka("api/stats отвечает", "podpischikov" in stat)

    # Разбивка «откуда пришли» — это карта нашего посева, собранная
    # неделями и руками. Адрес открыт всему интернету без пароля, и
    # отдавать её любому желающему незачем: у конкурента с бюджетом на
    # рекламу это готовый список чатов, которые работают.
    proverka("без ключа карта посева не отдаётся",
             "istochniki_7d" not in stat and "sobytiya_7d" not in stat,
             str(sorted(stat)))
    proverka("без ключа сказано, что закрыто", "podrobnosti" in stat)
    proverka("общие числа открыты и без ключа",
             "podpischikov" in stat and "s_uvedomleniyami" in stat,
             "по ним видно, что учёт жив, и ничего чужого они не выдают")
    # Наличие базы — не секрет, а самый нужный признак состояния: без неё
    # продукт молчит в канал и не шлёт оповещений. Узнать это иначе можно
    # было только из журнала Render или имея ключ к подробностям.
    proverka("видно, есть ли база, и без ключа",
             isinstance(stat.get("baza"), bool), str(stat.get("baza")))

    _byl_stats_key = os.environ.get("STATS_KEY")
    try:
        os.environ["STATS_KEY"] = "prover-ka-1"

        with urllib.request.urlopen(
                "http://127.0.0.1:18081/api/stats?key=nevernyy", timeout=10) as r:
            chuzhoy = json.loads(r.read().decode("utf-8"))
        proverka("неверный ключ карту посева не открывает",
                 "istochniki_7d" not in chuzhoy, str(sorted(chuzhoy)))

        with urllib.request.urlopen(
                "http://127.0.0.1:18081/api/stats?key=prover-ka-1", timeout=10) as r:
            svoy = json.loads(r.read().decode("utf-8"))
        proverka("верный ключ открывает разбивку",
                 "istochniki_7d" in svoy and "istochniki_30d" in svoy
                 and "sobytiya_7d" in svoy, str(sorted(svoy)))
        proverka("с ключом общие числа тоже на месте",
                 "podpischikov" in svoy)

        # Ключ подставляется в адрес и приходит закодированным.
        with urllib.request.urlopen(
                "http://127.0.0.1:18081/api/stats?a=1&key=prover-ka-1&b=2",
                timeout=10) as r:
            sredi = json.loads(r.read().decode("utf-8"))
        proverka("ключ находится среди других параметров",
                 "istochniki_7d" in sredi, str(sorted(sredi)))
    finally:
        os.environ.pop("STATS_KEY", None)
        if _byl_stats_key is not None:
            os.environ["STATS_KEY"] = _byl_stats_key

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
    #
    # Обрыв соединения здесь — тоже успех, и это не поблажка. Сервер
    # прочитал сколько положено, ответил и закрыл, а клиент в это время
    # ещё дописывал девять килобайт — вот и обрыв. Кто из двоих успеет,
    # зависит от планировщика, и раньше проверка от этого краснела на
    # совершенно здоровом коде примерно раз из пяти. Такие проверки
    # перестают читать, а вместе с ними перестают замечать настоящее.
    try:
        _bolshoe = poslat_sobytie(
            None, syroe=b'{"tip":"x","d":"' + b"a" * 9000 + b'"}')
        proverka("огромное тело не читается целиком", _bolshoe == 200,
                 "ответил " + str(_bolshoe))
    except (ConnectionError, urllib.error.URLError) as oshibka_obryva:
        proverka("огромное тело не читается целиком", True)
        del oshibka_obryva

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


# ── Цель по курсу: сквозной прогон ───────────────────────────────────
#
# Проверяем не куски, а весь путь: человек просит цель, присылает число,
# курс до неё доходит, приходит сообщение, цель снимается. Отправку
# в Telegram подменяем — всё остальное настоящее, включая хранилище.

import hranilishche  # noqa: E402

proverka("проверки пишут во временный файл, не в боевой",
         hranilishche.na_postgres() or hranilishche.FAYL == _VREMENNYY,
         "иначе тестовый прогон однажды затрёт настоящий список людей")

otpravleno = []
nastoyashchiy_poslat = bot.poslat


def perehvat(chat_id, text, knopki=None, html=True):
    otpravleno.append({"chat_id": chat_id, "text": text, "knopki": knopki})
    return {"ok": True}


bot.poslat = perehvat

# Курс, который бот считает сегодняшним. Ставим свой, чтобы прогон
# не зависел от того, что там сегодня у ЦБ.
#
# Даты СЧИТАЕМ ОТ СЕГОДНЯ, а не пишем константами. С фиксированным
# «2026-09-01» прогон был бы зелёным ровно до тех пор, пока эта дата не
# станет старше пяти дней: тогда бот перестал бы советовать по такому
# ряду — совершенно правильно — и половина проверок про советы покраснела
# бы в календарный срок, без единой правки кода.
from datetime import date as _data, timedelta as _delta      # noqa: E402


def _den_nazad(n):
    return (_data.today() - _delta(days=n)).isoformat()


istoriya = [{"date": _den_nazad(20 - i), "rub_uzs": 140.0} for i in range(20)]


def podmenit_kurs(segodnyashniy):
    ryad = istoriya + [{"date": _den_nazad(0), "rub_uzs": segodnyashniy}]
    import sovet as _s
    with bot._zamok:
        bot._dannye["snimok"] = {
            "ok": True,
            "cbu": {"rub_uzs": segodnyashniy, "usd_uzs": 12000,
                    "date": _data.today().strftime("%d.%m.%Y")},
            "services": [], "banks": [], "history": ryad,
            "sovet": _s.analiz(ryad)}
        bot._dannye["obnovleno"] = __import__("time").time()


TESTOVYY = -777001
podmenit_kurs(140.0)

try:
    hranilishche.zapisat_cheloveka(TESTOVYY, lang="ru", summa_rub=50000)

    otpravleno.clear()
    bot.sprosit_cel(TESTOVYY, "ru")
    proverka("бот спросил про цель", len(otpravleno) == 1 and
             "курс" in otpravleno[0]["text"].lower(), str(otpravleno[:1]))
    proverka("бот ждёт число", TESTOVYY in bot.zhdyom_cel)

    otpravleno.clear()
    bot.prinyat_cel(TESTOVYY, "ru", "148")
    proverka("цель записана",
             (hranilishche.chelovek(TESTOVYY) or {}).get("cel_kurs") == 148.0,
             str((hranilishche.chelovek(TESTOVYY) or {}).get("cel_kurs")))
    proverka("бот больше не ждёт число", TESTOVYY not in bot.zhdyom_cel)
    proverka("подтверждение отправлено", len(otpravleno) == 1)

    proverka("человек с целью виден в списке",
             any(c["chat_id"] == TESTOVYY for c in hranilishche.s_celyu()))

    # Курс ещё не дошёл — молчим.
    otpravleno.clear()
    bot.proverit_celi()
    proverka("до цели молчим", len(otpravleno) == 0,
             "курс 140 против цели 148 — сообщать не о чем")
    proverka("цель не снята раньше времени",
             (hranilishche.chelovek(TESTOVYY) or {}).get("cel_kurs") == 148.0)

    # Курс дошёл — пишем один раз.
    podmenit_kurs(149.0)
    otpravleno.clear()
    bot.proverit_celi()
    proverka("при достижении цели пришло сообщение", len(otpravleno) == 1,
             "отправлено: " + str(len(otpravleno)))
    proverka("в сообщении есть курс и цель",
             len(otpravleno) == 1 and "149" in otpravleno[0]["text"]
             and "148" in otpravleno[0]["text"],
             otpravleno[0]["text"][:120] if otpravleno else "")
    proverka("в сообщении есть его сумма",
             len(otpravleno) == 1 and "50 000" in otpravleno[0]["text"],
             "цель без своей суммы — это процент, который не чувствуют")
    proverka("цель снята после срабатывания",
             not (hranilishche.chelovek(TESTOVYY) or {}).get("cel_kurs"),
             "иначе человек получал бы это сообщение каждый день")

    # Второй обход — тишина.
    otpravleno.clear()
    bot.proverit_celi()
    proverka("повторно не пишем", len(otpravleno) == 0,
             "второе сообщение про ту же цель — верный способ быть отключённым")

    # Ноль снимает цель.
    otpravleno.clear()
    bot.prinyat_cel(TESTOVYY, "ru", "150")
    bot.prinyat_cel(TESTOVYY, "ru", "0")
    proverka("ноль снимает цель",
             not (hranilishche.chelovek(TESTOVYY) or {}).get("cel_kurs"))

    # Мусор не принимается.
    otpravleno.clear()
    proverka("буквы вместо числа не принимаются",
             bot.prinyat_cel(TESTOVYY, "ru", "скоро") is False)
    proverka("нелепый курс не принимается",
             bot.prinyat_cel(TESTOVYY, "ru", "1480") is False,
             "1480 — это опечатка в 148, а не желание")
    proverka("после отказа цель не появилась",
             not (hranilishche.chelovek(TESTOVYY) or {}).get("cel_kurs"))

    # Цель выше месячного максимума принимается, но с предупреждением.
    otpravleno.clear()
    bot.prinyat_cel(TESTOVYY, "ru", "200")
    proverka("недостижимая цель всё равно принимается",
             (hranilishche.chelovek(TESTOVYY) or {}).get("cel_kurs") == 200.0)
    proverka("но человека предупредили",
             len(otpravleno) == 1 and "редупреж" in otpravleno[0]["text"],
             otpravleno[0]["text"][:160] if otpravleno else "")

    # ── Подписка предлагается ПОСЛЕ пользы, и один раз ──────────────

    NOVYY = -777002
    otpravleno.clear()
    bot.privetstvie(NOVYY, "ru")
    proverka("на /start приходит ровно одно сообщение", len(otpravleno) == 1,
             "два подряд читаются как спам, каким бы полезным ни было второе")
    proverka("в приветствии нет предложения подписки",
             len(otpravleno) == 1 and "Написать, когда" not in otpravleno[0]["text"])
    proverka("в приветствии сразу есть живой курс",
             len(otpravleno) == 1 and "149" in otpravleno[0]["text"],
             otpravleno[0]["text"][:200] if otpravleno else "")
    proverka("в приветствии не осталось незаполненных мест",
             len(otpravleno) == 1 and "{" not in otpravleno[0]["text"],
             "фигурная скобка на экране — это забытая подстановка")
    proverka("приветствие короткое",
             len(otpravleno) == 1 and len(otpravleno[0]["text"]) < 420,
             "длина: " + str(len(otpravleno[0]["text"]) if otpravleno else 0) +
             " — стена текста на телефоне не читается")

    for _lang in ("uz", "ru"):
        otpravleno.clear()
        bot.privetstvie(NOVYY, _lang)
        proverka("приветствие собирается на " + _lang,
                 len(otpravleno) == 1 and "{" not in otpravleno[0]["text"])

    hranilishche.zapisat_cheloveka(NOVYY, lang="ru")
    proverka("новый человек НЕ подписан по умолчанию",
             not (hranilishche.chelovek(NOVYY) or {}).get("uvedomlyat"),
             "согласие, которого не давали, — это спам, как его ни назови")
    proverka("новый человек не попадает в рассылку",
             all(c["chat_id"] != NOVYY for c in hranilishche.podpisannye()))

    otpravleno.clear()
    bot.mozhet_predlozhit_podpisku(NOVYY)
    proverka("после расчёта предложение приходит", len(otpravleno) == 1,
             "человек уже увидел свою цифру — вот теперь можно спросить")
    proverka("это именно предложение подписки",
             len(otpravleno) == 1 and "Написать, когда" in otpravleno[0]["text"],
             otpravleno[0]["text"][:80] if otpravleno else "")

    otpravleno.clear()
    bot.mozhet_predlozhit_podpisku(NOVYY)
    proverka("второй раз не спрашиваем", len(otpravleno) == 0,
             "повторный тот же вопрос — это давление, а не предложение")

    # Согласился — больше не спрашиваем никогда.
    hranilishche.zapisat_cheloveka(NOVYY, uvedomlyat=True, sprosili_podpisku=True)
    otpravleno.clear()
    bot.mozhet_predlozhit_podpisku(NOVYY)
    proverka("согласившегося не спрашиваем", len(otpravleno) == 0)

    # Незнакомый chat_id — приложение могли открыть мимо бота.
    otpravleno.clear()
    bot.mozhet_predlozhit_podpisku(-999999)
    proverka("незнакомому не пишем", len(otpravleno) == 0,
             "приложение открывается и вне Telegram")
    otpravleno.clear()
    bot.mozhet_predlozhit_podpisku(None)
    proverka("без chat_id не падаем", len(otpravleno) == 0)

    try:
        if hranilishche.na_postgres():
            hranilishche._vypolnit("DELETE FROM podpischiki WHERE chat_id = %s", (NOVYY,))
        else:
            _v = hranilishche._chitat_fayl()
            _v.pop(str(NOVYY), None)
            hranilishche._pisat_fayl(_v)
    except Exception:
        pass

    # ── Пост в канал ────────────────────────────────────────────────
    #
    # Канал — главный источник людей: на него подписываются охотнее,
    # чем открывают приложение. Пост обязан быть полезным сам по себе,
    # иначе канал отписывают за неделю.

    poslannye = []
    nastoyashchiy_vyzov = bot.vyzov

    def perehvat_vyzova(metod, telo=None):
        if metod == "sendMessage":
            poslannye.append(telo or {})
            return {"ok": True}
        return {"ok": True}

    bot.vyzov = perehvat_vyzova

    # Проверки идут в файловом режиме, а без базы бот в канал не пишет
    # вовсе — иначе один пост уходит десятки раз (см. 16 августа).
    # Здесь проверяется САМ ПОСТ, поэтому базу подставляем.
    _byla_baza = hranilishche.na_postgres
    hranilishche.na_postgres = lambda: True
    try:
        os.environ.pop("CHANNEL_ID", None)
        poslannye.clear()
        proverka("без CHANNEL_ID в канал не пишем",
                 bot.opublikovat_v_kanale() is False and len(poslannye) == 0)

        os.environ["CHANNEL_ID"] = "@testovyy_kanal"
        poslannye.clear()
        proverka("пост опубликован", bot.opublikovat_v_kanale() is True)
        proverka("пост ушёл в указанный канал",
                 len(poslannye) == 1 and poslannye[0].get("chat_id") == "@testovyy_kanal")

        post = poslannye[0]["text"] if poslannye else ""
        proverka("в посте есть курс", "149" in post, post[:120])
        proverka("в посте есть среднее за месяц", "140" in post or "141" in post)
        proverka("в посте оба языка",
                 "урс рубля" in post and "ubl kursi" in post,
                 "канал читают и те, и другие")
        proverka("в посте нет незаполненных мест", "{" not in post,
                 "фигурная скобка в публичном посте — это позор")
        proverka("в посте есть размах месяца в сумах",
                 "50 000" in post and "сум" in post,
                 "цифра, ради которой пост пересылают")
        proverka("в посте есть совет", "день" in post or "kun" in post)
        proverka("пост не гигантский", len(post) < 1024,
                 "длина " + str(len(post)) + " — Telegram режет длинные посты")

        knopka = (poslannye[0].get("reply_markup") or {}).get("inline_keyboard")
        proverka("под постом есть кнопка", bool(knopka))
        proverka("кнопка ведёт обычной ссылкой, не web_app",
                 knopka and "url" in knopka[0][0],
                 "в канале Telegram не разрешает кнопки web_app")
        proverka("в ссылке есть метка канала",
                 knopka and "startapp=kanal" in knopka[0][0]["url"],
                 "без метки не понять, окупается ли канал")

        # Данных нет — молчим, а не публикуем пустой пост.
        with bot._zamok:
            sohranyonnoe = bot._dannye["snimok"]
            bot._dannye["snimok"] = {"ok": False, "sovet": None}
        poslannye.clear()
        proverka("без вердикта пост не публикуется",
                 bot.opublikovat_v_kanale() is False and len(poslannye) == 0,
                 "пустой пост в канале хуже отсутствия поста")
        with bot._zamok:
            bot._dannye["snimok"] = sohranyonnoe
    finally:
        bot.vyzov = nastoyashchiy_vyzov
        hranilishche.na_postgres = _byla_baza
        os.environ.pop("CHANNEL_ID", None)

    # ── Еженедельная сводка ─────────────────────────────────────────

    otpravleno.clear()
    os.environ.pop("ADMIN_CHAT_ID", None)
    bot.svodka_dlya_svoih()
    proverka("без ADMIN_CHAT_ID сводка молчит", len(otpravleno) == 0,
             "не задано — значит не мешаем")

    os.environ["ADMIN_CHAT_ID"] = "424242"
    otpravleno.clear()
    bot.svodka_dlya_svoih()
    proverka("сводка отправлена", len(otpravleno) == 1)
    proverka("сводка ушла именно админу",
             len(otpravleno) == 1 and otpravleno[0]["chat_id"] == "424242")
    proverka("в сводке есть число людей",
             len(otpravleno) == 1 and "Людей всего" in otpravleno[0]["text"],
             otpravleno[0]["text"][:100] if otpravleno else "")
    proverka("в сводке есть курс и вердикт",
             len(otpravleno) == 1 and "вердикт" in otpravleno[0]["text"])
    # Сбор сломался — сводка обязана об этом кричать. Разбор страницы
    # bank.uz держится на её вёрстке, и в день, когда её поменяют, курсы
    # перестанут собираться молча.
    with bot._zamok:
        _sohr = bot._dannye["snimok"]
        bot._dannye["snimok"] = {"ok": False, "cbu": None, "services": [],
                                 "sovet": None, "generated_at": None}
    otpravleno.clear()
    bot.svodka_dlya_svoih()
    proverka("сводка кричит, когда курсы не собираются",
             len(otpravleno) == 1
             and "НЕ СОБИРАЮТСЯ" in otpravleno[0]["text"]
             and "НЕ ОТВЕЧАЕТ ЦБ" in otpravleno[0]["text"],
             otpravleno[0]["text"][-200:] if otpravleno else "")
    # Здоровый снимок собираем явно: в подменённом для проверки целей
    # сервисов нет вовсе, и предупреждение на нём сработало бы по делу.
    import sovet as _sv
    _ryad = [{"date": "2026-08-%02d" % (i + 1), "rub_uzs": 140.0} for i in range(20)]
    with bot._zamok:
        bot._dannye["snimok"] = {
            "ok": True, "cbu": {"rub_uzs": 140.0, "usd_uzs": 12000, "date": "20.08.2026"},
            "services": [{"id": "x", "name": "X", "nacenka_percent": 4.0}],
            "banks": [], "history": _ryad, "sovet": _sv.analiz(_ryad),
            "generated_at": bot.datetime.now(bot.timezone.utc).replace(
                microsecond=0).isoformat(),
        }
        bot._dannye["obnovleno"] = __import__("time").time()

    otpravleno.clear()
    bot.svodka_dlya_svoih()
    proverka("при живом сборе сводка не пугает зря",
             len(otpravleno) == 1
             and "НЕ СОБИРАЮТСЯ" not in otpravleno[0]["text"]
             and "НЕ ОТВЕЧАЕТ" not in otpravleno[0]["text"]
             and "НЕ ОБНОВЛЯЛИСЬ" not in otpravleno[0]["text"],
             otpravleno[0]["text"][-160:] if otpravleno else "")

    with bot._zamok:
        bot._dannye["snimok"] = _sohr

    proverka("без базы сводка предупреждает о потере событий",
             hranilishche.na_postgres()
             or "DATABASE_URL" in otpravleno[0]["text"],
             "«нет событий» без базы значит «мы не считаем», а не «никто не приходил»")
    os.environ.pop("ADMIN_CHAT_ID", None)

finally:
    bot.poslat = nastoyashchiy_poslat
    # Прибираем за собой: тестовый человек не должен остаться в хранилище.
    try:
        if hranilishche.na_postgres():
            hranilishche._vypolnit("DELETE FROM podpischiki WHERE chat_id = %s",
                                   (TESTOVYY,))
        else:
            vse = hranilishche._chitat_fayl()
            vse.pop(str(TESTOVYY), None)
            hranilishche._pisat_fayl(vse)
    except Exception:
        pass


# ── Посты в канал: день, неделя, месяц, рывок ────────────────────────
#
# Канал — главный бесплатный источник людей, и посты уходят без единого
# человека в цикле. Значит проверять их надо здесь: если шаблон однажды
# разойдётся с данными, узнать об этом можно будет только от читателей,
# у которых в посте стоят фигурные скобки вместо курса.

for lang in ("uz", "ru"):
    proverka("пост дня есть на " + lang, bool(bot.POST_KANALA[lang].strip()))
    proverka("пост недели есть на " + lang, bool(bot.POST_NEDELI[lang].strip()))
    proverka("пост месяца есть на " + lang, bool(bot.POST_MESYACA[lang].strip()))
    proverka("пост рывка есть на " + lang,
             set(bot.POST_RYVOK[lang]) == {"vverh", "vniz"},
             "оба направления обязаны быть: пост «курс упал» нужен не меньше")
    proverka("упущенное описано на " + lang,
             set(bot.UPUSHCHENO[lang]) == {"est", "net"})

# Ряд, на котором собираются все виды постов: месяц данных, курс ходил
# вверх-вниз, последний день заметно ниже вчерашнего.
#
# Даты от сегодня: с фиксированными пост однажды начал бы выходить с
# советом «данные устарели» вместо настоящего — правильно по сути, но
# проверки про совет покраснели бы в календарный срок.
_kursy = [150 + (i % 5) - (i * 0.3) for i in range(29)] + [130.0]
_istoriya = [{"date": _den_nazad(len(_kursy) - 1 - i), "rub_uzs": v}
             for i, v in enumerate(_kursy)]
_dannye_posta = {"sovet": sovet.analiz(_istoriya), "history": _istoriya}

for vid in ("den", "nedelya", "mesyac", "ryvok"):
    sobrano = bot.sobrat_post(vid, _dannye_posta)
    proverka("пост «%s» собирается" % vid, sobrano is not None)
    if not sobrano:
        continue
    tekst, metka = sobrano
    proverka("в посте «%s» не осталось скобок" % vid,
             "{" not in tekst and "}" not in tekst,
             "незакрытая подстановка уедет читателям как есть")
    proverka("пост «%s» на двух языках" % vid, "· · ·" in tekst,
             "оба языка обязательны — это решение проекта")
    proverka("у поста «%s» своя метка" % vid, metka.startswith("kanal_"), metka)
    proverka("в посте «%s» нет точки в дробных" % vid,
             not any(z.isdigit() for z in tekst.split(".")[0][-1:]) or "," in tekst,
             "числа пишутся через запятую в обеих странах")

_metki = {bot.sobrat_post(v, _dannye_posta)[1]
          for v in ("den", "nedelya", "mesyac", "ryvok")}
proverka("метки постов не совпадают", len(_metki) == 4, str(_metki))

# Данных нет — молчим. Пост с прочерками вместо курса хуже, чем его
# отсутствие: он остаётся в канале навсегда и читается как поломка.
proverka("без данных пост не собирается",
         bot.sobrat_post("den", {}) is None)
proverka("без истории нет поста недели",
         bot.sobrat_post("nedelya", {"sovet": ocenka, "history": []}) is None)
# Наступили на живом прогоне: боевой бот отдавал вердикт, посчитанный
# прошлой версией, без поля с датой — и в пост уезжало «Курс рубля —
# None». В канале такая строка остаётся навсегда.
_bez_daty = dict(_dannye_posta["sovet"])
_bez_daty.pop("data", None)
_post_bez_daty = bot.sobrat_post("den", {"sovet": _bez_daty,
                                         "history": _istoriya})
proverka("дата берётся из истории, если её нет в вердикте",
         _post_bez_daty is not None and "one" not in _post_bez_daty[0],
         "вердикт от старой версии бота не должен печатать None")
proverka("совсем без даты пост не выходит",
         bot.sobrat_post("den", {"sovet": _bez_daty, "history": []}) is None,
         "молчание лучше, чем «Курс рубля — None» в публичном канале")

proverka("спокойный день не даёт поста о рывке",
         bot.sobrat_post("ryvok", {"sovet": ocenka, "history": [
             {"date": "2026-08-01", "rub_uzs": 140.0},
             {"date": "2026-08-02", "rub_uzs": 140.2}]}) is None,
         "0,14% за день — не новость")

# Направление в посте о рывке обязано совпадать с фактом. Ошибка здесь
# сказала бы человеку «курс вырос» в день, когда он упал.
_padenie = [{"date": "2026-08-01", "rub_uzs": 145.0},
            {"date": "2026-08-02", "rub_uzs": 140.0}]
_tekst_padeniya = bot.sobrat_post("ryvok", {"sovet": ocenka, "history": _padenie})[0]
proverka("падение названо падением",
         "tushdi" in _tekst_padeniya and "упал" in _tekst_padeniya,
         "в посте о падении не должно быть слова «вырос»")
proverka("в посте о падении нет минуса в сумме",
         "-250 000" not in _tekst_padeniya and "250 000" in _tekst_padeniya,
         "текст уже говорит «меньше», минус рядом читался бы как ошибка")

_rost = [{"date": "2026-08-01", "rub_uzs": 140.0},
         {"date": "2026-08-02", "rub_uzs": 145.0}]
_tekst_rosta = bot.sobrat_post("ryvok", {"sovet": ocenka, "history": _rost})[0]
proverka("рост назван ростом",
         "ko‘tarildi" in _tekst_rosta and "вырос" in _tekst_rosta)


# ── Ссылка на канал: строится из CHANNEL_ID ──────────────────────────
#
# Адрес канала едет и в приложение, и в кнопки бота. Строить его можно
# только из имени вида @kanal: числовой id публичного адреса не даёт, и
# выдумывать его нельзя — вышла бы битая ссылка, что хуже её отсутствия.

_byl_kanal = os.environ.get("CHANNEL_ID")
try:
    os.environ["CHANNEL_ID"] = "@rublkursi"
    proverka("ссылка на канал строится из имени",
             bot.ssylka_na_kanal() == "https://t.me/rublkursi",
             bot.ssylka_na_kanal())

    os.environ["CHANNEL_ID"] = "-1001234567890"
    proverka("из числового id ссылку не выдумываем",
             bot.ssylka_na_kanal() == "",
             "публичного адреса у числового id нет, вышла бы битая ссылка")

    os.environ["CHANNEL_ID"] = "@плохое имя"
    proverka("кривое имя канала отвергается", bot.ssylka_na_kanal() == "",
             bot.ssylka_na_kanal())

    os.environ.pop("CHANNEL_ID", None)
    proverka("без канала ссылки нет", bot.ssylka_na_kanal() == "")

    # Кнопка канала появляется сама, когда канал заведён. Отдельным
    # сообщением его слать нельзя — два подряд читаются как спам.
    poslannye_knopki = []

    def _perehvat(metod, telo=None):
        if metod == "sendMessage":
            poslannye_knopki.append(telo or {})
        return {"ok": True, "result": {}}

    _byl_vyzov = bot.vyzov
    bot.vyzov = _perehvat
    try:
        poslannye_knopki.clear()
        bot.privetstvie(1, "ru")
        proverka("приветствие — одно сообщение", len(poslannye_knopki) == 1,
                 "два подряд читаются как спам")
        _knopki = (poslannye_knopki[0].get("reply_markup") or {}).get(
            "inline_keyboard", [])
        proverka("без канала кнопки канала нет",
                 not any("t.me" in (k.get("url") or "")
                         for ryad in _knopki for k in ryad))

        os.environ["CHANNEL_ID"] = "@rublkursi"
        poslannye_knopki.clear()
        bot.privetstvie(1, "ru")
        _knopki = (poslannye_knopki[0].get("reply_markup") or {}).get(
            "inline_keyboard", [])
        proverka("канал заведён — кнопка появилась сама",
                 any("t.me/rublkursi" in (k.get("url") or "")
                     for ryad in _knopki for k in ryad),
                 "вписывать её руками никто не должен")
        proverka("приветствие всё ещё одно сообщение",
                 len(poslannye_knopki) == 1)
    finally:
        bot.vyzov = _byl_vyzov
finally:
    if _byl_kanal is None:
        os.environ.pop("CHANNEL_ID", None)
    else:
        os.environ["CHANNEL_ID"] = _byl_kanal


# ── Не дошло — не считаем отправленным ───────────────────────────────
#
# Telegram ограничивает рассылку и на превышение отвечает кодом 429.
# Раньше любая неудача отправки — 429, обрыв сети, пятисотка — считалась
# успешной: человеку проставлялись последний вердикт и время, пауза в
# трое суток начинала идти. Он не получал ничего, пропускал хороший курс,
# а в наших цифрах всё выглядело отправленным.

_bylo_pravilo = bot.mozhno_pisat_lyudyam
_bylo_poslat_uved = bot.poslat
_bylo_svezh = bot.svezhie_dannye
try:
    # Подменяем ПРАВИЛО, а не признак базы: na_postgres переключает и
    # само хранилище, и тогда проверки перестают видеть свои же записи.
    #
    # Правило здесь именно «писать людям»: у рассылки защита от повтора
    # лежит в профиле человека, и запасная память у Telegram её не
    # заменяет — там несколько отметок, а не сотни профилей.
    bot.mozhno_pisat_lyudyam = lambda: True

    _horoshiy_ryad = [{"date": "2026-08-%02d" % (i + 1), "rub_uzs": v}
                      for i, v in enumerate([140] * 9 + [150])]
    bot.svezhie_dannye = lambda *a, **k: {
        "sovet": sovet.analiz(_horoshiy_ryad), "history": _horoshiy_ryad}

    _komu = 424001
    hranilishche.zapisat_cheloveka(_komu, lang="ru", uvedomlyat=True,
                                   summa_rub=50000)

    # Telegram ответил «слишком часто» — отправки не было.
    bot.poslat = lambda *a, **k: {"ok": False, "error_code": 429}
    bot.razoslat_uvedomleniya()
    _posle_429 = hranilishche.chelovek(_komu) or {}
    proverka("после 429 вердикт не записан как отправленный",
             not _posle_429.get("posledniy_verdikt"),
             str(_posle_429.get("posledniy_verdikt")) +
             " — иначе пауза в трое суток пойдёт, а человек ничего не получил")

    # Сеть отвалилась — vyzov вернул None.
    bot.poslat = lambda *a, **k: None
    bot.razoslat_uvedomleniya()
    _posle_seti = hranilishche.chelovek(_komu) or {}
    proverka("после обрыва сети вердикт тоже не записан",
             not _posle_seti.get("posledniy_verdikt"))

    # А когда дошло — записываем.
    bot.poslat = lambda *a, **k: {"ok": True, "result": {}}
    bot.razoslat_uvedomleniya()
    _posle_uspeha = hranilishche.chelovek(_komu) or {}
    proverka("после успешной отправки вердикт записан",
             _posle_uspeha.get("posledniy_verdikt") == "otlichno",
             str(_posle_uspeha.get("posledniy_verdikt")))

    # Цель по курсу: не дошло — цель остаётся. Человек сам её назвал и
    # ждал неделями; потерять и сообщение, и цель разом — худшее из всего.
    hranilishche.zapisat_cheloveka(_komu, cel_kurs=140.0)
    bot.poslat = lambda *a, **k: {"ok": False, "error_code": 429}
    bot.proverit_celi()
    proverka("после 429 цель по курсу не снята",
             (hranilishche.chelovek(_komu) or {}).get("cel_kurs") == 140.0,
             "иначе человек теряет и сообщение, и цель, ничего не узнав")

    bot.poslat = lambda *a, **k: {"ok": True, "result": {}}
    bot.proverit_celi()
    proverka("после успешной отправки цель снята",
             not (hranilishche.chelovek(_komu) or {}).get("cel_kurs"),
             "цель срабатывает один раз, второго сигнала он не просил")

    # Предложение подписки приходит один раз за всю жизнь. Отметка «уже
    # спрашивали» ставилась ДО отправки: не дошло — человек помечен, и
    # предложения он не увидит уже никогда. Один сбой сети стоил бы
    # подписчика навсегда, и заметить это было нечем.
    _nesprosh = 424002
    hranilishche.zapisat_cheloveka(_nesprosh, lang="ru")
    bot.poslat = lambda *a, **k: {"ok": False, "error_code": 429}
    bot.predlozhit_podpisku(_nesprosh, "ru")
    proverka("не дошло — «уже спрашивали» не ставится",
             not (hranilishche.chelovek(_nesprosh) or {}).get("sprosili_podpisku"),
             "иначе один сбой сети стоит подписчика навсегда")

    bot.poslat = lambda *a, **k: {"ok": True, "result": {}}
    bot.predlozhit_podpisku(_nesprosh, "ru")
    proverka("дошло — отметка поставлена",
             (hranilishche.chelovek(_nesprosh) or {}).get("sprosili_podpisku")
             is True,
             "второй раз тот же вопрос — это давление, а не предложение")
finally:
    bot.mozhno_pisat_lyudyam = _bylo_pravilo
    bot.poslat = _bylo_poslat_uved
    bot.svezhie_dannye = _bylo_svezh


# ── Без всякой памяти в канал не пишем ───────────────────────────────
#
# Отметка «этот пост уже публиковали» лежит в хранилище. Без
# DATABASE_URL хранилище — файл на диске Render, а диск там эфемерный:
# тариф усыпляет сервис, монитор будит, файла больше нет, и бот честно
# считает, что сегодня ещё не публиковал.
#
# 16 августа это дало семнадцать одинаковых постов подряд с интервалом
# в две-три минуты, в канале с четырьмя подписчиками. Проверки идут в
# файловом режиме — значит именно здесь и ловится.
#
# С 17 августа у отметки появился второй дом — список команд канала у
# Telegram. Здесь он намеренно не поднят: проверяется поведение, когда
# памяти нет НИКАКОЙ. Что бывает, когда она есть, — ниже, отдельно.

_byl_kanal_pub = os.environ.get("CHANNEL_ID")
_poslannoe_v_kanal = []
_byl_vyzov_pub = bot.vyzov
bot.vyzov = lambda metod, telo=None: (
    _poslannoe_v_kanal.append(telo) if metod == "sendMessage" else None
) or {"ok": True, "result": {}}
try:
    os.environ["CHANNEL_ID"] = "@testovyy"
    _poslannoe_v_kanal.clear()
    bot._opublikovat("den")
    proverka("без базы пост в канал не уходит",
             len(_poslannoe_v_kanal) == 0,
             "ушло сообщений: %d — а перезапуск повторил бы это десятки раз"
             % len(_poslannoe_v_kanal))

    # То же для личных оповещений, и там последствия тяжелее: обе защиты
    # от повторов — пауза в трое суток и прошлый вердикт — живут в
    # профиле, то есть в том же стираемом файле. В канале за повторы
    # отписываются, в личных сообщениях блокируют бота, и это навсегда.
    _poslannoe_v_kanal.clear()
    hranilishche.zapisat_cheloveka(-777003, lang="ru", uvedomlyat=True)
    bot.razoslat_uvedomleniya()
    proverka("без базы оповещения не рассылаются",
             len(_poslannoe_v_kanal) == 0,
             "ушло сообщений: %d — блокировка бота необратима"
             % len(_poslannoe_v_kanal))

    # И то же в самом механизме «ровно один раз». Без базы это обещание
    # невыполнимо, а значит и действие выполнять нельзя — иначе оно
    # повторится столько раз, сколько Render решит нас разбудить.
    _schyotchik_odnazhdy = [0]

    def _sdelat():
        _schyotchik_odnazhdy[0] += 1
        return True

    bot.odnazhdy("proba_bez_bazy", "A", _sdelat)
    bot.odnazhdy("proba_bez_bazy", "A", _sdelat)
    proverka("без базы «ровно один раз» не выполняется вовсе",
             _schyotchik_odnazhdy[0] == 0,
             "выполнено раз: %d — обещание невыполнимо, значит и действия нет"
             % _schyotchik_odnazhdy[0])
finally:
    bot.vyzov = _byl_vyzov_pub
    os.environ.pop("CHANNEL_ID", None)
    if _byl_kanal_pub is not None:
        os.environ["CHANNEL_ID"] = _byl_kanal_pub


# ── Отписался — сумма стирается ──────────────────────────────────────
#
# Сумма хранится ровно для одного: чтобы оповещение говорило про его
# деньги, а не про абстрактные 50 000. Оповещений больше не будет —
# значит и повода держать её нет. LEGAL.md прямо запрещает хранить суммы
# переводов в привязке к личности дольше нужного.

_otpisavshiysya = 123123
hranilishche.zapisat_cheloveka(_otpisavshiysya, lang="ru", uvedomlyat=True,
                               summa_rub=50000)
proverka("сумма сохранилась, пока человек подписан",
         (hranilishche.chelovek(_otpisavshiysya) or {}).get("summa_rub") == 50000)

hranilishche.zapisat_cheloveka(_otpisavshiysya, uvedomlyat=False,
                               summa_rub="sbros")
_posle = hranilishche.chelovek(_otpisavshiysya) or {}
proverka("после отписки суммы не остаётся",
         not _posle.get("summa_rub"), str(_posle.get("summa_rub")))
proverka("отписка при этом записана", _posle.get("uvedomlyat") is False,
         str(_posle.get("uvedomlyat")))

# Обычный None по-прежнему значит «не трогать» — иначе любое обновление
# профиля стирало бы всё, чего в нём не назвали.
hranilishche.zapisat_cheloveka(_otpisavshiysya, summa_rub=70000)
hranilishche.zapisat_cheloveka(_otpisavshiysya, lang="uz")
proverka("обновление профиля не стирает соседние поля",
         (hranilishche.chelovek(_otpisavshiysya) or {}).get("summa_rub") == 70000)


# ── В базу попадает только известное ─────────────────────────────────
#
# Адрес /api/event открыт всему интернету: прислать туда можно что
# угодно. Мы обещаем не собирать личных данных — значит отвечаем и за
# то, что нам присылают. Обещание ничего не стоит, если мы кладём в базу
# любое поле, которое пришло.

proverka("чужое поле в базу не попадает",
         bot._chistye_dannye({"telefon": "+998901234567"}) is None,
         str(bot._chistye_dannye({"telefon": "+998901234567"})))
proverka("известные поля остаются",
         bot._chistye_dannye({"verdikt": "ploho", "summa": "50-150k"})
         == {"verdikt": "ploho", "summa": "50-150k"})
proverka("известное отделяется от чужого",
         bot._chistye_dannye({"verdikt": "ploho", "karta": "4111 1111"})
         == {"verdikt": "ploho"})
proverka("длинное значение обрезается",
         len(bot._chistye_dannye({"istochnik": "a" * 500})["istochnik"]) <= 40)
proverka("не словарь — ничего", bot._chistye_dannye("строка") is None)
proverka("пустое — ничего", bot._chistye_dannye({}) is None)
proverka("вложенное чужое не пролезает",
         bot._chistye_dannye({"verdikt": {"вложено": "что-то"}}) is None,
         "принимаем только простые значения")

# Точная сумма не должна лежать в базе ни в каком виде: это то самое
# число, которое человек собирается отправить домой.
proverka("сумма приводится к порядку", bot.poryadok_summy(50000) == "50-150k")
proverka("маленькая сумма — свой порядок", bot.poryadok_summy(5000) == "до10k")
proverka("большая сумма — свой порядок", bot.poryadok_summy(900000) == "от500k")
proverka("границы порядка те же, что в приложении",
         (bot.poryadok_summy(9999), bot.poryadok_summy(10000),
          bot.poryadok_summy(49999), bot.poryadok_summy(150000))
         == ("до10k", "10-50k", "10-50k", "150-500k"),
         "иначе бот и приложение считают разное под одним именем")


# ── В учёт не уходит текст живого человека ───────────────────────────
#
# Незнакомый человек может написать боту что угодно первым сообщением —
# «привет», «сколько будет 50000», свой номер телефона. Раньше этот текст
# клался в поле метки источника: он и засорял карту посева живыми
# словами, и попадал в базу, хотя мы обещаем личных данных не собирать.

_sobrannye = []
_bylo_sobytie = hranilishche.sobytie
hranilishche.sobytie = lambda chat_id, tip, dannye=None: _sobrannye.append(
    (tip, dannye))
_bylo_poslat_ = bot.poslat
bot.poslat = lambda *a, **k: {"ok": True}
try:
    _novyy_chelovek = 987654
    bot.obrabotat_soobshchenie({
        "chat": {"id": _novyy_chelovek}, "from": {"id": _novyy_chelovek},
        "text": "Salom, mening raqamim +998901234567",
    })
    _novye = [d for t, d in _sobrannye if t == "novyy"]
    proverka("текст человека не уходит в учёт",
             all(not d or "start" not in d for d in _novye),
             str(_novye) + " — в базу не должно попадать написанное человеком")

    _sobrannye.clear()
    bot.obrabotat_soobshchenie({
        "chat": {"id": _novyy_chelovek + 1}, "from": {"id": _novyy_chelovek + 1},
        "text": "/start chat_moskva1",
    })
    _novye = [d for t, d in _sobrannye if t == "novyy"]
    proverka("метка из /start в учёт уходит",
             any(d and d.get("start") == "chat_moskva1" for d in _novye),
             str(_novye) + " — иначе весь посев не посчитать")

    _sobrannye.clear()
    bot.obrabotat_soobshchenie({
        "chat": {"id": _novyy_chelovek + 2}, "from": {"id": _novyy_chelovek + 2},
        "text": "/start чат <script>",
    })
    _novye = [d for t, d in _sobrannye if t == "novyy"]
    proverka("мусор из метки /start вычищен",
             all(not d or "<" not in (d.get("start") or "") for d in _novye),
             str(_novye))
finally:
    hranilishche.sobytie = _bylo_sobytie
    bot.poslat = _bylo_poslat_


# ── Обещания, которых мы не даём ─────────────────────────────────────
#
# Пункты чек-листа приёмки, которые проверялись глазами. Глазами их
# проверяют один раз, а нарушают потом — когда правят текст и хочется
# написать поярче. То же самое проверяется и для приложения.

import re as _re_zapret                                    # noqa: E402

_ZAPRESHCHENO = [
    ("«самый выгодный»", r"самый выгодн|самый лучш|eng foydali|eng yaxshi kurs",
     "мы не знаем всех сервисов коридора и не можем называть лучший"),
    ("«придёт ровно столько»", r"придёт ровно|точно придёт|aniq keladi",
     "комиссии не объявлены, наш итог — верхняя граница"),
    ("«экономьте»", r"экономьте|сэконом|tejang",
     "обещание экономии — это обещание, а мы только считаем"),
    ("«гарантируем»", r"гарантир|kafolat", "мы ничего не гарантируем"),
    ("предсказание курса",
     r"курс вырастет|курс упадёт|kurs ko‘tariladi|kurs tushadi",
     "за предсказание курса нужна лицензия ЦБ — это закон"),
    ("«без комиссии»", r"без комисси|komissiyasiz",
     "комиссии сервисов как раз и неизвестны"),
]


def _vse_teksty_bota():
    """Все строки, которые бот может сказать человеку."""
    kuski = []

    def sobrat(znachenie):
        if isinstance(znachenie, str):
            kuski.append(znachenie)
        elif isinstance(znachenie, dict):
            for v in znachenie.values():
                sobrat(v)
        elif isinstance(znachenie, (list, tuple)):
            for v in znachenie:
                sobrat(v)

    for slovar in (bot.TEKSTY, bot.VERDIKTY, bot.DEYSTVIYA, bot.POST_KANALA,
                   bot.POST_NEDELI, bot.POST_MESYACA, bot.POST_RYVOK,
                   bot.UPUSHCHENO, bot.TEKSTY_POSEVA):
        sobrat(slovar)
    return "\n".join(kuski)


_teksty_bota = _vse_teksty_bota()
for _imya, _shablon, _pochemu in _ZAPRESHCHENO:
    _najdeno = _re_zapret.search(_shablon, _teksty_bota, _re_zapret.I)
    proverka("в текстах бота нет " + _imya, _najdeno is None,
             ("нашлось «%s»: " % _najdeno.group(0) if _najdeno else "") + _pochemu)


# ── По старым данным советов не даём ─────────────────────────────────
#
# Приложение при таких данных прячет курсы сервисов целиком, а совет
# продолжал говорить «сегодня хороший день» — по курсу многодневной
# давности. Тот же класс вреда, что и совет ждать в падающем рынке.

from datetime import datetime as _dtt, timedelta as _tdd   # noqa: E402


def _ocenka_vozrasta(dney):
    """Оценка, у которой дата курса — столько-то дней назад."""
    kogda = (_dtt.now() - _tdd(days=dney)).strftime("%Y-%m-%d")
    return {"deystvie": "otpravlyat", "data": kogda}


proverka("свежие данные — совет обычный",
         bot.kakoy_sovet(_ocenka_vozrasta(0)) == "otpravlyat")
proverka("вчерашние данные — совет ещё даём",
         bot.kakoy_sovet(_ocenka_vozrasta(1)) == "otpravlyat")
proverka("длинные выходные не отменяют совет",
         bot.kakoy_sovet(_ocenka_vozrasta(4)) == "otpravlyat",
         "ЦБ не публикует по выходным и в праздники — это норма, не сбой")
proverka("данные старше пяти дней — совета нет",
         bot.kakoy_sovet(_ocenka_vozrasta(8)) == "stale",
         "совет по курсу недельной давности — это совет потерять деньги")
proverka("без даты совет всё равно даём",
         bot.kakoy_sovet({"deystvie": "ne_zhdat"}) == "ne_zhdat",
         "промолчать из-за непонятой строки хуже, чем дать совет")
proverka("кривая дата не отменяет совет",
         bot.kakoy_sovet({"deystvie": "ne_zhdat", "data": "не дата"}) == "ne_zhdat")
proverka("без оценки совет обычный", bot.kakoy_sovet(None) == "obychno")

for lang in ("uz", "ru"):
    _staryy = bot.DEYSTVIYA[lang]["stale"]
    proverka("отказ советовать написан на " + lang, bool(_staryy.strip()))
    proverka("в отказе на %s не сказано «хороший день»" % lang,
             "yaxshi kun" not in _staryy and "хороший день" not in _staryy)


# ── Свежесть страницы под поиск ──────────────────────────────────────
#
# Числа на ней переписывает obnovit_zapas.py, которого надо не забыть
# запустить и залить. Того, что надо помнить, не делают — поэтому помнит
# бот и раз в неделю говорит об этом в сводке.

_vozrast = bot.svezhest_stranicy_poiska()
if _vozrast is None:
    preduprezhdenie("свежесть страницы поиска не проверена",
                    "github.io не ответил — это не поломка кода")
else:
    proverka("возраст страницы поиска читается", isinstance(_vozrast, int))
    proverka("возраст страницы не отрицательный", _vozrast >= 0,
             str(_vozrast) + " — дата из будущего значит, что разбор сломан")
    proverka("возраст страницы правдоподобен", _vozrast < 3650, str(_vozrast))

# Обложка стареет отдельно от страницы, а видят её чаще: это первое, что
# показывается человеку, которому переслали ссылку. Версия в адресе
# ставится сборщиком по дате курса, так что расхождение видно точно.
_vozrast_kartinki = bot.vozrast_oblozhki_dney()
if _vozrast_kartinki is None:
    preduprezhdenie("возраст обложки не проверен",
                    "github.io не ответил или в адресе картинки нет версии")
else:
    proverka("возраст обложки читается", isinstance(_vozrast_kartinki, int))
    proverka("возраст обложки не отрицательный", _vozrast_kartinki >= 0,
             str(_vozrast_kartinki) + " — дата из будущего значит, что "
             "версия в адресе ставится неверно")


# ── Повторные посты в канал ──────────────────────────────────────────
#
# Два способа отправить читателю один и тот же пост дважды, и оба
# выстрелили бы в первый же день после создания канала.
#
# Первый: отметка «сегодня уже публиковал» жила в памяти процесса. На
# бесплатном тарифе Render перезапускает сервис сам, и после каждого
# пробуждения бот считал, что ещё не публиковал.
#
# Второй: ключом был календарный день. ЦБ не публикует курс по выходным,
# значит в субботу и воскресенье выходили бы ещё два поста с теми же
# числами и той же пятничной датой.

_otpravleno_v_kanal = []


def _zapomnit_vyzov(metod, dannye=None):
    if metod == "sendMessage":
        _otpravleno_v_kanal.append(dannye)
    return {"ok": True, "result": {"message_id": len(_otpravleno_v_kanal)}}


_bylo_sostoyanie = {}


def _chistoe_sostoyanie():
    """Хранилище состояния с нуля — как у только что заведённого бота."""
    _bylo_sostoyanie.clear()
    bot.hranilishche.sostoyanie = lambda k, po_umolchaniyu=None: (
        _bylo_sostoyanie.get(k, po_umolchaniyu))
    bot.hranilishche.zapisat_sostoyanie = lambda k, z: (
        _bylo_sostoyanie.__setitem__(k, str(z)) or True)


_nastoyashchie = (bot.hranilishche.sostoyanie,
                  bot.hranilishche.zapisat_sostoyanie, bot.vyzov)
# Запоминаем ДО try: иначе первое же исключение внутри превратится в
# NameError из finally, и настоящая причина провала не доедет до вывода.
_byl_kanal_post = os.environ.get("CHANNEL_ID")

# Здесь проверяется РАСПИСАНИЕ постов: что выходит и когда. Без базы бот
# в канал не пишет вовсе — иначе один пост уходит десятки раз, как это и
# случилось 16 августа. Подменяем состояние на своё, значит база «есть».
_byla_baza_post = bot.hranilishche.na_postgres
bot.hranilishche.na_postgres = lambda: True
try:
    _chistoe_sostoyanie()

    # «odnazhdy» — сердце защиты: одно действие на одно значение метки.
    _schetchik = [0]

    def _deystvie():
        _schetchik[0] += 1
        return True

    proverka("первый раз действие выполняется",
             bot.odnazhdy("proba", "A", _deystvie) is True)
    proverka("на ту же метку второй раз не выполняется",
             bot.odnazhdy("proba", "A", _deystvie) is False)
    proverka("действие выполнилось ровно один раз", _schetchik[0] == 1,
             str(_schetchik[0]))
    proverka("на новую метку выполняется снова",
             bot.odnazhdy("proba", "B", _deystvie) is True)
    proverka("теперь ровно два раза", _schetchik[0] == 2, str(_schetchik[0]))

    # Неудачное действие не запоминается: через час попробуем ещё раз.
    proverka("неудача не запоминается",
             bot.odnazhdy("proba2", "A", lambda: False) is False)
    proverka("после неудачи попытка повторится",
             bot.odnazhdy("proba2", "A", lambda: True) is True)

    # Отметка переживает перезапуск. Изображаем его: состояние осталось,
    # а все переменные внутри цикла обнулились.
    proverka("после перезапуска повтора нет",
             bot.odnazhdy("proba", "B", _deystvie) is False,
             "отметка обязана лежать в хранилище, а не в памяти процесса")

    # Пост дня привязан к дате курса, а не к календарю.
    _chistoe_sostoyanie()
    bot.vyzov = _zapomnit_vyzov
    os.environ["CHANNEL_ID"] = "@testovyy_kanal"

    _dannye_pyatnicy = {
        "cbu": {"rub_uzs": 141.76, "usd_uzs": 12000.0, "date": "14.08.2026"},
        "history": [{"date": "2026-07-%02d" % d, "rub_uzs": 150.0}
                    for d in (17, 20, 21, 22, 23)]
        + [{"date": "2026-08-%02d" % d, "rub_uzs": k} for d, k in
           ((3, 150.4), (4, 149.5), (5, 147.4), (6, 146.4), (7, 146.2),
            (10, 145.2), (11, 144.6), (12, 143.9), (13, 144.3), (14, 141.76))],
    }
    _dannye_pyatnicy["sovet"] = sovet.analiz(_dannye_pyatnicy["history"])

    bot._dannye["snimok"] = _dannye_pyatnicy
    bot._dannye["obnovleno"] = __import__("time").time()

    proverka("дата курса берётся из данных, а не с часов",
             bot.data_kursa_seychas() == "2026-08-14",
             str(bot.data_kursa_seychas()))

    _otpravleno_v_kanal[:] = []
    bot.odnazhdy("post_den", bot.data_kursa_seychas(),
                 lambda: bot._opublikovat("den"))
    proverka("пятничный пост ушёл", len(_otpravleno_v_kanal) == 1,
             str(len(_otpravleno_v_kanal)))

    # Суббота и воскресенье: данные те же, курс тот же. Молчание.
    for _den in ("суббота", "воскресенье"):
        bot.odnazhdy("post_den", bot.data_kursa_seychas(),
                     lambda: bot._opublikovat("den"))
    proverka("в выходные пост не повторяется", len(_otpravleno_v_kanal) == 1,
             "%d сообщений — три одинаковых поста подряд читаются как спам"
             % len(_otpravleno_v_kanal))

    # Понедельник: ЦБ опубликовал новый курс — есть о чём сказать.
    _dannye_ponedelnika = dict(_dannye_pyatnicy)
    _dannye_ponedelnika["history"] = (
        _dannye_pyatnicy["history"] + [{"date": "2026-08-17", "rub_uzs": 143.0}])
    _dannye_ponedelnika["sovet"] = sovet.analiz(_dannye_ponedelnika["history"])
    bot._dannye["snimok"] = _dannye_ponedelnika

    proverka("дата курса сдвинулась на понедельник",
             bot.data_kursa_seychas() == "2026-08-17",
             str(bot.data_kursa_seychas()))

    bot.odnazhdy("post_den", bot.data_kursa_seychas(),
                 lambda: bot._opublikovat("den"))
    proverka("на новый курс пост выходит", len(_otpravleno_v_kanal) == 2,
             str(len(_otpravleno_v_kanal)))

    # Пятница-суббота. В пятницу выходит итог недели с пятничным курсом.
    # В субботу нового курса нет, и пост дня о том же курсе выглядел бы не
    # вторым постом, а первым, отставшим на сутки.
    _chistoe_sostoyanie()
    _otpravleno_v_kanal[:] = []
    bot._dannye["snimok"] = _dannye_pyatnicy

    _data = bot.data_kursa_seychas()
    if bot.odnazhdy("post_nedelya", "2026-33", lambda: bot._opublikovat("nedelya")):
        bot.hranilishche.zapisat_sostoyanie("kurs_osveshchen", _data)
    proverka("пятничный итог недели ушёл", len(_otpravleno_v_kanal) == 1,
             str(len(_otpravleno_v_kanal)))

    _uzhe = bot.hranilishche.sostoyanie("kurs_osveshchen") == _data
    proverka("курс помечен как освещённый", _uzhe,
             str(bot.hranilishche.sostoyanie("kurs_osveshchen")))
    if not _uzhe:
        bot.odnazhdy("post_den", _data, lambda: bot._opublikovat("den"))
    proverka("в субботу пост дня не дублирует пятничный",
             len(_otpravleno_v_kanal) == 1,
             "%d сообщений — тот же курс и та же дата сутки спустя"
             % len(_otpravleno_v_kanal))
finally:
    (bot.hranilishche.sostoyanie,
     bot.hranilishche.zapisat_sostoyanie, bot.vyzov) = _nastoyashchie
    bot.hranilishche.na_postgres = _byla_baza_post
    if _byl_kanal_post is None:
        os.environ.pop("CHANNEL_ID", None)
    else:
        os.environ["CHANNEL_ID"] = _byl_kanal_post


# ── Сообщение о незаданных настройках ────────────────────────────────
#
# Единственное место, куда Семён точно заглянет: логи Render открываются
# сами после заливки. До этого получался замкнутый круг — о незаданных
# переменных сообщала еженедельная сводка, но она уходит на
# ADMIN_CHAT_ID и, пока он не задан, молчит и о себе тоже.

import contextlib   # noqa: E402
import io as _io    # noqa: E402


def _chto_skazhet_pro_nastroyki(zadano):
    """Печать функции при заданных переменных `zadano` (словарь)."""
    bylo = {imya: os.environ.get(imya) for imya, _ in bot.NASTROYKI}
    try:
        for imya, _ in bot.NASTROYKI:
            os.environ.pop(imya, None)
        for imya, znachenie in zadano.items():
            os.environ[imya] = znachenie
        bufer = _io.StringIO()
        with contextlib.redirect_stdout(bufer):
            bot.soobshchit_o_nastroykah()
        return bufer.getvalue()
    finally:
        for imya, znachenie in bylo.items():
            if znachenie is None:
                os.environ.pop(imya, None)
            else:
                os.environ[imya] = znachenie


_nichego = _chto_skazhet_pro_nastroyki({})
proverka("без настроек названы все до одной",
         all(imya in _nichego for imya, _ in bot.NASTROYKI),
         _nichego.replace("\n", " | ")[:160])
proverka("сказано не только имя, но и последствие",
         "подписчики сотрутся" in _nichego,
         "имя переменной через месяц ни о чём не говорит, последствие говорит всё")
proverka("сказано, где это задаётся", "Environment" in _nichego)

_chastichno = _chto_skazhet_pro_nastroyki({"DATABASE_URL": "postgres://x"})
proverka("заданное не попадает в список пропущенного",
         "DATABASE_URL" not in _chastichno, _chastichno.replace("\n", " | ")[:160])
proverka("незаданное остаётся в списке", "CHANNEL_ID" in _chastichno)


# ── Вывеска бота: имя и описания под поиск ───────────────────────────
#
# Внутренний поиск Telegram — поисковая система на десятки миллионов
# человек, и место в ней даёт имя. Раньше это стояло в списке ручных дел
# Семёна (BotFather), то есть не делалось вовсе.

for _kluch, _tekst in bot.VITRINA.items():
    _predel = bot.VITRINA_METODY[_kluch][3]
    proverka("вывеска «%s» влезает в %d знаков" % (_kluch, _predel),
             len(_tekst) <= _predel,
             "длина %d — Telegram отвергнет целиком" % len(_tekst))
    proverka("вывеска «%s» на обоих языках" % _kluch,
             any("а" <= z <= "я" for z in _tekst.lower())
             and any(z in _tekst for z in "aeiou"),
             "аудитория читает и по-узбекски, и по-русски")

proverka("имя бота ловит поисковый запрос",
         "kurs" in bot.VITRINA["name"].lower()
         and "курс" in bot.VITRINA["name"].lower(),
         "имя — вывеска под поиск, а не бренд")

_byl_vyzov_vitriny = bot.vyzov
try:
    _stoit = {"name": "Qancha yetadi", "description": "",
              "short_description": ""}
    _postavleno = []

    def _vyzov_vitriny(metod, telo=None, popytok=2):
        telo = telo or {}
        for _k, (_sp, _po, _pole, _pr) in bot.VITRINA_METODY.items():
            if metod == _sp:
                return {"ok": True, "result": {_pole: _stoit[_k]}}
            if metod == _po:
                _stoit[_k] = telo.get(_k)
                _postavleno.append(_k)
                return {"ok": True, "result": True}
        return {"ok": True, "result": True}

    bot.vyzov = _vyzov_vitriny
    _pervyy_raz = bot.nastroit_vitrinu()
    proverka("вывеска ставится, когда стоит не то",
             sorted(_pervyy_raz) == sorted(bot.VITRINA),
             str(_pervyy_raz))

    _postavleno[:] = []
    _vtoroy_raz = bot.nastroit_vitrinu()
    proverka("при перезапуске вывеска не переставляется",
             _vtoroy_raz == [] and _postavleno == [],
             "Telegram ограничивает частоту смены имени, а Render "
             "перезапускает сервис постоянно")

    # Telegram отказал — не падаем и не считаем поставленным.
    bot.vyzov = lambda metod, telo=None, popytok=2: (
        {"ok": False, "error_code": 429, "description": "Too Many Requests"})
    proverka("отказ Telegram не роняет запуск", bot.nastroit_vitrinu() == [])
finally:
    bot.vyzov = _byl_vyzov_vitriny


# ── Свои выводятся из администраторов канала ─────────────────────────
#
# Узкое место продукта — не код, а пять минут человека, у которого их
# нет: SVOI и ADMIN_CHAT_ID стоят незаданными вторые сутки, и вместе с
# ними стоят служебные команды и еженедельная сводка. Кто здесь свой,
# Telegram знает и так: свои — те, кого Семён сам назначил
# администраторами канала.

_byl_vyzov_admin = bot.vyzov
_byl_kanal_admin = os.environ.get("CHANNEL_ID")
_byl_svoi = os.environ.get("SVOI")
_byl_admin_id = os.environ.get("ADMIN_CHAT_ID")
try:
    os.environ["CHANNEL_ID"] = "@testovyy_kanal"
    os.environ.pop("SVOI", None)
    os.environ.pop("ADMIN_CHAT_ID", None)

    _sprosheno = [0]

    def _admin_kanala(metod, telo=None, popytok=2):
        if metod == "getChatAdministrators":
            _sprosheno[0] += 1
            return {"ok": True, "result": [
                {"status": "creator", "user": {"id": 111, "is_bot": False}},
                {"status": "administrator", "user": {"id": 222, "is_bot": False}},
                {"status": "administrator", "user": {"id": 999, "is_bot": True}},
            ]}
        return {"ok": True, "result": True}

    bot.vyzov = _admin_kanala
    bot._admin_kanala.update({"kogda": 0.0, "sozdatel": "", "vse": set()})

    proverka("создатель канала — свой", bot.svoi(111))
    proverka("администратор канала — свой", bot.svoi(222))
    proverka("бот-администратор своим не считается", not bot.svoi(999),
             "он в списке админов всегда, и разговаривать с собой некому")
    proverka("посторонний своим не стал", not bot.svoi(333),
             "для него служебной команды не существует вовсе")

    proverka("сводка идёт СОЗДАТЕЛЮ, а не любому админу",
             bot.upravlyayut_kanalom()[0] == "111",
             "в сводке карта посева, собранная неделями и руками")

    proverka("список админов спрошен один раз, а не на каждое сообщение",
             _sprosheno[0] == 1, "спрошено раз: %d" % _sprosheno[0])

    # Сбой сети не должен выключать служебные команды на час.
    bot._admin_kanala.update({"kogda": 0.0, "sozdatel": "", "vse": set()})
    bot.vyzov = lambda metod, telo=None, popytok=2: None
    bot.upravlyayut_kanalom()
    _kogda_posle_sboya = bot._admin_kanala["kogda"]
    bot.vyzov = _admin_kanala
    proverka("после сбоя спросим снова через минуту, а не через час",
             __import__("time").time() - _kogda_posle_sboya > 3000,
             "иначе один сбой сети выключил бы служебные команды на час")

    # Заданное сильнее выведенного — на случай своего человека, который
    # каналом не управляет.
    os.environ["SVOI"] = "444"
    proverka("заданный в SVOI свой остаётся своим", bot.svoi(444))
finally:
    bot.vyzov = _byl_vyzov_admin
    bot._admin_kanala.update({"kogda": 0.0, "sozdatel": "", "vse": set()})
    for _imya, _znach in (("CHANNEL_ID", _byl_kanal_admin),
                          ("SVOI", _byl_svoi),
                          ("ADMIN_CHAT_ID", _byl_admin_id)):
        if _znach is None:
            os.environ.pop(_imya, None)
        else:
            os.environ[_imya] = _znach


# ── Запасная память у Telegram ───────────────────────────────────────
#
# Здесь проверяется единственное, ради чего она есть: канал публикует без
# базы и НЕ повторяется после перезапуска. Плюс все способы, которыми эта
# память может подвести, — и в каждом из них ответ обязан быть «молчим».
#
# Настоящего Telegram тут нет, и это не недостаток проверки: сам API
# проверяет себя на боевом при каждом запуске, записывая случайную метку
# и читая её обратно. Здесь проверяется наше поведение при каждом его
# ответе, включая те, которых мы не увидим, пока не станет поздно.

import pamyat_kanala   # noqa: E402


class _FeykTelegrama(object):
    """Telegram, который помнит. И умеет ломаться всеми способами.

    Умеет оба хранилища: команды чата и описание на чужом языке. Плюс
    `komandy_dlya_kanala` — так ведёт себя настоящий Telegram, если
    область `chat` для канала он не принимает.
    """

    def __init__(self, komandy_dlya_kanala=True):
        self.komandy = {}
        self.opisaniya = {}
        self.komandy_dlya_kanala = komandy_dlya_kanala
        self.chtenie_slomano = False
        self.zapis_slomana = False
        self.otdavat_staroe = None   # отдаёт это вместо записанного
        self.postov = 0
        self.zapisey = 0

    def _kanal_li(self, telo):
        oblast = telo.get("scope") or {}
        return oblast.get("type") == "chat"

    def vyzov(self, metod, telo=None, popytok=2):
        telo = telo or {}

        if metod in ("getMyCommands", "setMyCommands") and self._kanal_li(telo) \
                and not self.komandy_dlya_kanala:
            return {"ok": False, "error_code": 400,
                    "description": "Bad Request: BOT_COMMAND_SCOPE_INVALID"}

        if metod == "getMyCommands":
            if self.chtenie_slomano:
                return None
            istochnik = (self.komandy if self.otdavat_staroe is None
                         else self.otdavat_staroe)
            return {"ok": True, "result": [
                {"command": k, "description": z}
                for k, z in sorted(istochnik.items())]}
        if metod == "setMyCommands":
            if self.zapis_slomana:
                return {"ok": False, "error_code": 400,
                        "description": "Bad Request: не сегодня"}
            self.komandy = {k["command"]: k["description"]
                            for k in (telo.get("commands") or [])}
            self.zapisey += 1
            return {"ok": True, "result": True}

        if metod == "getMyDescription":
            if self.chtenie_slomano:
                return None
            if self.otdavat_staroe is not None:
                stroka = ";".join("%s=%s" % kz
                                  for kz in sorted(self.otdavat_staroe.items()))
            else:
                stroka = self.opisaniya.get(telo.get("language_code"), "")
            return {"ok": True, "result": {"description": stroka}}
        if metod == "setMyDescription":
            if self.zapis_slomana:
                return {"ok": False, "error_code": 400,
                        "description": "Bad Request: не сегодня"}
            self.opisaniya[telo.get("language_code")] = telo.get("description")
            self.zapisey += 1
            return {"ok": True, "result": True}

        if metod == "sendMessage":
            self.postov += 1
            return {"ok": True, "result": {"message_id": self.postov}}
        return {"ok": True, "result": True}


# Ключи, которыми пользуется планировщик. Если хоть один не пройдёт
# правила Telegram, тот отвергнет запись ЦЕЛИКОМ — вместе с остальными
# отметками. Проверка дешёвая, а находка была бы дорогой.
for _kluch in ("post_den", "post_nedelya", "post_mesyac", "post_ryvok",
               "kurs_osveshchen", "svodka"):
    proverka("ключ «%s» годится для хранилища Telegram" % _kluch,
             pamyat_kanala.prigoden(_kluch, "2026-08-17"))

# Метки недели и месяца выглядят иначе, чем даты, — их тоже проверяем.
proverka("метка недели годится", pamyat_kanala.prigoden("post_nedelya", "2026-33"))
proverka("метка месяца годится", pamyat_kanala.prigoden("post_mesyac", "2026-08"))

proverka("пустое значение не пишем",
         not pamyat_kanala.prigoden("post_den", ""),
         "Telegram отвергнет всю запись из-за пустого описания")
proverka("ключ с заглавными и точками не пишем",
         not pamyat_kanala.prigoden("Post.Den", "2026-08-17"))
proverka("значение с разделителем не пишем",
         not pamyat_kanala.prigoden("post_den", "2026;08"),
         "точка с запятой разделяет отметки — внутри значения она сломает разбор")
proverka("значение с равно не пишем",
         not pamyat_kanala.prigoden("post_den", "a=b"))

# Память работает: записали — прочитали. И так же после перезапуска.
for _kanalnye_komandy in (True, False):
    _kak = ("команды канала" if _kanalnye_komandy
            else "описание на чужом языке")
    _tg = _FeykTelegrama(komandy_dlya_kanala=_kanalnye_komandy)
    _pamyat = pamyat_kanala.PamyatTelegrama(_tg.vyzov, "@kanal")

    proverka("память поднимается (%s)" % _kak, _pamyat.podnyat(),
             _pamyat.pochemu)
    proverka("записанное читается обратно (%s)" % _kak,
             _pamyat.zapisat("post_den", "2026-08-14")
             and _pamyat.vse().get("post_den") == "2026-08-14")
    proverka("вторая отметка не затирает первую (%s)" % _kak,
             _pamyat.zapisat("kurs_osveshchen", "2026-08-14")
             and _pamyat.vse().get("post_den") == "2026-08-14")

    _posle = pamyat_kanala.PamyatTelegrama(_tg.vyzov, "@kanal")
    proverka("после перезапуска отметка на месте (%s)" % _kak,
             _posle.podnyat() and _posle.vse().get("post_den") == "2026-08-14",
             "ради этого всё и затевалось")

# Запись проверяется боем — но раз в сутки, не при каждом запуске.
# Render перезапускается постоянно, и проверка на каждом старте стала бы
# сотнями обращений в день там, где по делу нужно два.
_tg_schet = _FeykTelegrama()
pamyat_kanala.PamyatTelegrama(_tg_schet.vyzov, "@kanal").podnyat()
_posle_pervogo_podyoma = _tg_schet.zapisey
proverka("при первом подъёме за сутки запись проверяется боем",
         _posle_pervogo_podyoma == 1, str(_posle_pervogo_podyoma))

for _ in range(5):
    pamyat_kanala.PamyatTelegrama(_tg_schet.vyzov, "@kanal").podnyat()
proverka("пять перезапусков подряд ничего не пишут",
         _tg_schet.zapisey == _posle_pervogo_podyoma,
         "записей стало %d — на бесплатном Render это сотни в день"
         % _tg_schet.zapisey)

# И обратное: читать может, а писать нет — это НЕ память.
_tolko_chtenie = _FeykTelegrama()
_tolko_chtenie.zapis_slomana = True
_polovina = pamyat_kanala.PamyatTelegrama(_tolko_chtenie.vyzov, "@kanal")
proverka("читает, но не пишет — памяти нет", not _polovina.podnyat(),
         "иначе узнали бы об этом завтра по пустому каналу")

# Когда команды канала не принимаются — переходим ко второму способу, а
# не сдаёмся. Ровно это и случилось на боевом 17 августа.
_tg_bez_komand = _FeykTelegrama(komandy_dlya_kanala=False)
_zapasnaya = pamyat_kanala.PamyatTelegrama(_tg_bez_komand.vyzov, "@kanal")
_zapasnaya.podnyat()
proverka("отказ первого способа не останавливает — берём второй",
         isinstance(_zapasnaya.sposob, pamyat_kanala.VOpisaniiNaChuzhomYazyke),
         str(_zapasnaya.sposob))
proverka("отметки не лежат на языке наших людей",
         pamyat_kanala.YAZYK_TAYNIKA not in ("uz", "ru", "en"),
         "иначе человек увидел бы служебную строку вместо описания бота")

# Дальше — все способы подвести. В каждом ответ один: памяти нет.
_slomannoe = _FeykTelegrama()
_slomannoe.chtenie_slomano = True
_net_pamyati = pamyat_kanala.PamyatTelegrama(_slomannoe.vyzov, "@kanal")
proverka("не читает — памяти нет", not _net_pamyati.podnyat())
proverka("причина отказа названа", bool(_net_pamyati.pochemu),
         "молчащий канал без причины — поломка, о которой узнаёшь по "
         "пустой ленте через неделю")

# Запись отвалилась уже после подъёма — отметка не считается поставленной.
_slomannoe = _FeykTelegrama()
_ne_pishet = pamyat_kanala.PamyatTelegrama(_slomannoe.vyzov, "@kanal")
_ne_pishet.podnyat()
_slomannoe.zapis_slomana = True
proverka("перестал писать — отметка не считается поставленной",
         not _ne_pishet.zapisat("post_den", "2026-08-14"))

# Самый тихий случай: пишет, отвечает «ок», а читается старое. Именно он
# вернул бы нас к повторным постам, и заметить его иначе нечем.
_ustarevshee = _FeykTelegrama()
_pamyat_ust = pamyat_kanala.PamyatTelegrama(_ustarevshee.vyzov, "@kanal")
_pamyat_ust.podnyat()
_ustarevshee.otdavat_staroe = {"post_den": "2026-08-01"}
proverka("записали, а читается старое — отметка не считается поставленной",
         not _pamyat_ust.zapisat("post_den", "2026-08-14"),
         "иначе «уже публиковали» тоже читалось бы устаревшим")

# Чтение сломалось уже после подъёма: «не знаю» — это не «не публиковали».
_tg_zhivoy = _FeykTelegrama()
_pamyat_zhivaya = pamyat_kanala.PamyatTelegrama(_tg_zhivoy.vyzov, "@kanal")
_pamyat_zhivaya.podnyat()
_tg_zhivoy.chtenie_slomano = True
proverka("сбой чтения даёт «не знаю», а не пустоту",
         _pamyat_zhivaya.vse() is None)
proverka("поверх непрочитанного не пишем",
         not _pamyat_zhivaya.zapisat("post_den", "2026-08-14"),
         "затёрли бы остальные отметки, и повторы вернулись бы с другой стороны")
_tg_zhivoy.chtenie_slomano = False

# ── Как это ведёт себя внутри бота ───────────────────────────────────

_bylo_telegrama = bot.hranilishche._telegram
_byl_kanal_pamyati = os.environ.get("CHANNEL_ID")
_byl_vyzov_pamyati = bot.vyzov
try:
    _tg = _FeykTelegrama()
    bot.vyzov = _tg.vyzov
    os.environ["CHANNEL_ID"] = "@testovyy_kanal"

    proverka("без базы и без памяти наружу не пишем",
             not bot.mozhno_pisat_naruzhu(),
             "это состояние до 17 августа: канал молчит")

    proverka("память поднимается через хранилище",
             bot.hranilishche.pamyat_na_telegrame(_tg.vyzov, "@testovyy_kanal"))
    proverka("теперь наружу писать можно", bot.mozhno_pisat_naruzhu())
    proverka("но людям в личные — по-прежнему нет",
             not bot.mozhno_pisat_lyudyam(),
             "защита от повтора там лежит в профиле человека, а профилей "
             "без базы нет; за повтор в личных бота блокируют навсегда")

    # Пост дня уходит один раз — и не повторяется после перезапуска.
    bot._dannye["snimok"] = _dannye_pyatnicy
    bot._dannye["obnovleno"] = __import__("time").time()
    _data_posta = bot.data_kursa_seychas()

    bot.odnazhdy("post_den", _data_posta, lambda: bot._opublikovat("den"))
    proverka("без базы пост в канал всё-таки ушёл", _tg.postov == 1,
             "%d — канал молчал бы и дальше" % _tg.postov)

    # Перезапуск Render: процесс новый, память у Telegram та же.
    bot.hranilishche._telegram = None
    bot.hranilishche.pamyat_na_telegrame(_tg.vyzov, "@testovyy_kanal")
    bot.odnazhdy("post_den", _data_posta, lambda: bot._opublikovat("den"))
    bot.hranilishche._telegram = None
    bot.hranilishche.pamyat_na_telegrame(_tg.vyzov, "@testovyy_kanal")
    bot.odnazhdy("post_den", _data_posta, lambda: bot._opublikovat("den"))
    proverka("после двух перезапусков пост не повторился", _tg.postov == 1,
             "%d копий — ровно то, что случилось 16 августа" % _tg.postov)

    # Отметка ставится ДО поста. Значит неудачная отправка стоит одного
    # дня молчания, а не повтора: через час мы не попробуем ещё раз, и
    # это выбор, а не оплошность.
    proverka("на запасной памяти отметка ставится до действия",
             bot.hranilishche.zayavka_do_deystviya())

    _ne_vyshlo = bot.odnazhdy("post_ryvok", _data_posta, lambda: False)
    proverka("неудачное действие не выполняется второй раз",
             _ne_vyshlo is False
             and bot.odnazhdy("post_ryvok", _data_posta, lambda: True) is False,
             "с запасной памятью повтор опаснее пропуска")

    # Чтение отметки сломалось. Молчим: «не знаю» не разрешение.
    _tg.chtenie_slomano = True
    bot.odnazhdy("post_ryvok", "2026-08-14", lambda: bot._opublikovat("den"))
    proverka("при сбое чтения отметки пост не уходит", _tg.postov == 1,
             "%d — после любой икоты сети пост ушёл бы вторым разом"
             % _tg.postov)
    _tg.chtenie_slomano = False

    _tg.chtenie_slomano = True
    _otvet_pri_sboe = bot.hranilishche.sostoyanie("post_den")
    _tg.chtenie_slomano = False
    proverka("сбой чтения виден как НЕИЗВЕСТНО, а не как пустота",
             _otvet_pri_sboe is bot.hranilishche.NEIZVESTNO,
             repr(_otvet_pri_sboe))
    proverka("НЕИЗВЕСТНО не притворяется правдой в условии",
             not bot.hranilishche.NEIZVESTNO,
             "иначе «if otmetka:» где-нибудь однажды прочтёт его как значение")

    # Настоящая база всегда главнее: две памяти — это две правды о том,
    # что уже опубликовано.
    bot.hranilishche._telegram = None
    _byla_baza_pamyati = bot.hranilishche.na_postgres
    _bylo_sost = bot.hranilishche.sostoyanie
    _bylo_zap_sost = bot.hranilishche.zapisat_sostoyanie
    bot.hranilishche.na_postgres = lambda: True
    try:
        proverka("при живой базе запасную не поднимаем",
                 not bot.hranilishche.pamyat_na_telegrame(_tg.vyzov, "@kanal"))

        # Переезд на базу. Она пустая, а у Telegram лежит «сегодняшний
        # курс уже освещён». Не перенести — значит опубликовать его
        # второй раз в тот самый день, когда всё наконец настроено.
        _baza = {}
        bot.hranilishche.sostoyanie = lambda k, po_umolchaniyu=None: (
            _baza.get(k, po_umolchaniyu))
        bot.hranilishche.zapisat_sostoyanie = lambda k, z: (
            _baza.__setitem__(k, str(z)) or True)

        _perenes = bot.hranilishche.perenesti_otmetki(_tg.vyzov,
                                                      "@testovyy_kanal")
        proverka("при переезде на базу отметки перенеслись", _perenes >= 1,
                 "перенесено: %d" % _perenes)
        proverka("перенеслась именно отметка о посте",
                 _baza.get("post_den") == _data_posta,
                 str(_baza))
        _baza["post_den"] = "2026-08-01"
        bot.hranilishche.perenesti_otmetki(_tg.vyzov, "@testovyy_kanal")
        proverka("уже записанное в базе не затирается",
                 _baza["post_den"] == "2026-08-01",
                 "база всегда главнее запасной памяти")
    finally:
        bot.hranilishche.na_postgres = _byla_baza_pamyati
        bot.hranilishche.sostoyanie = _bylo_sost
        bot.hranilishche.zapisat_sostoyanie = _bylo_zap_sost
finally:
    bot.hranilishche._telegram = _bylo_telegrama
    bot.vyzov = _byl_vyzov_pamyati
    if _byl_kanal_pamyati is None:
        os.environ.pop("CHANNEL_ID", None)
    else:
        os.environ["CHANNEL_ID"] = _byl_kanal_pamyati

# Список берём из самого бота, а не переписываем сюда руками: копия
# разошлась с оригиналом в тот же день, когда добавилась пятая переменная,
# и проверка покраснела на здоровом коде.
_vsyo = _chto_skazhet_pro_nastroyki(
    {imya: "zadano" for imya, _ in bot.NASTROYKI})
proverka("когда всё задано, тревоги нет", "НЕ ЗАДАНО" not in _vsyo, _vsyo.strip())
proverka("названы все переменные, какие есть",
         all(imya in _nichego for imya, _ in bot.NASTROYKI),
         "список в проверке не должен отставать от списка в коде")

# Пустая строка — это не заданное значение. На Render переменную легко
# завести с пустым полем и решить, что дело сделано.
_pustaya = _chto_skazhet_pro_nastroyki({"DATABASE_URL": "   "})
proverka("пробелы вместо значения считаются незаданным",
         "DATABASE_URL" in _pustaya, _pustaya.replace("\n", " | ")[:160])


# ── Тексты для посева ────────────────────────────────────────────────
#
# Тексты в документе устаревают молча: числа в них остаются от того дня,
# когда документ писали. Человек копирует пост, публикует — и первый же
# читатель сверяет с cbu.uz и ловит нас на неправде.

_poslannye_teksty = []


def _perehvat_tekstov(metod, telo=None):
    if metod == "sendMessage":
        _poslannye_teksty.append((telo or {}).get("text", ""))
    return {"ok": True, "result": {}}


_byl_svoi = os.environ.get("SVOI")
_byl_vyzov2 = bot.vyzov
bot.vyzov = _perehvat_tekstov
try:
    os.environ.pop("SVOI", None)
    os.environ.pop("ADMIN_CHAT_ID", None)
    _poslannye_teksty.clear()
    bot.vydat_teksty_dlya_poseva(777)
    proverka("чужому команда не отвечает вовсе", len(_poslannye_teksty) == 0,
             "служебной команды для постороннего просто не существует")

    os.environ["SVOI"] = "777"
    _poslannye_teksty.clear()
    bot.vydat_teksty_dlya_poseva(777, "moskva1")
    _vse = "\n".join(_poslannye_teksty)
    proverka("своему тексты выданы", len(_poslannye_teksty) >= 4,
             "прислано сообщений: " + str(len(_poslannye_teksty)))
    proverka("тексты на обоих языках",
             "· UZ" in _vse and "· RU" in _vse)
    proverka("в текстах нет незаполненных мест",
             "{" not in _vse and "}" not in _vse,
             "фигурная скобка уедет прямо в чужой чат")
    proverka("метка чата попала в ссылку", "start=chat_moskva1" in _vse,
             "без метки непонятно, какой чат сработал")
    import re as _re                                   # noqa: E402
    proverka("курс в тексте написан через запятую",
             bool(_re.search(r"\d+,\d{2}", _vse)),
             "точка в дробной части читается как чужой формат")
    proverka("суммы разделены пробелами по три знака",
             bool(_re.search(r"\d{1,3} \d{3}", _vse)),
             "673000 без пробелов человек не прочитает с первого взгляда")
    proverka("ссылка ведёт на бота, а не на приложение",
             "t.me/QanchaYetadi_bot?start=" in _vse,
             "в чате ссылка на бота: он и метку запишет, и в приложение отправит")
    proverka("дата названа", "августа" in _vse or "avgust" in _vse
             or any(m in _vse for m in bot.MESYACY["ru"]),
             "число без даты — ложь, а этот текст уйдёт в чужой чат")

    _poslannye_teksty.clear()
    bot.vydat_teksty_dlya_poseva(777, "чат <script>алерт")
    proverka("мусор из метки вычищен",
             "<script>" not in "\n".join(_poslannye_teksty),
             "чужой текст не должен доезжать до ссылки как есть")
finally:
    bot.vyzov = _byl_vyzov2
    os.environ.pop("SVOI", None)
    if _byl_svoi is not None:
        os.environ["SVOI"] = _byl_svoi


# ── Разбивка «откуда пришли» ─────────────────────────────────────────
#
# Денег на рекламу нет, значит каждый человек пришёл из какого-то одного
# места. Без разбивки видно только «пришло сорок человек», и понять,
# повторять посев или бросать, нечем. Базы под рукой нет, поэтому
# проверяем то, что проверить можно: собирается ли запрос.

import hranilishche as _hr        # noqa: E402

_sql = _hr.SQL_ISTOCHNIKI % {"d": 7}
proverka("запрос по источникам собирается", bool(_sql))
proverka("двойные проценты свернулись", "%%" not in _sql,
         "иначе LIKE '{%%' уедет в базу как есть и ничего не найдёт")
proverka("интервал подставлен в обе половины",
         _sql.count("INTERVAL '7 days'") == 2, _sql)
proverka("условие LIKE корректно", _sql.count("LIKE '{%'") == 2)
proverka("считаются и заходы в приложение, и приходы к боту",
         "'otkryt'" in _sql and "'novyy'" in _sql,
         "в чатах ссылку дают на бота, а не на приложение — "
         "без второй половины половина посева не видна")
proverka("пустая метка не считается отдельным источником",
         "NULLIF(" in _sql,
         "иначе пустая строка станет источником с именем «»")
proverka("без базы разбивка пустая, а не падает",
         _hr.svodka_istochnikov(7) == [])

# Воронка: пришли — посчитали — переслали. По одним переходам источники
# не различить, а разница между зеваками и людьми с деньгами в руках —
# это ровно то, ради чего посев ведётся по одному чату за раз.
_sql_v = _hr.SQL_VORONKA % {"d": 7}
proverka("запрос воронки собирается", bool(_sql_v))
proverka("в воронке проценты свернулись", "%%" not in _sql_v)
proverka("в воронке интервал подставлен", "INTERVAL '7 days'" in _sql_v, _sql_v)
proverka("воронка считает все три шага",
         "'otkryt'" in _sql_v and "'raschet'" in _sql_v and "'share'" in _sql_v,
         "зашли, посчитали, переслали — иначе источники не различить")
proverka("без базы воронка пустая, а не падает",
         _hr.voronka_istochnikov(7) == [])

# Синтаксис запросов разбираем без базы.
#
# Postgres при разработке негде поднять, и до сих пор SQL проверялся
# только тем, что он «выглядит правильно» — то есть не проверялся. Ошибка
# в нём вылезла бы на боевом и молча: `_vypolnit` ловит исключение, а
# сводка показала бы пустую разбивку.
#
# sqlglot умеет разбирать диалект Postgres. Это не выполнение запроса и
# не гарантия, что он вернёт нужное, — но опечатку, лишнюю скобку и
# незакрытую кавычку он ловит, а именно они и ломают такие строки.
try:
    import sqlglot as _sqlglot                             # noqa: E402
except ImportError:
    _sqlglot = None
    preduprezhdenie("синтаксис SQL не проверен",
                    "нет sqlglot: py -m pip install sqlglot")

if _sqlglot:
    _zaprosy_dlya_razbora = [
        ("воронка по источникам", _hr.SQL_VORONKA % {"d": 7}),
        ("разбивка источников", _hr.SQL_ISTOCHNIKI % {"d": 7}),
    ]
    # Схема тоже: ошибка в ней ломает не отчёт, а весь запуск — таблицы
    # не создадутся, и всё остальное будет молча падать на каждом
    # обращении. А выполняется она только на боевом, где базы у нас нет.
    for _nomer, _ddl in enumerate(_hr.SQL_SHEMA, 1):
        _zaprosy_dlya_razbora.append(("схема, запрос %d" % _nomer, _ddl))

    for _imya_sql, _tekst_sql in _zaprosy_dlya_razbora:
        try:
            _razobrano = _sqlglot.parse_one(_tekst_sql, dialect="postgres")
            proverka("SQL «%s» разбирается" % _imya_sql, _razobrano is not None)
        except Exception as _oshibka_sql:
            proverka("SQL «%s» разбирается" % _imya_sql, False,
                     repr(_oshibka_sql)[:160])

# Пустой список и «не выполнилось» — разные вещи. Запрос сложный, а базы
# при разработке нет: синтаксис проверяется только на боевом. Упадёт —
# сводка покажет «источников нет», и это прочтётся как «людей не было».
# Разница между «никто не приходил» и «мы сломались» — это разница между
# «ждём» и «чиним сегодня».
_byla_pg = _hr.na_postgres
_bylo_vypolnit = _hr._vypolnit
try:
    _hr.na_postgres = lambda: True
    _hr._vypolnit = lambda *a, **k: None          # запрос не прошёл
    proverka("сломанный запрос отличается от пустого результата",
             _hr.voronka_istochnikov(7) is None,
             "иначе поломка выглядит как отсутствие людей")
    _hr._vypolnit = lambda *a, **k: []            # выполнился, данных нет
    proverka("выполненный запрос без данных — пустой список",
             _hr.voronka_istochnikov(7) == [])
finally:
    _hr.na_postgres = _byla_pg
    _hr._vypolnit = _bylo_vypolnit


# ── Какой пост выходит в какой день ──────────────────────────────────

from datetime import datetime as _dt      # noqa: E402

proverka("первого числа — итог месяца",
         bot.vid_posta_na_segodnya(_dt(2026, 9, 1)) == "mesyac")
proverka("в пятницу — итог недели",
         bot.vid_posta_na_segodnya(_dt(2026, 8, 21)) == "nedelya",
         "21 августа 2026 — пятница")
proverka("в обычный день — пост дня",
         bot.vid_posta_na_segodnya(_dt(2026, 8, 19)) == "den")
proverka("первое число важнее пятницы",
         bot.vid_posta_na_segodnya(_dt(2027, 1, 1)) == "mesyac",
         "1 января 2027 — пятница; месячный итог бывает раз в месяц")


# ── Метка источника в ссылке ─────────────────────────────────────────

proverka("метка попадает в ссылку", "startapp=kanal_den" in bot.ssylka("kanal_den"))
proverka("ссылка ведёт на приложение", bot.ssylka("x").startswith("https://t.me/"))
proverka("пустая метка не ломает ссылку",
         bot.ssylka("").endswith("startapp=kanal"))
proverka("мусор из метки вычищен",
         bot.ssylka("чат <script>") .endswith("startapp=script"),
         bot.ssylka("чат <script>") + " — в ссылку не должно попадать ничего "
         "кроме букв, цифр и дефиса")
proverka("длинная метка обрезана",
         len(bot.ssylka("a" * 200).split("startapp=")[1]) <= 32)


# ── Дата словами ─────────────────────────────────────────────────────

proverka("дата по-русски", bot.data_slovom("2026-08-03", "ru") == "3 августа",
         bot.data_slovom("2026-08-03", "ru"))
proverka("дата по-узбекски", bot.data_slovom("2026-08-03", "uz") == "3 avgust",
         bot.data_slovom("2026-08-03", "uz"))
proverka("месяцы покрыты на обоих языках",
         len(bot.MESYACY["uz"]) == 12 and len(bot.MESYACY["ru"]) == 12)
proverka("кривая дата не роняет пост",
         bot.data_slovom("не дата", "ru") == "не дата")


# ── Проценты со знаком ───────────────────────────────────────────────

proverka("рост со знаком плюс", bot.procent_znakom(1.23) == "+1,23")
proverka("падение со знаком минус", bot.procent_znakom(-1.23) == "-1,23")
proverka("ноль без плюса", bot.procent_znakom(0) == "0,00")
proverka("нет числа — прочерк", bot.procent_znakom(None) == "—")


# ── Итог ─────────────────────────────────────────────────────────────

print("Пройдено:", len(provereno))
for p in provereno:
    print("  + " + p)

if predupredit:
    print("\nНЕ ПРОВЕРЕНО:", len(predupredit))
    for p in predupredit:
        print("  ~ " + p)

if provalov:
    print("\nПРОВАЛЕНО:", len(provalov))
    for p in provalov:
        print("  - " + p)
    raise SystemExit(1)

# Непроверенное не объявляем зелёным: молчаливый пропуск опаснее красной
# строки — именно так две трети проверок приложения не гонялись неделю.
if predupredit:
    print("\nОстальное зелёное, но %d проверок выполнить не удалось."
          % len(predupredit))
else:
    print("\nВсе проверки зелёные.")
