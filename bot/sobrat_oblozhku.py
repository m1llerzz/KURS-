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
import re
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
TUSKLY = (108, 124, 138)

# Тон — это оценка, а не украшение. Те же две роли, что в приложении:
# акцент, когда курс выше обычного, и янтарь, когда ниже. Янтарь взят
# светлее приложенческого `--warn`: там он лежит на белом, здесь — на
# почти чёрном, и тёмное золото на тёмном фоне не читается вовсе.
TONA = {
    "otlichno": AKCENT,
    "horosho": AKCENT,
    "obychno": (138, 156, 170),
    "nize_obychnogo": (229, 168, 75),
    "ploho": (229, 168, 75),
}

# Нижняя полоса картинки отдана месяцу целиком, до самых краёв. На
# обложке это тот же мотив, что и на первом экране приложения: человек
# видит в чате ту же кривую, которую откроет, если нажмёт.
GRAFIK_VERH = 440
GRAFIK_POLE = 34          # воздух над самой высокой точкой и под низшей

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


def sleva(risuyu, x, y, tekst, fnt, cvet):
    risuyu.text((x, y), tekst, font=fnt, fill=cvet)


def sprava(risuyu, x, y, tekst, fnt, cvet):
    """От правого края внутрь: правая колонка обязана держать общий край."""
    risuyu.text((x - risuyu.textlength(tekst, font=fnt), y),
                tekst, font=fnt, fill=cvet)


def vrazryadku(tekst):
    """Вывеска набирается разрядкой. PIL межбуквенного расстояния не знает,
    поэтому оно набирается пробелами — приём старый и честный."""
    return " ".join(tekst)


def krivaya_mesyaca(ryad, ton, shirina, vysota):
    """Кривая курса за месяц во всю ширину, с растворяющейся заливкой.

    Почему отдельным слоем и в тройном размере. PIL рисует линии без
    сглаживания: наклонная получается лесенкой, и на картинке, которая
    уходит в чужие чаты, эта лесенка — прямая подпись «сделано на
    коленке». Слой рисуется втрое крупнее и ужимается обратно; сглаживание
    даёт уменьшение.

    Заливка под линией гаснет книзу. Ровная плашка тоном превратила бы
    оценку в обои — то самое, от чего избавлялись в приложении.
    """
    m = 3
    w, h = shirina * m, vysota * m
    sloy = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    risuyu = ImageDraw.Draw(sloy)

    kursy = [t["rub_uzs"] for t in ryad]
    nizhe, vyshe = min(kursy), max(kursy)
    razmah = (vyshe - nizhe) or 1.0

    # Снизу воздуха больше, чем сверху: у падающего курса сегодняшняя
    # точка садится на самый низ, и симметричные поля обрезали бы ей
    # свечение. Сверху столько же места держать незачем — там кривая
    # упирается в текст, а не в край.
    pole = GRAFIK_POLE * m
    pole_snizu = (GRAFIK_POLE + 18) * m

    # Слева кривая уходит за край, справа — не доходит до него.
    # Так и устроено время: прошлое обрезано кадром, а сегодняшняя точка
    # обязана поместиться целиком вместе со свечением. Без правого поля
    # она резалась ровно пополам — самое важное место графика.
    pole_sprava = 40 * m
    shag = (w - pole_sprava) / max(len(kursy) - 1, 1)
    tochki = [(i * shag,
               pole + (vyshe - k) / razmah * (h - pole - pole_snizu))
              for i, k in enumerate(kursy)]

    # Заливка: сначала сплошной тон под кривой, затем вертикальная маска,
    # которая уводит его в ничто у нижнего края.
    zalivka = Image.new("RGBA", (w, h), ton + (255,))
    maska = Image.new("L", (1, h))
    for y in range(h):
        # Плотность падает к низу, но не квадратом: при квадрате заливка
        # исчезала почти сразу, и у падающего курса — когда кривая идёт
        # низом — под ней не оставалось ничего. А ради падающего курса
        # обложка и нужна: он и есть повод остановиться.
        maska.putpixel((0, y), int(112 * (1 - y / h)))
    zalivka.putalpha(maska.resize((w, h)))

    forma = Image.new("L", (w, h), 0)
    ImageDraw.Draw(forma).polygon(tochki + [(w, h), (0, h)], fill=255)
    sloy.paste(zalivka, (0, 0), forma)

    risuyu.line(tochki, fill=ton + (255,), width=4 * m, joint="curve")

    # Сегодняшняя точка. В приложении она загорается последней, потому что
    # раскрытие месяца доходит до неё в конце; здесь движения нет, и
    # выделить её нечем, кроме свечения.
    x, y = tochki[-1]
    risuyu.ellipse([x - 22 * m, y - 22 * m, x + 22 * m, y + 22 * m],
                   fill=ton + (46,))
    risuyu.ellipse([x - 9 * m, y - 9 * m, x + 9 * m, y + 9 * m],
                   fill=ton + (255,))

    return sloy.resize((shirina, vysota), Image.LANCZOS)


def summa_slovom(n):
    return "{:,}".format(int(round(n))).replace(",", " ")


def data_slovom(iso):
    d = str(iso)[:10].split("-")
    if len(d) != 3:
        return str(iso)
    return "%d %s %s" % (int(d[2]), MESYACY[int(d[1]) - 1], d[0])


def _obnovit_versiyu_oblozhki(data_kursa):
    """Дописывает дату курса в адрес обложки: `oblozhka.png?v=20260814`.

    Зачем. Telegram и соцсети кешируют превью по АДРЕСУ и держат его
    неделями. Пересобранная картинка с новым числом просто не доедет:
    в чатах будет висеть прошлое. Меняется адрес — меняется и картинка.

    Версия — дата курса, а не время запуска: пересборка в тот же день
    ничего не меняет, а новый курс меняет и число, и адрес.
    """
    versiya = str(data_kursa or "").replace("-", "").replace(".", "")[:8]
    if not versiya.isdigit():
        print("  версию обложки поставить не из чего:", data_kursa, flush=True)
        return

    obrazec = re.compile(r'(content="https://[^"]*?oblozhka\.png)(\?v=\d+)?(")')
    for imya in ("index.html", "kurs.html"):
        put = os.path.normpath(os.path.join(PAPKA, "..", imya))
        if not os.path.exists(put):
            continue
        with open(put, "r", encoding="utf-8") as f:
            tekst = f.read()
        novyy, skolko = obrazec.subn(
            lambda m: m.group(1) + "?v=" + versiya + m.group(3), tekst)
        if not skolko:
            print("  ВНИМАНИЕ: в %s не найден адрес обложки" % imya, flush=True)
            continue
        if novyy != tekst:
            with open(put, "w", encoding="utf-8") as f:
                f.write(novyy)
            print("  %s: адрес обложки → ?v=%s" % (imya, versiya), flush=True)


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

    data_kursa = ocenka.get("data") or istoriya[-1]["date"]
    ton = TONA.get(ocenka["verdikt"], PRIGLUSHENNY)

    kartinka = Image.new("RGB", (SHIRINA, VYSOTA), FON)

    # Месяц кладётся первым, под текст: он подложка, а не иллюстрация
    # рядом. Ряд берётся тот же, по которому посчитан размах, — иначе
    # картинка говорила бы не про то число, что стоит над ней.
    ryad_okna = sorted(istoriya, key=lambda x: x["date"])[-ocenka["tochek"]:]
    if len(ryad_okna) >= 2:
        sloy = krivaya_mesyaca(ryad_okna, ton, SHIRINA, VYSOTA - GRAFIK_VERH)
        # Слой сам себе маска: прозрачное в нём обязано остаться фоном, а
        # не залиться чёрным прямоугольником.
        kartinka.paste(sloy, (0, GRAFIK_VERH), sloy)

    risuyu = ImageDraw.Draw(kartinka)

    LEVOE, PRAVOE = 72, SHIRINA - 72

    # Вывеска мелко, дата — в тот же ряд справа. Раньше всё стояло
    # столбиком по центру, и семь строк одинаковой важности читались как
    # объявление на подъезде: глазу негде было начать.
    sleva(risuyu, LEVOE, 58, vrazryadku("QANCHA YETADI"),
          shrift(19), TUSKLY)
    sprava(risuyu, PRAVOE, 58, "Rossiya - O‘zbekiston",
           shrift(19, zhirny=False), TUSKLY)

    # Курс дня — второе число обложки и единственное, ради которого
    # человек нажмёт прямо сейчас. Правая половина верха до него пустовала,
    # и вес композиции сваливался влево. Кегль вчетверо меньше главного:
    # это спутник размаха, а не соперник ему.
    sprava(risuyu, PRAVOE, 104,
           "1 ₽ = %s so‘m" % ("%.2f" % ocenka["segodnya"]).replace(".", ","),
           shrift(37), BELY)
    sprava(risuyu, PRAVOE, 152,
           "%s%% oyning o‘rtachasidan · от среднего" % (
               ("%+.1f" % ocenka["otklonenie_percent"])
               .replace(".", ",")
               # Минус, а не дефис: рядом с плюсом дефис короче и сидит
               # ниже, отчего пара «+»/«−» выглядит собранной наспех.
               .replace("-", "−")),
           shrift(20, zhirny=False), ton)

    # Число первым и самым крупным. Название продукта человек прочитает
    # потом — если число его остановит. Если не остановит, название не
    # поможет.
    #
    # Крупным набрано ЗНАЧЕНИЕ, а не подпись к нему: «so'm» рядом с
    # числом — единица измерения, и разница в кегле здесь такая же, как
    # между курсом и словом «сум» на первом экране приложения.
    chislo = summa_slovom(razmah_sum)
    shrift_chisla = shrift(134)
    sleva(risuyu, LEVOE, 104, chislo, shrift_chisla, BELY)
    sleva(risuyu, LEVOE + risuyu.textlength(chislo, font=shrift_chisla) + 18,
          202, "so‘m", shrift(34), PRIGLUSHENNY)

    sleva(risuyu, LEVOE, 262,
          "50 000 rublda oyning eng yaxshi va eng yomon kuni farqi",
          shrift(27, zhirny=False), PRIGLUSHENNY)
    sleva(risuyu, LEVOE, 300,
          "разница между лучшим и худшим днём месяца на 50 000 ₽",
          shrift(27, zhirny=False), PRIGLUSHENNY)

    # Обещание продукта — двумя языками, узбекский первый и тоном оценки.
    sleva(risuyu, LEVOE, 356, "Bugun yubormoqmi yoki kutmoqmi",
          shrift(32), ton)
    sleva(risuyu, LEVOE, 396, "Отправлять сегодня или подождать",
          shrift(32, zhirny=False), PRIGLUSHENNY)

    # Дата обязательна. Число без даты в этом продукте — ложь, и на
    # картинке, которая уйдёт в сотни чатов, это правило важнее всего:
    # её потом не поправишь. Стоит она у самой кривой — потому что
    # датирована именно кривая, её последняя точка.
    sprava(risuyu, PRAVOE, 396,
           "kurs %s · razmah %s%%" % (
               data_slovom(data_kursa),
               ("%.2f" % razmah_percent).replace(".", ",")),
           shrift(21, zhirny=False), TUSKLY)

    kartinka.save(KUDA, "PNG", optimize=True)
    print("готово:", KUDA, flush=True)

    _obnovit_versiyu_oblozhki(ocenka.get("data") or istoriya[-1]["date"])
    # «Публикаций», а не «дней»: ЦБ печатает курс по рабочим дням, и за
    # месячное окно их около двадцати одной.
    print("  число на обложке:", summa_slovom(razmah_sum), "сум по",
          ocenka["tochek"], "публикациям ЦБ", flush=True)
    print("Залей и проверь, как выглядит карточка при пересылке в чат.",
          flush=True)


if __name__ == "__main__":
    sys.exit(main())
