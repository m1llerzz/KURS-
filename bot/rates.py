# -*- coding: utf-8 -*-
"""СБОР КУРСОВ — единственный источник правды для приложения.

Зачем этот файл существует. До него цифры в приложении были выдуманы, и
поправить их мог только человек, вручную, раз в неделю. Продукт, который
живёт свежестью данных, не может зависеть от того, нашёл ли кто-то время
во вторник. Здесь курсы собираются сами, каждый час.

Три источника, по убыванию надёжности:

    1. ЦБ Узбекистана  — официальный курс. Открытый API, ключ не нужен.
       Проверено 15.08.2026: отвечает, отдаёт USD и RUB.
    2. bank.uz         — курсы денежных переводов РФ→УЗ. Разбор страницы.
       Проверено 15.08.2026: Yubor 136, Avosend 136 при курсе ЦБ 141,76.
    3. ручной слой     — rates_manual.json рядом с этим файлом. Всё, что
       нельзя добыть машиной (замеры Видадия по чекам), кладётся туда и
       перекрывает автоматику. Пустой файл — нормальное состояние.

Правило, ради которого всё написано: НИ ОДНОЙ ВЫДУМАННОЙ ЦИФРЫ. Источник
молчит — способ не показывается. Пустая строка хуже отсутствующей.

Зависимостей нет: только стандартная библиотека. Так же, как у бота.
"""
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

PAPKA = os.path.dirname(os.path.abspath(__file__))
FAYL_RUCHNOY = os.path.join(PAPKA, "rates_manual.json")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")

# Некоторые узбекские сайты отдают цепочку сертификатов не полностью.
# Ронять из-за этого сбор курсов нельзя: данные публичные, подделывать их
# никому не выгодно, а без них приложение показывает пустой экран.
_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE


def _skachat(url, timeout=25):
    """Возвращает текст страницы или None. Никогда не бросает исключение."""
    zapros = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "*/*",
        "Accept-Language": "ru,en;q=0.9",
    })
    try:
        with urllib.request.urlopen(zapros, timeout=timeout, context=_CTX) as otvet:
            return otvet.read().decode("utf-8", "replace")
    except Exception as oshibka:
        print("[rates] не скачалось", url, repr(oshibka)[:160], flush=True)
        return None


def _teper():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# Узбекистан живёт в UTC+5, и курс ЦБ датируется ЕГО днём, а не нашим.
CHASOVOY_POYAS = timedelta(hours=5)


def segodnya_v_tashkente():
    """Какое сегодня число там, где публикуют курс.

    Считать «сегодня» по UTC нельзя, и это не придирка. С семи вечера по
    UTC в Ташкенте уже следующий день: ЦБ публикует курс за него, наш
    сборщик про этот день даже не спрашивает — и ряд заканчивается
    позавчерашним числом, пока текущий курс на экране уже завтрашний.
    Ровно так и поймано: 16 августа 20:00 UTC, курс за 17-е опубликован,
    в ряду последняя точка за 14-е.

    Тот же по сути дефект уже чинили в кеше истории (61). Место другое,
    причина одна: день продукта считается там, где живут его люди.
    """
    return (datetime.now(timezone.utc) + CHASOVOY_POYAS).date()


# ── 1. ЦБ Узбекистана ────────────────────────────────────────────────

def kursy_cb(data=None):
    """Официальные курсы. data в виде '2026-08-14' или None — на сегодня.

    Возвращает {'usd_uzs':…, 'rub_uzs':…, 'date':'14.08.2026'} или None.
    """
    # Витрина без даты отстаёт от архива в момент публикации. 28.08.2026 в
    # 00:20 по Ташкенту архив уже отдавал курс на 28-е (RUB 136.73), а витрина
    # всё ещё 27-е (139.74) — при том, что ряд истории строится по архиву.
    # Снимок и ряд разъезжались на сутки, и проверка «дата снимка совпадает с
    # последней точкой ряда» краснела.
    #
    # Поэтому сначала спрашиваем архив за сегодняшнее ташкентское число. Это
    # не подмена источника: тот же ЦБ, тот же эндпоинт, дата по-прежнему
    # берётся из ответа. Если за сегодня ЦБ не публиковал (выходной,
    # праздник) — архив промолчит, и мы откатимся на витрину, как было.
    if data is None:
        segodnya = kursy_cb(segodnya_v_tashkente().isoformat())
        if segodnya:
            return segodnya

    # Без даты адрес отдаёт сегодняшний срез, с датой обязателен кусок
    # «all/» — иначе ЦБ отвечает 404. Наступили на это на живом прогоне.
    hvost = ("all/" + data + "/") if data else ""
    syroe = _skachat("https://cbu.uz/ru/arkhiv-kursov-valyut/json/" + hvost)
    if not syroe:
        return None
    try:
        spisok = json.loads(syroe)
    except Exception:
        return None

    # Потолок даты — запрошенное число, а для витрины (её спрашивают без
    # даты) сегодняшнее ташкентское. Без потолка витрина принимала бы
    # любую дату, включая завтрашнюю: архив такое отвергает, и разойтись
    # двум дверям в один источник нельзя.
    return razobrat_kursy(spisok, data or segodnya_v_tashkente().isoformat())


def razobrat_kursy(spisok, zaprosheno=None):
    """Разбор ответа ЦБ. Числа на входе — числа на выходе, сети здесь нет.

    Вынесено из `kursy_cb` не ради красоты. Тот же ответ разбирает
    приложение в браузере (`CALC.razborKursaCB` в calc.js): бот один, он
    уже приостанавливался, и курс обязан доезжать до человека без него.
    Две реализации одного разбора — это два официальных курса на одном
    экране в тот день, когда они разойдутся. Пока разбор был заперт
    внутри сетевой функции, сверить их было нечем; теперь сверяет
    `test_parity.py` на живых ответах ЦБ.

    `zaprosheno` — дата, за которую спрашивали, или None для витрины.
    """
    if not isinstance(spisok, list) or not spisok:
        return None

    def nayti(kod):
        for v in spisok:
            if isinstance(v, dict) and v.get("Ccy") == kod:
                return v
        return None

    def kurs(v):
        # Номинал у большинства валют 1, но у некоторых 10 или 100.
        # Делить обязательно, иначе курс завышается на порядок.
        try:
            znachenie = float(v.get("Rate"))
            nominal = float(v.get("Nominal") or 1)
        except (TypeError, ValueError):
            return None
        if znachenie <= 0:
            return None
        return znachenie / (nominal or 1)

    zapis_usd, zapis_rub = nayti("USD"), nayti("RUB")
    if not zapis_usd or not zapis_rub:
        return None

    usd, rub = kurs(zapis_usd), kurs(zapis_rub)
    if not usd or not rub:
        return None

    # Дату берём из ответа, а не из системных часов: на выходных ЦБ отдаёт
    # пятничный курс, и подписать его субботой значит соврать о свежести.
    opublikovano = _data_v_iso(zapis_usd.get("Date"))
    if not opublikovano:
        # Формат даты сменился. Подставить дату запроса — вернуться ровно
        # к той ошибке, которую этот разбор и чинит.
        print("[rates] ЦБ прислал дату в незнакомом виде: %r"
              % (zapis_usd.get("Date"),), flush=True)
        return None

    # Обе валюты обязаны быть одного дня: из них выводится кросс-курс
    # рубль→доллар, и взятые за разные дни они дадут курс, которого не
    # было ни в один из них.
    if _data_v_iso(zapis_rub.get("Date")) != opublikovano:
        print("[rates] ЦБ отдал доллар и рубль за разные дни: %s и %s"
              % (zapis_usd.get("Date"), zapis_rub.get("Date")), flush=True)
        return None

    # Архив отдаёт прошлое. Дата позже запрошенной — это не «выходные», а
    # сломавшийся источник, и такому числу верить нельзя.
    if zaprosheno and opublikovano > str(zaprosheno)[:10]:
        print("[rates] ЦБ на %s ответил датой из будущего: %s"
              % (zaprosheno, opublikovano), flush=True)
        return None

    return {"usd_uzs": round(usd, 2), "rub_uzs": round(rub, 2),
            "date": opublikovano, "source": "cbu.uz"}


def _data_v_iso(syraya):
    """«14.08.2026» -> «2026-08-14». Не разобрали — None, без догадок.

    ЦБ пишет дату по-русски, а мы всюду держим ISO: строки этого вида
    сравниваются как числа, и сортировка истории не требует разбора.
    """
    if not syraya:
        return None
    tekst = str(syraya).strip()[:10]
    for shablon in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(tekst, shablon).date().isoformat()
        except ValueError:
            continue
    return None


def kurs_valyuty(kod, data):
    """Одна валюта на одну дату. Ответ — 340 байт против 25 КБ у «all»,
    а для истории нужен ровно рубль. Тридцать дней это девять килобайт,
    а не семьсот пятьдесят.

    Возвращает `{"kurs": 141.76, "data": "2026-08-14"}` или None.

    Дата в ответе — не та же, что в запросе, и это главное здесь. По
    выходным и праздникам ЦБ отдаёт последний рабочий курс, помечая его
    ЕГО датой публикации: спросишь про воскресенье 16-го — получишь
    пятничные 141,76 с полем Date = 14.08.2026. Раньше эта дата
    выбрасывалась, и число подписывалось датой запроса — то есть продукт
    сам сочинял, что курс свежий. Треть ряда за месяц была такой.
    """
    syroe = _skachat("https://cbu.uz/ru/arkhiv-kursov-valyut/json/%s/%s/" % (kod, data))
    if not syroe:
        return None
    try:
        spisok = json.loads(syroe)
        if not spisok:
            return None
        v = spisok[0]
        kurs = float(v["Rate"]) / (float(v.get("Nominal") or 1) or 1)
    except Exception:
        return None

    opublikovano = _data_v_iso(v.get("Date"))
    if not opublikovano:
        # Формат даты сменился. Взять дату запроса — значит вернуться
        # ровно к той ошибке, которую эта функция и чинит, поэтому точка
        # просто не берётся. Ряд поредеет, вердикт замолчит, и молчание
        # тут честнее свежей на вид цифры.
        print("[rates] ЦБ прислал дату в незнакомом виде: %r" % (v.get("Date"),),
              flush=True)
        return None

    # Дата публикации не может быть позже запрошенной: архив отдаёт
    # прошлое. Если такое пришло — это не наш случай «выходные», а
    # что-то сломалось на той стороне, и класть это в историю нельзя.
    if opublikovano > str(data)[:10]:
        print("[rates] ЦБ на %s ответил датой из будущего: %s" % (data, opublikovano),
              flush=True)
        return None

    return {"kurs": kurs, "data": opublikovano}


FAYL_ISTORII = os.path.join(PAPKA, "istoriya_kesh.json")

# Версия формата ряда. Поднимается, когда меняется СМЫСЛ точек, а не их
# вид. Кеш, записанный старой версией, не читается — иначе правка, которая
# чинит данные, не доедет до тех, у кого файл уже лежит на диске.
#
# 2 — точки датируются днём публикации ЦБ, а не днём запроса; выходные
#     больше не дублируют пятницу.
FORMAT_ISTORII = 2


def _kesh_istorii():
    """Ряд из кеша, если он нашего формата. Иначе None."""
    try:
        if not os.path.exists(FAYL_ISTORII):
            return None
        with open(FAYL_ISTORII, "r", encoding="utf-8") as f:
            kesh = json.load(f)
    except Exception:
        return None

    if kesh.get("format") != FORMAT_ISTORII:
        return None
    ryad = kesh.get("ryad") or []
    if len(ryad) < 7:
        return None
    return kesh


def istoriya_s_keshem(dney=30, data_kursa=None):
    """История с суточным кешем на диске.

    Зачем кеш. Курс ЦБ меняется раз в рабочий день, а снимок пересобирается
    раз в час. Без кеша это 720 запросов к чужому серверу в сутки за
    данными, которые обновляются один раз, — так себя не ведут, и однажды
    нас просто перестанут пускать.

    Кеш живёт на диске рядом с ботом. На Render диск эфемерный, и после
    перезапуска история соберётся заново — это нормально: она нужна раз
    в сутки, а не постоянно.

    `data_kursa` — дата свежего курса ЦБ (ISO). Если она новее последней
    точки в кеше, кеш пересобирается независимо от календаря.

    Зачем это понадобилось. Сутки считались по UTC, то есть новый день
    для кеша начинался в пять утра по Ташкенту, а ЦБ публикует курс
    ближе к десяти. Кеш успевал собраться ДО публикации и держал
    вчерашний ряд до следующего утра. Текущий курс при этом обновлялся
    раз в час и был свежим — то есть на экране стоял сегодняшний курс, а
    вердикт считался по ряду, который заканчивается вчера. Числа
    настоящие, даты честные, а сравниваются разные дни.
    """
    segodnya = segodnya_v_tashkente().isoformat()

    kesh = _kesh_istorii()
    if kesh and kesh.get("sobrano") == segodnya:
        poslednyaya = max((str(t.get("date") or "") for t in kesh["ryad"]),
                          default="")
        if not (data_kursa and str(data_kursa) > poslednyaya):
            return kesh["ryad"]
        print("[rates] ЦБ опубликовал курс за %s, а в кеше только по %s — "
              "пересобираю" % (data_kursa, poslednyaya), flush=True)

    ryad = istoriya_cb(dney)

    # Сеть подвела — отдаём вчерашний кеш, если он есть. Вердикт по
    # вчерашнему ряду честнее отсутствия вердикта: за сутки среднее
    # за месяц не меняется настолько, чтобы совет перевернулся.
    if len(ryad) < 7:
        if kesh:
            print("[rates] история не собралась, беру вчерашнюю", flush=True)
            return kesh["ryad"]
        return ryad

    try:
        vremenny = FAYL_ISTORII + ".tmp"
        with open(vremenny, "w", encoding="utf-8") as f:
            json.dump({"sobrano": segodnya, "format": FORMAT_ISTORII,
                       "ryad": ryad}, f, ensure_ascii=False)
        os.replace(vremenny, FAYL_ISTORII)
    except Exception as oshibka:
        print("[rates] кеш истории не записался:", repr(oshibka)[:120], flush=True)

    return ryad


def istoriya_cb(dney=30):
    """Курс рубля за последние N дней. Нужен для оповещений и для ответа
    на вопрос «сегодня хороший курс или подождать».

    ЦБ отдаёт по одной дате за запрос, поэтому ходим по дням. Это тридцать
    лёгких запросов раз в сутки — для открытого API без ограничений это
    ничто, но делаем с паузой, чтобы не выглядеть перебором.

    Ряд собирается ПО ДАТАМ ПУБЛИКАЦИИ, а не по дням календаря. За тридцать
    дней это около двадцати одной точки: выходные и праздники ЦБ не
    публикует и на такой запрос отдаёт последний рабочий курс.

    Почему не оставить дубли. Раньше пятничный курс ложился в ряд трижды —
    под пятницей, субботой и воскресеньем. Стоило это двух вещей. Первая:
    дата у числа становилась чужой, и человек читал «курс на 16 августа»,
    когда курс был за 14-е. Вторая, дороже: тренд считается по трём
    последним точкам против трёх предыдущих, и в воскресенье «последние
    три дня» оказывались одним днём, посчитанным трижды. От тренда зависит
    совет ждать или не ждать — то есть чужие деньги.
    """
    po_publikacii = {}
    segodnya = segodnya_v_tashkente()
    for shag in range(dney):
        den = (segodnya - timedelta(days=shag)).isoformat()
        tochka = kurs_valyuty("RUB", den)
        if tochka:
            # Один и тот же день приходит несколько раз — значение то же,
            # так что кто последний записал, неважно.
            po_publikacii[tochka["data"]] = round(tochka["kurs"], 2)
        time.sleep(0.12)
    return [{"date": d, "rub_uzs": k} for d, k in sorted(po_publikacii.items())]


# ── 2. bank.uz — курсы денежных переводов ────────────────────────────

# Сервисы на странице идут блоками «Название … NNN сум». Разметка у bank.uz
# меняется, поэтому цепляемся не за классы, а за саму пару «имя + число
# рядом со словом сум». Пережить смену вёрстки это помогает, гарантией
# не является — потому результат всегда проверяется на правдоподобие.
_IMENA_SERVISOV = [
    "Yubor", "Avosend", "Paysend", "Zolotaya Korona", "Золотая Корона",
    "Korona", "Unistream", "Юнистрим", "Contact", "KoronaPay",
    "Sberbank", "Сбербанк", "Tinkoff", "Тинькофф", "MoneyGram", "Western Union",
]


def _tekst_stranicy(html):
    bez = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    bez = re.sub(r"<style.*?</style>", " ", bez, flags=re.S | re.I)
    bez = re.sub(r"<!--.*?-->", " ", bez, flags=re.S)
    bez = re.sub(r"<[^>]+>", "\n", bez)
    bez = re.sub(r"&nbsp;?", " ", bez)
    bez = re.sub(r"[ \t]+", " ", bez)
    return bez


def perevody_bankuz():
    """Курсы переводов РФ→УЗ. Список словарей или пустой список."""
    html = _skachat("https://bank.uz/kursi-denezhnih-perevodov")
    if not html:
        return []

    tekst = _tekst_stranicy(html)

    # Работаем только с куском «Из РФ в Узбекистан»: ниже на странице
    # начинается обратное направление с другими курсами, и без границы
    # мы бы смешали два разных коридора в одну таблицу.
    nachalo = tekst.find("Из РФ в Узбекистан")
    if nachalo == -1:
        nachalo = 0
    konec = tekst.find("Из Узбекистана в", nachalo + 10)
    if konec == -1:
        konec = min(len(tekst), nachalo + 6000)
    kusok = tekst[nachalo:konec]

    naydeno = []
    # Одно и то же число не может принадлежать двум сервисам. На bank.uz
    # строка называется «Avosend (Paysend)», и наивный поиск заводил два
    # сервиса с одним курсом — приложение показывало выдуманного конкурента
    # самому себе. Ключ — позиция числа, а не имя.
    zanyatye_chisla = set()

    for imya in _IMENA_SERVISOV:
        mesto = re.search(re.escape(imya), kusok, re.I)
        if not mesto:
            continue

        # Смотрим ВСЕ числа в пределах четырёхсот символов после имени, а
        # не только ближайшее. Раньше бралось первое, и сервис, у которого
        # перед курсом стоит «лимит 1 000 000 сум» или «комиссия 0 сум»,
        # пропадал целиком и молча: первое число не курс, а до второго
        # дело не доходило. Пропавший сервис ничем не отличается от
        # несуществующего, и заметить это можно было, только сверив
        # страницу глазами.
        hvost = kusok[mesto.end():mesto.end() + 400]

        for m in re.finditer(r"([\d]+[.,]?[\d]*)\s*сум", hvost):
            try:
                kurs = float(m.group(1).replace(",", "."))
            except ValueError:
                continue

            # Курс рубля к суму живёт в коридоре примерно 100–200. Всё, что
            # вне его, — это не курс, а комиссия, лимит или номер телефона,
            # случайно оказавшийся рядом. Такое пропускаем и смотрим
            # следующее число.
            if not (80 <= kurs <= 250):
                continue

            # Первое же похожее на курс число — наше или ничьё. Если его
            # уже забрал сервис выше по странице, значит это его строка, а
            # у нас своего курса нет: на bank.uz строка называется
            # «Avosend (Paysend)», и оба имени видят одно число. Искать
            # дальше нельзя — так Paysend забирал курс следующего сервиса,
            # тот у следующего, и вся таблица разъезжалась на один шаг.
            pozicia = mesto.end() + m.start(1)
            if pozicia in zanyatye_chisla:
                break

            zanyatye_chisla.add(pozicia)
            naydeno.append({"name": imya, "rate_rub_uzs": kurs})
            break

    return naydeno


# ── 3. Ручной слой ───────────────────────────────────────────────────

def ruchnye():
    """Замеры, которые машиной не берутся: чеки, звонки, скриншоты.

    Формат — тот же, что у автоматических источников. Всё отсюда
    перекрывает автоматику по совпадению id.
    """
    if not os.path.exists(FAYL_RUCHNOY):
        return {"services": [], "banks": []}
    try:
        with open(FAYL_RUCHNOY, "r", encoding="utf-8") as f:
            d = json.load(f)
        return {"services": d.get("services") or [], "banks": d.get("banks") or []}
    except Exception as oshibka:
        print("[rates] ручной файл не читается:", repr(oshibka)[:160], flush=True)
        return {"services": [], "banks": []}


# ── Сборка снимка ────────────────────────────────────────────────────

def _id_iz_imeni(imya):
    return re.sub(r"[^a-z0-9]+", "-", imya.lower()).strip("-")


# Адреса сервисов. Только проверенные: угаданный адрес уводит человека
# в никуда, и это хуже, чем отсутствие кнопки.
#
# Партнёрские ссылки кладутся сюда же, в поле partner_url, КОГДА появятся
# программы. На порядок в списке они не влияют никогда — сверху всегда тот
# способ, где человеку придёт больше. Это правило проекта, не настройка.
# Что известно про сервисы сверх курса. bank.uz этого не публикует, а
# знать надо: человек, которому показали расчёт на сумму выше лимита,
# получит отказ уже в самом сервисе — и вернётся к нам с вопросом,
# зачем мы посчитали.
#
# Лимиты сняты с сайта avosend.com 16 августа 2026. Оговорка: страница
# могла отдать условия другого региона — сайт подставляет их по стране
# посетителя. Число правдоподобно, но проверяется вместе с курсом.
_SAYTY = {
    "avosend": {
        "url": "https://avosend.com/",
        "limit_per_operation": 200000,      # ₽ за один перевод
        "limit_v_sutki": 380000,            # ₽ и не больше пяти операций
        "limit_v_mesyac": 1500000,
        "fee_fixed": 29,                    # ₽, объявлена на сайте
        "istochnik_uslovij": "avosend.com, 16.08.2026",
    },
    "yubor": {
        "url": "https://yubor.ru/",
        # Лимиты объявлены в ДОЛЛАРАХ: от 100 до 1200 за перевод. В рубли
        # переведены по курсу с их же страницы (1 USD ≈ 88,3 ₽) и округлены
        # внутрь: лучше не показать доступный способ, чем показать
        # недоступный. Курс доллара плавает, поэтому границы с запасом.
        "limit_min": 9000,                  # ≈ $100
        "limit_per_operation": 100000,      # ≈ $1200
        "fee_fixed": 0,                     # «комиссия 0%», сверх курса не берут
        "istochnik_uslovij": "yubor.ru, 16.08.2026",
    },
}


def snimok(s_istoriey=True):
    """Полный набор данных для приложения.

    Ключевое поле — nacenka_percent у каждого сервиса: насколько курс
    перевода хуже официального. Это и есть продукт. Считается здесь, а не
    в приложении, потому что зависит от курса ЦБ на ту же дату, что и курс
    сервиса, — сводить их на клиенте значит однажды сравнить разные дни.
    """
    cb = kursy_cb()
    servisy = []
    banki = []

    if cb:
        for s in perevody_bankuz():
            nacenka = (cb["rub_uzs"] - s["rate_rub_uzs"]) / cb["rub_uzs"] * 100
            imya_id = _id_iz_imeni(s["name"])
            # Общее — снизу, известное про конкретный сервис — сверху.
            # Порядок именно такой: то, что мы прочитали на сайте самого
            # сервиса, точнее наших умолчаний, и затирать его нельзя.
            zapis = {
                "id": imya_id,
                "name": s["name"],
                "route": "A",              # сервис объявляет курс сам
                "corridors": ["RU-UZ"],
                "fee_fixed": 0,
                "fee_percent": 0,
                "rate_rub_uzs": s["rate_rub_uzs"],
                # Умолчание, а не факт: настоящий лимит бывает сильно
                # меньше. У Avosend, например, 200 000 за перевод — и
                # человек, которому мы посчитали миллион, получил бы
                # отказ уже в самом сервисе.
                "limit_per_operation": 1000000,
                "delivery_minutes": 60,
                "incoming_fee": 0,
                "checked_at": _teper(),
                "verified_by_receipt": False,
                "source": "bank.uz",
                # Комиссия на bank.uz не публикуется. Ставить ноль честно
                # только с оговоркой, и оговорка едет в приложение флагом:
                # итог по такому способу — потолок, а не точная цифра.
                "fee_unknown": True,
                "nacenka_percent": round(nacenka, 2),
            }
            zapis.update(_SAYTY.get(imya_id, {}))

            # Комиссия названа на сайте сервиса — значит итог больше не
            # верхняя граница, а точная цифра, и оговорку надо снять.
            if "fee_fixed" in _SAYTY.get(imya_id, {}):
                zapis["fee_unknown"] = False

            servisy.append(zapis)

    # Ручные данные последним словом: они с чеков, а чек сильнее сайта.
    r = ruchnye()
    for s in r["services"]:
        servisy = [x for x in servisy if x["id"] != s.get("id")]
        servisy.append(s)
    for b in r["banks"]:
        banki = [x for x in banki if x["id"] != b.get("id")]
        banki.append(b)

    return {
        "ok": bool(cb) and bool(servisy),
        "generated_at": _teper(),
        "cbu": cb,
        "services": servisy,
        "banks": banki,
        # Дату свежего курса передаём внутрь: если ЦБ уже опубликовал
        # сегодняшний, а в кеше только вчерашний ряд, кеш пересоберётся —
        # иначе на экране стоял бы сегодняшний курс при вердикте,
        # посчитанном по ряду, который заканчивается вчера.
        "history": (istoriya_s_keshem(30, _data_v_iso((cb or {}).get("date")))
                    if s_istoriey else []),
    }


if __name__ == "__main__":
    d = snimok(s_istoriey=False)
    print(json.dumps(d, ensure_ascii=False, indent=2))
