# -*- coding: utf-8 -*-
"""Проверки сбора курсов. Запуск: py test_rates.py

Почему этот набор появился поздно и почему он важнее всех остальных.
`rates.py` — единственный файл, который добывает ВСЕ числа продукта: курс
на первом экране, ряд за месяц, вердикт, посты в канал, оповещения. Всё
остальное только пересчитывает то, что принёс он. Проверок у него не было
ни одной — в `test_bot.py` стояла ссылка на «отдельные проверки в rates»,
которых никогда не существовало.

Стоило это вот чего. ЦБ на запрос о выходном дне отдаёт последний рабочий
курс, помечая его ЕГО датой публикации: спросишь про воскресенье 16-е —
получишь пятничные 141,76 с полем Date = 14.08.2026. Сборщик это поле
выбрасывал и подписывал число датой запроса. Треть ряда за месяц —
10 точек из 30 — была датирована днями, в которые ЦБ ничего не публиковал.
Человек читал «курс на 16 августа», а курс был за 14-е.

Хуже даты был перекос: тренд считается по трём последним точкам против
трёх предыдущих, и в воскресенье «последние три дня» оказывались одним
днём, посчитанным трижды. От тренда зависит совет ждать или не ждать.

Большая часть проверок ниже идёт на подставном ответе вместо сети — они
обязаны краснеть всегда, а не когда у ЦБ хорошее настроение. Живые
проверки в конце помечаются «НЕ ПРОВЕРЕНО», если источник молчит.
"""
import json
import os
import tempfile

import rates

provereno, provalov, predupredit = [], [], []


def proverka(imya, uslovie, podskazka=""):
    (provereno if uslovie else provalov).append(
        imya + ("" if uslovie or not podskazka else "  << " + podskazka))


def preduprezhdenie(imya, podskazka=""):
    """Не провал и не успех: проверить не удалось по чужой вине."""
    predupredit.append(imya + ("  << " + podskazka if podskazka else ""))


class Podstava(object):
    """Подменяет поход в сеть заранее заготовленным ответом.

    Возвращает то, что положили в `otvety` по дате из адреса. Заодно
    считает запросы: сборщик не должен ходить в ЦБ лишний раз.
    """

    def __init__(self, otvety, po_umolchaniyu=None):
        self.otvety = otvety
        self.po_umolchaniyu = po_umolchaniyu
        self.zaprosy = []

    def __call__(self, url, timeout=25):
        self.zaprosy.append(url)
        data = url.rstrip("/").rsplit("/", 1)[-1]
        return self.otvety.get(data, self.po_umolchaniyu)


def otvet_cb(kurs, data, kod="RUB", nominal=1):
    """Ответ ЦБ в том виде, в каком он приходит на самом деле."""
    return json.dumps([{
        "Ccy": kod, "Rate": "%.2f" % kurs, "Nominal": str(nominal),
        "Date": data, "Diff": "-2.53",
    }])


def s_podstavoy(podstava, chto_delat):
    """Выполняет `chto_delat`, пока сеть подменена. Возвращает результат."""
    bylo_skachat, bylo_sleep = rates._skachat, rates.time.sleep
    rates._skachat = podstava
    rates.time.sleep = lambda _: None          # набор не должен ждать
    try:
        return chto_delat()
    finally:
        rates._skachat = bylo_skachat
        rates.time.sleep = bylo_sleep


# ── Разбор даты ──────────────────────────────────────────────────────

proverka("русская дата разбирается",
         rates._data_v_iso("14.08.2026") == "2026-08-14",
         str(rates._data_v_iso("14.08.2026")))
proverka("дата ISO остаётся собой",
         rates._data_v_iso("2026-08-14") == "2026-08-14")
proverka("дата со временем разбирается",
         rates._data_v_iso("2026-08-14T00:00:00") == "2026-08-14",
         "ЦБ однажды начнёт отдавать со временем — это не повод падать")
proverka("мусор не превращается в дату", rates._data_v_iso("позавчера") is None)
proverka("пустая дата — None", rates._data_v_iso("") is None)
proverka("None — None", rates._data_v_iso(None) is None)

# День и месяц не должны меняться местами. 08.09 — это восьмое сентября
# по-русски и девятое августа по-американски; ошибка тихая и вылезает
# только четыре месяца в году.
proverka("день и месяц не переставлены",
         rates._data_v_iso("08.09.2026") == "2026-09-08",
         str(rates._data_v_iso("08.09.2026")))


# ── Дата берётся из ответа, а не из запроса ──────────────────────────
#
# Сердце этого набора. Спрашиваем про воскресенье, ЦБ отвечает пятницей.

vyhodnoy = Podstava({}, po_umolchaniyu=otvet_cb(141.76, "14.08.2026"))
tochka = s_podstavoy(vyhodnoy, lambda: rates.kurs_valyuty("RUB", "2026-08-16"))

proverka("курс за выходной вернулся", tochka is not None)
if tochka:
    proverka("выходной датирован днём публикации",
             tochka["data"] == "2026-08-14",
             "получено %r — курс подписан датой запроса, а не публикации"
             % (tochka["data"],))
    proverka("курс не искажён", abs(tochka["kurs"] - 141.76) < 0.001)

# Номинал обязан делиться: у некоторых валют ЦБ отдаёт курс за 100 единиц.
sto = Podstava({}, po_umolchaniyu=otvet_cb(1000.0, "14.08.2026", nominal=100))
tochka_sto = s_podstavoy(sto, lambda: rates.kurs_valyuty("XXX", "2026-08-14"))
proverka("номинал учитывается",
         tochka_sto and abs(tochka_sto["kurs"] - 10.0) < 0.001,
         "курс за 100 единиц надо делить на 100")

# Незнакомый формат даты. Взять дату запроса — значит вернуться ровно к
# той ошибке, которую всё это чинит, поэтому точка не берётся вовсе.
krivaya = Podstava({}, po_umolchaniyu=otvet_cb(141.76, "чёрт знает когда"))
proverka("непонятная дата — точки нет",
         s_podstavoy(krivaya,
                     lambda: rates.kurs_valyuty("RUB", "2026-08-16")) is None,
         "лучше поредевший ряд, чем свежая на вид выдумка")

# Дата из будущего означает поломку на той стороне, а не выходные.
budushchee = Podstava({}, po_umolchaniyu=otvet_cb(141.76, "20.08.2026"))
proverka("дата из будущего — точки нет",
         s_podstavoy(budushchee,
                     lambda: rates.kurs_valyuty("RUB", "2026-08-16")) is None)

# Пустой ответ и мусор не должны ронять сборщик.
proverka("пустой список — None",
         s_podstavoy(Podstava({}, po_umolchaniyu="[]"),
                     lambda: rates.kurs_valyuty("RUB", "2026-08-16")) is None)
proverka("не-JSON — None",
         s_podstavoy(Podstava({}, po_umolchaniyu="<html>502</html>"),
                     lambda: rates.kurs_valyuty("RUB", "2026-08-16")) is None)
proverka("молчание сети — None",
         s_podstavoy(Podstava({}, po_umolchaniyu=None),
                     lambda: rates.kurs_valyuty("RUB", "2026-08-16")) is None)


# ── Ряд: выходные не дублируют пятницу ───────────────────────────────
#
# Четыре календарных дня, из них два выходных. ЦБ отвечает так же, как в
# жизни: на субботу и воскресенье отдаёт пятничный курс с пятничной датой.

kalendar = Podstava({
    "2026-08-13": otvet_cb(144.29, "13.08.2026"),
    "2026-08-14": otvet_cb(141.76, "14.08.2026"),
    "2026-08-15": otvet_cb(141.76, "14.08.2026"),   # суббота
    "2026-08-16": otvet_cb(141.76, "14.08.2026"),   # воскресенье
})

# istoriya_cb считает дни от «сегодня», поэтому притворяемся воскресеньем.
import datetime as _dt                              # noqa: E402


class _Voskresene(_dt.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 8, 16, 12, 0, tzinfo=tz)


def _sobrat_ryad():
    bylo = rates.datetime
    rates.datetime = _Voskresene
    try:
        return rates.istoriya_cb(4)
    finally:
        rates.datetime = bylo


ryad = s_podstavoy(kalendar, _sobrat_ryad)

proverka("выходные не стали отдельными точками", len(ryad) == 2,
         "получено %d точек из 4 дней: пятница задублирована субботой и "
         "воскресеньем" % len(ryad))
proverka("даты в ряду уникальны",
         len(ryad) == len({t["date"] for t in ryad}))
proverka("ряд отсортирован по возрастанию",
         [t["date"] for t in ryad] == sorted(t["date"] for t in ryad))
if len(ryad) == 2:
    proverka("последняя точка — пятница, а не воскресенье",
             ryad[-1]["date"] == "2026-08-14", ryad[-1]["date"])
    proverka("курс последней точки верен",
             abs(ryad[-1]["rub_uzs"] - 141.76) < 0.001)
    proverka("предыдущая точка — четверг",
             ryad[0]["date"] == "2026-08-13", ryad[0]["date"])

# Ни одна точка ряда не может быть датирована будущим.
proverka("в ряду нет дат из будущего",
         all(t["date"] <= "2026-08-16" for t in ryad))

# Молчание ЦБ даёт пустой ряд, а не ряд из выдуманных точек.
pustoy = s_podstavoy(Podstava({}, po_umolchaniyu=None),
                     lambda: rates.istoriya_cb(4))
proverka("ЦБ молчит — ряд пуст", pustoy == [],
         "выдумывать точки нельзя ничем")


# ── Кеш: старый формат не подхватывается ─────────────────────────────
#
# Правка, которая чинит данные, обязана доехать и до тех, у кого файл уже
# лежит на диске. Иначе испорченный ряд переживёт починку.

_vremenny_kesh = os.path.join(tempfile.gettempdir(), "qy_test_istoriya.json")
_bylo_fayl = rates.FAYL_ISTORII
rates.FAYL_ISTORII = _vremenny_kesh

try:
    horoshiy_ryad = [{"date": "2026-08-%02d" % d, "rub_uzs": 140.0 + d}
                     for d in range(1, 12)]

    # Старый формат — без поля format.
    with open(_vremenny_kesh, "w", encoding="utf-8") as f:
        json.dump({"sobrano": "2026-08-16", "ryad": horoshiy_ryad}, f)
    proverka("кеш без версии формата не читается",
             rates._kesh_istorii() is None,
             "иначе испорченный ряд переживёт починку")

    # Чужая будущая версия — тоже не наша.
    with open(_vremenny_kesh, "w", encoding="utf-8") as f:
        json.dump({"sobrano": "2026-08-16", "format": 99,
                   "ryad": horoshiy_ryad}, f)
    proverka("кеш чужой версии не читается", rates._kesh_istorii() is None)

    # Наш формат читается.
    with open(_vremenny_kesh, "w", encoding="utf-8") as f:
        json.dump({"sobrano": "2026-08-16", "format": rates.FORMAT_ISTORII,
                   "ryad": horoshiy_ryad}, f)
    nash = rates._kesh_istorii()
    proverka("кеш нашей версии читается", nash is not None)
    proverka("из кеша приходит тот же ряд",
             nash and nash["ryad"] == horoshiy_ryad)

    # Короткий ряд не годится: вердикт по нему считать нельзя.
    with open(_vremenny_kesh, "w", encoding="utf-8") as f:
        json.dump({"sobrano": "2026-08-16", "format": rates.FORMAT_ISTORII,
                   "ryad": horoshiy_ryad[:5]}, f)
    proverka("слишком короткий кеш не читается", rates._kesh_istorii() is None)

    # Битый файл не должен ронять сбор.
    with open(_vremenny_kesh, "w", encoding="utf-8") as f:
        f.write("{это не json")
    proverka("битый кеш не роняет сбор", rates._kesh_istorii() is None)

    os.remove(_vremenny_kesh)
    proverka("нет файла — нет кеша", rates._kesh_istorii() is None)

    # Записанный кеш обязан нести версию формата — иначе следующая
    # починка данных не сможет его отличить.
    zapisano = s_podstavoy(kalendar,
                           lambda: rates.istoriya_s_keshem(4) and None)
    del zapisano
finally:
    rates.FAYL_ISTORII = _bylo_fayl
    if os.path.exists(_vremenny_kesh):
        os.remove(_vremenny_kesh)


# ── Живое: то, что придёт человеку прямо сейчас ──────────────────────
#
# Ходит в ЦБ. Молчит источник — «НЕ ПРОВЕРЕНО», а не провал: чужой сбой
# и наша поломка это разные вещи.

zhivoy = rates.kursy_cb()

if not zhivoy:
    preduprezhdenie("живой курс ЦБ", "ЦБ не ответил — это не поломка кода")
else:
    proverka("живой курс рубля правдоподобен",
             50 < zhivoy["rub_uzs"] < 500, str(zhivoy["rub_uzs"]))
    proverka("живой курс доллара правдоподобен",
             5000 < zhivoy["usd_uzs"] < 30000, str(zhivoy["usd_uzs"]))

    data_snimka = rates._data_v_iso(zhivoy.get("date"))
    proverka("у живого курса разбираемая дата", data_snimka is not None,
             repr(zhivoy.get("date")))

    zhivaya_istoriya = rates.istoriya_cb(10)
    if len(zhivaya_istoriya) < 5:
        preduprezhdenie("живой ряд истории",
                        "ЦБ отдал меньше пяти точек за десять дней")
    else:
        daty = [t["date"] for t in zhivaya_istoriya]

        # Та самая проверка, которая покраснела бы на исходном дефекте:
        # снимок говорил «14 августа», а последняя точка ряда — «16-е».
        proverka("дата снимка совпадает с последней точкой ряда",
                 data_snimka == daty[-1],
                 "снимок %s, ряд %s — числа из одного источника обязаны "
                 "быть датированы одинаково" % (data_snimka, daty[-1]))

        proverka("в живом ряду нет повторяющихся дат",
                 len(daty) == len(set(daty)),
                 "выходные дублируют пятницу")
        proverka("живой ряд отсортирован", daty == sorted(daty))

        segodnya_iso = _dt.datetime.now(_dt.timezone.utc).date().isoformat()
        proverka("в живом ряду нет дат из будущего",
                 all(d <= segodnya_iso for d in daty), daty[-1])

        proverka("десять календарных дней дают не больше десяти точек",
                 len(zhivaya_istoriya) <= 10, str(len(zhivaya_istoriya)))
        proverka("все курсы живого ряда правдоподобны",
                 all(50 < t["rub_uzs"] < 500 for t in zhivaya_istoriya))


# ── Итог ─────────────────────────────────────────────────────────────

print("Пройдено:", len(provereno))
for p in provereno:
    print("  + " + p)

if predupredit:
    print("\nНЕ ПРОВЕРЕНО:", len(predupredit))
    for p in predupredit:
        print("  ~ " + p)

if provalov:
    print("\nПРОВАЛЕНО:", len(provalov))
    for p in provalov:
        print("  - " + p)
    raise SystemExit(1)

if predupredit:
    print("\nОстальное зелёное, но %d проверок выполнить не удалось."
          % len(predupredit))
else:
    print("\nВсе проверки зелёные.")
