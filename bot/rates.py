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


# ── 1. ЦБ Узбекистана ────────────────────────────────────────────────

def kursy_cb(data=None):
    """Официальные курсы. data в виде '2026-08-14' или None — на сегодня.

    Возвращает {'usd_uzs':…, 'rub_uzs':…, 'date':'14.08.2026'} или None.
    """
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

    def nayti(kod):
        for v in spisok:
            if v.get("Ccy") == kod:
                nominal = float(v.get("Nominal") or 1)
                # Номинал у большинства валют 1, но у некоторых 10 или 100.
                # Делить обязательно, иначе курс завышается на порядок.
                return float(v["Rate"]) / (nominal or 1)
        return None

    usd, rub = nayti("USD"), nayti("RUB")
    if not usd or not rub:
        return None

    # Дату берём из ответа, а не из системных часов: на выходных ЦБ отдаёт
    # пятничный курс, и подписать его субботой значит соврать о свежести.
    data_otveta = None
    for v in spisok:
        if v.get("Ccy") == "USD":
            data_otveta = v.get("Date")
            break

    return {"usd_uzs": round(usd, 2), "rub_uzs": round(rub, 2),
            "date": data_otveta, "source": "cbu.uz"}


def kurs_valyuty(kod, data):
    """Одна валюта на одну дату. Ответ — 340 байт против 25 КБ у «all»,
    а для истории нужен ровно рубль. Тридцать дней это девять килобайт,
    а не семьсот пятьдесят.
    """
    syroe = _skachat("https://cbu.uz/ru/arkhiv-kursov-valyut/json/%s/%s/" % (kod, data))
    if not syroe:
        return None
    try:
        spisok = json.loads(syroe)
        if not spisok:
            return None
        v = spisok[0]
        return float(v["Rate"]) / (float(v.get("Nominal") or 1) or 1)
    except Exception:
        return None


def istoriya_cb(dney=30):
    """Курс рубля за последние N дней. Нужен для оповещений и для ответа
    на вопрос «сегодня хороший курс или подождать».

    ЦБ отдаёт по одной дате за запрос, поэтому ходим по дням. Это тридцать
    лёгких запросов раз в сутки — для открытого API без ограничений это
    ничто, но делаем с паузой, чтобы не выглядеть перебором.

    За выходные ЦБ отдаёт пятничный курс — он для этих дат официальный,
    и это не дубль, а факт. Пропущенные даты не выдумываем ничем.
    """
    itog = []
    segodnya = datetime.now(timezone.utc).date()
    for shag in range(dney):
        den = (segodnya - timedelta(days=shag)).isoformat()
        rub = kurs_valyuty("RUB", den)
        if rub:
            itog.append({"date": den, "rub_uzs": round(rub, 2)})
        time.sleep(0.12)
    itog.sort(key=lambda x: x["date"])
    return itog


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
        m = re.search(re.escape(imya) + r"[^\d]{0,400}?([\d]+[.,]?[\d]*)\s*сум", kusok, re.I)
        if not m:
            continue
        pozicia = m.start(1)
        if pozicia in zanyatye_chisla:
            continue
        try:
            kurs = float(m.group(1).replace(",", "."))
        except ValueError:
            continue
        # Курс рубля к суму живёт в коридоре примерно 100–200. Всё, что
        # вне его, — это не курс, а комиссия, лимит или номер телефона,
        # случайно оказавшийся рядом. Такое молча выбрасываем.
        if not (80 <= kurs <= 250):
            continue
        zanyatye_chisla.add(pozicia)
        naydeno.append({"name": imya, "rate_rub_uzs": kurs})

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
_SAYTY = {
    "avosend": {"url": "https://avosend.com/"},
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
            servisy.append(dict(_SAYTY.get(imya_id, {}), **{
                "id": imya_id,
                "name": s["name"],
                "route": "A",              # сервис объявляет курс сам
                "corridors": ["RU-UZ"],
                "fee_fixed": 0,
                "fee_percent": 0,
                "rate_rub_uzs": s["rate_rub_uzs"],
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
            }))

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
        "history": istoriya_cb(30) if s_istoriey else [],
    }


if __name__ == "__main__":
    d = snimok(s_istoriey=False)
    print(json.dumps(d, ensure_ascii=False, indent=2))
