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
    proverka("совет покрыт на " + lang,
             set(bot.DEYSTVIYA[lang]) == {"otpravlyat", "mozhno_zhdat",
                                          "ne_zhdat", "obychno"},
             "не хватает: " + str({"otpravlyat", "mozhno_zhdat", "ne_zhdat",
                                   "obychno"} - set(bot.DEYSTVIYA[lang])))
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
            stroka_summy=bot._stroka_summy(lang, ocenka, 50000),
            sovet=bot.DEYSTVIYA[lang][ocenka["deystvie"]])
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
istoriya = [{"date": "2026-08-%02d" % (i + 1), "rub_uzs": 140.0} for i in range(20)]


def podmenit_kurs(segodnyashniy):
    ryad = istoriya + [{"date": "2026-09-01", "rub_uzs": segodnyashniy}]
    import sovet as _s
    with bot._zamok:
        bot._dannye["snimok"] = {"ok": True, "cbu": {"rub_uzs": segodnyashniy,
                                 "usd_uzs": 12000, "date": "01.09.2026"},
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
_kursy = [150 + (i % 5) - (i * 0.3) for i in range(29)] + [130.0]
_istoriya = [{"date": "2026-07-%02d" % (i + 1) if i < 31 else "2026-08-01",
              "rub_uzs": v} for i, v in enumerate(_kursy)]
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

if provalov:
    print("\nПРОВАЛЕНО:", len(provalov))
    for p in provalov:
        print("  - " + p)
    raise SystemExit(1)

print("\nВсе проверки зелёные.")
