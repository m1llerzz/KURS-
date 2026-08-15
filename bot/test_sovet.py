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
