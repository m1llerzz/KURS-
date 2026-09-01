# -*- coding: utf-8 -*-
"""ВСЕ ПРОВЕРКИ ОДНОЙ КОМАНДОЙ.

    py proverit.py

Наборы проверок лежат в разных местах и запускаются по-разному. Помнить
столько команд при пяти часах в неделю невозможно — значит их перестанут
запускать, а тесты, которые не запускают, не существуют.

Что гоняется:

    bot/test_rates.py    сбор курсов: даты, ряд за месяц, кеш
    bot/test_sovet.py    логика вердикта «отправлять или подождать»
    bot/test_bot.py      тексты двух языков и живой /api/rates
    bot/test_parity.py   sovet.py и calc.js обязаны считать одинаково
    test.html            расчёт, старые дефекты, вердикт  (нужен node)
    test-app.js          сквозной прогон приложения       (нужен node+jsdom)

Порядок не случаен: `rates.py` идёт первым, потому что он добывает все
числа продукта, а остальные наборы только пересчитывают добытое. Красное
там объясняет красное во всех прочих.

Чего нет — о том говорится прямо. Пропущенная проверка НЕ считается
пройденной: молчаливый пропуск опаснее красной строки.

Есть красное — не заливать. Это правило проекта, а не пожелание.
"""
import os
import re
import subprocess
import sys

KORNI = os.path.dirname(os.path.abspath(__file__))
BOT = os.path.join(KORNI, "bot")

ZELYONY = "\033[32m"
KRASNY = "\033[91m"
ZHELTY = "\033[33m"
SEROY = "\033[90m"
SBROS = "\033[0m"

# Цвет — только живому терминалу. Журнал работы GitHub и перенаправление
# в файл читает не человек, и escape-последовательности там только мешают
# искать слова в выводе.
if not sys.stdout.isatty():
    ZELYONY = KRASNY = ZHELTY = SEROY = SBROS = ""

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


# Таблица «символ -> байт» ровно как у Windows: в CP1251 позиция 0x98 не
# назначена, Python на ней падает, а Windows отдаёт управляющий U+0098.
# Именно он и лежал в index.html сто семьдесят раз.
_V_BAYT = {}
for _bayt in range(256):
    try:
        _simvol = bytes([_bayt]).decode("cp1251")
    except UnicodeDecodeError:
        _simvol = chr(_bayt)
    _V_BAYT.setdefault(_simvol, _bayt)


def _krakozyabry(tekst):
    """Похоже ли, что текст прочитали как CP1251 и сохранили как UTF-8.

    Признак точный, а не на глаз. Разворачиваем перекодировку назад: если
    получилось и вышла кириллица, которой раньше не было, — текст испорчен.
    Обычный русский так не разворачивается: его байты в CP1251 почти
    никогда не образуют правильный UTF-8. Файл из одной латиницы
    разворачивается сам в себя, и разницы не возникает.
    """
    try:
        syroe = bytes(_V_BAYT[s] for s in tekst)
        razvernuto = syroe.decode("utf-8")
    except (KeyError, UnicodeDecodeError):
        return None
    if razvernuto == tekst:
        return None
    if not any("А" <= s <= "я" for s in razvernuto):
        return None
    return razvernuto


def proverit_krakozyabry():
    """Ни одного файла, испорченного двойной перекодировкой.

    Наступили на живом продукте: index.html пролежал таким неизвестно
    сколько. Байты при этом остаются правильным UTF-8, редактор не ругается,
    ни одна проверка не краснеет — испорчен только смысл. А лежали там
    `<title>`, `description` и `og:description`, то есть подпись в поисковой
    выдаче и карточка при пересылке ссылки в чат.
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
                with open(put, "r", encoding="utf-8") as f:
                    tekst = f.read()
            except (OSError, UnicodeDecodeError):
                continue
            if _krakozyabry(tekst):
                plohie.append(os.path.relpath(put, KORNI))

    imya_nabora = "перекодировка"
    if plohie:
        print("%s- %-28s текст испорчен CP1251%s" % (KRASNY, imya_nabora, SBROS))
        for p in plohie:
            print("      " + p)
        return "upalo"

    print("%s+ %-28s кракозябр нет%s" % (ZELYONY, imya_nabora, SBROS))
    return "proshlo"


def proverit_utverzhdeniya():
    """Утверждения о мире, которые нельзя набирать руками.

    Зачем. 22 августа 2026 записали правило: не утверждать, что курс у
    сервисов одинаковый — это было правдой и кончилось. Проверку на него
    поставили в `test_bot.py`, но она смотрит только тексты бота. Страницу
    под поиск она не видела, и `kurs.html` до 28 августа отдавал
    поисковикам «на открытых данных их два, и курс у них одинаковый» —
    при Yubor 131 и Avosend 134.

    Правило без проверки возвращается. Эта смотрит на все текстовые файлы
    продукта, а не на один.

    Ищем не слово, а утверждение. Голое «одинаков» стоит в CSS-комментариях
    про радиусы и карточки — проверка, которая кричит на невиновных, не
    лучше той, что молчит. Совпадением считается «курс» и «одинаков» в
    пределах одного предложения.
    """
    zapreshcheno = [
        (re.compile(r"курс[^.!?]{0,80}одинаков|одинаков[^.!?]{0,80}курс",
                    re.IGNORECASE),
         "утверждение «курс у сервисов одинаковый» — было правдой до "
         "22 августа 2026 и кончилось"),
        (re.compile(r"kurs[^.!?]{0,80}bir xil|bir xil[^.!?]{0,80}kurs",
                    re.IGNORECASE),
         "то же самое на узбекском"),
        # Обещанная частота обновления — такое же утверждение о мире, как
        # и «курс одинаковый», и оно уже кончилось однажды: ежечасно
        # собирал бот, бот приостановлен с 21 августа, а данные
        # пересобирает GitHub несколько раз в сутки. Обещать людям час
        # мы больше не можем — и не должны: частота зависит от чужой
        # машины, а обещание висит в выдаче и на экране.
        (re.compile(r"(обновля[^.!?]{0,40}|собира[^.!?]{0,40})кажд(ый|ые)\s+час"
                    r"|har\s+soatda\s+yig|soatda\s+bir\s+yangilan",
                    re.IGNORECASE),
         "обещание обновлять «каждый час» — частота зависит от чужой "
         "машины, и однажды она уже кончилась"),
    ]
    fayly = ["kurs.html", "index.html", "i18n.js", "bot/privet-uz.txt"]

    plohie = []
    for imya in fayly:
        put = os.path.join(KORNI, imya)
        if not os.path.exists(put):
            continue
        with open(put, "r", encoding="utf-8") as f:
            tekst = f.read()
        for shablon, pochemu in zapreshcheno:
            najdeno = shablon.search(tekst)
            if najdeno:
                plohie.append("%s: %s\n        нашлось: %s"
                              % (imya, pochemu,
                                 " ".join(najdeno.group(0).split())[:90]))

    if plohie:
        print("%s- %-28s запрещённое утверждение в тексте%s"
              % (KRASNY, "утверждения о мире", SBROS))
        for p in plohie:
            print("      " + p)
        return "upalo"

    print("%s+ %-28s запрещённых утверждений нет%s"
          % (ZELYONY, "утверждения о мире", SBROS))
    return "proshlo"


def proverit_metki_stranicy():
    """Числа на странице под поиск обязан переписывать скрипт — все.

    Зачем. Страницу под поиск не открывает никто из нас, и ломается она
    молча. Число, у которого нет метки `data-zapas`, скрипт не тронет — оно
    останется таким, каким его набрали при вёрстке, и застынет навсегда.
    Человек из поиска увидит позапрошлый курс рядом со свежей датой и
    уйдёт, а мы об этом не узнаем.

    Обратная сторона тоже проверяется: метка, объявленная скриптом, но
    отсутствующая на странице, означает, что страницу переделали и число
    перестало обновляться.
    """
    imya_nabora = "метки страницы поиска"
    stranica = os.path.join(KORNI, "kurs.html")
    if not os.path.exists(stranica):
        print("%s~ %-28s пропущено: страницы нет%s"
              % (ZHELTY, imya_nabora, SBROS))
        return "propushcheno"

    sys.path.insert(0, BOT)
    try:
        import obnovit_zapas
    except Exception as oshibka:
        print("%s~ %-28s пропущено: %s%s"
              % (ZHELTY, imya_nabora, repr(oshibka)[:60], SBROS))
        return "propushcheno"

    with open(stranica, "r", encoding="utf-8") as f:
        tekst = f.read()

    na_stranice = set(re.findall(r'data-zapas="([a-z_0-9]+)"', tekst))
    umeem = set(obnovit_zapas.METKI_STRANICY)

    plohie = []
    for metka in sorted(na_stranice - umeem):
        plohie.append("на странице есть метка «%s», а скрипт её не "
                      "заполняет — число застынет навсегда" % metka)
    for metka in sorted(umeem - na_stranice):
        plohie.append("скрипт заполняет метку «%s», а на странице её нет — "
                      "страницу переделали" % metka)

    if plohie:
        print("%s- %-28s метки разошлись%s" % (KRASNY, imya_nabora, SBROS))
        for p in plohie:
            print("      " + p)
        return "upalo"

    print("%s+ %-28s все %d меток заполняются%s"
          % (ZELYONY, imya_nabora, len(umeem), SBROS))
    return "proshlo"


def proverit_rabotu_github():
    """Работа GitHub опирается только на то, что есть в репозитории.

    Зачем. Данные пересобирает GitHub четыре раза в сутки, и его машина
    видит РОВНО то, что лежит в коммите. Шаг зависимостей был написан как
    `npm install` — а `package.json` в репозиторий не входит: он в
    `.gitignore` рядом с `node_modules`, потому что приложение обязано
    остаться статическими файлами, а корень репозитория Pages раздаёт как
    есть. На чистой машине npm не находит манифест и выходит с ошибкой.
    То есть работа падала бы при каждом запуске, и узнали бы мы об этом
    в тот день, когда наконец пройдёт заливка.

    Поймано клоном, а не чтением: репозиторий склонировали в пустую папку
    и прошли по шагам работы руками. Эта проверка ловит тот же класс
    вперёд: всё, на что работа опирается, обязано быть в коммите.
    """
    imya_nabora = "работа GitHub"
    papka = os.path.join(KORNI, ".github", "workflows")
    if not os.path.isdir(papka):
        print("%s- %-28s папки с работами нет%s" % (KRASNY, imya_nabora, SBROS))
        return "upalo"

    raboty = {}
    for imya in sorted(os.listdir(papka)):
        if imya.endswith((".yml", ".yaml")):
            with open(os.path.join(papka, imya), "r", encoding="utf-8") as f:
                raboty[imya] = f.read()

    if not raboty:
        print("%s- %-28s работ нет вовсе%s" % (KRASNY, imya_nabora, SBROS))
        return "upalo"

    try:
        v_repozitorii = set(subprocess.run(
            ["git", "ls-files"], cwd=KORNI, capture_output=True,
            text=True, encoding="utf-8", timeout=30).stdout.splitlines())
    except (OSError, subprocess.SubprocessError):
        print("%s~ %-28s пропущено: git не ответил%s"
              % (ZHELTY, imya_nabora, SBROS))
        return "propushcheno"

    plohie = []

    # 1. Каждый скрипт, который запускает любая из работ, обязан лежать в
    #    коммите. Ищем по всем файлам работ, а не по одному: вторая работа
    #    заводится позже первой, и проверка, знающая только про первую,
    #    молчит ровно там, где ошибиться проще всего.
    for imya, tekst in raboty.items():
        for stroka in tekst.splitlines():
            golaya = stroka.strip()
            if golaya.startswith("#"):
                continue                      # в комментариях объяснения
            for skript in re.findall(r"[\w./-]+\.py", golaya):
                chistyy = skript.lstrip("./")
                gde = [p for p in v_repozitorii if p.endswith(chistyy)]
                if not gde:
                    plohie.append("%s запускает %s, а его нет в репозитории"
                                  % (imya, skript))

    # 2. Манифеста npm в коммите нет — значит jsdom ставится по имени.
    #    Голый `npm install` на чистой машине падает с ENOENT.
    if "package.json" not in v_repozitorii:
        # Читаем ТОЛЬКО рабочие строки и во ВСЕХ работах: в комментариях
        # рядом объяснено, почему голого `npm install` тут больше нет, и
        # проверка, ловящая собственное объяснение, краснеет на исправной
        # работе. А имя файла работы может однажды измениться — проверка,
        # знающая его наизусть, замолчала бы вместе с ним.
        stavyat = [stroka.strip()
                   for tekst in raboty.values()
                   for stroka in tekst.splitlines()
                   if "npm install" in stroka
                   and not stroka.strip().startswith("#")]
        if not stavyat:
            plohie.append("работа не ставит jsdom вовсе — три набора "
                          "проверок из девяти пропустятся")
        for stroka in stavyat:
            if "jsdom" not in stroka:
                plohie.append(
                    "package.json не в репозитории, а работа ставит "
                    "зависимости по нему: %s" % stroka)

    if plohie:
        print("%s- %-28s работа опирается на то, чего нет%s"
              % (KRASNY, imya_nabora, SBROS))
        for p in plohie:
            print("      " + p)
        return "upalo"

    print("%s+ %-28s опирается только на коммит%s"
          % (ZELYONY, imya_nabora, SBROS))
    return "proshlo"


def main():
    print("Проверки проекта Qancha yetadi")
    print("=" * 58)

    net_node = not est_node()
    net_jsdom = not est_jsdom()

    itogi = [
        proverit_bom(),
        proverit_krakozyabry(),
        proverit_utverzhdeniya(),
        proverit_rabotu_github(),
        proverit_metki_stranicy(),
        zapustit("сбор курсов (rates.py)", [sys.executable, "test_rates.py"], BOT),
        zapustit("вердикт (sovet.py)", [sys.executable, "test_sovet.py"], BOT),
        zapustit("обложка и шрифты", [sys.executable, "test_oblozhka.py"], BOT),
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
