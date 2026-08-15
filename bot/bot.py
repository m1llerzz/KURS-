# -*- coding: utf-8 -*-
"""Бот @QanchaYetadi_bot — советник по курсу и сервер данных приложения.

Три работы в одном процессе:

    1. РАЗГОВОР   — /start, выбор языка, кнопка приложения, подписка
                    на оповещения, мгновенный ответ про курс.
    2. ДАННЫЕ     — /api/rates отдаёт приложению живые курсы и вердикт.
                    Раньше цифры лежали в data.js и правились руками;
                    теперь они собираются сами и никогда не протухают.
    3. ОПОВЕЩЕНИЯ — раз в сутки проверяем курс и пишем только тем, кому
                    молчание стоило бы денег.

Почему всё в одном процессе: бесплатный тариф Render даёт один сервис.
Второй процесс — это второй сервис, то есть деньги, которых нет.

Что делает продукт полезным, а не назойливым (правила, зашитые в код):
    — оповещение только когда курс ЛУЧШЕ обычного;
    — не чаще раза в трое суток одному человеку;
    — молчим, пока вердикт не сменился;
    — в каждом оповещении кнопка «не писать больше», одним нажатием.

ТОКЕН В КОДЕ НЕ ХРАНИТСЯ:
    $env:BOT_TOKEN = "токен от BotFather"
    py bot.py
"""
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

import hranilishche
import rates
import sovet

TOKEN = os.environ.get("BOT_TOKEN", "").strip()
if not TOKEN:
    print("Нет BOT_TOKEN. Задай переменную окружения и запусти снова.")
    sys.exit(1)

API = "https://api.telegram.org/bot" + TOKEN
PRILOZHENIE = "https://m1llerzz.github.io/KURS-/"

# Как часто пересобираем курсы. ЦБ меняет курс раз в рабочий день, но
# курсы сервисов на bank.uz двигаются в течение дня, и час — разумная
# середина между свежестью и вежливостью к чужому серверу.
OBNOVLYAT_MINUT = 60

# Не чаще раза в трое суток одному человеку. Одна лишняя рассылка — и
# бота отключают навсегда, второго шанса Telegram не даёт.
PAUZA_MEZHDU_UVEDOMLENIYAMI_CHASOV = 72


# ── Общий кеш курсов ─────────────────────────────────────────────────

_dannye = {"snimok": None, "obnovleno": 0}
_zamok = threading.Lock()


def svezhie_dannye(prinuditelno=False):
    """Снимок курсов. Собирается фоном, наружу отдаётся мгновенно."""
    with _zamok:
        vozrast = time.time() - _dannye["obnovleno"]
        est = _dannye["snimok"] is not None
        if est and not prinuditelno and vozrast < OBNOVLYAT_MINUT * 60:
            return _dannye["snimok"]

    # Тяжёлую часть считаем ВНЕ замка: сбор истории это тридцать запросов,
    # и держать на них общий замок значит подвесить всех, кто читает.
    novyi = rates.snimok(s_istoriey=True)
    ocenka = sovet.analiz(novyi.get("history") or [])
    novyi["sovet"] = ocenka

    with _zamok:
        # Сеть подвела — лучше отдать вчерашнее с честной датой, чем ничего.
        if not novyi.get("ok") and _dannye["snimok"]:
            print("[курсы] сбор не удался, отдаю прошлый снимок", flush=True)
            return _dannye["snimok"]
        _dannye["snimok"] = novyi
        _dannye["obnovleno"] = time.time()

    print("[курсы] обновлено:", len(novyi.get("services") or []), "сервисов,",
          len(novyi.get("history") or []), "точек истории,",
          "вердикт", (ocenka or {}).get("verdikt"), flush=True)
    return novyi


def fonovoe_obnovlenie():
    while True:
        try:
            svezhie_dannye(prinuditelno=True)
        except Exception as oshibka:
            print("[курсы] сбой фонового сбора:", repr(oshibka)[:200], flush=True)
        time.sleep(OBNOVLYAT_MINUT * 60)


# ── Тексты ───────────────────────────────────────────────────────────

VYBOR_YAZYKA = "Tilni tanlang\nВыберите язык"

VERDIKTY = {
    "uz": {
        "otlichno":       "Bugun kurs oydagi odatdagidan sezilarli yaxshi",
        "horosho":        "Bugun kurs odatdagidan yaxshiroq",
        "obychno":        "Bugun kurs odatdagidek",
        "nize_obychnogo": "Bugun kurs odatdagidan pastroq",
        "ploho":          "Bugun kurs oydagi odatdagidan sezilarli yomon",
    },
    "ru": {
        "otlichno":       "Сегодня курс заметно лучше обычного",
        "horosho":        "Сегодня курс лучше обычного",
        "obychno":        "Сегодня курс обычный",
        "nize_obychnogo": "Сегодня курс ниже обычного",
        "ploho":          "Сегодня курс заметно хуже обычного",
    },
}

TEKSTY = {
    "uz": {
        "vybran": "Til: O‘zbekcha",
        "privet": (
            "<b>Pul jo‘natishdan oldin bitta savol: bugunmi yoki ertaga?</b>\n\n"
            "So‘nggi oyda rubl kursi 155 dan 141 gacha tushdi. Bu 9%. "
            "50 000 rublda — 670 ming so‘m. Kun tanlash servis tanlashdan "
            "ko‘ra ko‘proq pul hal qiladi, lekin buni sizga hech kim aytmaydi.\n\n"
            "Men aytaman. Bugungi kurs oyning o‘rtachasidan qanday farq "
            "qilishini ko‘rsataman va kartaga aniq qancha tushishini hisoblab beraman.\n\n"
            "O‘n soniya. Bepul. Pul o‘tkazmaymiz — faqat hisoblaymiz."
        ),
        "knopka": "Hisoblash",
        "knopka_kurs": "Bugungi kurs",
        "podpiska_predlozhenie": (
            "Kurs yaxshilanganda sizga xabar berayinmi?\n\n"
            "Faqat kurs odatdagidan yaxshi bo‘lganda yozaman — ya’ni "
            "jim turishim sizga pulga tushadigan paytda. Uch kunda bir martadan "
            "ko‘p emas. Istalgan payt to‘xtataman."
        ),
        "podpiska_da": "Ha, xabar bering",
        "podpiska_net": "Kerak emas",
        "podpisan": (
            "Yozib qo‘ydim. Kurs yaxshilanganda birinchi bo‘lib bilasiz.\n\n"
            "Odatda qancha jo‘natasiz? Summani yozing — shunda xabarda "
            "foiz emas, aynan sizning so‘mingizni ko‘rsataman."
        ),
        "otpisan": "Yaxshi, kurs haqida yozmayman. /kurs orqali o‘zingiz ko‘ra olasiz.",
        "summa_prinyata": "Eslab qoldim: {summa} rubl. Endi hisob aniq siznikiga mos bo‘ladi.",
        "summa_ne_ponyal": "Summani raqam bilan yozing, masalan: 50000",
        "kurs_zagolovok": "Rubl kursi",
        "kurs_segodnya": "Bugun: <b>{kurs}</b> so‘m",
        "kurs_srednee": "Oydagi o‘rtacha: {srednee} so‘m",
        "kurs_koridor": "Oy koridori: {mn} — {mx}",
        "kurs_na_summe": "Sizning {summa} rublingizda bu odatdagiga nisbatan {znak}{raznica} so‘m",
        "kurs_net": "Hozircha kurs ma’lumotlari yig‘ilmoqda. Bir necha daqiqadan keyin urinib ko‘ring.",
        "uvedomlenie": (
            "<b>{verdikt}</b>\n\n"
            "Rubl: {kurs} so‘m (oydagi o‘rtacha {srednee})\n"
            "{stroka_summy}\n\n"
            "Agar jo‘natmoqchi bo‘lsangiz — bugun yaxshi kun."
        ),
        "stop_knopka": "Boshqa yozmang",
        "trend": {"rastet": "kurs ko‘tarilmoqda",
                  "padaet": "kurs tushmoqda",
                  "stoit": "kurs turibdi"},
        "pomoshch": (
            "<b>Men nima qila olaman</b>\n\n"
            "/kurs — bugungi kurs va u odatdagidan qanday farq qilishi\n"
            "/hisob — kartaga qancha tushishini hisoblash\n"
            "/xabar — kurs haqida xabarlarni yoqish yoki o‘chirish\n"
            "/til — tilni almashtirish\n\n"
            "Pul o‘tkazmaymiz va qabul qilmaymiz. Faqat hisoblaymiz."
        ),
    },
    "ru": {
        "vybran": "Язык: русский",
        "privet": (
            "<b>Перед отправкой один вопрос: сегодня или завтра?</b>\n\n"
            "За последний месяц курс рубля прошёл путь от 155 до 141. Это 9%. "
            "На 50 000 ₽ — 670 тысяч сум. День отправки решает больше денег, "
            "чем выбор сервиса, и об этом вам не говорит никто.\n\n"
            "Я говорю. Покажу, чем сегодняшний курс отличается от среднего за "
            "месяц, и посчитаю, сколько именно дойдёт до карты.\n\n"
            "Десять секунд. Бесплатно. Деньги не переводим — только считаем."
        ),
        "knopka": "Посчитать",
        "knopka_kurs": "Курс сегодня",
        "podpiska_predlozhenie": (
            "Написать, когда курс станет лучше?\n\n"
            "Пишу только когда курс выше обычного — то есть когда моё молчание "
            "стоило бы вам денег. Не чаще раза в трое суток. Отключается одним "
            "нажатием в любой момент."
        ),
        "podpiska_da": "Да, пишите",
        "podpiska_net": "Не нужно",
        "podpisan": (
            "Записал. Узнаете о хорошем курсе первым.\n\n"
            "На какую сумму обычно отправляете? Напишите числом — тогда в "
            "сообщении будут ваши сумы, а не проценты."
        ),
        "otpisan": "Хорошо, про курс писать не буду. Посмотреть самому — /kurs.",
        "summa_prinyata": "Запомнил: {summa} ₽. Теперь расчёт будет про ваши деньги.",
        "summa_ne_ponyal": "Напишите сумму числом, например: 50000",
        "kurs_zagolovok": "Курс рубля",
        "kurs_segodnya": "Сегодня: <b>{kurs}</b> сум",
        "kurs_srednee": "Среднее за месяц: {srednee} сум",
        "kurs_koridor": "Коридор месяца: {mn} — {mx}",
        "kurs_na_summe": "На ваших {summa} ₽ это {znak}{raznica} сум против обычного",
        "kurs_net": "Курсы ещё собираются. Попробуйте через пару минут.",
        "uvedomlenie": (
            "<b>{verdikt}</b>\n\n"
            "Рубль: {kurs} сум (среднее за месяц {srednee})\n"
            "{stroka_summy}\n\n"
            "Если собирались отправлять — сегодня хороший день."
        ),
        "stop_knopka": "Больше не писать",
        "trend": {"rastet": "курс растёт",
                  "padaet": "курс падает",
                  "stoit": "курс стоит"},
        "pomoshch": (
            "<b>Что я умею</b>\n\n"
            "/kurs — курс сегодня и чем он отличается от обычного\n"
            "/schet — посчитать, сколько дойдёт до карты\n"
            "/uved — включить или выключить сообщения о курсе\n"
            "/lang — сменить язык\n\n"
            "Деньги не переводим и не принимаем. Только считаем."
        ),
    },
}


def yazyk(chat_id, po_umolchaniyu="uz"):
    c = hranilishche.chelovek(chat_id)
    lang = (c or {}).get("lang") or po_umolchaniyu
    return lang if lang in TEKSTY else "uz"


# ── Telegram ─────────────────────────────────────────────────────────

def vyzov(metod, telo=None):
    """Обращение к Bot API. Сетевые сбои не роняют бота — он живёт долго."""
    dannye = json.dumps(telo or {}).encode("utf-8")
    zapros = urllib.request.Request(
        API + "/" + metod, data=dannye,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(zapros, timeout=65) as otvet:
            return json.load(otvet)
    except urllib.error.HTTPError as oshibka:
        telo_oshibki = oshibka.read()[:200]
        print("ошибка", metod, oshibka.code, telo_oshibki, flush=True)
        # 403 — человек заблокировал бота. Это не сбой, это ответ:
        # больше ему не пишем, иначе будем долбиться в стену вечно.
        return {"ok": False, "error_code": oshibka.code}
    except Exception as oshibka:
        print("сеть", metod, oshibka, flush=True)
    return None


def poslat(chat_id, text, knopki=None, html=True):
    telo = {"chat_id": chat_id, "text": text,
            "disable_web_page_preview": True}
    if html:
        telo["parse_mode"] = "HTML"
    if knopki:
        telo["reply_markup"] = {"inline_keyboard": knopki}
    return vyzov("sendMessage", telo)


# ── Экраны разговора ─────────────────────────────────────────────────

def sprosit_yazyk(chat_id):
    poslat(chat_id, VYBOR_YAZYKA, [[
        {"text": "O‘zbekcha", "callback_data": "lang:uz"},
        {"text": "Русский", "callback_data": "lang:ru"},
    ]], html=False)


def privetstvie(chat_id, lang):
    t = TEKSTY[lang]
    poslat(chat_id, t["privet"], [
        [{"text": t["knopka"], "web_app": {"url": PRILOZHENIE}}],
        [{"text": t["knopka_kurs"], "callback_data": "kurs"}],
    ])
    # Подписку предлагаем отдельным сообщением и ПОСЛЕ пользы, а не до:
    # просить разрешение писать у человека, который ещё ничего не получил,
    # значит получить отказ. Сначала показываем, что умеем.
    predlozhit_podpisku(chat_id, lang)


def predlozhit_podpisku(chat_id, lang):
    t = TEKSTY[lang]
    poslat(chat_id, t["podpiska_predlozhenie"], [[
        {"text": t["podpiska_da"], "callback_data": "sub:1"},
        {"text": t["podpiska_net"], "callback_data": "sub:0"},
    ]], html=False)


def _stroka_summy(lang, ocenka, summa):
    if not summa:
        return ""
    t = TEKSTY[lang]
    raznica = sovet.vygoda_na_summe(ocenka, summa)
    return t["kurs_na_summe"].format(
        summa="{:,}".format(summa).replace(",", " "),
        znak="+" if raznica > 0 else "",
        raznica="{:,}".format(abs(raznica)).replace(",", " "),
    )


def pokazat_kurs(chat_id, lang):
    d = svezhie_dannye()
    ocenka = (d or {}).get("sovet")
    t = TEKSTY[lang]

    if not ocenka:
        poslat(chat_id, t["kurs_net"], html=False)
        return

    c = hranilishche.chelovek(chat_id) or {}
    summa = c.get("summa_rub")

    stroki = [
        "<b>" + VERDIKTY[lang][ocenka["verdikt"]] + "</b>",
        "",
        t["kurs_segodnya"].format(kurs=ocenka["segodnya"]),
        t["kurs_srednee"].format(srednee=ocenka["srednee_30"]),
        t["kurs_koridor"].format(mn=ocenka["min_30"], mx=ocenka["max_30"]),
    ]
    if ocenka.get("trend"):
        stroki.append(t["trend"][ocenka["trend"]])
    stroka_summy = _stroka_summy(lang, ocenka, summa)
    if stroka_summy:
        stroki += ["", stroka_summy]

    poslat(chat_id, "\n".join(stroki), [[
        {"text": t["knopka"], "web_app": {"url": PRILOZHENIE}}
    ]])
    hranilishche.sobytie(chat_id, "kurs_prosmotr", {"verdikt": ocenka["verdikt"]})


# ── Обработка входящего ──────────────────────────────────────────────

# Кого мы ждём с суммой. Держим в памяти: потеря этого состояния при
# перезапуске не страшна, человек просто напишет ещё раз.
zhdyom_summu = set()

KOMANDY_KURS = ("/kurs", "/rate")
KOMANDY_SCHET = ("/schet", "/hisob", "/calc")
KOMANDY_UVED = ("/uved", "/xabar")
KOMANDY_YAZYK = ("/lang", "/til", "/yazyk")
KOMANDY_POMOSHCH = ("/help", "/pomoshch", "/yordam")


def obrabotat_soobshchenie(soobshchenie):
    chat = soobshchenie.get("chat") or {}
    if not chat:
        return
    chat_id = chat["id"]
    tekst = (soobshchenie.get("text") or "").strip()
    nizhniy = tekst.lower()

    izvesten = hranilishche.chelovek(chat_id) is not None
    lang = yazyk(chat_id)

    # Ждём сумму — принимаем её раньше любых команд, кроме явных.
    if chat_id in zhdyom_summu and not nizhniy.startswith("/"):
        cifry = "".join(s for s in tekst if s.isdigit())
        if cifry and 1000 <= int(cifry) <= 1000000:
            summa = int(cifry)
            hranilishche.zapisat_cheloveka(chat_id, summa_rub=summa)
            zhdyom_summu.discard(chat_id)
            poslat(chat_id, TEKSTY[lang]["summa_prinyata"].format(
                summa="{:,}".format(summa).replace(",", " ")), html=False)
            hranilishche.sobytie(chat_id, "summa_zadana", {"summa": summa})
            pokazat_kurs(chat_id, lang)
        else:
            poslat(chat_id, TEKSTY[lang]["summa_ne_ponyal"], html=False)
        return

    if nizhniy.startswith(KOMANDY_KURS):
        pokazat_kurs(chat_id, lang)
        return

    if nizhniy.startswith(KOMANDY_SCHET):
        poslat(chat_id, TEKSTY[lang]["privet"], [[
            {"text": TEKSTY[lang]["knopka"], "web_app": {"url": PRILOZHENIE}}
        ]])
        return

    if nizhniy.startswith(KOMANDY_UVED):
        predlozhit_podpisku(chat_id, lang)
        return

    if nizhniy.startswith(KOMANDY_YAZYK):
        sprosit_yazyk(chat_id)
        return

    if nizhniy.startswith(KOMANDY_POMOSHCH):
        poslat(chat_id, TEKSTY[lang]["pomoshch"])
        return

    # /start и всё остальное. Знакомому язык уже известен — второй раз
    # спрашивать значит начинать отношения заново при каждом заходе.
    if izvesten:
        privetstvie(chat_id, lang)
    else:
        sprosit_yazyk(chat_id)
        hranilishche.sobytie(chat_id, "novyy", {"start": tekst[:64]})
    print("сообщение", chat_id, tekst[:40], flush=True)


def obrabotat_nazhatie(nazhatie):
    dannye = nazhatie.get("data") or ""
    soobshchenie = nazhatie.get("message") or {}
    chat = soobshchenie.get("chat") or {}
    if not chat:
        return
    chat_id = chat["id"]

    vyzov("answerCallbackQuery", {"callback_query_id": nazhatie["id"]})

    if dannye.startswith("lang:"):
        lang = dannye.split(":", 1)[1]
        if lang not in TEKSTY:
            lang = "uz"
        hranilishche.zapisat_cheloveka(chat_id, lang=lang)
        vyzov("editMessageText", {
            "chat_id": chat_id,
            "message_id": soobshchenie["message_id"],
            "text": TEKSTY[lang]["vybran"],
        })
        privetstvie(chat_id, lang)
        hranilishche.sobytie(chat_id, "yazyk", {"lang": lang})
        return

    lang = yazyk(chat_id)

    if dannye.startswith("sub:"):
        hochet = dannye.split(":", 1)[1] == "1"
        hranilishche.zapisat_cheloveka(chat_id, uvedomlyat=hochet)
        if hochet:
            zhdyom_summu.add(chat_id)
            poslat(chat_id, TEKSTY[lang]["podpisan"], html=False)
        else:
            poslat(chat_id, TEKSTY[lang]["otpisan"], html=False)
        hranilishche.sobytie(chat_id, "podpiska", {"vkl": hochet})
        return

    if dannye == "kurs":
        pokazat_kurs(chat_id, lang)
        return

    if dannye == "stop":
        hranilishche.zapisat_cheloveka(chat_id, uvedomlyat=False)
        poslat(chat_id, TEKSTY[lang]["otpisan"], html=False)
        hranilishche.sobytie(chat_id, "otpiska")
        return


# ── Оповещения ───────────────────────────────────────────────────────

def razoslat_uvedomleniya():
    """Раз в сутки. Пишем только тем, кому это принесёт деньги."""
    d = svezhie_dannye()
    ocenka = (d or {}).get("sovet")
    if not ocenka:
        return

    lyudi = hranilishche.podpisannye()
    otpravleno = propushcheno = 0

    for c in lyudi:
        chat_id = c["chat_id"]
        if not sovet.stoit_uvedomit(ocenka, c.get("posledniy_verdikt")):
            propushcheno += 1
            continue

        lang = c.get("lang") if c.get("lang") in TEKSTY else "uz"
        t = TEKSTY[lang]
        tekst = t["uvedomlenie"].format(
            verdikt=VERDIKTY[lang][ocenka["verdikt"]],
            kurs=ocenka["segodnya"],
            srednee=ocenka["srednee_30"],
            stroka_summy=_stroka_summy(lang, ocenka, c.get("summa_rub")),
        )
        otvet = poslat(chat_id, tekst, [
            [{"text": t["knopka"], "web_app": {"url": PRILOZHENIE}}],
            [{"text": t["stop_knopka"], "callback_data": "stop"}],
        ])

        # Заблокировал или удалил чат — больше не беспокоим. Иначе список
        # мёртвых адресов растёт, а Telegram считает нас навязчивыми.
        if otvet and otvet.get("error_code") in (400, 403):
            hranilishche.zapisat_cheloveka(chat_id, uvedomlyat=False)
            continue

        hranilishche.zapisat_cheloveka(
            chat_id, posledniy_verdikt=ocenka["verdikt"])
        hranilishche.sobytie(chat_id, "uvedomlenie", {"verdikt": ocenka["verdikt"]})
        otpravleno += 1
        # Telegram ограничивает рассылку примерно тридцатью сообщениями
        # в секунду. Идём медленнее с большим запасом: спешить некуда,
        # а попасть в ограничение значит потерять часть рассылки молча.
        time.sleep(0.2)

    print("[оповещения] отправлено", otpravleno, "пропущено", propushcheno, flush=True)


def chasovoy_uvedomleniy():
    """Проверяем раз в час, шлём не чаще раза в сутки и только днём.

    Время узбекское, UTC+5. Писать человеку про курс в три ночи — верный
    способ быть отключённым, каким бы полезным ни было сообщение.
    """
    posledniy_den = None
    while True:
        try:
            teper = datetime.now(timezone.utc) + timedelta(hours=5)
            den = teper.date()
            if 10 <= teper.hour <= 20 and den != posledniy_den:
                razoslat_uvedomleniya()
                posledniy_den = den
        except Exception as oshibka:
            print("[оповещения] сбой:", repr(oshibka)[:200], flush=True)
        time.sleep(3600)


# ── HTTP: живость + данные приложению ────────────────────────────────

class Stranica(BaseHTTPRequestHandler):
    """Отдаёт приложению курсы и держит сервис живым.

    Render гасит сервис без открытого порта, а бесплатный тариф засыпает
    после четверти часа тишины — этот же адрес пингует UptimeRobot.
    """

    def _otvetit(self, telo, tip="text/plain; charset=utf-8", kod=200):
        self.send_response(kod)
        self.send_header("Content-Type", tip)
        self.send_header("Content-Length", str(len(telo)))
        # Приложение живёт на github.io, бот на onrender.com — это разные
        # источники, и без этого заголовка браузер не отдаст ответ скрипту.
        self.send_header("Access-Control-Allow-Origin", "*")
        # Пять минут кеша: приложение открывают часто, а курсы меняются
        # раз в час. Без этого каждый запуск дёргает нас заново.
        self.send_header("Cache-Control", "public, max-age=300")
        self.end_headers()
        return telo

    def do_GET(self):
        put = self.path.split("?")[0].rstrip("/") or "/"

        if put == "/api/rates":
            d = svezhie_dannye() or {"ok": False}
            telo = json.dumps(d, ensure_ascii=False).encode("utf-8")
            self.wfile.write(self._otvetit(telo, "application/json; charset=utf-8"))
            return

        if put == "/api/stats":
            vsego, podpisano = hranilishche.skolko_vsego()
            telo = json.dumps({
                "podpischikov": vsego,
                "s_uvedomleniyami": podpisano,
                "sobytiya_7d": hranilishche.svodka_sobytiy(7),
                "kursy_obnovleny": _dannye["obnovleno"],
            }, ensure_ascii=False).encode("utf-8")
            self.wfile.write(self._otvetit(telo, "application/json; charset=utf-8"))
            return

        self.wfile.write(self._otvetit("QanchaYetadi bot: живой".encode("utf-8")))

    def do_HEAD(self):
        # UptimeRobot проверяет живость методом HEAD. Без обработчика
        # BaseHTTPRequestHandler отвечает 501, монитор считает сервис
        # упавшим и шлёт письма о недоступности — при живом сервисе.
        self._otvetit(b"")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.end_headers()

    def log_message(self, *args):
        pass                      # пинги раз в пять минут засоряют журнал


def podnyat_stranicu():
    port = int(os.environ.get("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), Stranica)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print("страница живости и /api/rates на порту", port, flush=True)


# ── Запуск ───────────────────────────────────────────────────────────

def main():
    hranilishche.podnyat()
    podnyat_stranicu()
    threading.Thread(target=fonovoe_obnovlenie, daemon=True).start()
    threading.Thread(target=chasovoy_uvedomleniy, daemon=True).start()

    ya = vyzov("getMe")
    if not ya or not ya.get("ok"):
        print("Токен не принят. Проверь BOT_TOKEN.")
        return
    print("бот запущен: @" + ya["result"]["username"], flush=True)

    # Меню команд в интерфейсе Telegram: человек видит, что бот умеет,
    # не читая переписку. Ставится один раз при запуске.
    vyzov("setMyCommands", {"commands": [
        {"command": "kurs", "description": "Курс сегодня · Bugungi kurs"},
        {"command": "schet", "description": "Посчитать · Hisoblash"},
        {"command": "uved", "description": "Сообщения о курсе · Kurs xabarlari"},
        {"command": "lang", "description": "Язык · Til"},
        {"command": "help", "description": "Что я умею · Nima qila olaman"},
    ]})

    # На хостинге сервис перезапускается, и старый опрос ещё какое-то время
    # держит очередь: без сброса новый экземпляр получает конфликт и молчит.
    vyzov("deleteWebhook", {"drop_pending_updates": True})

    smeshchenie = None
    while True:
        obnovleniya = vyzov("getUpdates", {
            "timeout": 50,
            "offset": smeshchenie,
            "allowed_updates": ["message", "callback_query"],
        })
        if not obnovleniya or not obnovleniya.get("ok"):
            time.sleep(3)
            continue

        for u in obnovleniya["result"]:
            smeshchenie = u["update_id"] + 1
            try:
                if "message" in u:
                    obrabotat_soobshchenie(u["message"])
                elif "callback_query" in u:
                    obrabotat_nazhatie(u["callback_query"])
            except Exception as oshibka:
                # Одно кривое сообщение не должно останавливать бота для всех.
                print("сбой обработки:", repr(oshibka)[:200], flush=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nостановлен")
