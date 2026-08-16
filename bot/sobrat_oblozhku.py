# -*- coding: utf-8 -*-
"""Сборка обложки для пересылки: app/oblozhka.png.

    py sobrat_oblozhku.py

Зачем это нужно. Ссылка на приложение уходит в каждой пересылке — а
пересылка это единственный бесплатный источник роста, который у нас есть.
Карточка без картинки в чате выглядит бледной строкой, и её пролистывают.
Картинка с крупным числом заставляет остановиться.

Почему собирается скриптом, а не рисуется руками. На обложке стоит
ЧИСЛО — размах курса за месяц. Через полгода оно станет неправдой, а
поправить картинку, нарисованную вручную, никто не вспомнит. Здесь она
пересобирается одной командой из живых данных, и число всегда с датой.

Раньше на обложке было старое обещание — про курс банка получателя. Замер
показал, что банк решает 0,84%, а день отправки 9,49%: обложка звала
человека к самому слабому рычагу из трёх.

ВАЖНО: никаких эмодзи. PIL рисует их пустыми квадратами.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

import rates
import sovet

PAPKA = os.path.dirname(os.path.abspath(__file__))
KUDA = os.path.normpath(os.path.join(PAPKA, "..", "oblozhka.png"))

# 1200×630 — размер, который Telegram и все соцсети показывают целиком,
# ничего не обрезая. Меньше — картинка растянется и замылится.
SHIRINA, VYSOTA = 1200, 630

FON = (16, 24, 32)
BELY = (255, 255, 255)
PRIGLUSHENNY = (155, 172, 187)
AKCENT = (79, 179, 217)

MESYACY = ["yanvar", "fevral", "mart", "aprel", "may", "iyun",
           "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"]

SHRIFTY = [
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/seguisb.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def shrift(razmer, zhirny=True):
    """Первый найденный шрифт нужного веса.

    Кириллица и латиница обязаны рисоваться оба: обложка двуязычная.
    Встроенный шрифт PIL умеет только латиницу, и на нём русская строка
    превратилась бы в квадраты.
    """
    poryadok = SHRIFTY if zhirny else SHRIFTY[2:] + SHRIFTY[:2]
    for put in poryadok:
        if os.path.exists(put):
            try:
                return ImageFont.truetype(put, razmer)
            except Exception:
                continue
    raise SystemExit("не найден ни один шрифт с кириллицей — обложку не собрать")


def po_centru(risuyu, y, tekst, fnt, cvet):
    shirina = risuyu.textlength(tekst, font=fnt)
    risuyu.text(((SHIRINA - shirina) / 2, y), tekst, font=fnt, fill=cvet)


def summa_slovom(n):
    return "{:,}".format(int(round(n))).replace(",", " ")


def data_slovom(iso):
    d = str(iso)[:10].split("-")
    if len(d) != 3:
        return str(iso)
    return "%d %s %s" % (int(d[2]), MESYACY[int(d[1]) - 1], d[0])


def main():
    print("собираю живые данные…", flush=True)
    snimok = rates.snimok(s_istoriey=True)
    istoriya = snimok.get("history") or []

    ocenka = sovet.analiz(istoriya)
    if not ocenka:
        raise SystemExit("истории не хватает — обложку с выдуманным числом "
                         "делать нельзя")

    razmah_sum = (ocenka["max_30"] - ocenka["min_30"]) * 50000
    razmah_percent = ((ocenka["max_30"] - ocenka["min_30"])
                      / ocenka["min_30"] * 100)

    kartinka = Image.new("RGB", (SHIRINA, VYSOTA), FON)
    risuyu = ImageDraw.Draw(kartinka)

    # Число первым и самым крупным. Название продукта человек прочитает
    # потом — если число его остановит. Если не остановит, название не
    # поможет.
    po_centru(risuyu, 96, summa_slovom(razmah_sum), shrift(150), BELY)
    po_centru(risuyu, 262,
              "so‘m — 50 000 rublda oyning eng yaxshi va eng yomon kuni farqi",
              shrift(29, zhirny=False), PRIGLUSHENNY)
    po_centru(risuyu, 302,
              "сум — разница между лучшим и худшим днём месяца на 50 000 ₽",
              shrift(29, zhirny=False), PRIGLUSHENNY)

    risuyu.line([(360, 372), (840, 372)], fill=(48, 62, 74), width=2)

    po_centru(risuyu, 404, "Qancha yetadi", shrift(66), BELY)
    po_centru(risuyu, 490, "Bugun yubormoqmi yoki kutmoqmi",
              shrift(31, zhirny=False), AKCENT)
    po_centru(risuyu, 530, "Отправлять сегодня или подождать",
              shrift(31, zhirny=False), PRIGLUSHENNY)

    # Дата обязательна. Число без даты в этом продукте — ложь, и на
    # картинке, которая уйдёт в сотни чатов, это правило важнее всего:
    # её потом не поправишь.
    po_centru(risuyu, 578,
              "kurs %s · %s · %s%%" % (
                  data_slovom(ocenka.get("data") or istoriya[-1]["date"]),
                  "Rossiya - O‘zbekiston",
                  ("%.2f" % razmah_percent).replace(".", ",")),
              shrift(22, zhirny=False), (108, 124, 138))

    kartinka.save(KUDA, "PNG", optimize=True)
    print("готово:", KUDA, flush=True)
    # «Публикаций», а не «дней»: ЦБ печатает курс по рабочим дням, и за
    # месячное окно их около двадцати одной.
    print("  число на обложке:", summa_slovom(razmah_sum), "сум по",
          ocenka["tochek"], "публикациям ЦБ", flush=True)
    print("Залей и проверь, как выглядит карточка при пересылке в чат.",
          flush=True)


if __name__ == "__main__":
    sys.exit(main())
