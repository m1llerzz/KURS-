# -*- coding: utf-8 -*-
"""Бот @QanchaYetadi_bot — выбор языка и приветствие с кнопкой запуска.

Как устроен разговор:
    /start          -> предложение выбрать язык, надпись на обоих сразу
    нажатие кнопки  -> цепляющий текст на выбранном языке + кнопка приложения

Почему сначала язык, а не сразу текст. Язык Telegram у мигранта часто
русский, хотя читать он хочет на узбекском — угадывать тут нельзя,
а спросить стоит одного нажатия.

Узбекский текст приветствия написан носителем-редактором (Gemini) по
русской смысловой основе, а не переведён дословно: дословный перевод
в таком тексте всегда звучит чужим.

ТОКЕН В КОДЕ НЕ ХРАНИТСЯ. Перед запуском:
    $env:BOT_TOKEN = "токен от BotFather"
    py bot.py

Ни одной зависимости: только стандартная библиотека.
"""
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

TOKEN = os.environ.get("BOT_TOKEN", "").strip()
if not TOKEN:
    print("Нет BOT_TOKEN. Задай переменную окружения и запусти снова.")
    sys.exit(1)

API = "https://api.telegram.org/bot" + TOKEN
PRILOZHENIE = "https://m1llerzz.github.io/KURS-/"

VYBOR_YAZYKA = "Tilni tanlang\nВыберите язык"

TEKSTY = {
    "uz": {
        "vybran": "Til: O‘zbekcha",
        "privet": (
            "<b>Siz rubl yuborasiz. Kartaga qancha tushishini esa servis emas, "
            "bank hal qiladi.</b>\n\n"
            "Pul bu yerdan rublda chiqadi. So‘mga esa uni O‘zbekistondagi bank "
            "o‘z kursi bo‘yicha, pul tushgan paytda aylantiradi.\n\n"
            "Banklar orasidagi farq 3–5%. Bu har bir o‘tkazmada siz ko‘rmaydigan "
            "minglab so‘m degani: hech qaysi servis kartaga aynan qancha tushishini "
            "ochiq ko‘rsatmaydi.\n\n"
            "Men ko‘rsataman. Summani kiriting — har bir usul bo‘yicha yakuniy "
            "hisobni va eng yaxshi hamda eng yomon o‘rtasidagi farqni bilib olasiz.\n\n"
            "O‘n soniya. Bepul. Pul o‘tkazmaymiz va qabul qilmaymiz — faqat hisoblab beramiz."
        ),
        "knopka": "Hisoblash",
    },
    "ru": {
        "vybran": "Язык: русский",
        "privet": (
            "<b>Вы отправляете рубли. А сколько дойдёт до карты — решает не сервис, "
            "а банк.</b>\n\n"
            "Деньги уходят в рублях. В сумы их превращает банк получателя — "
            "по своему курсу, в день зачисления.\n\n"
            "Разброс между банками 3–5%. На вашем переводе это тысячи сумов, которых "
            "вы не видите: ни один сервис не показывает, сколько именно ляжет на карту.\n\n"
            "Я показываю. Введите сумму — увидите итог по каждому способу и разницу "
            "между лучшим и худшим.\n\n"
            "Десять секунд. Бесплатно. Деньги не переводим и не принимаем — только считаем."
        ),
        "knopka": "Посчитать",
    },
}


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
        print("ошибка", metod, oshibka.code, oshibka.read()[:200], flush=True)
    except Exception as oshibka:                      # сеть моргнула
        print("сеть", metod, oshibka, flush=True)
    return None


def sprosit_yazyk(chat_id):
    vyzov("sendMessage", {
        "chat_id": chat_id,
        "text": VYBOR_YAZYKA,
        "reply_markup": {"inline_keyboard": [[
            {"text": "O‘zbekcha", "callback_data": "lang:uz"},
            {"text": "Русский", "callback_data": "lang:ru"},
        ]]},
    })


def privetstvie(chat_id, lang):
    t = TEKSTY[lang]
    vyzov("sendMessage", {
        "chat_id": chat_id,
        "text": t["privet"],
        "parse_mode": "HTML",
        "reply_markup": {"inline_keyboard": [[
            {"text": t["knopka"], "web_app": {"url": PRILOZHENIE}}
        ]]},
    })


def obrabotat_soobshchenie(soobshchenie):
    chat = soobshchenie.get("chat") or {}
    if not chat:
        return
    # На любое сообщение спрашиваем язык: у бота одна задача — довести
    # человека до кнопки, разбирать команды нам пока нечего.
    sprosit_yazyk(chat["id"])
    print("спросил язык", chat.get("id"), flush=True)


def obrabotat_nazhatie(nazhatie):
    dannye = nazhatie.get("data") or ""
    soobshchenie = nazhatie.get("message") or {}
    chat = soobshchenie.get("chat") or {}
    if not dannye.startswith("lang:") or not chat:
        return

    lang = dannye.split(":", 1)[1]
    if lang not in TEKSTY:
        lang = "uz"

    # Гасим «часики» на кнопке — без этого Telegram крутит их до таймаута.
    vyzov("answerCallbackQuery", {"callback_query_id": nazhatie["id"]})

    # Кнопки выбора убираем, чтобы человек не тыкал их повторно.
    vyzov("editMessageText", {
        "chat_id": chat["id"],
        "message_id": soobshchenie["message_id"],
        "text": TEKSTY[lang]["vybran"],
    })

    privetstvie(chat["id"], lang)
    print("выбран язык", chat.get("id"), lang, flush=True)


class Stranica(BaseHTTPRequestHandler):
    """Страница для проверки живости.

    Render обслуживает только те сервисы, которые слушают порт из $PORT:
    без открытого порта он считает запуск неудачным и гасит его. Этот же
    адрес пингует UptimeRobot раз в пять минут — бесплатный тариф Render
    засыпает после четверти часа тишины, и пинг не даёт ему уснуть.
    """

    OTVET = "QanchaYetadi bot: живой".encode("utf-8")

    def _shapka(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(self.OTVET)))
        self.end_headers()

    def do_GET(self):
        self._shapka()
        self.wfile.write(self.OTVET)

    def do_HEAD(self):
        # UptimeRobot проверяет живость методом HEAD, а не GET. Без этого
        # обработчика BaseHTTPRequestHandler отвечает 501, монитор считает
        # сервис упавшим и шлёт письма о недоступности — при живом сервисе.
        self._shapka()

    def log_message(self, *args):
        pass                      # пинги раз в пять минут засоряют журнал


def podnyat_stranicu():
    port = int(os.environ.get("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), Stranica)
    potok = threading.Thread(target=server.serve_forever, daemon=True)
    potok.start()
    print("страница живости на порту", port, flush=True)


def main():
    # Локально порт не нужен, но пусть работает одинаково везде:
    # разное поведение на машине и на хостинге — источник сюрпризов.
    podnyat_stranicu()

    ya = vyzov("getMe")
    if not ya or not ya.get("ok"):
        print("Токен не принят. Проверь BOT_TOKEN.")
        return
    print("бот запущен: @" + ya["result"]["username"], flush=True)
    print("останов — Ctrl+C", flush=True)

    # На хостинге сервис перезапускается, и старый опрос ещё какое-то время
    # держит очередь: без сброса новый экземпляр получает конфликт и молчит.
    vyzov("deleteWebhook", {"drop_pending_updates": True})

    smeshchenie = None
    while True:
        # long polling: соединение висит до 50 секунд и возвращается,
        # как только приходит событие. Опрашивать чаще незачем.
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
            if "message" in u:
                obrabotat_soobshchenie(u["message"])
            elif "callback_query" in u:
                obrabotat_nazhatie(u["callback_query"])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nостановлен")
