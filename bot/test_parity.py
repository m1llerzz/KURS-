# -*- coding: utf-8 -*-
"""Сверка двух реализаций вердикта: sovet.py и calc.js.

Зачем. Вердикт «отправлять сегодня или подождать» считается дважды: у бота
на Python (для оповещений) и в приложении на JavaScript (чтобы работать
без сети). Это сознательное дублирование, и у него одна цена — они могут
разойтись. Разойдясь, они скажут одному человеку два разных совета про
его деньги, и он перестанет верить обоим.

Поэтому обе реализации гоняются по одним и тем же числам и сверяются
поле в поле. Запуск: py test_parity.py  (нужен node)
"""
import json
import os
import subprocess
import sys

import rates
import sovet

CALC_JS = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "calc.js"))


def ryad(znacheniya):
    return [{"date": "2026-08-%02d" % (i + 1), "rub_uzs": float(v)}
            for i, v in enumerate(znacheniya)]


def ryad_dat(pary):
    """Ряд с настоящими датами — с дырами там, где ЦБ не публиковал."""
    return [{"date": d, "rub_uzs": float(k)} for d, k in pary]


# Настоящий август 2026, как его отдаёт ЦБ: двадцать одна публикация за
# тридцать календарных дней, выходные пропущены. Сплошные наборы выше
# такой ряд не заменяют — окна считаются по календарю, и разойтись две
# реализации могут ровно на дырах.
NASTOYASHCHIY_AVGUST = ryad_dat([
    ("2026-07-17", 155.22),
    ("2026-07-20", 153.24), ("2026-07-21", 152.53), ("2026-07-22", 152.09),
    ("2026-07-23", 152.88), ("2026-07-24", 153.75),
    ("2026-07-27", 153.87), ("2026-07-28", 153.49), ("2026-07-29", 153.29),
    ("2026-07-30", 151.46), ("2026-07-31", 150.44),
    ("2026-08-03", 150.42), ("2026-08-04", 149.48), ("2026-08-05", 147.42),
    ("2026-08-06", 146.37), ("2026-08-07", 146.19),
    ("2026-08-10", 145.21), ("2026-08-11", 144.64), ("2026-08-12", 143.93),
    ("2026-08-13", 144.29), ("2026-08-14", 141.76),
])


NABORY = {
    "ровный курс":        ryad([140] * 10),
    "резкий рост":        ryad([140] * 9 + [150]),
    "резкое падение":     ryad([150] * 9 + [140]),
    "мелкое отклонение":  ryad([140] * 9 + [140.5]),
    "ровно семь точек":   ryad([141, 142, 143, 142, 141, 140, 139]),
    "пила":               ryad([140, 145, 139, 148, 141, 150, 138, 147, 142, 144]),
    "живой август":       ryad([155.22, 155.22, 155.22, 153.24, 152.53, 152.09,
                                152.88, 153.75, 153.75, 153.75, 153.87, 153.49,
                                153.29, 151.46, 150.44, 150.44, 150.44, 150.42,
                                149.48, 147.42, 146.37, 146.19, 146.19, 146.19,
                                145.21, 144.64, 143.93, 144.29, 141.76, 141.76]),
    "длиннее окна":       ryad([200] * 10) + [
        {"date": "2026-09-%02d" % (i + 1), "rub_uzs": 140.0} for i in range(30)],
    "мало данных":        ryad([140] * 6),
    # Совет обязан совпадать в обе стороны: разные советы про одни и те же
    # деньги — худшее, что могут сделать бот и приложение вместе.
    "низкий и растущий":  ryad([160, 160, 160, 135, 136, 137, 140, 141, 142]),
    "высокий и падающий": ryad([140] * 6 + [152, 151, 150]),

    # Ряды с дырами. Пока сборщик дублировал пятницу под выходные, таких
    # не существовало, и обе реализации сходились по случайности.
    "настоящий август":   NASTOYASHCHIY_AVGUST,
    # Хвост длиной ровно в месяц плюс старьё за окном: обе реализации
    # обязаны одинаково решить, где кончается месяц.
    "старьё за окном":    ryad_dat(
        [("2026-06-%02d" % d, 200.0) for d in (1, 2, 3, 4, 5)]
    ) + NASTOYASHCHIY_AVGUST,
    # Неделя, разорванная выходными: строка «за неделю» обязана взять
    # публикацию не позже чем семь дней назад, а не восьмую с конца.
    "неделя через выходные": ryad_dat([
        ("2026-08-03", 150.0), ("2026-08-04", 150.5), ("2026-08-05", 151.0),
        ("2026-08-06", 151.5), ("2026-08-07", 152.0),
        ("2026-08-10", 145.0), ("2026-08-11", 144.0), ("2026-08-12", 143.0),
        ("2026-08-13", 142.0), ("2026-08-14", 141.0),
    ]),
    # Ряд длинный, а окно месяца тонкое: запас не пересобирали три недели,
    # и единственная свежая точка — сегодняшняя, добавленная приложением
    # из ЦБ. «Среднее за месяц» по двум старым публикациям и одной новой
    # это не среднее за месяц, и обе реализации обязаны промолчать.
    "тонкое окно при длинном ряде": ryad_dat([
        ("2026-07-01", 150.0), ("2026-07-02", 150.5), ("2026-07-03", 151.0),
        ("2026-07-06", 151.5), ("2026-07-07", 152.0), ("2026-07-08", 152.5),
        ("2026-07-09", 153.0), ("2026-07-10", 153.5),
        ("2026-08-20", 140.0), ("2026-08-21", 139.5), ("2026-09-15", 138.0),
    ]),
    # Дыра длиннее недели: сравнивать не с чем, и обе реализации обязаны
    # одинаково промолчать, а не подставить ближайшее подходящее число.
    "провал в данных":    ryad_dat([
        ("2026-07-01", 150.0), ("2026-07-02", 150.0), ("2026-07-03", 150.0),
        ("2026-07-06", 150.0), ("2026-07-07", 150.0), ("2026-07-08", 150.0),
        ("2026-08-13", 141.0), ("2026-08-14", 141.5),
    ]),
}

# ── JS ───────────────────────────────────────────────────────────────

skript = """
global.window = {};
require(%s);
const nabory = JSON.parse(process.argv[1]);
const itog = {};
for (const imya in nabory) {
  const o = global.window.CALC.sovet(nabory[imya]);
  if (!o) { itog[imya] = null; continue; }
  delete o.ryad;                       // ряд сверять незачем, это вход
  o.vygoda_50k = global.window.CALC.vygodaNaSumme(o, 50000);
  itog[imya] = o;
}
process.stdout.write(JSON.stringify(itog));
""" % json.dumps(CALC_JS.replace("\\", "/"))

try:
    gotovo = subprocess.run(
        ["node", "-e", skript, json.dumps(NABORY, ensure_ascii=False)],
        capture_output=True, text=True, encoding="utf-8", timeout=60)
except FileNotFoundError:
    print("node не найден — сверку выполнить нечем.")
    sys.exit(1)

if gotovo.returncode != 0:
    print("node упал:\n", gotovo.stderr[:2000])
    sys.exit(1)

js = json.loads(gotovo.stdout)

# ── Python ───────────────────────────────────────────────────────────

py = {}
for imya, dannye in NABORY.items():
    o = sovet.analiz(dannye)
    if o:
        o = dict(o)
        o["vygoda_50k"] = sovet.vygoda_na_summe(o, 50000)
    py[imya] = o

# ── Сверка ───────────────────────────────────────────────────────────

rashozhdeniy = 0
for imya in NABORY:
    a, b = py[imya], js.get(imya)

    if (a is None) != (b is None):
        print("РАСХОЖДЕНИЕ [%s]: python=%s js=%s" % (imya, a, b))
        rashozhdeniy += 1
        continue
    if a is None:
        print("  = %-20s оба молчат (данных мало)" % imya)
        continue

    plohie = []
    for pole in sorted(a):
        x, y = a[pole], b.get(pole)
        if isinstance(x, float) and isinstance(y, (int, float)):
            if abs(x - y) > 0.011:       # округление до сотых с двух сторон
                plohie.append("%s: py=%s js=%s" % (pole, x, y))
        elif x != y:
            plohie.append("%s: py=%r js=%r" % (pole, x, y))

    if plohie:
        rashozhdeniy += 1
        print("РАСХОЖДЕНИЕ [%s]" % imya)
        for p in plohie:
            print("     " + p)
    else:
        print("  = %-20s %-14s %-13s откл %+6.2f%%  выгода 50к: %s"
              % (imya, a["verdikt"], a.get("deystvie"),
                 a["otklonenie_percent"], a["vygoda_50k"]))


# ── Пороги, заданные числом в двух местах ────────────────────────────
#
# Часть правил живёт не в формуле, а константой — и потому не попадает в
# сверку выше. Их приходится сравнивать отдельно, иначе однажды поменяют
# одно из двух, и один человек получит разные советы в чате и в мини-аппе.

import re as _re                                            # noqa: E402

# Читаем ИСХОДНИКИ, а не импортируем: bot.py при импорте требует токен и
# выходит, а сверять две константы можно и не поднимая бота.
KORNI_ = os.path.dirname(os.path.abspath(__file__))


def _chislo_iz_fayla(put, shablon):
    """Число из исходника. None — не нашли или файла нет.

    Сравниваем как float: «30» и «30.0» — одно и то же число, и падать
    на этом было бы придиркой, а не проверкой.
    """
    try:
        with open(put, "r", encoding="utf-8") as f:
            najdeno = _re.search(shablon, f.read(), _re.M)
        return float(najdeno.group(1)) if najdeno else None
    except OSError:
        return None


PARY_KONSTANT = [
    # имя, файл+шаблон для Python, файл+шаблон для JS, чем грозит расхождение
    ("порог совета",
     ("bot.py", r"^PREDEL_SOVETA_DNEY = ([\d.]+)"),
     ("app.js", r"const PREDEL_SOVETA_DNEY = ([\d.]+)"),
     "по старым данным один будет советовать, а другой молчать"),
    ("порог заметности",
     ("sovet.py", r"^PORAG_ZAMETNOSTI = ([\d.]+)"),
     ("calc.js", r"const PORAG_ZAMETNOSTI = ([\d.]+)"),
     "один назовёт курс обычным, другой — хуже обычного"),
    ("порог сильного отклонения",
     ("sovet.py", r"^PORAG_SILNYY = ([\d.]+)"),
     ("calc.js", r"const PORAG_SILNYY = ([\d.]+)"),
     "«заметно хуже» и «просто хуже» разойдутся"),
    ("окно месяца",
     ("sovet.py", r"^OKNO_DNEY = ([\d.]+)"),
     ("calc.js", r"const OKNO_DNEY = ([\d.]+)"),
     "среднее будет считаться по разным отрезкам"),
    ("минимум публикаций",
     ("sovet.py", r"^MIN_TOCHEK = ([\d.]+)"),
     ("calc.js", r"const MIN_TOCHEK = ([\d.]+)"),
     "один замолчит на тонком ряде, другой посчитает среднее по трём точкам"),
    ("окно недели",
     ("sovet.py", r"^NEDELYA_DNEY = ([\d.]+)"),
     ("calc.js", r"const NEDELYA_DNEY = ([\d.]+)"),
     "строка «за неделю» покажет разные числа"),
]

for _imya_k, (_fayl_py, _shab_py), (_fayl_js, _shab_js), _chem in PARY_KONSTANT:
    _v_py = _chislo_iz_fayla(os.path.join(KORNI_, _fayl_py), _shab_py)
    _v_js = _chislo_iz_fayla(
        os.path.join(KORNI_, _fayl_js if _fayl_js.endswith(".py")
                     else os.path.join("..", _fayl_js)), _shab_js)

    if _v_py is None or _v_js is None:
        print("РАСХОЖДЕНИЕ [%s]" % _imya_k)
        print("     константа не найдена: py=%s js=%s" % (_v_py, _v_js))
        rashozhdeniy += 1
    elif _v_py != _v_js:
        print("РАСХОЖДЕНИЕ [%s]" % _imya_k)
        print("     py=%s js=%s — %s" % (_v_py, _v_js, _chem))
        rashozhdeniy += 1
    else:
        print("  = %-20s %s в обоих" % (_imya_k, _v_py))

# ── Разбор ответа ЦБ: тот же JSON двумя реализациями ─────────────────
#
# Курс приложение теперь спрашивает у ЦБ само, напрямую из браузера: бот
# один, он уже приостанавливался на неделю, и официальный курс обязан
# доезжать до человека без него. Значит один и тот же ответ cbu.uz
# разбирают двое — rates.razobrat_kursy и CALC.razborKursaCB. Разойдясь,
# они покажут два разных ОФИЦИАЛЬНЫХ курса, и это хуже, чем разные советы:
# официальный курс — то единственное, что человек может проверить сам.

OTVETY_CB = {
    "обычный день": ([
        {"Ccy": "USD", "Rate": "11801.23", "Nominal": "1", "Date": "28.08.2026"},
        {"Ccy": "RUB", "Rate": "136.73", "Nominal": "1", "Date": "28.08.2026"},
    ], "2026-08-31"),
    "номинал не единица": ([
        {"Ccy": "USD", "Rate": "11801.23", "Nominal": "1", "Date": "28.08.2026"},
        {"Ccy": "RUB", "Rate": "1367.30", "Nominal": "10", "Date": "28.08.2026"},
    ], "2026-08-31"),
    "выходной: курс пятницы": ([
        {"Ccy": "USD", "Rate": "11801.23", "Nominal": "1", "Date": "28.08.2026"},
        {"Ccy": "RUB", "Rate": "136.73", "Nominal": "1", "Date": "28.08.2026"},
    ], "2026-08-30"),
    "дата из будущего": ([
        {"Ccy": "USD", "Rate": "11801.23", "Nominal": "1", "Date": "05.09.2026"},
        {"Ccy": "RUB", "Rate": "136.73", "Nominal": "1", "Date": "05.09.2026"},
    ], "2026-08-31"),
    "незнакомая дата": ([
        {"Ccy": "USD", "Rate": "11801.23", "Nominal": "1", "Date": "позавчера"},
        {"Ccy": "RUB", "Rate": "136.73", "Nominal": "1", "Date": "позавчера"},
    ], "2026-08-31"),
    "без рубля": ([
        {"Ccy": "USD", "Rate": "11801.23", "Nominal": "1", "Date": "28.08.2026"},
        {"Ccy": "EUR", "Rate": "13000.00", "Nominal": "1", "Date": "28.08.2026"},
    ], "2026-08-31"),
    "курс нулём": ([
        {"Ccy": "USD", "Rate": "11801.23", "Nominal": "1", "Date": "28.08.2026"},
        {"Ccy": "RUB", "Rate": "0", "Nominal": "1", "Date": "28.08.2026"},
    ], "2026-08-31"),
    "валюты за разные дни": ([
        {"Ccy": "USD", "Rate": "11801.23", "Nominal": "1", "Date": "28.08.2026"},
        {"Ccy": "RUB", "Rate": "136.73", "Nominal": "1", "Date": "27.08.2026"},
    ], "2026-08-31"),
    "пустой ответ": ([], "2026-08-31"),
    "витрина без даты запроса": ([
        {"Ccy": "USD", "Rate": "11801.23", "Nominal": "1", "Date": "28.08.2026"},
        {"Ccy": "RUB", "Rate": "136.73", "Nominal": "1", "Date": "28.08.2026"},
    ], None),
}

skript_cb = """
global.window = {};
require(%s);
const nabory = JSON.parse(process.argv[1]);
const itog = {};
for (const imya in nabory) {
  itog[imya] = global.window.CALC.razborKursaCB(nabory[imya][0], nabory[imya][1]);
}
process.stdout.write(JSON.stringify(itog));
""" % json.dumps(CALC_JS.replace("\\", "/"))

gotovo_cb = subprocess.run(
    ["node", "-e", skript_cb, json.dumps(OTVETY_CB, ensure_ascii=False)],
    capture_output=True, text=True, encoding="utf-8", timeout=60)

if gotovo_cb.returncode != 0:
    print("node упал на разборе ответа ЦБ:\n", gotovo_cb.stderr[:2000])
    sys.exit(1)

js_cb = json.loads(gotovo_cb.stdout)

for _imya in OTVETY_CB:
    _spisok, _zaprosheno = OTVETY_CB[_imya]
    _py = rates.razobrat_kursy(_spisok, _zaprosheno)
    _js = js_cb.get(_imya)

    if _py != _js:
        print("РАСХОЖДЕНИЕ [разбор ЦБ: %s]" % _imya)
        print("     py=%r" % (_py,))
        print("     js=%r" % (_js,))
        rashozhdeniy += 1
    elif _py is None:
        print("  = разбор ЦБ: %-22s оба молчат" % _imya)
    else:
        print("  = разбор ЦБ: %-22s %s за %s" % (_imya, _py["rub_uzs"], _py["date"]))


print()
if rashozhdeniy:
    print("РАСХОЖДЕНИЙ:", rashozhdeniy)
    sys.exit(1)
print("Обе реализации считают одинаково на", len(NABORY),
      "наборах, разбирают ЦБ одинаково на", len(OTVETY_CB),
      "ответах, пороги совпадают.")
