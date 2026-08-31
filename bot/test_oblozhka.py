# -*- coding: utf-8 -*-
"""Проверки обложки: шрифт и буквы, которые он обязан рисовать.

Зачем отдельный набор. Обложка — единственная картинка продукта, которая
уходит наружу: её видит каждый, кому переслали приложение. Проверить её
прогоном нельзя (это картинка), а глазами смотрят раз в неделю — и за
эту неделю она уже дважды уходила в чаты испорченной:

    27.08.2026  на macOS подставился Arial: кириллица есть, ₽ нет —
                посреди «50 000 ₽» стоял пустой квадрат;
    31.08.2026  обычное начертание Helvetica Neue на двадцатом кегле
                закрывает просвет у «е», и «от среднего» читалось как
                «от срөднөго». Знак рубля при этом был на месте.

Оба раза дефект был в ШРИФТЕ, а не в коде, и оба раза его нашли глазами.
Здесь то же самое проверяется числом.

    cd app/bot && py test_oblozhka.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from PIL import ImageFont
except ImportError:
    print("Pillow не установлен — проверки обложки НЕ выполнены.")
    sys.exit(2)

import sobrat_oblozhku as obl

proshlo, upalo, preduprezhdeniya = [], [], []


def proverka(imya, uslovie, podskazka=""):
    if uslovie:
        proshlo.append(imya)
    else:
        upalo.append(imya + ("  << " + podskazka if podskazka else ""))


def preduprezhdenie(imya, podskazka=""):
    preduprezhdeniya.append(imya + ("  << " + podskazka if podskazka else ""))


# ── Шрифт, который выберется на этой машине ──────────────────────────

for kegl, zhirny, imya in ((obl.KEGL_PROVERKI, False, "обычный"),
                           (obl.KEGL_PROVERKI, True, "жирный")):
    try:
        fnt = obl.shrift(kegl, zhirny=zhirny)
    except SystemExit as e:
        proverka("шрифт %s найден" % imya, False, str(e))
        continue

    proverka("шрифт %s найден" % imya, fnt is not None)
    proverka("%s рисует ₽" % imya, obl._est_bukva(fnt, obl.PROVERKA_RUBLYA),
             "посреди суммы будет пустой квадрат")
    proverka("%s рисует узбекскую ʻ" % imya, obl._est_bukva(fnt, obl.PROVERKA_UZ),
             "«soʻm» уйдёт в чаты с квадратом посреди слова")
    proverka("%s рисует кириллицу" % imya, obl._est_bukva(fnt, "ы"),
             "обложка двуязычная")

# ── «е» обязана остаться «е» ─────────────────────────────────────────
#
# Мера: «е» — это «о» с короткой перекладиной, «ө» — «о» с перекладиной во
# всю ширину. У исправного шрифта площадь «е» ближе к «о», чем к «ө».

def _put_i_nomer(zapis):
    return (zapis[0], zapis[1]) if isinstance(zapis, tuple) else (zapis, 0)


# Читаемый шрифт нужного веса обязан побеждать нечитаемый: если в списке
# есть и тот и другой, выбор не должен останавливаться на первом.
_est_chitaemyy = False
for zapis in obl.SHRIFTY_OBYCHNYE:
    put, nomer = _put_i_nomer(zapis)
    if not os.path.exists(put):
        continue
    fnt = obl._otkryt(zapis, obl.KEGL_PROVERKI)
    if fnt is None or not obl._umeet_bukvy(fnt):
        continue
    if obl._e_ostayotsya_e(zapis):
        _est_chitaemyy = True
    elif _est_chitaemyy is False:
        pass    # нечитаемый стоит раньше читаемого — это и проверяем ниже

if _est_chitaemyy:
    vybran = obl.shrift(obl.KEGL_PROVERKI, zhirny=False)
    proverka("выбран шрифт, у которого «е» остаётся «е»",
             obl._chernila(vybran, "е") and obl._chernila(vybran, "ө")
             and abs(obl._chernila(vybran, "е") - obl._chernila(vybran, "ө"))
             / obl._chernila(vybran, "ө") >= obl.PORAG_RAZLICHIYA,
             "выбран %s — на нём «от среднего» читается как «от срөднөго»"
             % getattr(vybran, "path", "?"))

# Вес важнее читаемости мелкого кегля: обычному тексту жирный шрифт
# доставаться не должен ни при каких обстоятельствах. Это уже ломалось
# однажды на Linux, когда два списка перебирались подряд.
_obychnyy = obl.shrift(obl.KEGL_PROVERKI, zhirny=False)
_zhirnye_puti = {_put_i_nomer(z) for z in obl.SHRIFTY_ZHIRNYE}
proverka("обычному тексту не достался жирный шрифт",
         (getattr(_obychnyy, "path", ""), getattr(_obychnyy, "index", 0))
         not in _zhirnye_puti,
         "выбран %s" % getattr(_obychnyy, "path", "?"))

# Мера должна уметь сказать «нет»: на macOS обычное начертание Helvetica
# Neue — тот самый случай, ради которого она написана.
_HELVETICA = ("/System/Library/Fonts/HelveticaNeue.ttc", 0)
if os.path.exists(_HELVETICA[0]):
    proverka("мера ловит закрытую «е»", obl._e_ostayotsya_e(_HELVETICA) is False,
             "на этом начертании «от среднего» читается как «от срөднөго»")
else:
    preduprezhdenie("нечего проверить мерой", "Helvetica Neue есть только на macOS")

# Заглушка не считается буквой: у пустого квадрата тоже есть очертания, и
# прежняя проверка «есть ли хоть что-нибудь» его пропускала.
_PT = ("/System/Library/Fonts/Supplemental/PTSans.ttc", 0)
if os.path.exists(_PT[0]):
    pt = obl._otkryt(_PT, obl.KEGL_PROVERKI)
    proverka("пустой квадрат не считается буквой",
             obl._est_bukva(pt, obl.PROVERKA_UZ) is False,
             "в PT Sans нет ʻ, но заглушка рисуется")
else:
    preduprezhdenie("нечего проверить заглушкой", "PT Sans есть только на macOS")


# ── Итог ─────────────────────────────────────────────────────────────

print("Пройдено: %d" % len(proshlo))
for p in proshlo:
    print("  + " + p)
for p in preduprezhdeniya:
    print("  ~ " + p)
if upalo:
    print("\nПРОВАЛЕНО: %d" % len(upalo))
    for p in upalo:
        print("  - " + p)
    sys.exit(1)
print("\nВсе проверки зелёные.")
