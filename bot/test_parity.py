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

import sovet

CALC_JS = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "calc.js"))


def ryad(znacheniya):
    return [{"date": "2026-08-%02d" % (i + 1), "rub_uzs": float(v)}
            for i, v in enumerate(znacheniya)]


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

print()
if rashozhdeniy:
    print("РАСХОЖДЕНИЙ:", rashozhdeniy)
    sys.exit(1)
print("Обе реализации считают одинаково на", len(NABORY), "наборах.")
