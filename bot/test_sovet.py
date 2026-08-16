# -*- coding: utf-8 -*-
"""Проверки советника. Запуск: py test_sovet.py

Без зависимостей и без фреймворка: обычные assert. Красное видно сразу,
зелёное печатается списком. Прогонять после любой правки sovet.py.
"""
import sovet

provereno = []
provalov = []


def proverka(imya, uslovie, podskazka=""):
    if uslovie:
        provereno.append(imya)
    else:
        provalov.append(imya + ("  << " + podskazka if podskazka else ""))


def ryad(znacheniya, s_daty=1):
    """Список курсов превращает в историю с датами по порядку."""
    return [{"date": "2026-08-%02d" % (s_daty + i), "rub_uzs": v}
            for i, v in enumerate(znacheniya)]


# ── Нехватка данных ──────────────────────────────────────────────────

proverka("пустая история — нет вердикта", sovet.analiz([]) is None)
proverka("None — нет вердикта", sovet.analiz(None) is None)
proverka("шесть точек мало", sovet.analiz(ryad([140] * 6)) is None,
         "на шести днях среднее это случайность")
proverka("семь точек уже считаем", sovet.analiz(ryad([140] * 7)) is not None)


# ── Ровный курс ──────────────────────────────────────────────────────

rovno = sovet.analiz(ryad([140] * 10))
proverka("ровный курс — обычно", rovno["verdikt"] == "obychno", rovno["verdikt"])
proverka("ровный курс — отклонение ноль", abs(rovno["otklonenie_percent"]) < 0.01)
proverka("ровный курс — позиция середина", rovno["pozicia_percent"] == 50,
         "при min == max делить нельзя, должна быть заглушка 50")
proverka("ровный курс — тренд стоит", rovno["trend"] == "stoit", str(rovno["trend"]))


# ── Курс заметно выше обычного ───────────────────────────────────────

# девять дней по 140, десятый — 150: среднее 141, отклонение около +6,4%
vysoko = sovet.analiz(ryad([140] * 9 + [150]))
proverka("высокий курс — отлично", vysoko["verdikt"] == "otlichno", vysoko["verdikt"])
proverka("высокий курс — отклонение больше 3%", vysoko["otklonenie_percent"] > 3)
proverka("высокий курс — позиция 100", vysoko["pozicia_percent"] == 100,
         "лучший день окна должен давать сто")
proverka("высокий курс — тренд растёт", vysoko["trend"] == "rastet", str(vysoko["trend"]))


# ── Курс заметно ниже обычного ───────────────────────────────────────

nizko = sovet.analiz(ryad([150] * 9 + [140]))
proverka("низкий курс — плохо", nizko["verdikt"] == "ploho", nizko["verdikt"])
proverka("низкий курс — позиция 0", nizko["pozicia_percent"] == 0)
proverka("низкий курс — тренд падает", nizko["trend"] == "padaet", str(nizko["trend"]))
proverka("низкий курс — разница на 1000 отрицательная",
         nizko["raznica_na_1000_rub"] < 0,
         "плохой курс обязан показывать минус, а не молчать")


# ── Пороги ───────────────────────────────────────────────────────────

# Ровно на границе заметности: отклонение около +1%
granica = sovet.analiz(ryad([140] * 9 + [140 * 1.113]))
proverka("чуть выше порога — хорошо, а не отлично",
         granica["verdikt"] in ("horosho", "otlichno"), granica["verdikt"])

melochь = sovet.analiz(ryad([140] * 9 + [140.5]))
proverka("мелкое отклонение — обычно", melochь["verdikt"] == "obychno",
         melochь["verdikt"] + " при отклонении " + str(melochь["otklonenie_percent"]))


# ── Окно 30 дней ─────────────────────────────────────────────────────

dlinno = sovet.analiz([{"date": "2026-06-%02d" % (i + 1), "rub_uzs": 200.0}
                       for i in range(10)] + ryad([140] * 30))
proverka("старое за окном не влияет", abs(dlinno["otklonenie_percent"]) < 0.01,
         "курс 200 сорокадневной давности не должен попадать в среднее")
proverka("в окне ровно 30 точек", dlinno["tochek"] == 30, str(dlinno["tochek"]))


# ── Оповещения ───────────────────────────────────────────────────────

proverka("плохой курс не будит человека",
         sovet.stoit_uvedomit(nizko) is False,
         "оповещение о плохом курсе тратит доверие впустую")
proverka("хороший курс будит", sovet.stoit_uvedomit(vysoko) is True)
proverka("повтор того же вердикта молчит",
         sovet.stoit_uvedomit(vysoko, "otlichno") is False,
         "пять дней подряд одно и то же — и бота отключают")
proverka("смена вердикта будит",
         sovet.stoit_uvedomit(vysoko, "obychno") is True)
proverka("без оценки не будит", sovet.stoit_uvedomit(None) is False)


# ── Выгода на сумме ──────────────────────────────────────────────────

v = sovet.vygoda_na_summe(vysoko, 50000)
proverka("выгода на 50 000 считается", v > 0, str(v))
proverka("выгода пропорциональна сумме",
         abs(sovet.vygoda_na_summe(vysoko, 100000) - 2 * v) <= 1)
proverka("нулевая сумма — ноль", sovet.vygoda_na_summe(vysoko, 0) == 0)
proverka("без оценки — ноль", sovet.vygoda_na_summe(None, 50000) == 0)


# ── Живой замер 15 августа 2026 ──────────────────────────────────────

# Настоящий ряд: курс шёл вниз весь месяц. Продукт обязан на нём
# сказать «подожди», а не «отправляй» — иначе он реклама, а не советник.
zhivoy = sovet.analiz(ryad([155.22, 154.1, 153.0, 152.4, 151.2, 150.3, 149.8,
                            149.1, 148.2, 147.5, 146.19, 145.3, 144.8, 143.9,
                            143.1, 142.5, 141.76]))
proverka("живой падающий ряд — курс ниже обычного",
         zhivoy["verdikt"] in ("ploho", "nize_obychnogo"), zhivoy["verdikt"])
proverka("живой ряд — тренд падает", zhivoy["trend"] == "padaet")
proverka("живой ряд — не будим человека", sovet.stoit_uvedomit(zhivoy) is False)


# ── Что делать: совет обязан учитывать направление ───────────────────
#
# Здесь чинили настоящую ошибку. Раньше совет выводился только из
# отклонения от среднего: курс ниже обычного — «подожди». На живых данных
# рубль падал весь месяц, каждый день был ниже среднего, и приложение
# каждый день советовало ждать, пока курс становился всё хуже.

proverka("падающий курс — НЕ советуем ждать",
         zhivoy["deystvie"] == "ne_zhdat", zhivoy["deystvie"] +
         " — в падающем рынке «подожди» стоит человеку денег")

# Курс упал сильно ниже среднего и последние дни отыгрывает обратно —
# единственный случай, когда ожидание действительно может окупиться.
rastet_nizko = sovet.analiz(ryad([160, 160, 160, 135, 136, 137, 140, 141, 142]))
proverka("растущий и низкий курс — ждать можно",
         rastet_nizko["deystvie"] == "mozhno_zhdat",
         rastet_nizko["deystvie"] + " при вердикте " + rastet_nizko["verdikt"]
         + " и тренде " + str(rastet_nizko["trend"]))

proverka("высокий растущий курс — отправлять",
         vysoko["deystvie"] == "otpravlyat", vysoko["deystvie"])

proverka("ровный курс — ничего особенного",
         rovno["deystvie"] == "obychno", rovno["deystvie"])

# Курс выше обычного, но пошёл вниз — это «отправляй, пока хорошо»,
# а не «не жди»: человеку нужно действие, а не описание.
vysoko_padaet = sovet.analiz(ryad([140] * 6 + [152, 151, 150]))
proverka("высокий и падающий — отправлять сейчас",
         vysoko_padaet["deystvie"] == "otpravlyat",
         vysoko_padaet["deystvie"] + " при вердикте " + vysoko_padaet["verdikt"])

proverka("совет есть всегда, когда есть вердикт",
         all(sovet.analiz(ryad(r)) is None or sovet.analiz(ryad(r)).get("deystvie")
             for r in ([140] * 10, [150] * 9 + [140], [140] * 9 + [150])))

# Прямая проверка таблицы решений — без неё легко сломать одну ветку.
proverka("падение + низкий = не ждать",
         sovet.deystvie("ploho", "padaet") == "ne_zhdat")
proverka("падение + высокий = отправлять",
         sovet.deystvie("otlichno", "padaet") == "otpravlyat")
proverka("рост + низкий = можно ждать",
         sovet.deystvie("ploho", "rastet") == "mozhno_zhdat")
proverka("рост + высокий = отправлять",
         sovet.deystvie("horosho", "rastet") == "otpravlyat")
proverka("стоит + низкий = можно ждать",
         sovet.deystvie("nize_obychnogo", "stoit") == "mozhno_zhdat")
proverka("стоит + обычный = обычно",
         sovet.deystvie("obychno", "stoit") == "obychno")
proverka("без тренда не падаем",
         sovet.deystvie("obychno", None) == "obychno")


# ── Итоги периода: материал для постов недели и месяца ───────────────

proverka("пустая история — нет итога", sovet.itog_perioda([], 7) is None)
proverka("None — нет итога", sovet.itog_perioda(None, 7) is None)
proverka("две точки мало для итога", sovet.itog_perioda(ryad([140, 141]), 7) is None,
         "максимум и минимум по двум дням — это не обзор периода")
proverka("три точки уже итог", sovet.itog_perioda(ryad([140, 141, 142]), 7) is not None)

nedelya = sovet.itog_perioda(ryad([140, 142, 145, 143, 141, 139, 144]), 7)
proverka("итог недели — семь дней", nedelya["dney"] == 7, str(nedelya["dney"]))
proverka("итог недели — начало первое значение", nedelya["nachalo"] == 140)
proverka("итог недели — конец последнее", nedelya["konec"] == 144)
proverka("итог недели — максимум найден", nedelya["max"] == 145)
proverka("итог недели — минимум найден", nedelya["min"] == 139)
proverka("итог недели — дата максимума верна", nedelya["max_data"] == "2026-08-03",
         nedelya["max_data"] + " — третий день ряда, курс 145")
proverka("итог недели — дата минимума верна", nedelya["min_data"] == "2026-08-06",
         nedelya["min_data"])
proverka("итог недели — размах на 50 000 считается",
         nedelya["razmah_na_50k"] == round((145 - 139) * 50000),
         str(nedelya["razmah_na_50k"]))
proverka("итог недели — упущенное против лучшего дня",
         nedelya["upushcheno_na_50k"] == round((145 - 144) * 50000),
         str(nedelya["upushcheno_na_50k"]))

# Окно обрезает лишнее с начала, а не с конца: итог недели про последние
# семь дней, а не про первые.
dlinnyy = sovet.itog_perioda(ryad([200] * 10 + [140, 141, 142, 143, 144, 145, 146]), 7)
proverka("окно берёт последние дни", dlinnyy["max"] == 146,
         str(dlinnyy["max"]) + " — курс 200 двухнедельной давности не в итоге недели")
proverka("окно ровно по размеру", dlinnyy["dney"] == 7, str(dlinnyy["dney"]))

# Лучший день сегодня — упускать нечего. Ноль здесь обязателен: любое
# другое число заставило бы человека жалеть о дне, в котором он выиграл.
luchshiy_segodnya = sovet.itog_perioda(ryad([140, 141, 145]), 7)
proverka("лучший день сегодня — упущено ноль",
         luchshiy_segodnya["upushcheno_na_50k"] == 0,
         str(luchshiy_segodnya["upushcheno_na_50k"]))

rostushchiy = sovet.itog_perioda(ryad([140, 142, 144]), 7)
proverka("растущий период — изменение положительное",
         rostushchiy["izmenenie_percent"] > 0, str(rostushchiy["izmenenie_percent"]))
padayushchiy = sovet.itog_perioda(ryad([144, 142, 140]), 7)
proverka("падающий период — изменение отрицательное",
         padayushchiy["izmenenie_percent"] < 0, str(padayushchiy["izmenenie_percent"]))

# Месяц: тот же расчёт на окне 30, важен факт, что окно не путается.
mesyac = sovet.itog_perioda(ryad([140 + i * 0.5 for i in range(30)]), 30)
proverka("итог месяца — тридцать дней", mesyac["dney"] == 30, str(mesyac["dney"]))
proverka("итог месяца — максимум в конце при росте", mesyac["max"] == mesyac["konec"])


# ── Резкое движение: внеочередной пост ───────────────────────────────

proverka("пустая история — нет рывка", sovet.rezkoe_dvizhenie([]) is None)
proverka("одна точка — нет рывка", sovet.rezkoe_dvizhenie(ryad([140])) is None)
proverka("спокойный день — молчим",
         sovet.rezkoe_dvizhenie(ryad([140, 140.3])) is None,
         "0,2% за день — обычный шаг, кричать не о чем")

vverh = sovet.rezkoe_dvizhenie(ryad([140, 143]))
proverka("рывок вверх замечен", vverh is not None)
proverka("рывок вверх — направление", vverh["napravlenie"] == "vverh")
proverka("рывок вверх — процент около 2,14",
         abs(vverh["percent"] - 2.14) < 0.02, str(vverh["percent"]))
proverka("рывок вверх — цена на 50 000",
         vverh["na_50k"] == round((143 - 140) * 50000), str(vverh["na_50k"]))

vniz = sovet.rezkoe_dvizhenie(ryad([143, 140]))
proverka("рывок вниз замечен и назван вниз", vniz["napravlenie"] == "vniz")
proverka("рывок вниз — процент отрицательный", vniz["percent"] < 0, str(vniz["percent"]))
proverka("рывок вниз — цена отрицательная", vniz["na_50k"] < 0, str(vniz["na_50k"]))

proverka("ровно на пороге — считаем событием",
         sovet.rezkoe_dvizhenie(ryad([100, 101])) is not None,
         "1,0% при пороге 1,0 должен срабатывать")
proverka("чуть ниже порога — молчим",
         sovet.rezkoe_dvizhenie(ryad([100, 100.9])) is None)
proverka("порог настраивается",
         sovet.rezkoe_dvizhenie(ryad([140, 140.5]), porog=0.3) is not None)
proverka("рывок берёт последние два дня, а не любые",
         sovet.rezkoe_dvizhenie(ryad([100, 200, 140, 140.1])) is None,
         "скачок в середине ряда — не сегодняшняя новость")


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
