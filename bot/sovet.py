# -*- coding: utf-8 -*-
"""СОВЕТНИК — отправлять сегодня или подождать.

Почему это главная функция продукта, а не украшение.

Замер 15.08.2026 по курсам ЦБ за 30 дней:

    размах курса рубля            9,49%   (155,22 → 141,76)
    курс перевода против ЦБ       4,06%   (136 против 141,76)
    разброс банков-получателей    0,84%   (замер 15.08, RATE-CHECK.md)

День отправки решает больше, чем выбор сервиса и банка вместе. На 50 000 ₽
это 673 000 сум против 288 000 и 55 000. Человек, который умеет выбрать
день, зарабатывает больше, чем человек, который умеет выбрать сервис.

И об этом ему не говорит никто: сервисы зарабатывают на объёме и
заинтересованы, чтобы он отправил сейчас.

Здесь только чистые функции: получают числа — возвращают вердикт.
Ни сети, ни файлов, ни Telegram. Поэтому проверяются построчно.

Про окна времени. «Неделя» и «месяц» здесь считаются по КАЛЕНДАРЮ, а не
по числу точек. Разница не теоретическая: ЦБ публикует курс по рабочим
дням, и за тридцать календарных дней приходит около двадцати одной точки.
Взять «последние семь точек» значит показать полторы недели и назвать это
неделей. Раньше эти способы совпадали лишь потому, что сборщик дублировал
пятничный курс под субботу и воскресенье, то есть ряд был сплошным ценой
неправды в датах.
"""
from datetime import date, datetime, timedelta, timezone


def _granica(posledniy_den, dney):
    """Дата, начиная с которой точка попадает в окно длиной `dney`.

    Окно включает сам последний день, поэтому шагаем назад на `dney - 1`.
    Дату не разобрали — None, и вызывающий откатывается на счёт по точкам:
    это хуже, но лучше, чем уронить вердикт целиком.
    """
    try:
        god, mesyac, den = (int(ch) for ch in str(posledniy_den)[:10].split("-"))
        return (date(god, mesyac, den) - timedelta(days=max(dney - 1, 0))).isoformat()
    except (ValueError, TypeError):
        return None


def _okno(ryad, dney):
    """Точки за последние `dney` календарных дней. Ряд уже отсортирован."""
    if not ryad:
        return []
    granica = _granica(ryad[-1]["date"], dney)
    if granica is None:
        return ryad[-dney:]
    return [t for t in ryad if str(t["date"])[:10] >= granica]

# Насколько сегодняшний курс должен отличаться от обычного, чтобы об этом
# вообще стоило говорить. Ниже порога разница тонет в комиссии, и совет
# «подожди» стоил бы человеку больше, чем принёс.
PORAG_ZAMETNOSTI = 1.0      # процент
PORAG_SILNYY = 3.0          # процент — тут уже стоит менять планы

# Меньше семи публикаций — «среднее» это не среднее, а случайность. Порог
# один и на ряд целиком, и на окно месяца. То же число живёт в calc.js под
# тем же именем, за совпадением следит test_parity.py.
MIN_TOCHEK = 7

# Сколько КАЛЕНДАРНЫХ дней берём за «обычный курс». Тридцать: короче — шум
# отдельных дней, длиннее — в среднее лезет курс, к которому рынок уже не
# вернётся. Точек внутри окажется около двадцати одной: выходные ЦБ не
# публикует, и выдумывать за них курс мы не станем.
OKNO_DNEY = 30

# Все вердикты, какие может выдать analiz(). Список нужен не здесь, а
# тем, кто подписывает их словами: у бота и приложения на каждый вердикт
# должна быть строка на обоих языках, иначе оповещение упадёт на
# KeyError у живого человека.
#
# Держим рядом с логикой, которая их порождает. Перечисленный отдельно
# отстаёт: добавят шестой вердикт — проверки о нём не узнают.
VSE_VERDIKTY = ("otlichno", "horosho", "obychno", "nize_obychnogo", "ploho")

# То же для советов. «stale» — не решение советника, а отказ советовать
# по старым данным; в словарях он обязан быть наравне с остальными.
VSE_SOVETY = ("otpravlyat", "mozhno_zhdat", "ne_zhdat", "obychno", "stale")

# Сколько календарных дней считать «неделей» для строки «за неделю курс
# изменился на столько-то».
NEDELYA_DNEY = 7


def _srednee(znacheniya):
    return sum(znacheniya) / len(znacheniya) if znacheniya else None


def deystvie(verdikt, trend):
    """Что человеку делать. Это НЕ то же самое, что вердикт.

    Ошибка, которую здесь чинили: раньше совет выводился только из
    отклонения от среднего. Курс ниже обычного — значит «подожди».

    На живых данных это оказалось вредным. Рубль падал весь месяц: каждый
    день был ниже среднего, каждый день приложение говорило «подожди», и
    каждый следующий день курс был ХУЖЕ предыдущего. Совет стоил человеку
    денег ровно столько раз, сколько он его послушал.

    Ждать имеет смысл только тогда, когда курс РАСТЁТ. В падающем рынке
    «подожди» — это худшее, что можно сказать: завтра будет меньше.

    Возвращает:
        otpravlyat   — сегодня хороший день, откладывать нечего
        mozhno_zhdat — курс ниже обычного И растёт: ожидание может окупиться
        ne_zhdat     — курс падает: чем дольше ждёшь, тем меньше придёт
        obychno      — ничего особенного, решать человеку
    """
    nizhe = verdikt in ("ploho", "nize_obychnogo")
    vyshe = verdikt in ("otlichno", "horosho")

    if trend == "padaet":
        # Падение перевешивает всё: завтра будет меньше, тянуть незачем.
        # Но если курс при этом ещё выше обычного — это не «не жди»,
        # а прямо «отправляй, пока хорошо».
        return "otpravlyat" if vyshe else "ne_zhdat"

    if trend == "rastet":
        # Растёт и при этом ниже обычного — единственный случай, когда
        # ожидание имеет смысл: рынок возвращается к своему уровню.
        return "mozhno_zhdat" if nizhe else "otpravlyat"

    # Курс стоит: решает только отклонение.
    if vyshe:
        return "otpravlyat"
    if nizhe:
        return "mozhno_zhdat"
    return "obychno"


def analiz(istoriya):
    """История вида [{'date': '2026-08-01', 'rub_uzs': 148.2}, …].

    Возвращает словарь с оценкой сегодняшнего курса или None, если данных
    не хватает. Порог — семь точек: на трёх днях «среднее» это не среднее,
    а случайность, и строить на нём совет человеку про его деньги нельзя.
    """
    if not istoriya or len(istoriya) < MIN_TOCHEK:
        return None

    ryad = sorted(istoriya, key=lambda x: x["date"])
    kursy = [x["rub_uzs"] for x in ryad]
    segodnya = kursy[-1]

    okno = [t["rub_uzs"] for t in _okno(ryad, OKNO_DNEY)]

    # Публикаций в окне должно хватать, чтобы называть его месяцем. Порог
    # тот же, что и у ряда целиком, и причина та же. Ряд может остаться
    # длинным, а окно — истончиться: приложение умеет добавить в ряд
    # сегодняшнюю точку от ЦБ само, и при непересобранном неделями запасе
    # «среднее за месяц» посчиталось бы по двум точкам трёхнедельной
    # давности. Молчать честнее.
    if len(okno) < MIN_TOCHEK:
        return None

    srednee = _srednee(okno)
    minimum, maksimum = min(okno), max(okno)

    otklonenie = (segodnya - srednee) / srednee * 100

    # Где сегодняшний курс внутри коридора месяца: 0 — худший день месяца,
    # 100 — лучший. Это понятнее процентов: «лучше 80% дней месяца».
    if maksimum > minimum:
        pozicia = (segodnya - minimum) / (maksimum - minimum) * 100
    else:
        pozicia = 50.0

    # Куда движется: сравниваем последние три дня с предыдущими тремя.
    # Не «вчера против сегодня» — один день это шум, а человек по нему
    # принял бы решение.
    trend = None
    if len(kursy) >= 6:
        svezhie = _srednee(kursy[-3:])
        proshlye = _srednee(kursy[-6:-3])
        if proshlye:
            izmenenie = (svezhie - proshlye) / proshlye * 100
            if izmenenie > 0.3:
                trend = "rastet"
            elif izmenenie < -0.3:
                trend = "padaet"
            else:
                trend = "stoit"

    # Вердикт. Он обязан быть честным в обе стороны: продукт, который
    # всегда говорит «отправляй», — это реклама, а не советник.
    if otklonenie >= PORAG_SILNYY:
        verdikt = "otlichno"        # курс заметно выше обычного
    elif otklonenie >= PORAG_ZAMETNOSTI:
        verdikt = "horosho"
    elif otklonenie <= -PORAG_SILNYY:
        verdikt = "ploho"           # заметно ниже — есть смысл подождать
    elif otklonenie <= -PORAG_ZAMETNOSTI:
        verdikt = "nize_obychnogo"
    else:
        verdikt = "obychno"

    # Сдвиг за неделю. «Курс падает» — это направление, а «за неделю на 2%»
    # это уже величина, по которой человек может решать. Одно без другого
    # не работает: направление без величины ни к чему не обязывает.
    # Точка отсчёта — последняя публикация НЕ ПОЗЖЕ чем неделю назад.
    # Не «восьмая с конца»: восьмая публикация назад это одиннадцать
    # календарных дней, и строка «за неделю» описывала бы полторы.
    nedelya = None
    nedelyu_nazad = _granica(ryad[-1]["date"], NEDELYA_DNEY + 1)
    if nedelyu_nazad is not None:
        rannie = [t for t in ryad if str(t["date"])[:10] <= nedelyu_nazad]
        bylo = rannie[-1]["rub_uzs"] if rannie else None
        if bylo:
            nedelya = round((segodnya - bylo) / bylo * 100, 2)
    elif len(kursy) >= 8 and kursy[-8]:
        nedelya = round((segodnya - kursy[-8]) / kursy[-8] * 100, 2)

    return {
        "verdikt": verdikt,
        "deystvie": deystvie(verdikt, trend),
        "nedelya_percent": nedelya,
        "segodnya": round(segodnya, 2),
        # Дата последнего курса. ЦБ не публикует по выходным, и в
        # понедельник «сегодняшний курс» — это курс за пятницу. Без даты
        # такое число становится ложью, а правило проекта прямое:
        # цифра без даты не показывается.
        "data": ryad[-1]["date"],
        "srednee_30": round(srednee, 2),
        "min_30": round(minimum, 2),
        "max_30": round(maksimum, 2),
        "otklonenie_percent": round(otklonenie, 2),
        "pozicia_percent": round(pozicia),
        "trend": trend,
        "tochek": len(okno),
        # Сколько человек потеряет или выиграет на каждую тысячу рублей
        # против обычного курса. Умножить на свою сумму умеет каждый,
        # а процент от абстрактного курса не чувствует никто.
        "raznica_na_1000_rub": round((segodnya - srednee) * 1000),
    }


# Сколько часов молчать после отправленного оповещения. Трое суток: это
# не про удобство рассылки, а про то, сколько человек готов терпеть от
# бота, которого он не просил писать часто.
PAUZA_CHASOV = 72


def _chasov_proshlo(kogda, teper=None):
    """Часы с момента `kogda` (строка ISO). Не разобрали — None."""
    if not kogda:
        return None
    tekst = str(kogda).strip().replace("Z", "+00:00")
    try:
        bylo = datetime.fromisoformat(tekst)
    except ValueError:
        return None
    teper = teper or datetime.now(timezone.utc)
    if bylo.tzinfo is None:
        bylo = bylo.replace(tzinfo=timezone.utc)
    if teper.tzinfo is None:
        teper = teper.replace(tzinfo=timezone.utc)
    return (teper - bylo).total_seconds() / 3600.0


def stoit_uvedomit(ocenka, proshlyy_verdikt=None, uvedomlen_v=None, teper=None):
    """Слать ли оповещение.

    Правило жёсткое и намеренно скупое: беспокоим только когда курс
    заметно ЛУЧШЕ обычного, то есть когда молчание стоило бы человеку
    денег. Плохой курс — не повод для сообщения: человек и так не пошлёт,
    а мы потратим единственный кредит доверия.

    Второе условие — вердикт должен смениться. Пять дней подряд писать
    «курс хороший» значит стать фоном, который отключают.

    Третье — трое суток тишины после прошлого письма. Одной смены вердикта
    мало: отклонение ходит вокруг порога, и «хорошо» с «отлично»
    сменяют друг друга через день. Формально каждый раз новый вердикт, а
    человек получает сообщение ежедневно и отключает бота на третий раз.
    Правило это было записано в документах с самого начала, но в коде его
    не было.
    """
    if not ocenka:
        return False
    if ocenka["verdikt"] not in ("otlichno", "horosho"):
        return False
    if ocenka["verdikt"] == proshlyy_verdikt:
        return False

    proshlo = _chasov_proshlo(uvedomlen_v, teper)
    if proshlo is not None and proshlo < PAUZA_CHASOV:
        return False
    return True


def vygoda_na_summe(ocenka, summa_rub):
    """Сколько сум даёт (или отнимает) сегодняшний курс против обычного."""
    if not ocenka or not summa_rub:
        return 0
    return round((ocenka["segodnya"] - ocenka["srednee_30"]) * summa_rub)


# ── Итоги периода: для постов в канал ────────────────────────────────
#
# Зачем отдельно от analiz(). Ежедневный пост отвечает на вопрос «что
# делать сегодня». Итог недели отвечает на другой: «что вообще
# произошло». Один и тот же формат каждый день читают неделю, потом
# перестают — канал, в котором нечего вспомнить, отписывают.
#
# Здесь только арифметика по ряду. Ни языка, ни Telegram.

def itog_perioda(istoriya, dney):
    """Что случилось с курсом за последние `dney` дней.

    Возвращает None, если точек меньше трёх: «максимум и минимум» по двум
    дням — это не итог периода, а два числа, и выдавать их за обзор
    значит врать формой.

    Даты лучшего и худшего дня возвращаются нарочно. «Курс ходил от 141
    до 155» — это статистика; «лучший день был 3 августа» — это то, что
    человек соотносит со своей зарплатой и своим переводом.

    `dney` — календарные дни, а не точки. Пятничный пост называется «итог
    недели», и семь последних публикаций ЦБ вместо семи дней превратили бы
    его в итог полутора недель, не изменив ни заголовка, ни вида.
    """
    if not istoriya:
        return None

    ryad = _okno(sorted(istoriya, key=lambda x: x["date"]), dney)
    if len(ryad) < 3:
        return None

    kursy = [x["rub_uzs"] for x in ryad]
    nachalo, konec = kursy[0], kursy[-1]

    luchshiy = max(ryad, key=lambda x: x["rub_uzs"])
    hudshiy = min(ryad, key=lambda x: x["rub_uzs"])

    izmenenie = (konec - nachalo) / nachalo * 100 if nachalo else 0.0

    return {
        # Длина окна в календарных днях — то, что стоит в заголовке поста.
        # Сколько внутри публикаций, говорит `tochek`: за неделю их обычно
        # пять, и путать одно с другим значит однажды написать «за 5 дней».
        "dney": dney,
        "tochek": len(ryad),
        "nachalo": round(nachalo, 2),
        "konec": round(konec, 2),
        "izmenenie_percent": round(izmenenie, 2),
        "max": round(luchshiy["rub_uzs"], 2),
        "min": round(hudshiy["rub_uzs"], 2),
        "max_data": luchshiy["date"],
        "min_data": hudshiy["date"],
        # Разница между лучшим и худшим днём периода на переводе 50 000 ₽.
        # Это и есть цена вопроса: ради неё пост пересылают.
        "razmah_na_50k": round((luchshiy["rub_uzs"] - hudshiy["rub_uzs"]) * 50000),
        # Сколько стоил бы сегодняшний перевод против лучшего дня периода.
        # Ноль означает, что лучший день — сегодня.
        "upushcheno_na_50k": round((luchshiy["rub_uzs"] - konec) * 50000),
    }


# Насколько курс должен дёрнуться за сутки, чтобы об этом стоило сказать
# отдельным постом. Обычный дневной шаг рубля к суму — доли процента;
# процент за день это уже событие, о котором человек хочет знать в тот же
# день, а не завтра утром.
PORAG_RYVKA = 1.0


def rezkoe_dvizhenie(istoriya, porog=PORAG_RYVKA):
    """Дёрнулся ли курс за сутки настолько, что это отдельная новость.

    Возвращает None, когда ничего не произошло, — и это основной случай.
    Молчание здесь важнее срабатывания: канал, который каждый день кричит
    «важно», перестают читать быстрее, чем канал, который молчит.
    """
    if not istoriya or len(istoriya) < 2:
        return None

    ryad = sorted(istoriya, key=lambda x: x["date"])
    vchera, segodnya = ryad[-2]["rub_uzs"], ryad[-1]["rub_uzs"]
    if not vchera:
        return None

    izmenenie = (segodnya - vchera) / vchera * 100
    if abs(izmenenie) < porog:
        return None

    return {
        "percent": round(izmenenie, 2),
        "napravlenie": "vverh" if izmenenie > 0 else "vniz",
        "vchera": round(vchera, 2),
        "segodnya": round(segodnya, 2),
        "na_50k": round((segodnya - vchera) * 50000),
        "data": ryad[-1]["date"],
        # Дата предыдущей точки. «Вчера» здесь было бы неправдой: между
        # двумя публикациями ЦБ могут лежать выходные, и предыдущий курс
        # окажется трёхдневной давности.
        "data_vchera": ryad[-2]["date"],
    }
