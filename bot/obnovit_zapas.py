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
        {"usd_uzs": cb["usd_uzs"], "rub_uzs": cb["rub_uzs"], "zapas": True},
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
    print("Не забудь поднять ?v= у скриптов в index.html — иначе Telegram "
          "будет отдавать старую версию из кеша.", flush=True)


if __name__ == "__main__":
    sys.exit(main())
