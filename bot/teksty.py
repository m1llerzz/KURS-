# -*- coding: utf-8 -*-
"""Тексты для посева на сегодняшних числах — без бота.

    cd app/bot
    py teksty.py             без метки чата
    py teksty.py moskva1     с меткой: по ней видно, сколько людей пришло

Зачем это есть. Посев — единственный канал, который приводит людей, а
тексты для него умел выдавать только живой бот по команде `/tekst`. Бот
на Render приостановлен с 21 августа, и вместе с ним останавливался
посев: писать в чаты стало нечем. Здесь те же тексты, собранные тем же
кодом (`bot.sobrat_teksty_poseva`), — расходиться им негде.

Правила те же и остаются: числа только сегодняшние, а пост про выбор
сервиса не выдаётся, пока данные его вывод подтверждают не полностью.
Данных нет — не печатаем ничего: текст с выдуманным числом ловится
первым же читателем, который откроет cbu.uz.
"""
import os
import sys
import tempfile

# Токен не нужен — посылать отсюда некуда. Но `bot.py` без него не
# импортируется, и это правильно: запуск бота без токена — опечатка, а
# не работа. Проверки проекта поступают так же.
os.environ.setdefault("BOT_TOKEN", "0:teksty")

# Хранилище уводим во временный файл: печать текстов не должна трогать
# рабочую память бота — ни подписчиков, ни отметки о постах.
os.environ.setdefault(
    "HRANILISHCHE_FAYL",
    os.path.join(tempfile.gettempdir(), "qy-teksty-vremenno.json"))

import bot                                                     # noqa: E402

CHERTA = "─" * 62


def main():
    metka = sys.argv[1] if len(sys.argv) > 1 else ""

    print("собираю живые данные…", flush=True)
    dannye = bot.svezhie_dannye()
    sobrano = bot.sobrat_teksty_poseva(dannye or {}, metka)

    if not sobrano:
        print("\nДанных нет — тексты с выдуманными числами не выдаю.")
        return 1

    posty, propushcheno, chistaya, data_ru = sobrano

    for zagolovok, yazyk, tekst in posty:
        print("\n" + CHERTA)
        print("%s · %s" % (zagolovok, yazyk))
        print(CHERTA)
        print(tekst)

    print("\n" + CHERTA)
    print("Числа на %s. Метка чата: %s" % (data_ru, chistaya or "нет"))
    print("Метку задавать так: py teksty.py moskva1")
    if propushcheno:
        print("\nСегодня не выдал: " + "; ".join(propushcheno))
    return 0


if __name__ == "__main__":
    sys.exit(main())
