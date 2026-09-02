# -*- coding: utf-8 -*-
"""ВТОРАЯ ДВЕРЬ ДЛЯ УТРЕННЕГО ПОСТА: пишет в канал, когда Render молчит.

    py post_iz_github.py

ЗАЧЕМ ЭТО ЕСТЬ. Канал — единственное, что приводит людей в продукт, а
пишет в него бот на Render. Бесплатных часов там хватает примерно на
месяц: с 21 по 30 августа бот молчал девять дней подряд, и канал молчал
вместе с ним. Следующий раз это случится около 20 сентября, и дальше
каждый месяц. Падение Render приложение уже переживает — данные
пересобирает работа GitHub. Канал пока нет. Здесь он переживает тоже.

КАК РЕШАЕТСЯ, ПИСАТЬ ЛИ. Сначала спрашиваем сам Render. **Ответил —
молча выходим**, каким бы ни был ответ по существу. Правило нарочно
грубое: пока бот жив, автор поста ровно один. Правило потоньше («ответил,
но память у него сломана — значит пишем мы») выглядит умнее и стоит
канала: у живого бота отметки в Postgres, у нас — у Telegram, и две
памяти сразу это две правды о том, что уже опубликовано.

ОДИН КОД НА ДВЕ ДВЕРИ. Что публиковать сегодня и под какой отметкой,
решает `bot.utrenniy_post` — та же функция, что работает у бота на
Render. Своей копии здесь нет и быть не должно: копии разошлись бы, и
канал получил бы либо два поста за день, либо ни одного.

ПАМЯТЬ. Отметка «этот пост уже публиковали» лежит на серверах Telegram
(`pamyat_kanala`), а не в базе: `DATABASE_URL` — это полный доступ к
данным подписчиков, и в секретах публичного репозитория ему не место.
Когда Render просыпается, бот забирает наши отметки себе
(`hranilishche.perenesti_otmetki`) — при запуске и раз в сутки. Две
правды не сосуществуют ни минуты.

ЧТО НУЖНО ЗАДАТЬ: секреты `BOT_TOKEN` и `CHANNEL_ID`. И всё.
`DATABASE_URL` не нужен и не заводится.
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

# Адрес бота. Переменной можно подменить — проверкам нужен заведомо
# глухой адрес, а не боевой.
ADRES = (os.environ.get("BOT_URL", "").strip()
         or "https://qanchayetadi-bot.onrender.com")

# Сколько раз спрашивать и сколько ждать ответа.
#
# ЖДАТЬ ДОЛГО ОБЯЗАТЕЛЬНО. Бесплатный тариф Render усыпляет сервис после
# четверти часа тишины, и наш же запрос его будит: холодный старт — это
# полминуты-минута молчания, после которых бот отвечает и публикует сам.
# Короткое ожидание прочитало бы этот старт как «Render мёртв», и пост
# ушёл бы дважды: от нас и от проснувшегося бота.
#
# И ПАУЗЫ ТОЖЕ. Отказ приходит мгновенно — не только когда бесплатные
# часы кончились, но и когда Render просто перезапускает сервис: полминуты
# он отвечает 503 со своего края. Без пауз четыре мгновенных отказа
# уложились бы в секунду, окно перезапуска целиком легло бы внутрь, и мы
# опубликовали бы поверх живого бота. Поэтому вопрос растянут минуты на
# три: спешить публикатору некуда, работа GitHub бесплатна.
POPYTOK = 4
ZHDAT_SEKUND = 60
PAUZA_SEKUND = 40


def _slovami(stats):
    """Короткая выжимка из /api/stats — чтобы журнал работы читался."""
    kuski = []
    if stats.get("kod"):
        kuski.append("код " + str(stats["kod"]))
    kuski.append("канал пишет" if stats.get("kanal_pishet")
                 else "канал НЕ пишет")
    sekund = stats.get("opros_sekund_nazad")
    if isinstance(sekund, int):
        kuski.append("опрос отвечал %d с назад" % sekund)
    return ", ".join(kuski)


def sprosit_render(adres=None, popytok=None, pauza=None):
    """Отвечает ли бот на Render. Возвращает (отвечает, чем именно).

    Отвечает — это код 200 и разборный JSON от `/api/stats`, а не просто
    открытый порт: свою страницу отказа Render отдаёт с собственного
    края, и бот к ней отношения не имеет.

    Ошибка сети здесь читается как «Render молчит», и это осознанно: не
    смогли спросить — значит и человек, открывший канал, ничего от бота
    не дождётся. Но платим за это тремя попытками с долгим ожиданием, а
    не одной короткой.
    """
    # Сроки читаются из модуля, а не проставляются значениями по
    # умолчанию: те привязываются один раз при разборе файла, и проверка,
    # подменившая их снаружи, гоняла бы совсем не то, что боевая работа.
    adres = (adres or ADRES).rstrip("/") + "/api/stats"
    popytok = POPYTOK if popytok is None else popytok
    pauza = PAUZA_SEKUND if pauza is None else pauza
    prichiny = []

    for nomer in range(1, popytok + 1):
        if nomer > 1 and pauza:
            time.sleep(pauza)
        try:
            zapros = urllib.request.Request(
                adres, headers={"User-Agent": "qanchayetadi-post-iz-github"})
            with urllib.request.urlopen(zapros, timeout=ZHDAT_SEKUND) as svyaz:
                kod = svyaz.getcode()
                syroe = svyaz.read()
        except Exception as oshibka:
            prichiny.append("попытка %d: %s" % (nomer, repr(oshibka)[:120]))
            continue

        try:
            stats = json.loads(syroe.decode("utf-8"))
        except Exception as oshibka:
            prichiny.append("попытка %d: код %s, но ответ не разобрался (%s)"
                            % (nomer, kod, repr(oshibka)[:80]))
            continue

        if kod == 200 and isinstance(stats, dict):
            return True, _slovami(stats)

        prichiny.append("попытка %d: код %s" % (nomer, kod))

    return False, "; ".join(prichiny) or "не спросили ни разу"


def main():
    kanal = os.environ.get("CHANNEL_ID", "").strip()
    token = os.environ.get("BOT_TOKEN", "").strip()

    # Секретов нет — вторая дверь просто не поставлена. Говорим прямо и
    # выходим зелёными.
    #
    # Красная работа каждое утро выглядела бы честнее, но обошлась бы
    # дороже: письмо, которое приходит ежедневно и означает одно и то же,
    # перестают читать на третий день — а вместе с ним перестают читать
    # письма сторожа, и вот те приходят по делу. Задача «завести два
    # секрета» и так стоит в DEYSTVIYA-SEMYONA.md.
    net = [imya for imya, est in (("BOT_TOKEN", token),
                                  ("CHANNEL_ID", kanal)) if not est]
    if net:
        print("[github-пост] вторая дверь не поставлена: нет секретов %s. "
              "Пока их нет, канал живёт ровно столько, сколько живёт "
              "Render. Заводятся в Settings -> Secrets and variables -> "
              "Actions." % ", ".join(net), flush=True)
        return 0

    otvechaet, chto = sprosit_render()
    if otvechaet:
        print("[github-пост] Render отвечает (%s) — пишет он, я молчу."
              % chto, flush=True)
        return 0

    print("[github-пост] Render не ответил: %s" % chto, flush=True)

    # Бота ввозим ЗДЕСЬ, а не наверху файла. На пустом BOT_TOKEN он
    # выходит прямо на импорте, и до объяснения выше дело бы не дошло —
    # а это объяснение и есть вся разница между «дверь не поставлена» и
    # «работа сломалась».
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import bot
    import hranilishche

    hranilishche.podnyat()

    # Базы здесь нет и не будет — значит отметки живут у Telegram. Не
    # поднялись — не публикуем вовсе: без памяти, переживающей
    # перезапуск, «ровно один раз» не гарантировать, а канал, получивший
    # один пост дважды, отписывают.
    if not hranilishche.pamyat_na_telegrame(bot.vyzov, kanal):
        print("[github-пост] запасной памяти нет — молчу: %s"
              % (hranilishche.pochemu_net_pamyati() or "причина не названа"),
              flush=True)
        return 0

    # Час — узбекский, как и у бота: раньше девяти утра `utrenniy_post`
    # не пишет сам. Сдвигать часы только у одной стороны нельзя.
    teper = datetime.now(timezone.utc) + timedelta(hours=5)
    data_kursa = bot.data_kursa_seychas()
    print("[github-пост] Ташкент %s, курс за %s, вид поста «%s»"
          % (teper.strftime("%Y-%m-%d %H:%M"), data_kursa or "—",
             bot.vid_posta_na_segodnya(teper)), flush=True)

    if bot.utrenniy_post(teper, data_kursa):
        print("[github-пост] опубликовано за Render.", flush=True)
    else:
        print("[github-пост] публиковать нечего: этот курс уже освещён, "
              "час ещё не настал или данных на пост не хватает.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
