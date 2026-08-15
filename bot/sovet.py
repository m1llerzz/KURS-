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
"""

# Насколько сегодняшний курс должен отличаться от обычного, чтобы об этом
# вообще стоило говорить. Ниже порога разница тонет в комиссии, и совет
# «подожди» стоил бы человеку больше, чем принёс.
PORAG_ZAMETNOSTI = 1.0      # процент
PORAG_SILNYY = 3.0          # процент — тут уже стоит менять планы

# Сколько дней берём за «обычный курс». Тридцать: короче — шум отдельных
# дней, длиннее — в среднее лезет курс, к которому рынок уже не вернётся.
OKNO_DNEY = 30


def _srednee(znacheniya):
    return sum(znacheniya) / len(znacheniya) if znacheniya else None


def analiz(istoriya):
    """История вида [{'date': '2026-08-01', 'rub_uzs': 148.2}, …].

    Возвращает словарь с оценкой сегодняшнего курса или None, если данных
    не хватает. Порог — семь точек: на трёх днях «среднее» это не среднее,
    а случайность, и строить на нём совет человеку про его деньги нельзя.
    """
    if not istoriya or len(istoriya) < 7:
        return None

    ryad = sorted(istoriya, key=lambda x: x["date"])
    kursy = [x["rub_uzs"] for x in ryad]
    segodnya = kursy[-1]

    okno = kursy[-OKNO_DNEY:]
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

    return {
        "verdikt": verdikt,
        "segodnya": round(segodnya, 2),
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


def stoit_uvedomit(ocenka, proshlyy_verdikt=None):
    """Слать ли оповещение.

    Правило жёсткое и намеренно скупое: беспокоим только когда курс
    заметно ЛУЧШЕ обычного, то есть когда молчание стоило бы человеку
    денег. Плохой курс — не повод для сообщения: человек и так не пошлёт,
    а мы потратим единственный кредит доверия.

    Второе условие — вердикт должен смениться. Пять дней подряд писать
    «курс хороший» значит стать фоном, который отключают.
    """
    if not ocenka:
        return False
    if ocenka["verdikt"] not in ("otlichno", "horosho"):
        return False
    return ocenka["verdikt"] != proshlyy_verdikt


def vygoda_na_summe(ocenka, summa_rub):
    """Сколько сум даёт (или отнимает) сегодняшний курс против обычного."""
    if not ocenka or not summa_rub:
        return 0
    return round((ocenka["segodnya"] - ocenka["srednee_30"]) * summa_rub)
