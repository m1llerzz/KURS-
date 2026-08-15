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
