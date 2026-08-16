# -*- coding: utf-8 -*-
"""ВСЕ ПРОВЕРКИ ОДНОЙ КОМАНДОЙ.

    py proverit.py

Пять наборов проверок лежат в разных местах и запускаются по-разному.
Помнить пять команд при пяти часах в неделю невозможно — значит их
перестанут запускать, а тесты, которые не запускают, не существуют.

Что гоняется:

    bot/test_sovet.py    логика вердикта «отправлять или подождать»
    bot/test_bot.py      тексты двух языков и живой /api/rates
    bot/test_parity.py   sovet.py и calc.js обязаны считать одинаково
    test.html            расчёт, старые дефекты, вердикт  (нужен node)
    test-app.js          сквозной прогон приложения       (нужен node+jsdom)

Чего нет — о том говорится прямо. Пропущенная проверка НЕ считается
пройденной: молчаливый пропуск опаснее красной строки.

Есть красное — не заливать. Это правило проекта, а не пожелание.
"""
import os
import subprocess
import sys

KORNI = os.path.dirname(os.path.abspath(__file__))
BOT = os.path.join(KORNI, "bot")

ZELYONY = "\033[32m"
KRASNY = "\033[91m"
ZHELTY = "\033[33m"
SEROY = "\033[90m"
SBROS = "\033[0m"

if os.name == "nt":
    # Windows-консоль понимает цвета только после явного включения.
    # Не вышло — работаем без цвета, это не повод падать.
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleMode(
            ctypes.windll.kernel32.GetStdHandle(-11), 7)
    except Exception:
        ZELYONY = KRASNY = ZHELTY = SEROY = SBROS = ""


def est_node():
    try:
        subprocess.run(["node", "--version"], capture_output=True, timeout=20)
        return True
    except Exception:
        return False


def est_jsdom():
    if not est_node():
        return False
    gotovo = subprocess.run(
        ["node", "-e", "require.resolve('jsdom')"],
        capture_output=True, cwd=KORNI, timeout=30)
    return gotovo.returncode == 0


# Прогон test.html без браузера: грузим calc.js и встроенный скрипт
# в jsdom и читаем итоговую строку со стенда. Открывать файл руками
# по-прежнему можно и нужно — здесь это для одной команды.
SKRIPT_TEST_HTML = r"""
const fs = require('fs'), path = require('path');
const { JSDOM } = require('jsdom');
const korni = process.argv[1];
const dom = new JSDOM(fs.readFileSync(path.join(korni, 'test.html'), 'utf8'),
                      { runScripts: 'outside-only' });
const w = dom.window;
w.eval(fs.readFileSync(path.join(korni, 'calc.js'), 'utf8'));
const vstroennye = Array.from(w.document.querySelectorAll('script'))
  .filter(s => !s.src).map(s => s.textContent).join('\n');
w.eval(vstroennye);
const provaleno = Array.from(w.document.querySelectorAll('#checks tbody tr'))
  .filter(tr => tr.querySelector('.fail'));
console.log(w.document.getElementById('itog').textContent);
provaleno.forEach(tr => console.log('  ПРОВАЛ: ' + tr.cells[0].textContent));
process.exit(provaleno.length ? 1 : 0);
"""


def zapustit(imya, komanda, papka, propustit_esli=None, prichina=""):
    if propustit_esli:
        print("%s~ %-28s пропущено: %s%s" % (ZHELTY, imya, prichina, SBROS))
        return "propushcheno"

    gotovo = subprocess.run(komanda, cwd=papka, capture_output=True,
                            text=True, encoding="utf-8", errors="replace")
    vyvod = (gotovo.stdout or "") + (gotovo.stderr or "")

    if gotovo.returncode == 0:
        # Показываем последнюю содержательную строку — обычно это итог.
        stroki = [s for s in vyvod.strip().splitlines() if s.strip()]
        itog = stroki[-1] if stroki else "готово"

        # Набор мог пройти, но часть проверок внутри выполнить не удалось —
        # чужой сервер не ответил. Это не провал и не успех, и объявлять
        # такой прогон полностью зелёным нельзя: молчаливый пропуск
        # опаснее красной строки. Ровно так две трети проверок приложения
        # не гонялись неделю, а сводка каждый раз говорила «всё хорошо».
        if "НЕ ПРОВЕРЕНО" in vyvod:
            print("%s~ %-28s %s%s" % (ZHELTY, imya, itog.strip(), SBROS))
            for stroka in vyvod.splitlines():
                if stroka.strip().startswith("~"):
                    print("      " + stroka.strip())
            return "propushcheno"

        print("%s+ %-28s %s%s" % (ZELYONY, imya, itog.strip(), SBROS))
        return "proshlo"

    print("%s- %-28s ПРОВАЛ%s" % (KRASNY, imya, SBROS))
    for stroka in vyvod.strip().splitlines():
        print("      " + stroka)
    return "upalo"


def proverit_bom():
    """Ни одного файла с меткой BOM в начале.

    Наступили на живом прогоне: редактор PowerShell дописывает в начало
    файла невидимые три байта, и Python отказывается такой файл читать —
    «invalid non-printable character U+FEFF» в первой строке, где на вид
    ничего нет. В HTML и JS ломается тише и потому опаснее.

    Проверка занимает миллисекунды и снимает целый класс поломок,
    которые ищут по полчаса.
    """
    plohie = []
    for papka, _, fayly in os.walk(KORNI):
        if "node_modules" in papka or "__pycache__" in papka or ".git" in papka:
            continue
        for imya in fayly:
            if not imya.endswith((".py", ".js", ".html", ".json", ".txt", ".md")):
                continue
            put = os.path.join(papka, imya)
            try:
                with open(put, "rb") as f:
                    if f.read(3) == b"\xef\xbb\xbf":
                        plohie.append(os.path.relpath(put, KORNI))
            except Exception:
                pass

    if plohie:
        print("%s- %-28s BOM в начале файла%s" % (KRASNY, "кодировка файлов", SBROS))
        for p in plohie:
            print("      " + p)
        return "upalo"

    print("%s+ %-28s BOM нигде нет%s" % (ZELYONY, "кодировка файлов", SBROS))
    return "proshlo"


def main():
    print("Проверки проекта Qancha yetadi")
    print("=" * 58)

    net_node = not est_node()
    net_jsdom = not est_jsdom()

    itogi = [
        proverit_bom(),
        zapustit("вердикт (sovet.py)", [sys.executable, "test_sovet.py"], BOT),
        zapustit("бот и /api/rates", [sys.executable, "test_bot.py"], BOT),
        zapustit("паритет py и js", [sys.executable, "test_parity.py"], BOT,
                 net_node, "не найден node"),
        zapustit("расчёт (test.html)",
                 ["node", "-e", SKRIPT_TEST_HTML, KORNI], KORNI,
                 net_jsdom, "нет node или jsdom (npm install jsdom)"),
        zapustit("приложение целиком", ["node", "test-app.js"], KORNI,
                 net_jsdom, "нет node или jsdom (npm install jsdom)"),
    ]

    print("=" * 58)
    upalo = itogi.count("upalo")
    propushcheno = itogi.count("propushcheno")
    proshlo = itogi.count("proshlo")

    if upalo:
        print("%sПРОВАЛЕНО НАБОРОВ: %d. Заливать нельзя.%s" % (KRASNY, upalo, SBROS))
        return 1

    if propushcheno:
        print("%sПройдено %d, пропущено %d.%s" % (ZHELTY, proshlo, propushcheno, SBROS))
        print("%sПропущенное не проверено. Поставь недостающее и прогони снова.%s"
              % (SEROY, SBROS))
        return 0

    print("%sВсе %d наборов зелёные. Заливать можно.%s" % (ZELYONY, proshlo, SBROS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
