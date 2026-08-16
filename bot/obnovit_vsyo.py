# -*- coding: utf-8 -*-
"""Обновить всё, что стареет само: данные, страницу поиска, обложку.

    cd app/bot
    py obnovit_vsyo.py

Три вещи стареют независимо, и раньше каждая требовала своей команды:

    obnovit_zapas.py     запас в data.js и числа в kurs.html
    sobrat_oblozhku.py   картинка карточки при пересылке
    руками               поднять ?v= у скриптов в index.html

Последний шаг — ручной и самый забываемый, а без него Telegram будет
часами отдавать людям старую версию приложения. Здесь он делается сам.

Что НЕ делает этот скрипт: не заливает. Заливка — отдельное решение, и
перед ней положено прогнать `py proverit.py` из папки `app`.
"""
import os
import re
import subprocess
import sys

PAPKA = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.normpath(os.path.join(PAPKA, "..", "index.html"))


def podnyat_versiyu_skriptov():
    """`?v=37` -> `?v=38` у всех скриптов приложения.

    Telegram держит файлы мини-аппа в кеше часами. Без смены адреса
    человек открывает старую версию и видит вчерашние числа — при том
    что мы их только что обновили.

    Все скрипты обязаны получить ОДНУ версию: разъехавшись, часть файлов
    приедет из кеша старой, и приложение соберётся из двух разных.
    """
    if not os.path.exists(INDEX):
        print("  index.html не найден — версию не трогаю", flush=True)
        return None

    with open(INDEX, "r", encoding="utf-8") as f:
        tekst = f.read()

    versii = set(re.findall(r"\.js\?v=(\d+)", tekst))
    if not versii:
        print("  ВНИМАНИЕ: в index.html нет версий у скриптов", flush=True)
        return None

    if len(versii) > 1:
        print("  ВНИМАНИЕ: версии разъехались — %s. Ставлю общую."
              % ", ".join(sorted(versii)), flush=True)

    novaya = max(int(v) for v in versii) + 1
    tekst = re.sub(r"(\.js)\?v=\d+", r"\1?v=%d" % novaya, tekst)

    with open(INDEX, "w", encoding="utf-8") as f:
        f.write(tekst)

    print("  версия скриптов: %d" % novaya, flush=True)
    return novaya


def zapustit(imya, fayl):
    print("\n── %s ──" % imya, flush=True)
    gotovo = subprocess.run([sys.executable, fayl], cwd=PAPKA)
    if gotovo.returncode != 0:
        print("  НЕ ПОЛУЧИЛОСЬ: %s вернул %d" % (fayl, gotovo.returncode),
              flush=True)
        return False
    return True


def main():
    print("Обновляю всё, что стареет само.")

    # Порядок важен: обложка берёт число из тех же живых данных, а версию
    # в её адресе ставит сборщик — значит он должен отработать до того,
    # как мы поднимем версии скриптов.
    if not zapustit("данные приложения и страница поиска", "obnovit_zapas.py"):
        return 1
    if not zapustit("картинка карточки", "sobrat_oblozhku.py"):
        return 1

    print("\n── версия скриптов ──", flush=True)
    podnyat_versiyu_skriptov()

    print("""
Готово. Дальше руками, и в этом порядке:

    cd ..
    py proverit.py          есть красное — не заливать
    git add -A && git commit && git push
    py proverit_zhivoe.py   проверить, что видят люди
""", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
