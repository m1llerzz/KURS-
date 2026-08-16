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
import hmac
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import hranilishche
import rates
import sovet

TOKEN = os.environ.get("BOT_TOKEN", "").strip()
if not TOKEN:
    print("Нет BOT_TOKEN. Задай переменную окружения и запусти снова.")
    sys.exit(1)

API = "https://api.telegram.org/bot" + TOKEN
PRILOZHENIE = "https://m1llerzz.github.io/KURS-/"

# Ссылка на мини-апп для КАНАЛА. В канале кнопка web_app не работает —
# Telegram разрешает там только обычный адрес. Метка нужна, чтобы в
# цифрах было видно, сколько людей приходит из канала: без неё нельзя
# понять, окупается ли он вообще.
PRILOZHENIE_SSYLKA = "https://t.me/QanchaYetadi_bot/call?startapp=kanal"


def ssylka(metka="kanal"):
    """Ссылка на приложение со своей меткой источника.

    Разные виды постов получают разные метки — kanal_den, kanal_nedelya,
    kanal_mesyac, kanal_ryvok. Через месяц по цифрам будет видно не просто
    «канал работает», а какой именно формат поста приводит людей, а какой
    только занимает ленту. Без этого пришлось бы гадать.
    """
    chisto = "".join(z for z in str(metka).lower()
                     if z.isalnum() and z.isascii() or z in "_-")[:32]
    return "https://t.me/QanchaYetadi_bot/call?startapp=" + (chisto or "kanal")


# Месяцы для дат в постах. Голая дата 2026-08-03 читается как машинная
# запись; «3 августа» человек соотносит со своим днём зарплаты.
MESYACY = {
    "uz": ["yanvar", "fevral", "mart", "aprel", "may", "iyun",
           "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"],
    "ru": ["января", "февраля", "марта", "апреля", "мая", "июня",
           "июля", "августа", "сентября", "октября", "ноября", "декабря"],
}


def data_slovom(iso, lang="ru"):
    """2026-08-03 -> «3 августа» / «3 avgust». Кривую дату отдаём как есть."""
    try:
        d = datetime.strptime(str(iso)[:10], "%Y-%m-%d")
    except Exception:
        return str(iso)
    return "%d %s" % (d.day, MESYACY.get(lang, MESYACY["ru"])[d.month - 1])


def segodnya_li(iso, teper=None):
    """Сегодняшняя ли это дата по узбекскому времени."""
    teper = teper or (datetime.now(timezone.utc) + timedelta(hours=5))
    return str(iso)[:10] == teper.strftime("%Y-%m-%d")


def podpis_kursa(iso, lang="ru", teper=None):
    """«Сегодняшний курс» или «Курс на 14 августа».

    Зачем так подробно. ЦБ Узбекистана не публикует курс по выходным и
    праздникам, и в понедельник утром свежайшая точка истории — за
    пятницу. Пост, который называет её сегодняшней, врёт три дня в
    неделю, и первый же человек, сверивший с cbu.uz, поймает нас на
    этом. Продукт про честность цифр не может позволить себе такое
    ради одного слова.
    """
    if segodnya_li(iso, teper):
        return "Bugungi kurs" if lang == "uz" else "Сегодняшний курс"
    if lang == "uz":
        return "%s kursi" % data_slovom(iso, "uz")
    return "Курс на %s" % data_slovom(iso, "ru")


# Сколько дней данные могут быть старыми, прежде чем мы перестанем
# советовать. Мягче правила про курсы сервисов (трое суток) намеренно:
# ЦБ не публикует по выходным и в праздники, длинные каникулы — норма.
PREDEL_SOVETA_DNEY = 5


def sovet_ustarel(ocenka, teper=None):
    """Слишком ли стары данные, чтобы что-то советовать.

    Приложение при таких данных прячет курсы сервисов целиком, а совет
    продолжал бодро говорить «сегодня хороший день» — по курсу
    многодневной давности. Это тот же класс вреда, что и совет ждать в
    падающем рынке: человек послушает и потеряет.

    Не смогли разобрать дату — считаем свежим: промолчать из-за
    непонятой строки хуже, чем дать совет.
    """
    if not ocenka:
        return False
    try:
        byla = datetime.strptime(str(ocenka.get("data"))[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return False
    teper = teper or (datetime.now(timezone.utc) + timedelta(hours=5))
    return (teper.date() - byla.date()).days > PREDEL_SOVETA_DNEY


def kakoy_sovet(ocenka):
    """Какой совет давать: обычный или «данные старые»."""
    if sovet_ustarel(ocenka):
        return "stale"
    return (ocenka or {}).get("deystvie") or "obychno"


def podpis_dnya(iso, lang="ru", teper=None):
    """«Сегодня» или «14 августа» — для строк, где речь про день."""
    if segodnya_li(iso, teper):
        return "Bugun" if lang == "uz" else "Сегодня"
    return data_slovom(iso, lang)

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

# Вердикт описывает КУРС, а не день, и потому обходится без слова
# «сегодня». Раньше оно здесь стояло — и три дня в неделю это была
# неправда: ЦБ не публикует курс по выходным, в понедельник свежайшая
# точка за пятницу, а текст называл её сегодняшней. Дату курса теперь
# несёт заголовок поста, и вердикт читается в её контексте.
VERDIKTY = {
    "uz": {
        "otlichno":       "Kurs oydagi odatdagidan sezilarli yaxshi",
        "horosho":        "Kurs odatdagidan yaxshiroq",
        "obychno":        "Kurs odatdagidek",
        "nize_obychnogo": "Kurs odatdagidan pastroq",
        "ploho":          "Kurs oydagi odatdagidan sezilarli yomon",
    },
    "ru": {
        "otlichno":       "Курс заметно лучше обычного",
        "horosho":        "Курс лучше обычного",
        "obychno":        "Курс обычный",
        "nize_obychnogo": "Курс ниже обычного",
        "ploho":          "Курс заметно хуже обычного",
    },
}

TEKSTY = {
    "uz": {
        "vybran": "Til: O‘zbekcha",
        "privet": (
            "<b>Yuborishdan oldin: bugunmi yoki kutamizmi?</b>\n\n"
            "Oy ichida rubl kursi 9% ga o‘zgardi. 50 000 rublda bu — 670 ming "
            "so‘m. Qaysi servis emas, qaysi <b>kun</b> — asosiy pul shunda.\n\n"
            "{stroka_kursa}\n\n"
            "Bepul. Pul o‘tkazmaymiz — faqat hisoblaymiz."
        ),
        # Живая строка курса прямо в приветствии. Человек получает пользу
        # в первом же сообщении, до всякого нажатия, — и сразу видит, что
        # цифры тут настоящие, а не рассказ о том, какие мы хорошие.
        "privet_kurs": "{podpis}: <b>{kurs}</b> so‘m · oyda o‘rtacha {srednee} — {verdikt}",
        "privet_bez_kursa": "Summani kiriting — kartaga qancha yetib borishini aytaman.",
        "knopka": "Hisoblash",
        "knopka_kurs": "Bugungi kurs",
        "knopka_kanal": "Kanal — har kuni kurs",
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
        "kurs_segodnya": "{podpis}: <b>{kurs}</b> so‘m",
        "kurs_srednee": "Oydagi o‘rtacha: {srednee} so‘m",
        "kurs_koridor": "Oy koridori: {mn} — {mx}",
        "kurs_nedelya_up": "Haftada: +{p}%",
        "kurs_nedelya_down": "Haftada: −{p}%",
        "kurs_na_summe": "Sizning {summa} rublingizda bu odatdagiga nisbatan {znak}{raznica} so‘m",
        "kurs_net": "Hozircha kurs ma’lumotlari yig‘ilmoqda. Bir necha daqiqadan keyin urinib ko‘ring.",
        "uvedomlenie": (
            "<b>{verdikt}</b>\n\n"
            "Rubl: {kurs} so‘m, {data} (oydagi o‘rtacha {srednee})\n"
            "{stroka_summy}\n\n"
            "{sovet}"
        ),
        "stop_knopka": "Boshqa yozmang",
        "trend": {"rastet": "kurs ko‘tarilmoqda",
                  "padaet": "kurs tushmoqda",
                  "stoit": "kurs turibdi"},
        "cel_sprosit": (
            "Qaysi kursda sizga xabar berishim kerak?\n\n"
            "Raqam yozing — masalan <b>148</b>. Rubl shu darajaga chiqqan "
            "kuni bir marta yozaman va to‘xtayman.\n\n"
            "{podpis}: {kurs} · oydagi eng yuqori: {mx}"
        ),
        "cel_prinyata": (
            "Yozib qo‘ydim: <b>{cel}</b> so‘m.\n\n"
            "Kurs shu darajaga chiqqanda birinchi bo‘lib bilasiz. "
            "Bekor qilish — /maqsad va 0 raqami."
        ),
        "cel_snyata": "Maqsad bekor qilindi.",
        "cel_slishkom": (
            "Ogohlantiraman: bu kurs oxirgi oyda bo‘lmagan (eng yuqori {mx}). "
            "Kutish uzoq cho‘zilishi mumkin."
        ),
        "cel_ne_ponyal": "Kursni raqam bilan yozing, masalan: 148",
        "cel_dostignuta": (
            "<b>Siz kutgan kurs keldi.</b>\n\n"
            "Rubl: {kurs} so‘m — siz so‘ragan {cel} dan yuqori.\n"
            "{stroka_summy}\n\n"
            "Maqsad o‘chirildi. Yangisini /maqsad orqali qo‘yasiz."
        ),
        "cel_knopka": "Kursni kutish",
        "pomoshch": (
            "<b>Men nima qila olaman</b>\n\n"
            "/kurs — bugungi kurs va u odatdagidan qanday farq qilishi\n"
            "/hisob — kartaga qancha tushishini hisoblash\n"
            "/maqsad — kerakli kursni belgilash, kelganda aytaman\n"
            "/xabar — kurs haqida xabarlarni yoqish yoki o‘chirish\n"
            "/til — tilni almashtirish\n\n"
            "Pul o‘tkazmaymiz va qabul qilmaymiz. Faqat hisoblaymiz."
        ),
    },
    "ru": {
        "vybran": "Язык: русский",
        "privet": (
            "<b>Перед отправкой: сегодня или подождать?</b>\n\n"
            "За месяц курс рубля прошёл 9%. На 50 000 ₽ это 670 тысяч сум. "
            "Не какой сервис, а какой <b>день</b> — вот где основные деньги.\n\n"
            "{stroka_kursa}\n\n"
            "Бесплатно. Деньги не переводим — только считаем."
        ),
        "privet_kurs": "{podpis}: <b>{kurs}</b> сум · в среднем за месяц {srednee} — {verdikt}",
        "privet_bez_kursa": "Введите сумму — скажу, сколько дойдёт до карты.",
        "knopka": "Посчитать",
        "knopka_kurs": "Курс сегодня",
        "knopka_kanal": "Канал — курс каждый день",
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
        "kurs_segodnya": "{podpis}: <b>{kurs}</b> сум",
        "kurs_srednee": "Среднее за месяц: {srednee} сум",
        "kurs_koridor": "Коридор месяца: {mn} — {mx}",
        "kurs_nedelya_up": "За неделю: +{p}%",
        "kurs_nedelya_down": "За неделю: −{p}%",
        "kurs_na_summe": "На ваших {summa} ₽ это {znak}{raznica} сум против обычного",
        "kurs_net": "Курсы ещё собираются. Попробуйте через пару минут.",
        "uvedomlenie": (
            "<b>{verdikt}</b>\n\n"
            "Рубль: {kurs} сум на {data} (среднее за месяц {srednee})\n"
            "{stroka_summy}\n\n"
            "{sovet}"
        ),
        "stop_knopka": "Больше не писать",
        "trend": {"rastet": "курс растёт",
                  "padaet": "курс падает",
                  "stoit": "курс стоит"},
        "cel_sprosit": (
            "При каком курсе вам написать?\n\n"
            "Напишите число — например <b>148</b>. В день, когда рубль "
            "поднимется до него, напишу один раз и замолчу.\n\n"
            "{podpis}: {kurs} · максимум за месяц: {mx}"
        ),
        "cel_prinyata": (
            "Записал: <b>{cel}</b> сум.\n\n"
            "Когда курс дойдёт — узнаете первым. Отменить: /cel и цифра 0."
        ),
        "cel_snyata": "Цель снята.",
        "cel_slishkom": (
            "Предупреждаю: такого курса за последний месяц не было "
            "(максимум {mx}). Ждать, возможно, придётся долго."
        ),
        "cel_ne_ponyal": "Напишите курс числом, например: 148",
        "cel_dostignuta": (
            "<b>Курс, которого вы ждали.</b>\n\n"
            "Рубль: {kurs} сум — выше вашей отметки {cel}.\n"
            "{stroka_summy}\n\n"
            "Цель снята. Новую поставить: /cel"
        ),
        "cel_knopka": "Ждать свой курс",
        "pomoshch": (
            "<b>Что я умею</b>\n\n"
            "/kurs — курс сегодня и чем он отличается от обычного\n"
            "/schet — посчитать, сколько дойдёт до карты\n"
            "/cel — назначить нужный курс, скажу когда придёт\n"
            "/uved — включить или выключить сообщения о курсе\n"
            "/lang — сменить язык\n\n"
            "Деньги не переводим и не принимаем. Только считаем."
        ),
    },
}


def chislo(z, znakov=2):
    """Число так, как его пишут по-русски и по-узбекски: через запятую.

    Питон печатает 141.76, а человек в обеих странах читает 141,76. Точка
    в дробной части — мелочь ровно до того момента, пока не поймёшь, что
    именно из таких мелочей складывается ощущение «сделано на коленке».
    """
    if z is None:
        return "—"
    return ("%.*f" % (znakov, float(z))).replace(".", ",")


def summa_slovom(n):
    """Целое число с пробелами по три знака: 673000 -> 673 000."""
    return "{:,}".format(int(round(n))).replace(",", " ")


# Поля, которые вообще принимаются в событии. Адрес /api/event открыт
# всему интернету: прислать туда можно что угодно, и без белого списка
# это «что угодно» осело бы у нас в базе.
#
# Мы обещаем не собирать личных данных — значит отвечаем и за то, что
# нам присылают. Обещание «не собираем» ничего не стоит, если мы кладём
# в базу любое поле, которое пришло.
POLYA_SOBYTIYA = {
    "verdikt",        # каков был курс, когда человек пришёл
    "istochnik",      # метка: канал, поиск, чат, пересылка
    "iz_peresylki",   # пришёл по чужому расчёту
    "summa",          # ПОРЯДОК суммы, не сама сумма
    "sposobov",       # сколько способов показали
    "servis",         # куда ушёл
    "partner",        # была ли партнёрская ссылка
}


def _chistye_dannye(syroe):
    """Оставляет только известные поля и режет длину значений."""
    if not isinstance(syroe, dict):
        return None
    chistoe = {}
    for kluch in POLYA_SOBYTIYA:
        if kluch not in syroe:
            continue
        znachenie = syroe[kluch]
        if isinstance(znachenie, bool) or isinstance(znachenie, int):
            chistoe[kluch] = znachenie
        elif isinstance(znachenie, str):
            chistoe[kluch] = znachenie[:40]
        elif znachenie is None:
            chistoe[kluch] = None
    return chistoe or None


def mozhno_pisat_naruzhu():
    """Можно ли сейчас делать то, что уходит к людям и повторяется.

    Правило одно на все такие действия: посты в канал, рассылку
    оповещений, еженедельную сводку. Все они защищены от повторов
    отметкой — «этот пост уже публиковали», «этому человеку писали в
    среду». Отметка обязана пережить перезапуск: без DATABASE_URL
    хранилище это файл на диске Render, а он стирается при каждом
    пробуждении сервиса.

    16 августа так вышло семнадцать копий одного поста подряд в канале с
    четырьмя подписчиками. В личных сообщениях то же кончилось бы
    блокировкой бота, и это навсегда.

    Домов у отметки два: Postgres и — для нескольких ключей — список
    команд канала на серверах Telegram (`pamyat_kanala`). Второй
    появляется, только если при запуске доказал боем, что помнит.

    Отдельной функцией, а не проверкой по месту: у правила есть имя, и
    оно читается там, где применяется.
    """
    return hranilishche.pamyat_perezhivet_perezapusk()


def mozhno_pisat_lyudyam():
    """То же правило, но для личных сообщений. Здесь только Postgres.

    Разница не в осторожности, а в том, где лежит защита от повтора. У
    поста в канал это одна отметка на весь канал — её берёт и запасная
    память. У оповещения защита лежит В ПРОФИЛЕ КАЖДОГО ЧЕЛОВЕКА: когда
    ему писали в прошлый раз и какой вердикт был тогда. Это сотни записей
    с личными данными, и хранить их негде, кроме базы.

    А цена ошибки здесь выше: за повтор в канале отписываются, за повтор
    в личных бота блокируют, и второго шанса написать человеку не будет.
    """
    return hranilishche.na_postgres()


def poryadok_summy(n):
    """Порядок суммы вместо самой суммы: 50 000 -> «50-150k».

    Ровно те же границы, что в приложении. Для решений порядка хватает,
    а для вреда — нет: сумма, которую человек собирается отправить домой,
    в нашей базе лежать не должна ни в каком виде.
    """
    v = abs(int(n or 0))
    if v < 10000:
        return "до10k"
    if v < 50000:
        return "10-50k"
    if v < 150000:
        return "50-150k"
    if v < 500000:
        return "150-500k"
    return "от500k"


def yazyk(chat_id, po_umolchaniyu="uz"):
    c = hranilishche.chelovek(chat_id)
    lang = (c or {}).get("lang") or po_umolchaniyu
    return lang if lang in TEKSTY else "uz"


# ── Telegram ─────────────────────────────────────────────────────────

def vyzov(metod, telo=None, popytok=2):
    """Обращение к Bot API. Сетевые сбои не роняют бота — он живёт долго.

    Отдельно про 429 «слишком часто». Telegram ограничивает рассылку
    примерно тридцатью сообщениями в секунду и на превышение отвечает
    кодом 429, называя в ответе, сколько подождать.

    Без этой обработки выходило хуже потери сообщения: рассылка считала
    отправку состоявшейся, записывала человеку «последний вердикт» и
    время — и пауза в трое суток начинала идти. Человек не получал
    ничего и пропускал хороший курс, а мы об этом не знали. Пока
    подписчиков единицы, 429 не случается; на сотне случится.
    """
    dannye = json.dumps(telo or {}).encode("utf-8")

    for popytka in range(max(1, popytok)):
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

            if oshibka.code == 429 and popytka + 1 < max(1, popytok):
                # Telegram сам говорит, сколько ждать. Верхнюю границу
                # ставим: висеть полчаса в одном вызове нельзя, за это
                # время встанет и опрос сообщений.
                zhdat = 3
                try:
                    razbor = json.loads(telo_oshibki.decode("utf-8", "replace"))
                    zhdat = int((razbor.get("parameters") or {})
                                .get("retry_after") or 3)
                except Exception:
                    pass
                zhdat = max(1, min(zhdat, 30))
                print("[telegram] слишком часто, жду %d с и повторяю" % zhdat,
                      flush=True)
                time.sleep(zhdat)
                continue

            # 403 — человек заблокировал бота. Это не сбой, это ответ:
            # больше ему не пишем, иначе будем долбиться в стену вечно.
            return {"ok": False, "error_code": oshibka.code}
        except Exception as oshibka:
            print("сеть", metod, oshibka, flush=True)
            return None

    return {"ok": False, "error_code": 429}


def poslat(chat_id, text, knopki=None, html=True):
    telo = {"chat_id": chat_id, "text": text,
            "disable_web_page_preview": True}
    if html:
        telo["parse_mode"] = "HTML"
    if knopki:
        telo["reply_markup"] = {"inline_keyboard": knopki}
    return vyzov("sendMessage", telo)


# ── Экраны разговора ─────────────────────────────────────────────────

def sprosit_yazyk(chat_id, posle=""):
    """Спрашиваем язык. `posle` — что сделать после выбора: показать
    приветствие (по умолчанию) или сразу предложить подписку, если человек
    пришёл по ссылке «хочу оповещения» из приложения.
    """
    poslat(chat_id, VYBOR_YAZYKA, [[
        {"text": "O‘zbekcha", "callback_data": "lang:uz:" + posle},
        {"text": "Русский", "callback_data": "lang:ru:" + posle},
    ]], html=False)


def privetstvie(chat_id, lang):
    """Одно сообщение. Ровно одно.

    Раньше следом сразу летело второе — предложение подписки. Два
    сообщения подряд от бота, которому человек написал одно слово,
    читаются как спам, каким бы полезным ни было второе.
    """
    t = TEKSTY[lang]
    ocenka = (svezhie_dannye() or {}).get("sovet")

    # Курс подставляем прямо в приветствие. Человек получает пользу в первом
    # же сообщении, до единого нажатия, — и сразу видит, что цифры здесь
    # настоящие, а не рассказ о том, какие мы хорошие.
    if ocenka:
        # Подпись с датой, а не слово «сегодня». ЦБ не публикует курс по
        # выходным: в понедельник свежайшее число — за пятницу, и «сегодня
        # 141,76» было бы неправдой три дня в неделю. Вердикты от этого
        # слова уже избавили, а эти две строки остались с ним.
        stroka = t["privet_kurs"].format(
            podpis=podpis_kursa(ocenka.get("data"), lang),
            kurs=chislo(ocenka["segodnya"]), srednee=chislo(ocenka["srednee_30"]),
            verdikt=VERDIKTY[lang][ocenka["verdikt"]].lower())
    else:
        stroka = t["privet_bez_kursa"]

    knopki = [
        [{"text": t["knopka"], "web_app": {"url": PRILOZHENIE}}],
        [{"text": t["knopka_kurs"], "callback_data": "kurs"}],
    ]

    # Канал — второй путь возврата, и он мягче подписки: на канал
    # подписываются охотнее, потому что он не пишет лично. Кнопкой в том
    # же сообщении, а не отдельным — правило про два сообщения подряд
    # никуда не делось.
    kanal = ssylka_na_kanal()
    if kanal:
        knopki.append([{"text": t["knopka_kanal"], "url": kanal}])

    poslat(chat_id, t["privet"].format(stroka_kursa=stroka), knopki)


def predlozhit_podpisku(chat_id, lang):
    """Предложение приходит один раз за всю жизнь — и только если дошло.

    Отметка «уже спрашивали» ставилась ДО отправки. Не дошло — человек
    всё равно помечен, и предложения он не увидит уже никогда: второй
    раз мы намеренно не спрашиваем. Один сбой сети стоил бы подписчика
    навсегда, и никто бы этого не заметил.

    Порядок «сначала отправить, потом запомнить» даёт риск обратного —
    спросить дважды, если запись не удалась. Из двух зол это меньшее:
    повтор один раз читается как неловкость, молчание навсегда — как
    потерянный человек.
    """
    t = TEKSTY[lang]
    otvet = poslat(chat_id, t["podpiska_predlozhenie"], [[
        {"text": t["podpiska_da"], "callback_data": "sub:1"},
        {"text": t["podpiska_net"], "callback_data": "sub:0"},
    ]], html=False)

    if otvet and otvet.get("ok"):
        hranilishche.zapisat_cheloveka(chat_id, sprosili_podpisku=True)
        return True
    return False


def mozhet_predlozhit_podpisku(chat_id):
    """Предложить подписку — но только когда человек уже получил пользу.

    Момент выбран не случайно: приложение сообщает боту о расчёте, значит
    человек только что увидел свою цифру. Предложение придёт в чат и
    попадётся ему на глаза, когда он выйдет из приложения, — а не до того,
    как он вообще понял, зачем мы нужны.

    Условия жёсткие: спрашиваем ОДИН раз за всю жизнь, не спрашиваем тех,
    кто уже согласился, и не спрашиваем того, кто уже отказался. Второй
    заход с тем же вопросом — это давление, а не предложение.
    """
    if not chat_id:
        return
    c = hranilishche.chelovek(chat_id)
    if not c:
        return                       # не наш человек, приложение открыто со стороны
    if c.get("sprosili_podpisku") or c.get("uvedomlyat"):
        return

    lang = c.get("lang") if c.get("lang") in TEKSTY else "uz"
    # Событие — только если предложение дошло. Иначе в цифрах будет
    # «предложили ста, согласились двое», хотя часть из ста ничего не
    # видела, и доля согласий окажется заниженной без причины.
    if predlozhit_podpisku(chat_id, lang):
        hranilishche.sobytie(chat_id, "podpiska_predlozhena")


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
        t["kurs_segodnya"].format(
            podpis=podpis_kursa(ocenka.get("data"), lang),
            kurs=chislo(ocenka["segodnya"])),
        t["kurs_srednee"].format(srednee=chislo(ocenka["srednee_30"])),
        t["kurs_koridor"].format(mn=chislo(ocenka["min_30"]), mx=chislo(ocenka["max_30"])),
    ]
    # Сдвиг за неделю в процентах, а если его нет — хотя бы направление.
    # «Падает» без величины ни к чему не обязывает.
    nedelya = ocenka.get("nedelya_percent")
    if nedelya is not None and abs(nedelya) >= 0.1:
        kluch = "kurs_nedelya_up" if nedelya > 0 else "kurs_nedelya_down"
        stroki.append(t[kluch].format(p=chislo(abs(nedelya), 1)))
    elif ocenka.get("trend"):
        stroki.append(t["trend"][ocenka["trend"]])
    stroka_summy = _stroka_summy(lang, ocenka, summa)
    if stroka_summy:
        stroki += ["", stroka_summy]

    # Что делать — отдельной строкой и последней. Человек читает курс,
    # а уходит с решением; без этой строки он уходит только с цифрой.
    stroki += ["", DEYSTVIYA[lang][kakoy_sovet(ocenka)]]

    # Кнопка цели стоит рядом с курсом не случайно: человек видит цифру,
    # решает «мало» — и тут же может сказать, при какой напомнить.
    # Спрятанная в меню, эта возможность не нашлась бы никогда.
    poslat(chat_id, "\n".join(stroki), [
        [{"text": t["knopka"], "web_app": {"url": PRILOZHENIE}}],
        [{"text": t["cel_knopka"], "callback_data": "cel"}],
    ])
    hranilishche.sobytie(chat_id, "kurs_prosmotr", {"verdikt": ocenka["verdikt"]})


# ── Обработка входящего ──────────────────────────────────────────────

# Кого мы ждём с суммой. Держим в памяти: потеря этого состояния при
# перезапуске не страшна, человек просто напишет ещё раз.
zhdyom_summu = set()
zhdyom_cel = set()

KOMANDY_KURS = ("/kurs", "/rate")
KOMANDY_SCHET = ("/schet", "/hisob", "/calc")
KOMANDY_UVED = ("/uved", "/xabar")
KOMANDY_YAZYK = ("/lang", "/til", "/yazyk")
KOMANDY_POMOSHCH = ("/help", "/pomoshch", "/yordam")
KOMANDY_CEL = ("/cel", "/maqsad", "/target")
# Только для своих: выдаёт готовые тексты для посева с живыми числами.
KOMANDY_TEKST = ("/tekst", "/matn")

# Курс рубля к суму живёт примерно в этих границах. Цель вне их — это
# опечатка (148 набрали как 1480), а не желание; принять такое значит
# пообещать сообщение, которое не придёт никогда.
CEL_MIN, CEL_MAX = 80.0, 400.0


def sprosit_cel(chat_id, lang):
    d = svezhie_dannye()
    ocenka = (d or {}).get("sovet")
    if not ocenka:
        poslat(chat_id, TEKSTY[lang]["kurs_net"], html=False)
        return
    zhdyom_cel.add(chat_id)
    poslat(chat_id, TEKSTY[lang]["cel_sprosit"].format(
        podpis=podpis_kursa(ocenka.get("data"), lang),
        kurs=chislo(ocenka["segodnya"]), mx=chislo(ocenka["max_30"])))


def prinyat_cel(chat_id, lang, tekst):
    """Разбирает присланное число. Возвращает True, если разобрал."""
    ochishcheno = tekst.replace(",", ".").strip()
    znaki = "".join(s for s in ochishcheno if s.isdigit() or s == ".")
    try:
        cel = float(znaki)
    except ValueError:
        poslat(chat_id, TEKSTY[lang]["cel_ne_ponyal"], html=False)
        return False

    # Ноль — договорённый способ отказаться. Отдельной команды для этого
    # заводить не надо: человек уже в разговоре про цель.
    if cel == 0:
        hranilishche.zapisat_cheloveka(chat_id, cel_kurs="sbros")
        zhdyom_cel.discard(chat_id)
        poslat(chat_id, TEKSTY[lang]["cel_snyata"], html=False)
        hranilishche.sobytie(chat_id, "cel_snyata")
        return True

    if not (CEL_MIN <= cel <= CEL_MAX):
        poslat(chat_id, TEKSTY[lang]["cel_ne_ponyal"], html=False)
        return False

    zhdyom_cel.discard(chat_id)
    # Записываем ДО отправки подтверждения — и это не то же самое, что
    # отметка «мы уже спрашивали».
    #
    # Здесь мы фиксируем РЕШЕНИЕ ЧЕЛОВЕКА: он назвал курс и ждёт сигнала.
    # Не дойдёт наше «записал» — цель всё равно сохранится и сработает,
    # то есть ошибка играет в его пользу. А отметка «спрашивали» — это
    # наше собственное действие, и записывать его до отправки значит
    # молча лишить человека того, о чём мы так и не спросили.
    #
    # Правило: своё действие записываем после подтверждения, чужое
    # решение — сразу.
    hranilishche.zapisat_cheloveka(chat_id, cel_kurs=cel, uvedomlyat=True)

    # Цель принимаем всегда — это его деньги и его ожидание. Но если такого
    # курса за месяц не было ни разу, говорим об этом сразу, одним и тем же
    # сообщением. Запрещать нельзя, промолчать тоже: человек будет ждать
    # сигнала, который может не прийти.
    ocenka = (svezhie_dannye() or {}).get("sovet") or {}
    maksimum = ocenka.get("max_30")
    otvet = TEKSTY[lang]["cel_prinyata"].format(cel=chislo(cel))
    if maksimum and cel > maksimum:
        otvet += "\n\n" + TEKSTY[lang]["cel_slishkom"].format(mx=chislo(maksimum))

    poslat(chat_id, otvet)
    hranilishche.sobytie(chat_id, "cel_zadana",
                         {"cel": cel, "vyshe_maksimuma": bool(maksimum and cel > maksimum)})
    return True


def obrabotat_soobshchenie(soobshchenie):
    chat = soobshchenie.get("chat") or {}
    if not chat:
        return
    chat_id = chat["id"]
    tekst = (soobshchenie.get("text") or "").strip()
    nizhniy = tekst.lower()

    izvesten = hranilishche.chelovek(chat_id) is not None
    lang = yazyk(chat_id)

    # Ждём цель по курсу — она перехватывает ввод раньше суммы: человек
    # только что попросил её поставить, и число сейчас означает курс.
    if chat_id in zhdyom_cel and not nizhniy.startswith("/"):
        prinyat_cel(chat_id, lang, tekst)
        return

    # Ждём сумму — принимаем её раньше любых команд, кроме явных.
    if chat_id in zhdyom_summu and not nizhniy.startswith("/"):
        cifry = "".join(s for s in tekst if s.isdigit())
        if cifry and 1000 <= int(cifry) <= 1000000:
            summa = int(cifry)
            hranilishche.zapisat_cheloveka(chat_id, summa_rub=summa)
            zhdyom_summu.discard(chat_id)
            poslat(chat_id, TEKSTY[lang]["summa_prinyata"].format(
                summa="{:,}".format(summa).replace(",", " ")), html=False)
            # Порядок суммы, а не сама сумма. Приложение так и делает,
            # а бот писал в базу точное число — то самое, которое человек
            # собирается отправить домой. Правило одно для обоих:
            # наружу уходит порядок, потому что для решений его хватает,
            # а для вреда — нет.
            hranilishche.sobytie(chat_id, "summa_zadana",
                                 {"summa": poryadok_summy(summa)})
            pokazat_kurs(chat_id, lang)
        else:
            poslat(chat_id, TEKSTY[lang]["summa_ne_ponyal"], html=False)
        return

    if nizhniy.startswith(KOMANDY_TEKST):
        # Метка чата приходит хвостом: «/tekst moskva1».
        chasti_t = tekst.split(None, 1)
        vydat_teksty_dlya_poseva(
            chat_id, chasti_t[1].strip() if len(chasti_t) > 1 else "")
        return

    if nizhniy.startswith(KOMANDY_KURS):
        pokazat_kurs(chat_id, lang)
        return

    if nizhniy.startswith(KOMANDY_SCHET):
        poslat(chat_id, TEKSTY[lang]["privet"], [[
            {"text": TEKSTY[lang]["knopka"], "web_app": {"url": PRILOZHENIE}}
        ]])
        return

    if nizhniy.startswith(KOMANDY_CEL):
        # Число могли прислать сразу командой: «/cel 148».
        hvost = tekst.split(None, 1)[1] if len(tekst.split(None, 1)) > 1 else ""
        if hvost.strip():
            prinyat_cel(chat_id, lang, hvost)
        else:
            sprosit_cel(chat_id, lang)
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

    # ── /start с параметром ──────────────────────────────────────────
    # Ссылка «хочу оповещения» из приложения ведёт на /start uved, а
    # пересланный расчёт — на /start share. Без разбора параметра человек,
    # нажавший в приложении «да, пишите», попадал на общее приветствие и
    # не понимал, куда делась его просьба.
    if nizhniy.startswith("/start"):
        chasti = tekst.split(None, 1)
        parametr = chasti[1].strip().lower() if len(chasti) > 1 else ""

        if not izvesten:
            sprosit_yazyk(chat_id, posle="uved" if parametr == "uved" else "")
            # Метку чистим так же, как в приложении: Telegram и так
            # ограничивает набор символов в start-параметре, но полагаться
            # на чужие ограничения в том, что уходит к нам в базу и потом
            # в сводку, — плохая привычка.
            metka = "".join(z for z in parametr
                            if (z.isalnum() and z.isascii()) or z in "_-")[:32]
            hranilishche.sobytie(chat_id, "novyy",
                                 {"start": metka} if metka else None)
            return

        if parametr == "uved":
            predlozhit_podpisku(chat_id, lang)
            return

        privetstvie(chat_id, lang)
        return

    # ── Всё остальное ────────────────────────────────────────────────
    if not izvesten:
        sprosit_yazyk(chat_id)
        # Метки здесь НЕТ, и это важно. Раньше сюда клался текст самого
        # сообщения — то есть в разбивку «откуда пришли» попадали строки
        # «привет», «здравствуйте» и что угодно ещё, что человек напишет
        # первым. Карта посева, ради которой всё это и считается,
        # засорялась словами живых людей.
        #
        # Вторая причина серьёзнее: мы обещаем не собирать личных данных,
        # а в первом сообщении человек может написать что угодно, включая
        # свой номер телефона. Такому не место в нашей базе.
        hranilishche.sobytie(chat_id, "novyy")
        print("сообщение", chat_id, tekst[:40], flush=True)
        return

    # Знакомому на произвольный текст показываем КУРС, а не приветствие.
    # Раньше в ответ на «спасибо» прилетал рассказ о том, кто мы такие, —
    # это выглядит так, будто бот тебя не помнит.
    pokazat_kurs(chat_id, lang)
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
        chasti = dannye.split(":")
        lang = chasti[1] if len(chasti) > 1 else "uz"
        posle = chasti[2] if len(chasti) > 2 else ""
        if lang not in TEKSTY:
            lang = "uz"
        hranilishche.zapisat_cheloveka(chat_id, lang=lang)

        # Вопрос про язык убираем совсем, а не превращаем в надпись
        # «Язык: русский». Отработавший вопрос — это мусор в переписке,
        # и его накапливается по одному на каждый заход.
        udaleno = vyzov("deleteMessage", {
            "chat_id": chat_id, "message_id": soobshchenie["message_id"]})
        if not udaleno or not udaleno.get("ok"):
            # Старше двух суток Telegram удалять не даёт — тогда хотя бы
            # снимаем кнопки, чтобы по ним не нажимали второй раз.
            vyzov("editMessageText", {
                "chat_id": chat_id,
                "message_id": soobshchenie["message_id"],
                "text": TEKSTY[lang]["vybran"],
            })

        if posle == "uved":
            predlozhit_podpisku(chat_id, lang)
        else:
            privetstvie(chat_id, lang)
        hranilishche.sobytie(chat_id, "yazyk", {"lang": lang})
        return

    lang = yazyk(chat_id)

    if dannye.startswith("sub:"):
        hochet = dannye.split(":", 1)[1] == "1"
        if hochet:
            hranilishche.zapisat_cheloveka(chat_id, uvedomlyat=True)
        else:
            # Отписался — стираем и сумму. Она хранилась ровно для одного:
            # чтобы оповещение говорило про его деньги, а не про абстрактные
            # 50 000. Оповещений больше не будет — значит и повода держать
            # её нет. `LEGAL.md`: суммы переводов не хранятся в привязке к
            # личности дольше, чем нужно для того, ради чего человек их сам
            # назвал.
            hranilishche.zapisat_cheloveka(
                chat_id, uvedomlyat=False, summa_rub="sbros")
        if hochet:
            zhdyom_summu.add(chat_id)
            poslat(chat_id, TEKSTY[lang]["podpisan"], html=False)
        else:
            # Отказался от личных сообщений — предлагаем канал, но только
            # кнопкой в том же ответе. Человек отказал нам в праве писать
            # ему лично; канал этого права не требует, и потому это не
            # обход отказа, а уважение к нему. Второго сообщения нет.
            kanal = ssylka_na_kanal()
            poslat(chat_id, TEKSTY[lang]["otpisan"],
                   [[{"text": TEKSTY[lang]["knopka_kanal"], "url": kanal}]]
                   if kanal else None, html=False)
        hranilishche.sobytie(chat_id, "podpiska", {"vkl": hochet})
        return

    if dannye == "kurs":
        pokazat_kurs(chat_id, lang)
        return

    if dannye == "cel":
        sprosit_cel(chat_id, lang)
        return

    if dannye == "stop":
        # Кнопка «больше не писать» из самого оповещения. Сумму стираем
        # здесь так же, как при отказе: держать её дальше не для чего.
        hranilishche.zapisat_cheloveka(
            chat_id, uvedomlyat=False, summa_rub="sbros")
        poslat(chat_id, TEKSTY[lang]["otpisan"], html=False)
        hranilishche.sobytie(chat_id, "otpiska")
        return


# ── Оповещения ───────────────────────────────────────────────────────

def proverit_celi():
    """Курс дошёл до отметки, которую человек назначил сам.

    Это сильнее любой нашей рассылки: сообщение приходит по его решению,
    а не по нашему расписанию. Поэтому цель снимается сразу после того,
    как сработала, — ждать второго сигнала он не просил.
    """
    ocenka = (svezhie_dannye() or {}).get("sovet")
    if not ocenka:
        return

    segodnya = ocenka["segodnya"]
    srabotalo = 0

    for c in hranilishche.s_celyu():
        cel = c.get("cel_kurs")
        if not cel or segodnya < cel:
            continue

        chat_id = c["chat_id"]
        lang = c.get("lang") if c.get("lang") in TEKSTY else "uz"
        otvet = poslat(chat_id, TEKSTY[lang]["cel_dostignuta"].format(
            kurs=chislo(segodnya), cel=chislo(cel),
            stroka_summy=_stroka_summy(lang, ocenka, c.get("summa_rub"))), [
                [{"text": TEKSTY[lang]["knopka"], "web_app": {"url": PRILOZHENIE}}]
            ])

        # Заблокировал бота — цель тоже снимаем, иначе она будет висеть
        # вечно и дёргать нас каждый день.
        if otvet and otvet.get("error_code") in (400, 403):
            hranilishche.zapisat_cheloveka(chat_id, cel_kurs="sbros",
                                           uvedomlyat=False)
            continue

        # Не дошло — цель НЕ снимаем.
        #
        # Она снималась до проверки ответа, то есть при любой неудаче
        # отправки. Человек сам назвал курс, при котором его разбудить,
        # ждал его неделями — и терял бы и сообщение, и саму цель разом,
        # ничего об этом не узнав. Попробуем в следующий час.
        if not otvet or not otvet.get("ok"):
            print("[цели] не дошло до %s, цель оставляю" % chat_id, flush=True)
            continue

        hranilishche.zapisat_cheloveka(chat_id, cel_kurs="sbros")
        hranilishche.sobytie(chat_id, "cel_dostignuta", {"cel": cel, "kurs": segodnya})
        srabotalo += 1
        time.sleep(0.2)

    if srabotalo:
        print("[цели] сработало", srabotalo, flush=True)


def razoslat_uvedomleniya():
    """Раз в сутки. Пишем только тем, кому это принесёт деньги."""
    # Без базы не рассылаем — по той же причине, по которой не публикуем
    # в канал, но последствия здесь тяжелее.
    #
    # Обе защиты от повторов живут в профиле человека: «когда писали в
    # прошлый раз» и «какой вердикт был тогда». Без DATABASE_URL профиль
    # лежит в файле на эфемерном диске Render, а тот стирается при каждом
    # пробуждении сервиса. После стирания пауза в трое суток обнуляется,
    # прошлый вердикт исчезает — и человек получает одно и то же
    # оповещение снова и снова.
    #
    # В канале за такое отписываются. В личных сообщениях — блокируют
    # бота, и это навсегда: второго шанса написать человеку не будет.
    if not mozhno_pisat_lyudyam():
        print("[оповещения] НЕ РАССЫЛАЮ: нет DATABASE_URL. Пауза между "
              "письмами и прошлый вердикт не переживут перезапуск, и один "
              "и тот же текст уйдёт человеку многократно.", flush=True)
        return

    d = svezhie_dannye()
    ocenka = (d or {}).get("sovet")
    if not ocenka:
        return

    lyudi = hranilishche.podpisannye()
    otpravleno = propushcheno = 0

    for c in lyudi:
        chat_id = c["chat_id"]
        if not sovet.stoit_uvedomit(ocenka, c.get("posledniy_verdikt"),
                                    c.get("uvedomlen_v")):
            propushcheno += 1
            continue

        lang = c.get("lang") if c.get("lang") in TEKSTY else "uz"
        t = TEKSTY[lang]
        tekst = t["uvedomlenie"].format(
            verdikt=VERDIKTY[lang][ocenka["verdikt"]],
            kurs=chislo(ocenka["segodnya"]),
            # Дата курса. Оповещение уходит в день смены вердикта, но
            # правило проекта не знает исключений: цифра без даты не
            # показывается никому и никогда.
            data=data_slovom(ocenka.get("data"), lang),
            srednee=chislo(ocenka["srednee_30"]),
            stroka_summy=_stroka_summy(lang, ocenka, c.get("summa_rub")),
            # Совет берём из общей таблицы, а не пишем в шаблоне: иначе
            # оповещение однажды скажет одно, а приложение другое.
            sovet=DEYSTVIYA[lang][kakoy_sovet(ocenka)],
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

        # Не дошло — не записываем, что дошло.
        #
        # Здесь этой проверки не было, и любая неудача отправки (429
        # «слишком часто», обрыв сети, пятисотка на стороне Telegram)
        # засчитывалась как успешная: человеку проставлялся последний
        # вердикт и время, пауза в трое суток начинала идти. Он не
        # получал ничего, пропускал хороший курс, а в наших цифрах всё
        # выглядело отправленным.
        if not otvet or not otvet.get("ok"):
            propushcheno += 1
            print("[оповещения] не дошло до %s, попробуем в следующий раз"
                  % chat_id, flush=True)
            continue

        # Время отправки записываем обязательно: по нему держится пауза в
        # трое суток. Без него смены вердикта туда-сюда давали бы человеку
        # сообщение хоть каждый день.
        hranilishche.zapisat_cheloveka(
            chat_id, posledniy_verdikt=ocenka["verdikt"],
            uvedomlen_v=datetime.now(timezone.utc).isoformat())
        hranilishche.sobytie(chat_id, "uvedomlenie", {"verdikt": ocenka["verdikt"]})
        otpravleno += 1
        # Telegram ограничивает рассылку примерно тридцатью сообщениями
        # в секунду. Идём медленнее с большим запасом: спешить некуда,
        # а попасть в ограничение значит потерять часть рассылки молча.
        time.sleep(0.2)

    print("[оповещения] отправлено", otpravleno, "пропущено", propushcheno, flush=True)


POST_KANALA = {
    "uz": (
        "<b>Rubl kursi — {den}</b>\n\n"
        "1 ₽ = <b>{kurs}</b> so‘m\n"
        "Oyda o‘rtacha: {srednee}\n"
        "{verdikt}\n\n"
        "Oy davomida kurs {mn} dan {mx} gacha yurdi. "
        "50 000 rublda eng yaxshi va eng yomon kun orasidagi farq — "
        "<b>{razmah} so‘m</b>.\n\n"
        "{sovet}"
    ),
    "ru": (
        "<b>Курс рубля — {den}</b>\n\n"
        "1 ₽ = <b>{kurs}</b> сум\n"
        "В среднем за месяц: {srednee}\n"
        "{verdikt}\n\n"
        "За месяц курс ходил от {mn} до {mx}. На переводе 50 000 ₽ разница "
        "между лучшим и худшим днём — <b>{razmah} сум</b>.\n\n"
        "{sovet}"
    ),
}

# Пост недели, по пятницам. Другой формат намеренно: один и тот же вид
# поста каждый день читают неделю, потом перестают замечать. Итог недели
# отвечает на другой вопрос — не «что делать сегодня», а «что вообще
# было», и его пересылают тем, кто собирается отправлять на выходных.
POST_NEDELI = {
    "uz": (
        "<b>Hafta yakuni</b>\n\n"
        "Rubl kursi: {nachalo} → {konec} ({izmenenie}%)\n"
        "Eng yaxshi kun — {max_data}, kurs {mx}\n"
        "Eng yomon kun — {min_data}, kurs {mn}\n\n"
        "50 000 rublda shu ikki kun orasidagi farq — <b>{razmah} so‘m</b>.\n\n"
        "{upushcheno}\n\n"
        "{sovet}"
    ),
    "ru": (
        "<b>Итог недели</b>\n\n"
        "Курс рубля: {nachalo} → {konec} ({izmenenie}%)\n"
        "Лучший день — {max_data}, курс {mx}\n"
        "Худший день — {min_data}, курс {mn}\n\n"
        "На переводе 50 000 ₽ разница между этими днями — "
        "<b>{razmah} сум</b>.\n\n"
        "{upushcheno}\n\n"
        "{sovet}"
    ),
}

UPUSHCHENO = {
    "uz": {
        "est": "{kurs} haftaning eng yaxshi kunidan {skolko} so‘mga "
               "past (50 000 rublda).",
        "net": "{den} — haftaning eng yaxshi kuni.",
    },
    "ru": {
        "est": "{kurs} на {skolko} сум хуже лучшего дня недели — "
               "это на переводе 50 000 ₽.",
        "net": "{den} — лучший день недели.",
    },
}

# Пост месяца, первого числа. Ровно та цифра, на которой стоит весь
# продукт: сколько стоит выбор дня. Раз в месяц её стоит показать целиком.
POST_MESYACA = {
    "uz": (
        "<b>Oxirgi 30 kun</b>\n\n"
        "Kurs {mn} dan {mx} gacha yurdi — bu {razmah_percent}%.\n"
        "Eng yaxshi kun {max_data}, eng yomon {min_data}.\n\n"
        "50 000 rubl yuborganda shu ikki kun orasidagi farq — "
        "<b>{razmah} so‘m</b>.\n\n"
        "Servis tanlash bunchalik farq bermaydi. Eng ko‘p pulni "
        "yuborish KUNI hal qiladi — buni hech kim aytmaydi.\n\n"
        "{sovet}"
    ),
    "ru": (
        "<b>Последние 30 дней</b>\n\n"
        "Курс ходил от {mn} до {mx} — это {razmah_percent}%.\n"
        "Лучший день {max_data}, худший {min_data}.\n\n"
        "На переводе 50 000 ₽ разница между этими днями — "
        "<b>{razmah} сум</b>.\n\n"
        "Выбор сервиса столько не даёт. Больше всего решает ДЕНЬ "
        "отправки, и об этом не говорит никто.\n\n"
        "{sovet}"
    ),
}

# Внеочередной пост: курс дёрнулся за сутки сильнее обычного. Выходит
# редко и потому читается. Канал, который каждый день кричит «важно»,
# перестают открывать быстрее, чем канал, который молчит.
POST_RYVOK = {
    "uz": {
        "vverh": (
            "<b>Kurs keskin ko‘tarildi</b>\n\n"
            "{data_vchera}: {vchera}\n"
            "{data}: <b>{segodnya}</b> — {percent}%\n\n"
            "50 000 rublda bu <b>{na_50k} so‘m</b> ko‘proq.\n\n"
            "{sovet}"
        ),
        "vniz": (
            "<b>Kurs keskin tushdi</b>\n\n"
            "{data_vchera}: {vchera}\n"
            "{data}: <b>{segodnya}</b> — {percent}%\n\n"
            "50 000 rublda bu <b>{na_50k} so‘m</b> kam.\n\n"
            "{sovet}"
        ),
    },
    "ru": {
        "vverh": (
            "<b>Курс резко вырос</b>\n\n"
            "{data_vchera}: {vchera}\n"
            "{data}: <b>{segodnya}</b> — {percent}%\n\n"
            "На переводе 50 000 ₽ это <b>{na_50k} сум</b> больше.\n\n"
            "{sovet}"
        ),
        "vniz": (
            "<b>Курс резко упал</b>\n\n"
            "{data_vchera}: {vchera}\n"
            "{data}: <b>{segodnya}</b> — {percent}%\n\n"
            "На переводе 50 000 ₽ это <b>{na_50k} сум</b> меньше.\n\n"
            "{sovet}"
        ),
    },
}

# Совет говорит, что ДЕЛАТЬ, и учитывает направление курса. Раньше здесь
# было «ниже обычного — подожди», и в падающем рынке это советовало ждать,
# когда каждый следующий день хуже предыдущего.
DEYSTVIYA = {
    "uz": {
        "otpravlyat":   "Yubormoqchi bo‘lsangiz — bugun yaxshi kun.",
        "mozhno_zhdat": "Kurs past, lekin ko‘tarilmoqda — kutish ma’noli.",
        "ne_zhdat":     "Kurs tushmoqda — qancha kutsangiz, shuncha kam yetadi.",
        "obychno":      "Kurs odatdagidek.",
        # Ma'lumotlar eski bo'lsa — maslahat yo'q. Ko'p kunlik kurs
        # bo'yicha «bugun yaxshi kun» deyish odamga pulga tushadi.
        "stale":        "Ma’lumotlar eski — bugun uchun maslahat bermayman.",
    },
    "ru": {
        "otpravlyat":   "Если собирались отправлять — сегодня хороший день.",
        "mozhno_zhdat": "Курс ниже обычного и растёт — есть смысл подождать.",
        "ne_zhdat":     "Курс падает — чем дольше ждёте, тем меньше дойдёт.",
        "obychno":      "Курс обычный.",
        # По старым данным советов не даём: «сегодня хороший день» по
        # курсу недельной давности — это совет потерять деньги.
        "stale":        "Данные устарели — совет на сегодня не даю.",
    },
}


def opublikovat_v_kanale():
    """Ежедневный пост с курсом в канал.

    Зачем это важнее, чем кажется. Узкое место продукта — не деньги и не
    код, а люди. На канал подписываются охотно: курс смотрят каждый день,
    и ради этого не надо ничего устанавливать. Приложение открывают те,
    кому нужно посчитать; канал читают все.

    Пост полезен сам по себе, даже если человек никогда не откроет
    приложение. Это условие: канал, который существует ради ссылки,
    отписывают за неделю.

    Пишем один раз в сутки. Адрес канала — в переменной CHANNEL_ID
    (@imya_kanala или числовой id). Нет переменной — молчим.
    """
    return _opublikovat(vid_posta_na_segodnya())


def ssylka_na_kanal():
    """Публичный адрес канала — или пусто, если канала ещё нет.

    `CHANNEL_ID` бывает двух видов: `@imya_kanala` и числовой id. Ссылку
    можно построить только из первого; числовой id публичного адреса не
    даёт, и выдумывать его нельзя — получилась бы битая ссылка в
    приложении, что хуже, чем её отсутствие.
    """
    kanal = os.environ.get("CHANNEL_ID", "").strip()
    if not kanal.startswith("@") or len(kanal) < 3:
        return ""
    imya = kanal[1:]
    if not all(z.isalnum() or z == "_" for z in imya):
        return ""
    return "https://t.me/" + imya


def procent_znakom(z):
    """+1,23 или -1,23. Знак обязателен: «1,23%» не говорит, куда."""
    if z is None:
        return "—"
    return ("+" if z > 0 else "") + chislo(z)


def vid_posta_na_segodnya(teper=None):
    """Какой пост идёт сегодня. Отдельной функцией — чтобы проверялась.

    Первое число месяца перебивает пятницу: итог тридцати дней бывает раз
    в месяц, а итог недели — четыре раза, и терять редкий ради частого
    незачем.
    """
    teper = teper or (datetime.now(timezone.utc) + timedelta(hours=5))
    if teper.day == 1:
        return "mesyac"
    if teper.weekday() == 4:      # пятница: на выходных отправляют чаще
        return "nedelya"
    return "den"


def sobrat_post(vid, dannye):
    """Текст поста и метка ссылки. Чистая функция: ни сети, ни Telegram.

    Возвращает (текст, метка) или None, если данных на такой пост не
    хватает. Молчание здесь лучше поста с прочерками вместо чисел.
    """
    ocenka = (dannye or {}).get("sovet")
    if not ocenka:
        return None
    istoriya = (dannye or {}).get("history") or []
    # Совет в посте — по тем же правилам, что везде: на старых данных
    # его не даём. Пост выходит на новый курс, так что срабатывать это
    # почти не будет, — но «почти» в денежном продукте не считается.
    kluch_soveta = kakoy_sovet(ocenka)

    # Дата последнего курса. ЦБ молчит по выходным, и называть пятничный
    # курс сегодняшним — значит врать три дня в неделю.
    #
    # Берём из вердикта, а если его считала старая версия бота — из самой
    # истории. Нет ни там, ни там — пост не выходит вовсе: строка
    # «Курс рубля — None» в публичном канале хуже, чем день молчания,
    # и остаётся там навсегда.
    data_kursa = ocenka.get("data") or (
        max((z.get("date") or "") for z in istoriya) if istoriya else None)
    if not data_kursa:
        return None

    bloki = []

    if vid == "nedelya":
        itog = sovet.itog_perioda(istoriya, 7)
        if not itog:
            return None
        for lang in ("uz", "ru"):
            if itog["upushcheno_na_50k"] > 0:
                upushcheno = UPUSHCHENO[lang]["est"].format(
                    kurs=podpis_kursa(data_kursa, lang),
                    skolko=summa_slovom(itog["upushcheno_na_50k"]))
            else:
                upushcheno = UPUSHCHENO[lang]["net"].format(
                    den=podpis_dnya(data_kursa, lang))
            bloki.append(POST_NEDELI[lang].format(
                nachalo=chislo(itog["nachalo"]), konec=chislo(itog["konec"]),
                izmenenie=procent_znakom(itog["izmenenie_percent"]),
                mn=chislo(itog["min"]), mx=chislo(itog["max"]),
                min_data=data_slovom(itog["min_data"], lang),
                max_data=data_slovom(itog["max_data"], lang),
                razmah=summa_slovom(itog["razmah_na_50k"]),
                upushcheno=upushcheno,
                sovet=DEYSTVIYA[lang][kluch_soveta],
            ))
        return "\n\n· · ·\n\n".join(bloki), "kanal_nedelya"

    if vid == "mesyac":
        itog = sovet.itog_perioda(istoriya, 30)
        if not itog:
            return None
        # Размах в процентах от худшего дня: именно так его проверит
        # любой, кто решит нас поймать на цифре.
        razmah_percent = ((itog["max"] - itog["min"]) / itog["min"] * 100
                          if itog["min"] else 0)
        for lang in ("uz", "ru"):
            bloki.append(POST_MESYACA[lang].format(
                mn=chislo(itog["min"]), mx=chislo(itog["max"]),
                razmah_percent=chislo(razmah_percent),
                min_data=data_slovom(itog["min_data"], lang),
                max_data=data_slovom(itog["max_data"], lang),
                razmah=summa_slovom(itog["razmah_na_50k"]),
                sovet=DEYSTVIYA[lang][kluch_soveta],
            ))
        return "\n\n· · ·\n\n".join(bloki), "kanal_mesyac"

    if vid == "ryvok":
        dvizhenie = sovet.rezkoe_dvizhenie(istoriya)
        if not dvizhenie:
            return None
        for lang in ("uz", "ru"):
            bloki.append(POST_RYVOK[lang][dvizhenie["napravlenie"]].format(
                data_vchera=data_slovom(dvizhenie["data_vchera"], lang),
                data=data_slovom(dvizhenie["data"], lang),
                vchera=chislo(dvizhenie["vchera"]),
                segodnya=chislo(dvizhenie["segodnya"]),
                percent=procent_znakom(dvizhenie["percent"]),
                # В тексте уже сказано «больше» или «меньше», знак минуса
                # рядом с этим читался бы как ошибка.
                na_50k=summa_slovom(abs(dvizhenie["na_50k"])),
                sovet=DEYSTVIYA[lang][kluch_soveta],
            ))
        return "\n\n· · ·\n\n".join(bloki), "kanal_ryvok"

    # Обычный день.
    razmah = int(round((ocenka["max_30"] - ocenka["min_30"]) * 50000))
    for lang in ("uz", "ru"):
        bloki.append(POST_KANALA[lang].format(
            den=podpis_dnya(data_kursa, lang).lower(),
            kurs=chislo(ocenka["segodnya"]),
            srednee=chislo(ocenka["srednee_30"]),
            verdikt=VERDIKTY[lang][ocenka["verdikt"]],
            mn=chislo(ocenka["min_30"]), mx=chislo(ocenka["max_30"]),
            razmah=summa_slovom(razmah),
            sovet=DEYSTVIYA[lang][kluch_soveta],
        ))
    return "\n\n· · ·\n\n".join(bloki), "kanal_den"


def _opublikovat(vid):
    """Собрать пост нужного вида и отправить в канал."""
    kanal = os.environ.get("CHANNEL_ID", "").strip()
    if not kanal:
        return False

    # БЕЗ БАЗЫ В КАНАЛ НЕ ПИШЕМ. Это не перестраховка — это то, что уже
    # случилось.
    #
    # Отметка «этот пост уже публиковали» лежит в хранилище. Без
    # DATABASE_URL хранилище — файл на диске Render, а диск там
    # эфемерный: бесплатный тариф усыпляет сервис, монитор его будит,
    # и после каждого пробуждения файла нет. Бот честно считает, что
    # сегодня ещё не публиковал, и публикует снова.
    #
    # 16 августа это дало семнадцать одинаковых постов подряд с
    # интервалом в две-три минуты, в канале с четырьмя подписчиками.
    # Канал с семнадцатью копиями одного поста отписывают все и сразу,
    # а второго шанса у канала не бывает.
    #
    # Выбор здесь между «молчит» и «спамит», и молчание лучше.
    if not mozhno_pisat_naruzhu():
        print("[канал] НЕ ПУБЛИКУЮ: памяти, переживающей перезапуск, нет — "
              "ни базы, ни запасной у Telegram. Отметка о публикации не "
              "переживёт перезапуск, и один пост уйдёт в канал десятки "
              "раз. Задай DATABASE_URL на Render.", flush=True)
        return False

    dannye = svezhie_dannye() or {}
    sobrano = sobrat_post(vid, dannye)
    if not sobrano:
        print("[канал] данных на пост «%s» не хватает, молчу" % vid, flush=True)
        return False

    tekst, metka = sobrano
    otvet = vyzov("sendMessage", {
        "chat_id": kanal,
        "text": tekst,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_markup": {"inline_keyboard": [[
            {"text": "Hisoblash · Посчитать", "url": ssylka(metka)}
        ]]},
    })

    if otvet and otvet.get("ok"):
        verdikt = (dannye.get("sovet") or {}).get("verdikt")
        print("[канал] опубликовано «%s», вердикт %s" % (vid, verdikt), flush=True)
        hranilishche.sobytie(None, "post_v_kanal", {"vid": vid, "verdikt": verdikt})
        return True

    print("[канал] опубликовать не удалось", flush=True)
    return False


def svoi(chat_id):
    """Свой ли это человек — тот, кому доступны служебные команды.

    Список в переменной `SVOI`, через запятую; `ADMIN_CHAT_ID` входит
    всегда. Нет переменных — служебных команд нет ни у кого, включая
    случайного прохожего: команда просто молчит, как будто её не бывает.
    """
    razresheno = set()
    for imya in ("ADMIN_CHAT_ID", "SVOI"):
        for kusok in os.environ.get(imya, "").replace(" ", "").split(","):
            if kusok:
                razresheno.add(kusok)
    return str(chat_id) in razresheno


# Готовые тексты для посева. Живут в коде, а не в документе, ровно по той
# же причине, по которой BOT-TEXTS.md стал указателем: копия в документе
# расходится с настоящим за два дня.
#
# Числа подставляются сегодняшние. Это не удобство, а требование: правило
# проекта — не публиковать число без даты, а Видадий, копирующий пост из
# файла месячной давности, опубликует позапрошлый курс и будет пойман на
# этом первым же человеком, решившим нас проверить.
TEKSTY_POSEVA = {
    "otkrytie": {
        "uz": (
            "Hisoblab ko‘rdim va o‘zim ham hayron qoldim.\n\n"
            "Oxirgi 30 kunda rubl kursi {mx} dan {mn} gacha yurdi. "
            "Bu {razmah_percent}%.\n"
            "50 000 rublda — {razmah} so‘m.\n\n"
            "Komissiya-yu servis tanlash bunga nisbatan mayda gap.\n"
            "Eng ko‘p pulni yuborish KUNI hal qiladi, lekin buni hech kim "
            "aytmaydi.\n\n"
            "Bugungi kurs oyning o‘rtachasidan qanday farq qilishini shu "
            "yerda ko‘rsatyapti: {ssylka}"
        ),
        "ru": (
            "Посчитал и сам удивился.\n\n"
            "За последние 30 дней курс рубля прошёл от {mx} до {mn}. "
            "Это {razmah_percent}%.\n"
            "На переводе 50 000 ₽ — {razmah} сум.\n\n"
            "Комиссия и выбор сервиса рядом с этим — мелочь.\n"
            "Больше всего решает ДЕНЬ отправки, но об этом не говорит никто.\n\n"
            "Вот тут показывает, чем сегодняшний курс отличается от среднего "
            "за месяц: {ssylka}"
        ),
    },
    "otvet": {
        "uz": (
            "Ochig‘ini aytsam, servislar orasidagi farq deyarli yo‘q — "
            "tekshirdim, kurs bir xil.\n\n"
            "Haqiqiy farq boshqa joyda: qaysi KUNI yuborasiz.\n"
            "Oy ichida kurs {razmah_percent}% ga o‘zgardi. Servis tanlash "
            "bunchalik bermaydi.\n\n"
            "Men bugungi kurs odatdagidan yaxshimi yoki yomonmi — shu yerdan "
            "qarayman: {ssylka}"
        ),
        "ru": (
            "Если честно — разницы между сервисами почти нет, "
            "проверял, курс у них одинаковый.\n\n"
            "Настоящая разница в другом: в какой ДЕНЬ отправляешь.\n"
            "За месяц курс менялся на {razmah_percent}%. Выбор сервиса "
            "столько не даёт.\n\n"
            "Я смотрю здесь, лучше сегодня курс обычного или хуже: {ssylka}"
        ),
    },
    "nacenka": {
        "uz": (
            "Yana bir narsa, buni hech kim ko‘rsatmaydi.\n\n"
            "Markaziy bank kursi {data} holatiga {kurs}. Pul o‘tkazma esa "
            "{kurs_servisa} bo‘yicha o‘tadi.\n"
            "Farqi {nacenka_percent}% — 50 000 rublda {nacenka} so‘m.\n\n"
            "Bu komissiya emas. Bu kurs. Va u hech qayerda yozilmagan.\n\n"
            "{ssylka}"
        ),
        "ru": (
            "И ещё одно, чего не показывает никто.\n\n"
            "Официальный курс ЦБ на {data} — {kurs}. А перевод идёт по "
            "{kurs_servisa}.\n"
            "Разница {nacenka_percent}% — это {nacenka} сум на 50 000 ₽.\n\n"
            "Это не комиссия. Это курс. И его нигде не пишут.\n\n"
            "{ssylka}"
        ),
    },
}


def vydat_teksty_dlya_poseva(chat_id, metka=""):
    """Готовые посты для чатов, с сегодняшними числами и меткой чата.

    Зачем команда, а не файл. Тексты в документе устаревают молча: числа
    в них остаются от того дня, когда документ писали. Человек копирует
    пост, публикует — и первый же читатель сверяет с cbu.uz и ловит нас
    на неправде. Здесь числа всегда сегодняшние, а у каждого чата своя
    метка, без которой посев превращается в гадание.
    """
    if not svoi(chat_id):
        return                       # чужому команды просто не существует

    ocenka = (svezhie_dannye() or {}).get("sovet")
    d = svezhie_dannye() or {}
    if not ocenka:
        poslat(chat_id, "Данных нет — тексты с выдуманными числами "
                        "не выдаю.", html=False)
        return

    chistaya = "".join(z for z in metka.lower()
                       if (z.isalnum() and z.isascii()) or z in "_-")[:24]
    ssylka_posta = ("https://t.me/QanchaYetadi_bot?start=chat_" + chistaya
                    if chistaya else "https://t.me/QanchaYetadi_bot?start=chat")

    razmah_percent = ((ocenka["max_30"] - ocenka["min_30"])
                      / ocenka["min_30"] * 100)
    razmah = (ocenka["max_30"] - ocenka["min_30"]) * 50000

    servisy = [s for s in (d.get("services") or []) if s.get("rate_rub_uzs")]
    luchshiy = max(servisy, key=lambda s: s["rate_rub_uzs"]) if servisy else None
    kurs_cb = (d.get("cbu") or {}).get("rub_uzs") or ocenka["segodnya"]

    obshchee = {
        "mn": chislo(ocenka["min_30"]), "mx": chislo(ocenka["max_30"]),
        "razmah_percent": chislo(razmah_percent),
        "razmah": summa_slovom(razmah),
        "kurs": chislo(kurs_cb),
        "ssylka": ssylka_posta,
    }

    zagolovki = {
        "otkrytie": "ПОСТ 1 — открытие",
        "otvet": "ПОСТ 2 — ответ на «через что дешевле»",
        "nacenka": "ПОСТ 3 — про скрытую наценку, через неделю после первого",
    }

    for vid in ("otkrytie", "otvet", "nacenka"):
        if vid == "nacenka":
            if not luchshiy:
                continue
            polya = dict(obshchee,
                         data=data_slovom(ocenka.get("data"), "ru"),
                         kurs_servisa=chislo(luchshiy["rate_rub_uzs"]),
                         nacenka_percent=chislo(
                             (kurs_cb - luchshiy["rate_rub_uzs"]) / kurs_cb * 100),
                         nacenka=summa_slovom(
                             (kurs_cb - luchshiy["rate_rub_uzs"]) * 50000))
            polya_uz = dict(polya, data=data_slovom(ocenka.get("data"), "uz"))
        else:
            polya = polya_uz = obshchee

        # Каждый пост отдельным сообщением: их копируют по одному, и
        # склеенные в кучу пришлось бы разбирать руками.
        poslat(chat_id, "<b>%s · UZ</b>\n\n<code>%s</code>" % (
            zagolovki[vid], TEKSTY_POSEVA[vid]["uz"].format(**polya_uz)))
        poslat(chat_id, "<b>%s · RU</b>\n\n<code>%s</code>" % (
            zagolovki[vid], TEKSTY_POSEVA[vid]["ru"].format(**polya)))

    poslat(chat_id,
           "Числа на %s. Метка чата: <code>%s</code> — по ней будет видно, "
           "сколько людей пришло именно оттуда.\n\n"
           "Метку задавать так: <code>/tekst moskva1</code>"
           % (data_slovom(ocenka.get("data"), "ru"), chistaya or "нет"))
    hranilishche.sobytie(chat_id, "teksty_vydany", {"metka": chistaya})


def opublikovat_ryvok():
    """Внеочередной пост, когда курс дёрнулся за сутки сильнее обычного.

    Выходит редко и потому читается. Здесь важнее не срабатывать, а
    молчать: канал, который каждый день объявляет событие, перестают
    открывать быстрее, чем канал, в котором ничего не происходит.
    """
    return _opublikovat("ryvok")


def svezhest_stranicy_poiska():
    """Сколько дней числам на странице под поиск. None — не удалось узнать.

    Зачем бот вообще смотрит на чужую страницу. Числа на ней переписывает
    `obnovit_zapas.py`, которого надо не забыть запустить и залить. Того,
    что надо помнить, не делают — и через полгода страница, которую никто
    не открывает, будет показывать позапрошлый курс, выглядя исправной.
    Так что помнит бот, а не человек.
    """
    try:
        zapros = urllib.request.Request(
            "https://m1llerzz.github.io/KURS-/kurs.html",
            headers={"User-Agent": "qy-svodka/1"})
        with urllib.request.urlopen(zapros, timeout=30) as o:
            stranica = o.read().decode("utf-8", "replace")
    except Exception:
        return None

    najdeno = re.search(r'data-zapas="data_ru">([^<]+)<', stranica)
    if not najdeno:
        return None

    # «16 августа 2026» -> дата. Месяц ищем по нашему же списку.
    kuski = najdeno.group(1).strip().split()
    if len(kuski) != 3:
        return None
    try:
        den, mesyac, god = int(kuski[0]), kuski[1], int(kuski[2])
        nomer = MESYACY["ru"].index(mesyac) + 1
        byla = datetime(god, nomer, den, tzinfo=timezone.utc)
    except (ValueError, IndexError):
        return None

    return (datetime.now(timezone.utc) - byla).days


def vozrast_oblozhki_dney():
    """Сколько дней числу на картинке карточки. None — не удалось узнать.

    Обложка — первое, что видит человек, которому переслали ссылку: на
    ней крупное число, ради которого пост и пересылают. Устарев, она не
    ломается и не подаёт признаков — просто показывает прошлый месяц.

    Дату берём из адреса: `oblozhka.png?v=20260814`. Версия ставится
    сборщиком по дате курса, так что расхождение видно точно, а не по
    возрасту файла.
    """
    try:
        zapros = urllib.request.Request(
            "https://m1llerzz.github.io/KURS-/",
            headers={"User-Agent": "qy-svodka/1"})
        with urllib.request.urlopen(zapros, timeout=30) as o:
            stranica = o.read().decode("utf-8", "replace")
    except Exception:
        return None

    najdeno = re.search(r"oblozhka\.png\?v=(\d{8})", stranica)
    if not najdeno:
        return None

    syroe = najdeno.group(1)
    try:
        byla = datetime(int(syroe[:4]), int(syroe[4:6]), int(syroe[6:8]),
                        tzinfo=timezone.utc)
    except ValueError:
        return None

    return (datetime.now(timezone.utc) - byla).days


def svodka_dlya_svoih():
    """Еженедельная сводка тому, кто ведёт проект.

    Зачем. Метрики лежат по адресу /api/stats, и открывать его надо
    помнить. Того, что надо помнить, не делают. Раз в неделю цифры
    приходят сами — и тогда видно, живой продукт или нет, без усилия.

    Адрес берётся из ADMIN_CHAT_ID. Нет переменной — молчим и не мешаем.
    """
    admin = os.environ.get("ADMIN_CHAT_ID", "").strip()
    if not admin:
        return

    vsego, podpisano = hranilishche.skolko_vsego()
    sobytiya = hranilishche.svodka_sobytiy(7)
    ocenka = (svezhie_dannye() or {}).get("sovet") or {}

    # Собирается по ходу, печатается в конце: тревожное должно стоять
    # последним, иначе его прочитают первым и не дочитают цифры.
    predupredit = []

    stroki = ["<b>Qancha yetadi — неделя</b>", ""]
    stroki.append("Людей всего: %d" % vsego)
    stroki.append("С оповещениями: %d" % podpisano)

    if sobytiya:
        stroki.append("")
        stroki.append("<b>За 7 дней</b>")
        for s in sobytiya:
            stroki.append("%s: %d" % (s["tip"], s["skolko"]))

        # Откуда пришли и что там делали. Это главная часть всей сводки:
        # денег на рекламу нет, значит вопрос не «сколько людей», а «что
        # из сделанного их привело».
        #
        # Три числа, а не одно: чат с двумя сотнями заходов и нулём
        # расчётов хуже, чем чат с двадцатью заходами и пятнадцатью
        # расчётами. По одним переходам их не различить.
        voronka = hranilishche.voronka_istochnikov(7)
        if voronka is None:
            # Запрос не выполнился — это не «людей не было». Молчать здесь
            # значит показать пустую разбивку и заставить думать, что
            # посев не сработал, когда сломались мы.
            predupredit.append("РАЗБИВКА «ОТКУДА ПРИШЛИ» НЕ СОБРАЛАСЬ — "
                               "ошибка запроса, смотри журнал Render")
        elif voronka:
            stroki.append("")
            stroki.append("<b>Откуда пришли</b>")
            stroki.append("<i>источник: зашли / посчитали / переслали</i>")
            for i in voronka:
                stroki.append("%s: %d / %d / %d" % (
                    i["otkuda"], i["prishli"], i["poschitali"], i["pereslali"]))
    else:
        stroki.append("")
        stroki.append("Событий за неделю нет.")
        if not hranilishche.na_postgres():
            # Без базы события никуда не пишутся — и «нет событий» значит
            # не «никто не приходил», а «мы не считаем». Разница
            # принципиальная, и молчать о ней нельзя.
            stroki.append("ВНИМАНИЕ: нет DATABASE_URL, события не сохраняются.")

    if ocenka:
        stroki.append("")
        stroki.append("Курс сегодня: %s (среднее %s), вердикт %s, совет %s"
                      % (chislo(ocenka.get("segodnya")),
                         chislo(ocenka.get("srednee_30")),
                         ocenka.get("verdikt"), ocenka.get("deystvie")))

    # Здоровье сбора. Разбор страницы bank.uz держится на её вёрстке, и в
    # день, когда вёрстку поменяют, курсы сервисов перестанут собираться
    # молча. Приложение спрячет их само через 72 часа по правилу свежести,
    # но узнать об этом надо раньше, чем через три дня.
    d = svezhie_dannye() or {}
    servisov = len(d.get("services") or [])
    if not servisov:
        predupredit.append("НЕ СОБИРАЮТСЯ КУРСЫ СЕРВИСОВ — проверь разбор bank.uz")
    elif servisov < 2:
        # Дыра, которую видно только так. Полный отказ разбора заметен
        # сразу: сервисов ноль. А вот когда из двух нашёлся один, продукт
        # продолжает работать как ни в чём не бывало — только сравнивать
        # ему больше не с чем, а он про сравнение. Молчать об этом
        # нельзя: половина данных исчезает, ничего не ломая.
        predupredit.append(
            "НАЙДЕН ТОЛЬКО ОДИН СЕРВИС из двух — вероятно, изменилась "
            "вёрстка bank.uz. Сравнивать не с чем, проверь разбор")
    if not d.get("cbu"):
        predupredit.append("НЕ ОТВЕЧАЕТ ЦБ Узбекистана")

    sobrano = d.get("generated_at")
    if sobrano:
        try:
            vozrast = (datetime.now(timezone.utc)
                       - datetime.fromisoformat(sobrano)).total_seconds() / 3600
            if vozrast > 26:
                predupredit.append("ДАННЫЕ НЕ ОБНОВЛЯЛИСЬ %d ч" % vozrast)
        except Exception:
            pass

    # Страница под поиск и обложка живут отдельно от бота и не обновляются
    # сами. Напоминаем не «раз в месяц», а по факту устаревания.
    vozrast_stranicy = svezhest_stranicy_poiska()
    if vozrast_stranicy is None:
        predupredit.append("НЕ ОТКРЫВАЕТСЯ СТРАНИЦА ПОИСКА kurs.html")
    elif vozrast_stranicy > 30:
        predupredit.append(
            "ЧИСЛАМ НА СТРАНИЦЕ ПОИСКА %d дней. Пересобери и залей:\n"
            "  cd app/bot\n"
            "  py obnovit_zapas.py\n"
            "  py sobrat_oblozhku.py\n"
            "  cd .. && py proverit.py" % vozrast_stranicy)

    # Обложка стареет отдельно от страницы, а видят её чаще: это первое,
    # что показывается человеку, которому переслали ссылку.
    vozrast_kartinki = vozrast_oblozhki_dney()
    if vozrast_kartinki is not None and vozrast_kartinki > 30 \
            and (vozrast_stranicy is None or vozrast_stranicy <= 30):
        predupredit.append(
            "ЧИСЛУ НА КАРТИНКЕ КАРТОЧКИ %d дней — её видят все, кому "
            "переслали ссылку. Пересобери:\n"
            "  cd app/bot && py sobrat_oblozhku.py" % vozrast_kartinki)

    if predupredit:
        stroki.append("")
        stroki += predupredit

    poslat(admin, "\n".join(stroki))
    print("[сводка] отправлена", flush=True)


def data_kursa_seychas():
    """Дата последнего курса ЦБ, а не сегодняшнее число. Или None."""
    dannye = svezhie_dannye() or {}
    ocenka = dannye.get("sovet") or {}
    if ocenka.get("data"):
        return str(ocenka["data"])[:10]
    istoriya = dannye.get("history") or []
    if istoriya:
        return max((str(z.get("date") or "")[:10] for z in istoriya)) or None
    return None


def odnazhdy(kluch, metka, deystvie):
    """Выполняет `deystvie` один раз на каждое новое значение `metka`.

    Отметка живёт в хранилище, а не в памяти процесса, и в этом весь
    смысл. На бесплатном тарифе Render перезапускает сервис сам, и
    переменная внутри цикла обнулялась вместе с ним: после каждого
    пробуждения бот считал, что сегодня ещё не публиковал, — и публиковал
    заново. Читатель видел бы один и тот же пост столько раз, сколько
    Render решит нас разбудить, а канал отписывают за меньшее.

    Записываем ПОСЛЕ действия: не сделали — не запомнили, попробуем через
    час. Если запомнить не удалось, говорим об этом вслух — молча
    оставлять возможность повтора нельзя.

    **Без базы не делаем ничего.** Смысл этой функции — обещание «ровно
    один раз»; без хранилища, переживающего перезапуск, выполнить его
    невозможно. Тогда честнее не выполнять действие, чем выполнять его
    неизвестное число раз: 16 августа так вышло семнадцать копий одного
    поста подряд.

    Правило общее для всего, что продукт делает сам и наружу: нет
    памяти — нет действия. Не «действие с оговорками», а нет действия.
    """
    if not mozhno_pisat_naruzhu():
        print("[планировщик] «%s» пропущено: памяти, переживающей "
              "перезапуск, нет — а без неё «ровно один раз» не "
              "гарантировать: при каждом перезапуске оно повторилось бы "
              "заново." % kluch, flush=True)
        return False

    metka = str(metka)
    otmetka = hranilishche.sostoyanie(kluch)

    # Прочитать не удалось — не действуем. «Не знаю» это не «не делали»:
    # после сбоя чтения пост ушёл бы вторым разом, а через час мы просто
    # попробуем снова. Молчание стоит одного пропущенного дня, повтор —
    # подписчиков.
    if otmetka is hranilishche.NEIZVESTNO:
        print("[планировщик] «%s» пропущено: отметку не удалось прочитать, "
              "а без неё повтор возможен. Попробую через час." % kluch,
              flush=True)
        return False

    if otmetka == metka:
        return False

    if not deystvie():
        return False

    if not hranilishche.zapisat_sostoyanie(kluch, metka):
        print("[планировщик] ВНИМАНИЕ: «%s» сделано, но не запомнилось — "
              "возможен повтор" % kluch, flush=True)
    return True


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

            # Сводка по понедельникам, одна за неделю. Ключ — номер недели,
            # а не дата: иначе при перезапуске в тот же понедельник она
            # ушла бы второй раз.
            if teper.weekday() == 0 and teper.hour >= 10:
                odnazhdy("svodka", "%d-%02d" % teper.isocalendar()[:2],
                         svodka_dlya_svoih)

            # Пост в канал — утром, и только когда есть о чём сказать.
            #
            # Ключ — ДАТА КУРСА, а не сегодняшнее число. ЦБ не публикует по
            # выходным, и по календарю в субботу и воскресенье выходили бы
            # ещё два поста с теми же числами и той же пятничной датой:
            # три одинаковых сообщения подряд. Правило проекта прямое —
            # молчание лучше повтора, и канал, в котором нечего сказать,
            # честнее канала, который повторяется.
            #
            # Итоги недели и месяца привязаны к своим срокам, а не к
            # курсу: они выходят раз в неделю и раз в месяц независимо от
            # того, обновился ли курс в этот день.
            vid = vid_posta_na_segodnya(teper)
            data_kursa = data_kursa_seychas()
            tolko_chto_pisali = False
            if teper.hour >= 9:
                if vid == "nedelya":
                    metka = "%d-%02d" % teper.isocalendar()[:2]
                elif vid == "mesyac":
                    metka = teper.strftime("%Y-%m")
                else:
                    metka = data_kursa

                # Про один курс — один пост дня, каким бы видом он ни был
                # рассказан. Иначе выходило так: в пятницу итог недели с
                # пятничным курсом, а в субботу ещё и пост дня с ним же —
                # те же числа и та же дата, только сутки спустя. Читатель
                # видит не два поста, а один отставший.
                #
                # Не удалось прочитать — считаем, что говорили. Ошибиться
                # тут можно в две стороны, и они неравны: пропущенный
                # пост стоит одного дня, лишний — подписчиков.
                osveshchen = hranilishche.sostoyanie("kurs_osveshchen")
                uzhe_govorili = (vid == "den" and data_kursa
                                 and (osveshchen is hranilishche.NEIZVESTNO
                                      or osveshchen == data_kursa))

                if metka and not uzhe_govorili:
                    tolko_chto_pisali = odnazhdy(
                        "post_" + vid, metka, lambda: _opublikovat(vid))
                    if tolko_chto_pisali and data_kursa:
                        hranilishche.zapisat_sostoyanie("kurs_osveshchen",
                                                        data_kursa)

            # Внеочередной пост про резкое движение курса — после обеда и
            # никогда в том же проходе, что утренний. Два сообщения подряд
            # читаются как спам даже в канале, а разнесённые по времени —
            # как две разные новости. Проход бывает и в два часа дня: бот
            # перезапускается когда угодно, и тогда оба поста собрались бы
            # в одну минуту.
            #
            # Ключ снова дата курса: рывок описывает движение к ней, и по
            # календарю он повторился бы все выходные.
            if teper.hour >= 13 and not tolko_chto_pisali and data_kursa:
                odnazhdy("post_ryvok", data_kursa, opublikovat_ryvok)
            if 10 <= teper.hour <= 20 and den != posledniy_den:
                # Сначала личные цели, потом общая рассылка. Порядок важен:
                # человек, дождавшийся своего курса, не должен получить
                # сперва общее «сегодня хороший день» — это обесценивает
                # то, ради чего он и ставил отметку.
                proverit_celi()
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
            d = dict(svezhie_dannye() or {"ok": False})
            # Адрес канала едет вместе с данными, а не лежит в data.js.
            # Иначе после создания канала пришлось бы править код, поднимать
            # версию скриптов и заливать заново — три шага, из которых
            # забудут хотя бы один. Задал переменную на Render — ссылка
            # появилась в приложении сама.
            kanal = ssylka_na_kanal()
            if kanal:
                d["channel"] = kanal
            telo = json.dumps(d, ensure_ascii=False).encode("utf-8")
            self.wfile.write(self._otvetit(telo, "application/json; charset=utf-8"))
            return

        if put == "/api/stats":
            vsego, podpisano = hranilishche.skolko_vsego()

            # Общие числа открыты: по ним видно, что учёт жив, и ничего
            # чужого они не выдают.
            otvet = {
                "podpischikov": vsego,
                "s_uvedomleniyami": podpisano,
                "kursy_obnovleny": _dannye["obnovleno"],
                # Есть ли база — не секрет, а самый нужный признак
                # состояния: без неё продукт молчит в канал и не шлёт
                # оповещений. Узнать это иначе можно было только из
                # журнала Render или имея ключ к подробностям.
                "baza": hranilishche.na_postgres(),
                # Может ли канал публиковать. Отдельно от базы: пока её
                # нет, отметки о постах живут у Telegram, и по одному
                # признаку «база» состояние канала уже не прочитать.
                "kanal_pishet": hranilishche.pamyat_perezhivet_perezapusk(),
            }

            # А вот разбивка «откуда пришли» — это карта нашего посева.
            # Адрес открыт всему интернету без пароля, и по нему любой —
            # включая тех, у кого есть бюджет на рекламу, — прочтёт, какие
            # чаты нам дают людей, а какие нет. Мы этот список собираем
            # неделями и руками, и отдавать его даром незачем.
            #
            # Ключ в переменной STATS_KEY, спрашивается как ?key=…
            # Не задан — подробностей не отдаём никому, включая нас самих:
            # цифры и так приходят еженедельной сводкой в Telegram.
            kluch = os.environ.get("STATS_KEY", "").strip()
            sprosheno = ""
            if "?" in self.path:
                for kusok in self.path.split("?", 1)[1].split("&"):
                    if kusok.startswith("key="):
                        sprosheno = urllib.parse.unquote(kusok[4:])

            # Сравниваем длинным способом: обычное сравнение строк
            # заканчивается на первом несовпавшем символе, и по времени
            # ответа ключ подбирается посимвольно.
            if kluch and hmac.compare_digest(kluch, sprosheno):
                otvet["sobytiya_7d"] = hranilishche.svodka_sobytiy(7)
                # Неделя показывает, что работает сейчас; месяц — что это
                # не разовая случайность.
                otvet["istochniki_7d"] = hranilishche.svodka_istochnikov(7)
                otvet["istochniki_30d"] = hranilishche.svodka_istochnikov(30)
                # Воронка: пришли — посчитали — переслали. Отвечает не на
                # «сколько людей», а на «какой источник даёт тех, кому
                # правда надо», — а это разные вопросы.
                otvet["voronka_7d"] = hranilishche.voronka_istochnikov(7)
                otvet["voronka_30d"] = hranilishche.voronka_istochnikov(30)
            else:
                otvet["podrobnosti"] = "закрыто: нужен ?key="

            telo = json.dumps(otvet, ensure_ascii=False).encode("utf-8")
            self.wfile.write(self._otvetit(telo, "application/json; charset=utf-8"))
            return

        self.wfile.write(self._otvetit("QanchaYetadi bot: живой".encode("utf-8")))

    def do_POST(self):
        """Учёт событий из приложения.

        Зачем это нужно раньше денег. Партнёрскую программу не дают под
        обещание — просят показать поток. Пока мы не считаем, сколько людей
        доходит до выбора способа, разговаривать с Remitly или Wise не о чем.
        Значит считать надо с первого дня, а не с того, когда понадобится.

        Учёт свой и бесплатный: ни одного внешнего сервиса, ни одной копейки,
        ни одного стороннего скрипта в приложении. См. METRICS.md.

        Личных данных не собираем. Никаких: ни имени, ни телефона, ни номера
        карты. Только «кто-то посчитал 50 000» — этого достаточно, чтобы
        понимать продукт, и мало, чтобы навредить человеку.
        """
        if self.path.split("?")[0].rstrip("/") != "/api/event":
            self.wfile.write(self._otvetit("нет такого адреса".encode("utf-8"), kod=404))
            return

        try:
            dlina = int(self.headers.get("Content-Length") or 0)
            # Ограничение на размер обязательно: без него один запрос
            # с гигабайтом тела кладёт бесплатный тариф целиком.
            if dlina > 4096:
                raise ValueError("слишком большое тело")
            telo = json.loads(self.rfile.read(dlina).decode("utf-8")) if dlina else {}

            tip = str(telo.get("tip") or "")[:40]
            if tip:
                syroy_id = str(telo.get("chat_id") or "")
                chat_id = int(syroy_id) if syroy_id.lstrip("-").isdigit() else None
                hranilishche.sobytie(chat_id, tip, _chistye_dannye(telo.get("dannye")))

                # Человек только что посчитал — значит уже получил то, зачем
                # приходил. Вот теперь можно спросить про оповещения: он
                # увидит вопрос, когда закроет приложение.
                #
                # Отдельным потоком: отправка в Telegram занимает до секунды,
                # а приложение ждать нашу вежливость не должно.
                if tip == "raschet" and chat_id:
                    threading.Thread(
                        target=mozhet_predlozhit_podpisku,
                        args=(chat_id,), daemon=True).start()
        except Exception as oshibka:
            print("[событие] не разобрано:", repr(oshibka)[:120], flush=True)

        # Отвечаем «принято» в любом случае. Приложение не должно ни падать,
        # ни ждать из-за нашей аналитики: она нужна нам, а не человеку.
        self.wfile.write(self._otvetit(b"{}", "application/json", kod=200))

    def do_HEAD(self):
        # UptimeRobot проверяет живость методом HEAD. Без обработчика
        # BaseHTTPRequestHandler отвечает 501, монитор считает сервис
        # упавшим и шлёт письма о недоступности — при живом сервисе.
        self._otvetit(b"")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, *args):
        pass                      # пинги раз в пять минут засоряют журнал


def podnyat_stranicu():
    """Поднимает /api/rates, /api/event и страницу живости.

    Сервер потоковый, и это не запас на будущее. Обычный HTTPServer
    обрабатывает запросы по одному: пока один человек ждёт ответа, все
    остальные стоят в очереди. А ответ бывает долгим — если кеш курсов
    устарел, обработчик собирает данные сам, а это несколько запросов к
    чужим серверам.

    В такую минуту вставало бы всё сразу: приложение у второго человека,
    учёт событий и пинг UptimeRobot. Последнее особенно неприятно —
    монитор решил бы, что сервис упал, и начал слать письма о поломке
    при живом сервисе.

    Общие данные защищены замком, а psycopg2 открывает соединение на
    каждый запрос, так что потоки друг другу не мешают.
    """
    port = int(os.environ.get("PORT", "10000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Stranica)
    server.daemon_threads = True     # не держим выход из процесса
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print("страница живости и /api/rates на порту", port, flush=True)


# ── Запуск ───────────────────────────────────────────────────────────

# Что перестаёт работать без каждой переменной. Формулировки нарочно про
# последствие, а не про имя: «нет CHANNEL_ID» ни о чём не говорит через
# месяц, а «постов в канале не будет» говорит всё.
NASTROYKI = [
    ("DATABASE_URL", "подписчики сотрутся при первом же перезапуске, события "
                     "не пишутся, ОПОВЕЩЕНИЯ НЕ РАССЫЛАЮТСЯ. Канал держится "
                     "на запасной памяти у Telegram — она рассчитана на "
                     "несколько отметок и базу не заменяет"),
    ("CHANNEL_ID", "постов в канале не будет, ссылка на канал не появится"),
    ("ADMIN_CHAT_ID", "еженедельная сводка не придёт"),
    ("SVOI", "команда /tekst недоступна даже своим"),
    ("STATS_KEY", "разбивка «откуда пришли» на /api/stats закрыта — "
                  "цифры смотреть только в еженедельной сводке"),
]


def soobshchit_o_nastroykah():
    """Список того, что не задано, и что из-за этого не работает.

    Пишется в журнал при каждом запуске. Это единственное место, куда
    Семён точно заглянет: логи Render открываются сами после заливки.

    Иначе получался замкнутый круг. О незаданных переменных сообщала
    еженедельная сводка — но она сама уходит на ADMIN_CHAT_ID, и пока он
    не задан, молчит и о себе, и обо всём остальном.
    """
    net = [(imya, chto) for imya, chto in NASTROYKI
           if not os.environ.get(imya, "").strip()]

    if not net:
        print("[настройки] всё задано: " +
              ", ".join(imya for imya, _ in NASTROYKI), flush=True)
        return

    print("", flush=True)
    print("[настройки] НЕ ЗАДАНО %d из %d — вот что из-за этого не работает:"
          % (len(net), len(NASTROYKI)), flush=True)
    for imya, chto in net:
        print("[настройки]   %-14s %s" % (imya, chto), flush=True)
    print("[настройки] Render -> сервис -> Environment. "
          "Подробно: DEYSTVIYA-SEMYONA.md", flush=True)
    print("", flush=True)


def main():
    soobshchit_o_nastroykah()
    hranilishche.podnyat()

    # Базы нет — пробуем запасную память у Telegram, чтобы канал не молчал.
    # Строго до запуска потоков: планировщик проверяет расписание сразу,
    # и решение «можно ли писать наружу» должно быть принято раньше.
    #
    # База есть — забираем из запасной памяти то, что там успело
    # накопиться. Иначе в день, когда DATABASE_URL наконец задан, пустая
    # база решила бы, что сегодняшний курс ещё не освещали.
    _kanal_pri_zapuske = os.environ.get("CHANNEL_ID", "").strip()
    if hranilishche.na_postgres():
        hranilishche.perenesti_otmetki(vyzov, _kanal_pri_zapuske)
    else:
        hranilishche.pamyat_na_telegrame(vyzov, _kanal_pri_zapuske)

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
        {"command": "cel", "description": "Ждать свой курс · Kursni kutish"},
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
