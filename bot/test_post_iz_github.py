# -*- coding: utf-8 -*-
"""Проверки второй двери канала. Запуск: py test_post_iz_github.py

Ни сети, ни Telegram здесь нет: Render подставной, Telegram подставной,
курсы заготовлены. Проверяется то, что ломается тише всего.

ЧТО ИМЕННО СТОРОЖИМ:

    1. Render живой — публикатор молчит. Иначе канал получит два поста
       за утро, от бота и от нас.
    2. Долгое ожидание не срезано. Холодный старт Render — это минута
       молчания, и короткий срок прочитал бы её как смерть сервиса.
    3. Отметка ставится ДО отправки: сбой отправки стоит одного дня,
       повтор — канала.
    4. Ключи отметок годятся для памяти у Telegram. Ключ, не прошедший
       её правило, отвергается ВМЕСТЕ СО ВСЕЙ записью — то есть уносит
       и остальные отметки.
    5. Решение «какой пост сегодня» здесь не повторяется, а зовётся у
       бота. Две копии разошлись бы.
    6. Работа по расписанию идёт позже утреннего часа бота и не просит
       DATABASE_URL.
"""
import io
import os
import re
import tempfile
import types
import urllib.request
from datetime import datetime, timedelta, timezone

os.environ.setdefault("BOT_TOKEN", "0:proverka")

# Проверки не должны трогать боевой список подписчиков — см. test_bot.py.
_VREMENNYY = os.path.join(tempfile.gettempdir(), "qy_test_post_github.json")
os.environ["HRANILISHCHE_FAYL"] = _VREMENNYY
if os.path.exists(_VREMENNYY):
    os.remove(_VREMENNYY)

# Адрес заведомо глухой: если подмена сети где-то не сработает, проверка
# упрётся в отказ соединения, а не пойдёт стучаться в боевого бота.
os.environ["BOT_URL"] = "http://127.0.0.1:9"

import bot                # noqa: E402
import hranilishche       # noqa: E402
import pamyat_kanala      # noqa: E402
import post_iz_github     # noqa: E402
import sovet              # noqa: E402

PAPKA = os.path.dirname(os.path.abspath(__file__))
KORNI = os.path.dirname(PAPKA)

provereno, provalov = [], []


def proverka(imya, uslovie, podskazka=""):
    (provereno if uslovie else provalov).append(
        imya + ("" if uslovie or not podskazka else "  << " + str(podskazka)))


# ── Подставная сеть ──────────────────────────────────────────────────

class _Svyaz(object):
    """Ответ, который умеет то же, что ответ urlopen: код, тело, `with`."""

    def __init__(self, kod, telo):
        self._kod, self._telo = kod, telo

    def getcode(self):
        return self._kod

    def read(self):
        return self._telo

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Set(object):
    """Отвечает заготовленным по очереди и считает, сколько раз спросили.

    Последний ответ повторяется: так задаётся «отказывает всегда» одной
    строкой, а не списком из трёх одинаковых.
    """

    def __init__(self, *otvety):
        self.otvety = list(otvety)
        self.sprosheno = 0

    def __call__(self, zapros, timeout=None):
        self.sprosheno += 1
        chto = self.otvety[min(self.sprosheno - 1, len(self.otvety) - 1)]
        if isinstance(chto, Exception):
            raise chto
        return _Svyaz(*chto)


def _podmenit_set(set_):
    """Подменяет сеть только внутри публикатора, а не во всём Python."""
    post_iz_github.urllib = types.SimpleNamespace(
        request=types.SimpleNamespace(urlopen=set_,
                                      Request=urllib.request.Request))


def _json(telo):
    return (200, io.BytesIO(telo.encode("utf-8")).getvalue())


# ── 1. Спросить Render ───────────────────────────────────────────────

post_iz_github.PAUZA_SEKUND = 0     # ждать между попытками проверкам незачем

_zhivoy = '{"podpischikov": 3, "kanal_pishet": true, "kod": "1a44421", ' \
          '"opros_sekund_nazad": 12}'

_set = _Set(_json(_zhivoy))
_podmenit_set(_set)
_otvechaet, _chto = post_iz_github.sprosit_render()
proverka("живой Render узнаётся", _otvechaet is True, _chto)
proverka("живого спрашиваем один раз", _set.sprosheno == 1, _set.sprosheno)
proverka("в журнал идёт состояние бота, а не голое «жив»",
         "1a44421" in _chto and "канал пишет" in _chto, _chto)

_set = _Set(_json('{"kanal_pishet": false}'))
_podmenit_set(_set)
proverka("молчащий канал у живого бота виден в журнале",
         "канал НЕ пишет" in post_iz_github.sprosit_render()[1])

# Страница отказа Render приходит с его собственного края, и бот к ней
# отношения не имеет. Считать её ответом бота значит промолчать в день,
# когда бесплатные часы кончились, — ровно в тот, ради которого всё это.
_set = _Set(urllib.request.URLError("отказ"))
_podmenit_set(_set)
_otvechaet, _chto = post_iz_github.sprosit_render()
proverka("отказ сети — не ответ", _otvechaet is False, _chto)
proverka("прежде чем сдаться, спрашиваем все попытки",
         _set.sprosheno == post_iz_github.POPYTOK, _set.sprosheno)

_set = _Set((200, b"<html>Service Unavailable</html>"))
_podmenit_set(_set)
proverka("код 200 без JSON — не ответ бота",
         post_iz_github.sprosit_render()[0] is False)

# Ради этого случая попытки и заведены: бесплатный тариф усыпляет сервис,
# наш же запрос его будит, и первые полминуты он молчит. Прочитать этот
# старт как смерть — значит опубликовать вторым постом поверх бота.
_set = _Set(urllib.request.URLError("холодный старт"),
            urllib.request.URLError("холодный старт"),
            _json(_zhivoy))
_podmenit_set(_set)
proverka("проснувшийся на третьей попытке считается живым",
         post_iz_github.sprosit_render()[0] is True,
         "иначе холодный старт Render читается как его смерть")

proverka("ожидание не срезано",
         post_iz_github.ZHDAT_SEKUND >= 30 and post_iz_github.POPYTOK >= 2,
         "холодный старт Render — до минуты; короткий срок даст два поста")


# ── 2. Подставной Telegram ───────────────────────────────────────────

class _Telegram(object):
    """Помнит список команд канала и складывает отправленное в корзину."""

    def __init__(self, otpravka_udayotsya=True):
        self.komandy = {}
        self.poslano = []
        self.otpravka_udayotsya = otpravka_udayotsya

    def __call__(self, metod, telo=None, popytok=2):
        telo = telo or {}
        if metod == "getMyCommands":
            return {"ok": True, "result": [{"command": k, "description": z}
                                           for k, z in sorted(self.komandy.items())]}
        if metod == "setMyCommands":
            self.komandy = {z["command"]: z["description"]
                            for z in telo.get("commands") or []}
            return {"ok": True, "result": True}
        if metod == "sendMessage":
            if not self.otpravka_udayotsya:
                return {"ok": False, "error_code": 400,
                        "description": "подставной отказ отправки"}
            self.poslano.append(telo)
            return {"ok": True, "result": {"message_id": len(self.poslano)}}
        return {"ok": True, "result": {}}


# Ряд, на котором собираются все виды постов: месяц данных, последний
# день заметно ниже вчерашнего. Даты от сегодня — с постоянными пост
# однажды начал бы выходить с советом «данные устарели».
def _den_nazad(n):
    return (datetime.now() - timedelta(days=n)).strftime("%Y-%m-%d")


_kursy = [150 + (i % 5) - (i * 0.3) for i in range(29)] + [130.0]
_istoriya = [{"date": _den_nazad(len(_kursy) - 1 - i), "rub_uzs": v}
             for i, v in enumerate(_kursy)]
_DANNYE = {"sovet": sovet.analiz(_istoriya), "history": _istoriya}
_DATA_KURSA = _DANNYE["sovet"]["data"]


def _chasy_na(den):
    """Одиннадцать утра по Ташкенту в заданный день.

    Прибивать проверку к настоящим часам нельзя дважды. По часам:
    `utrenniy_post` до девяти утра молчит, и половина набора краснела бы
    по ночам на исправном коде. По календарю: вид поста зависит от числа
    и дня недели, и набор, живущий в сегодня, находит свои бомбы в тот
    день, когда они взрываются, — так 1 сентября покраснел исправный бот.
    """

    class _Chasy(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(den.year, den.month, den.day, 6, 0,
                            tzinfo=timezone.utc)

    return _Chasy


def _den_s_vidom(vid):
    """Ближайший день, в который выходит пост такого вида.

    Спрашиваем у самого продукта, а не считаем календарь заново: правило
    «первое число перебивает пятницу» живёт в `vid_posta_na_segodnya`, и
    вторая его копия однажды разойдётся с первой.
    """
    segodnya = datetime.now(timezone.utc).date()
    for sdvig in range(40):
        den = segodnya + timedelta(days=sdvig)
        if bot.vid_posta_na_segodnya(datetime(den.year, den.month,
                                              den.day, 11)) == vid:
            return den
    return None


def _prigotovit(otpravka_udayotsya=True, render_zhiv=False, den=None):
    """Чистая площадка: пустая память, подставной Telegram, наши часы."""
    telegram = _Telegram(otpravka_udayotsya)
    hranilishche._telegram = None
    bot.vyzov = telegram
    bot.svezhie_dannye = lambda *a, **k: _DANNYE
    post_iz_github.datetime = _chasy_na(
        den or datetime.now(timezone.utc).date())
    post_iz_github.sprosit_render = (
        lambda *a, **k: (render_zhiv, "подстава"))
    return telegram


_nastoyashchiy_vyzov = bot.vyzov
_nastoyashchie_dannye = bot.svezhie_dannye


# ── 3. Живой Render — молчим ─────────────────────────────────────────

_telegram = _prigotovit(render_zhiv=True)
_kod = post_iz_github.main()
proverka("при живом Render выходим зелёными", _kod == 0, _kod)
proverka("при живом Render не пишем ни строчки",
         _telegram.poslano == [],
         "иначе канал получит два поста за утро — от бота и от нас")


# ── 4. Нет секретов — дверь не поставлена, но работа зелёная ─────────

_bylo_kanal = os.environ.get("CHANNEL_ID", "")
os.environ["CHANNEL_ID"] = ""
_telegram = _prigotovit()
_sprosili = {"raz": 0}


def _schitat(*a, **k):
    _sprosili["raz"] += 1
    return (False, "подстава")


post_iz_github.sprosit_render = _schitat
_kod = post_iz_github.main()
proverka("без CHANNEL_ID работа не краснеет", _kod == 0, _kod)
proverka("без CHANNEL_ID Render даже не спрашиваем", _sprosili["raz"] == 0,
         "спрашивать некому и незачем: публиковать всё равно некуда")
proverka("без CHANNEL_ID ничего не отправлено", _telegram.poslano == [])
os.environ["CHANNEL_ID"] = _bylo_kanal or "-1001234567890"


# ── 5. Памяти нет — не публикуем вовсе ───────────────────────────────

_telegram = _prigotovit()
_nastoyashchaya_pamyat = hranilishche.pamyat_na_telegrame
hranilishche.pamyat_na_telegrame = lambda *a, **k: False
_kod = post_iz_github.main()
hranilishche.pamyat_na_telegrame = _nastoyashchaya_pamyat
proverka("без памяти не публикуем", _telegram.poslano == [],
         "без отметки, переживающей перезапуск, «ровно один раз» "
         "не гарантировать")
proverka("без памяти всё равно выходим зелёными", _kod == 0, _kod)


# ── 6. Render молчит — публикуем, и ровно один раз ───────────────────

# Все три вида поста, а не тот, что выпал на сегодня: у каждого своя
# отметка, и разойтись они могут поодиночке.
for _vid in ("den", "nedelya", "mesyac"):
    _den = _den_s_vidom(_vid)
    if _den is None:
        provalov.append("не нашёлся день с постом «%s»" % _vid)
        continue

    _telegram = _prigotovit(den=_den)
    post_iz_github.main()
    proverka("при молчащем Render пост «%s» уходит" % _vid,
             len(_telegram.poslano) == 1,
             "%s: отправлено %d" % (_den, len(_telegram.poslano)))

    if _telegram.poslano:
        _tekst = _telegram.poslano[0].get("text") or ""
        proverka("в посте «%s» нет незакрытых подстановок" % _vid,
                 "{" not in _tekst and "}" not in _tekst)
        proverka("пост «%s» на двух языках" % _vid, "· · ·" in _tekst)
        proverka("пост «%s» ушёл именно в канал" % _vid,
                 str(_telegram.poslano[0].get("chat_id")) ==
                 os.environ["CHANNEL_ID"])

    # Второй запуск в тот же день — то, ради чего вся память и заведена.
    post_iz_github.main()
    proverka("второй запуск за день молчит («%s»)" % _vid,
             len(_telegram.poslano) == 1,
             "отправлено %d — повтор в канале стоит подписчиков"
             % len(_telegram.poslano))

    proverka("отметка «%s» легла в память у Telegram" % _vid,
             any(k.startswith("post_") for k in _telegram.komandy),
             str(sorted(_telegram.komandy)))


# ── 7. Отправка сорвалась — но повтора не будет ──────────────────────
#
# Обычно правильно наоборот: не сделали — не запомнили, попробуем позже.
# Здесь ошибка обязана играть в сторону молчания. Сбой отправки стоит
# одного пропущенного дня, повтор — канала.

_telegram = _prigotovit(otpravka_udayotsya=False,
                        den=_den_s_vidom("den"))
post_iz_github.main()
_otmetki_posle_sboya = dict(_telegram.komandy)
proverka("сорванная отправка всё равно отмечена",
         any(k.startswith("post_") for k in _otmetki_posle_sboya),
         "иначе следующий запуск отправит тот же пост заново")

_telegram.otpravka_udayotsya = True
post_iz_github.main()
proverka("после сорванной отправки сегодня уже молчим",
         _telegram.poslano == [],
         "молчание стоит одного дня, повтор — канала")

bot.vyzov = _nastoyashchiy_vyzov
bot.svezhie_dannye = _nastoyashchie_dannye
hranilishche._telegram = None


# ── 8. Ключи отметок годятся для памяти у Telegram ───────────────────
#
# Ключ, не прошедший правило Telegram, отвергается ВМЕСТЕ СО ВСЕЙ
# записью — то есть уносит с собой и остальные отметки. Проверяем все
# четыре, которыми пользуется `utrenniy_post`, на настоящих значениях.

_segodnya = datetime.now(timezone.utc) + timedelta(hours=5)
for _kluch, _znachenie in (
        ("post_den", _DATA_KURSA),
        ("post_nedelya", "%d-%02d" % _segodnya.isocalendar()[:2]),
        ("post_mesyac", _segodnya.strftime("%Y-%m")),
        ("kurs_osveshchen", _DATA_KURSA)):
    proverka("отметка «%s» ложится в память у Telegram" % _kluch,
             pamyat_kanala.prigoden(_kluch, _znachenie),
             "%s=%s — Telegram отвергнет ВСЮ запись, включая чужие отметки"
             % (_kluch, _znachenie))


# ── 9. Один код на две двери ─────────────────────────────────────────

_ishodnik = io.open(os.path.join(PAPKA, "post_iz_github.py"),
                    encoding="utf-8").read()
_delo = "\n".join(s for s in _ishodnik.splitlines()
                  if not s.strip().startswith("#"))

proverka("публикатор зовёт решение бота", "bot.utrenniy_post(" in _delo)
proverka("публикатор не решает сам, какой сегодня пост",
         "sobrat_post(" not in _delo,
         "вторая копия решения разойдётся с первой")
proverka("публикатор не отправляет сообщения мимо бота",
         "sendMessage" not in _delo,
         "отправка живёт в одном месте — в _opublikovat")

# Ищем ОБРАЩЕНИЕ к переменной, а не слово: в шапке файла объяснено, почему
# DATABASE_URL здесь не заводится, и проверка на голом слове краснела бы
# на собственном объяснении.
proverka("публикатор не читает DATABASE_URL",
         re.search(r"environ[^\n]*DATABASE_URL", _ishodnik) is None,
         "это полный доступ к данным подписчиков")


# ── 10. Бот забирает чужие отметки перед решением о посте ────────────

_bot_ishodnik = io.open(os.path.join(PAPKA, "bot.py"), encoding="utf-8").read()
_chasovoy = _bot_ishodnik.split("def chasovoy_uvedomleniy(")[-1]
_chasovoy = _chasovoy.split("\ndef ")[0]
_chasovoy_delo = "\n".join(s for s in _chasovoy.splitlines()
                           if not s.strip().startswith("#"))

proverka("часовой проход забирает чужие отметки",
         "perenesti_otmetki(" in _chasovoy_delo,
         "иначе проснувшийся бот повторит пост, сделанный работой GitHub")
proverka("отметки забираются ДО решения о посте",
         ("perenesti_otmetki(" in _chasovoy_delo
          and _chasovoy_delo.index("perenesti_otmetki(")
          < _chasovoy_delo.index("utrenniy_post(")),
         "после решения они уже не спасают — пост ушёл")


# ── 11. Работа по расписанию ─────────────────────────────────────────

_rabota = os.path.join(KORNI, ".github", "workflows", "post-v-kanal.yml")
proverka("работа по расписанию есть", os.path.exists(_rabota), _rabota)

if os.path.exists(_rabota):
    _yml = io.open(_rabota, encoding="utf-8").read()
    # Читаем только рабочие строки: в комментариях рядом объяснено,
    # почему DATABASE_URL здесь нет, и проверка на голом слове покраснела
    # бы на собственном объяснении.
    _yml_delo = "\n".join(s for s in _yml.splitlines()
                          if not s.strip().startswith("#"))

    _chasy = []
    for _stroka in re.findall(r"cron:\s*'([^']+)'", _yml_delo):
        _polya = _stroka.split()
        if len(_polya) >= 2:
            _chasy += [int(c) for c in _polya[1].split(",") if c.isdigit()]

    proverka("расписание задано", bool(_chasy), _yml_delo[:200])
    # Бот пишет сам с девяти утра по Ташкенту, то есть с 4:00 UTC. Работа,
    # вставшая раньше, отняла бы у него его же пост.
    proverka("работа идёт позже утреннего часа бота",
             all(c >= 4 for c in _chasy),
             "часы UTC: %s; девять утра в Ташкенте — это 4:00 UTC" % _chasy)
    proverka("работа просит оба секрета",
             "secrets.BOT_TOKEN" in _yml_delo and "secrets.CHANNEL_ID" in _yml_delo)
    # Опять же обращение, а не слово: в шапке работы объяснено, почему
    # этого секрета здесь нет. Ищем и сам секрет, и переменную окружения
    # с таким именем — завести его можно двумя способами.
    proverka("работа не заводит DATABASE_URL",
             "secrets.DATABASE_URL" not in _yml
             and not re.search(r"^\s*DATABASE_URL\s*:", _yml_delo, re.M),
             "полный доступ к данным подписчиков в публичном репозитории")
    proverka("работа запускает публикатор", "post_iz_github.py" in _yml_delo)
    proverka("два запуска работы не идут разом",
             "concurrency" in _yml_delo,
             "иначе оба прочтут пустую отметку до того, как её поставит первый")


# ── Итог ─────────────────────────────────────────────────────────────

print("Пройдено:", len(provereno))
for p in provereno:
    print("  + " + p)

if provalov:
    print("\nПРОВАЛЕНО:", len(provalov))
    for p in provalov:
        print("  - " + p)
    raise SystemExit(1)

print("\nВсе проверки зелёные.")
