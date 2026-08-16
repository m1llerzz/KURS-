# -*- coding: utf-8 -*-
"""Пересборка запасных данных в app/data.js из живых источников.

Зачем отдельный скрипт. Запасные значения в data.js нужны на случай, когда
недоступен и бот, и ЦБ. Но запас, набранный руками, устаревает молча и
однажды показывает человеку курс полугодовой давности как сегодняшний.

Поэтому запас не пишется руками никогда. Запускается это:

    py obnovit_zapas.py

Скрипт ходит в ЦБ и bank.uz, собирает настоящие числа и переписывает
в data.js три блока: SERVICES, KURSY_ZAPAS и HISTORY_ZAPAS. Всё остальное
в файле остаётся нетронутым.

Разумная частота — раз в месяц или перед показом продукта людям.
"""
import json
import os
import re
import sys

import rates

DATA_JS = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "data.js"))

# Страница под поиск. Её числа лежат прямо в разметке — иначе поисковику
# читать нечего, — и потому устаревают ровно так же, как запас в data.js.
KURS_HTML = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "kurs.html"))

# Карта сайта. Дата в ней говорит поисковику, стоит ли заходить снова.
SITEMAP = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "sitemap.xml"))

MESYACY_RU = ["января", "февраля", "марта", "апреля", "мая", "июня",
              "июля", "августа", "сентября", "октября", "ноября", "декабря"]
MESYACY_UZ = ["yanvar", "fevral", "mart", "aprel", "may", "iyun",
              "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"]


def _zamenit_blok(tekst, imya, novoe):
    """Меняет `window.ИМЯ = …;` целиком, считая вложенные скобки."""
    metka = "window." + imya + " = "
    nachalo = tekst.find(metka)
    if nachalo == -1:
        raise SystemExit("в data.js не найден блок " + imya)

    i = nachalo + len(metka)
    glubina = 0
    while i < len(tekst):
        s = tekst[i]
        if s in "[{":
            glubina += 1
        elif s in "]}":
            glubina -= 1
            if glubina == 0:
                i += 1
                break
        elif s == ";" and glubina == 0:
            break
        i += 1

    # Точку с запятой съедаем, только если она стоит сразу за значением.
    # Искать её дальше по файлу нельзя: один прогон без неё — и следующий
    # проглотит всё до следующей точки с запятой вместе с чужими блоками.
    # Ровно так и потерялся HISTORY_ZAPAS на живом прогоне.
    konec = i
    while konec < len(tekst) and tekst[konec] in " \t":
        konec += 1
    if konec < len(tekst) and tekst[konec] == ";":
        konec += 1
    else:
        konec = i

    # Точку с запятой возвращаем на место обязательно. Без неё файл ещё
    # работает — интерпретатор достраивает её сам, — но ровно до того дня,
    # когда следующая строка начнётся со скобки. Такую поломку ищут часами.
    return tekst[:nachalo] + metka + novoe + ";" + tekst[konec:]


def _chislo(z):
    """141.76 -> «141,76». В обеих странах дробную часть пишут запятой."""
    return ("%.2f" % float(z)).replace(".", ",")


def _summa(n):
    return "{:,}".format(int(round(n))).replace(",", " ")


def _data_slovom(iso, mesyacy, s_godom=True):
    d = str(iso)[:10].split("-")
    if len(d) != 3:
        return str(iso)
    den = "%d %s" % (int(d[2]), mesyacy[int(d[1]) - 1])
    return den + " " + d[0] if s_godom else den


def _period(ot, do, mesyacy, predlogi=False):
    """«с 18 июля по 16 августа 2026» — год один раз, в конце.

    Мелочь ровно до того момента, пока не прочитаешь «с 18 июля 2026 по
    16 августа 2026» глазами: именно из такого складывается ощущение,
    что страницу собрал робот, а числам на ней верить не стоит.
    """
    odin_god = str(ot)[:4] == str(do)[:4]
    nachalo = _data_slovom(ot, mesyacy, s_godom=not odin_god)
    konec = _data_slovom(do, mesyacy)
    if predlogi:
        return "с %s по %s" % (nachalo, konec)
    return "%s — %s" % (nachalo, konec)


def _obnovit_stranicu_poiska(snimok):
    """Переписывает числа в kurs.html по меткам data-zapas.

    Зачем не руками. Страница живёт годами и её никто не открывает —
    именно поэтому числа на ней однажды окажутся полугодовой давности, а
    заметит это первый же человек из поиска. Правило проекта простое:
    ни одного числа без даты и ни одного числа, набранного руками.

    Меток нет в файле — значит страницу переделали, и молча промолчать
    здесь нельзя: об этом говорится вслух.
    """
    if not os.path.exists(KURS_HTML):
        print("  kurs.html не найден — пропускаю", flush=True)
        return

    cb = snimok["cbu"]
    istoriya = snimok.get("history") or []
    kursy = [t["rub_uzs"] for t in istoriya]
    servisy = [s for s in (snimok.get("services") or []) if s.get("rate_rub_uzs")]

    znacheniya = {
        "kurs": _chislo(cb["rub_uzs"]),
        "data_ru": _data_slovom(istoriya[-1]["date"], MESYACY_RU),
        "data_uz": _data_slovom(istoriya[-1]["date"], MESYACY_UZ),
    }

    if kursy:
        mn, mx = min(kursy), max(kursy)
        znacheniya.update({
            "kurs_min": _chislo(mn),
            "kurs_max": _chislo(mx),
            "razmah_percent": _chislo((mx - mn) / mn * 100),
            "razmah_sum": _summa((mx - mn) * 50000),
            "period_ru": _period(istoriya[0]["date"], istoriya[-1]["date"],
                                 MESYACY_RU, predlogi=True),
            "period_uz": _period(istoriya[0]["date"], istoriya[-1]["date"],
                                 MESYACY_UZ),
        })

    if servisy:
        # Лучший курс, а не первый попавшийся: человек пойдёт туда, где
        # ему придёт больше, и сравнивать надо именно с этим.
        luchshiy = max(servisy, key=lambda s: s["rate_rub_uzs"])
        stavka = luchshiy["rate_rub_uzs"]
        znacheniya.update({
            "kurs_servisa": _chislo(stavka),
            "nacenka_percent": _chislo((cb["rub_uzs"] - stavka) / cb["rub_uzs"] * 100),
            "nacenka_sum": _summa((cb["rub_uzs"] - stavka) * 50000),
            "itog_50k": _summa(stavka * 50000),
        })

    with open(KURS_HTML, "r", encoding="utf-8") as f:
        tekst = f.read()

    zameneno, ne_naydeno = 0, []
    for metka, znachenie in znacheniya.items():
        shablon = re.compile(
            r'(<span data-zapas="%s">)[^<]*(</span>)' % re.escape(metka))
        tekst, skolko = shablon.subn(
            lambda m: m.group(1) + znachenie + m.group(2), tekst)
        if skolko:
            zameneno += skolko
        else:
            ne_naydeno.append(metka)

    with open(KURS_HTML, "w", encoding="utf-8") as f:
        f.write(tekst)

    print("  kurs.html: обновлено мест — %d" % zameneno, flush=True)
    if ne_naydeno:
        print("  ВНИМАНИЕ: в kurs.html нет меток: " + ", ".join(sorted(ne_naydeno)),
              flush=True)


def _obnovit_sitemap(data_iso):
    """Ставит в карту сайта дату последнего обновления страниц.

    Дата берётся из данных, а не с часов машины: пересобрать запас можно
    и в понедельник, а курс на странице будет за пятницу. Отметка о
    свежести, которая свежее самих чисел, — это обещание, которого
    страница не выполняет.
    """
    if not os.path.exists(SITEMAP):
        print("  sitemap.xml не найден — пропускаю", flush=True)
        return

    with open(SITEMAP, "r", encoding="utf-8") as f:
        tekst = f.read()

    tekst, skolko = re.subn(r"<lastmod>[^<]*</lastmod>",
                            "<lastmod>%s</lastmod>" % data_iso, tekst)

    if not skolko:
        print("  ВНИМАНИЕ: в sitemap.xml нет ни одного <lastmod>", flush=True)
        return

    with open(SITEMAP, "w", encoding="utf-8") as f:
        f.write(tekst)
    print("  sitemap.xml: дата обновлена в %d местах — %s" % (skolko, data_iso),
          flush=True)


def main():
    print("собираю живые данные…", flush=True)
    snimok = rates.snimok(s_istoriey=True)

    if not snimok.get("cbu"):
        raise SystemExit("ЦБ не ответил — запас не трогаю, старый честнее пустого")

    istoriya = snimok.get("history") or []
    servisy = snimok.get("services") or []
    print("  курс ЦБ:", snimok["cbu"]["rub_uzs"],
          "· сервисов:", len(servisy), "· точек истории:", len(istoriya), flush=True)

    if len(istoriya) < 7:
        raise SystemExit("истории меньше недели — вердикт по ней считать нельзя")

    with open(DATA_JS, "r", encoding="utf-8") as f:
        tekst = f.read()

    # Сервисы — как есть, но без служебных полей сборщика.
    chistye = []
    for s in servisy:
        c = dict(s)
        c.pop("source", None)
        chistye.append(c)
    tekst = _zamenit_blok(tekst, "SERVICES",
                          json.dumps(chistye, ensure_ascii=False, indent=2))

    cb = snimok["cbu"]
    tekst = _zamenit_blok(tekst, "KURSY_ZAPAS", json.dumps(
        {"usd_uzs": cb["usd_uzs"], "rub_uzs": cb["rub_uzs"],
         # Дата обязательна. Запас показывается человеку, когда бот спит,
         # и без даты это цифра без даты — ровно то, что правило проекта
         # запрещает. Раньше её здесь не было, и приложение в такие
         # минуты честно рисовало прочерк вместо дня.
         "date": cb.get("date") or (istoriya[-1]["date"] if istoriya else None),
         "zapas": True},
        ensure_ascii=False))

    # История — по две точки в строке, чтобы файл читался глазами.
    stroki = []
    for i in range(0, len(istoriya), 2):
        para = istoriya[i:i + 2]
        stroki.append("  " + " ".join(
            "{ date: '%s', rub_uzs: %s }," % (t["date"], t["rub_uzs"]) for t in para))
    tekst = _zamenit_blok(tekst, "HISTORY_ZAPAS",
                          "[\n" + "\n".join(stroki) + "\n]")

    with open(DATA_JS, "w", encoding="utf-8") as f:
        f.write(tekst)

    print("data.js обновлён настоящими числами.", flush=True)

    _obnovit_stranicu_poiska(snimok)
    _obnovit_sitemap(str(istoriya[-1]["date"])[:10])

    print("Не забудь поднять ?v= у скриптов в index.html — иначе Telegram "
          "будет отдавать старую версию из кеша.", flush=True)


if __name__ == "__main__":
    sys.exit(main())
