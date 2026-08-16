# -*- coding: utf-8 -*-
"""ПАМЯТЬ НА СТОРОНЕ TELEGRAM — чтобы канал не молчал, пока нет базы.

Зачем это есть.

Правило проекта: любое действие, которое продукт делает сам и наружу,
обязано иметь память, переживающую перезапуск. Нет памяти — нет действия.
16 августа нарушение этого правила стоило семнадцати копий одного поста
в канале с четырьмя подписчиками.

Память бота живёт в Postgres. Пока `DATABASE_URL` не задан, её нет вовсе:
на бесплатном тарифе Render диск стирается при каждом пробуждении сервиса,
и файл с отметкой «этот пост уже публиковали» исчезает вместе с ним.
Поэтому канал — единственный работающий источник людей — молчал сутки.

Но одно место, переживающее наши перезапуски, у бота всё-таки есть:
сервера самого Telegram. Токен туда уже есть, и мы уже кладём туда данные
о себе. Годятся два места, и оба проверяются боем, а не на слово:

1. **Список команд для одного чата.** `setMyCommands` с областью `chat`:
   имя команды — ключ, описание — значение. Место опрятное, но Telegram
   разрешает такую область для групп и супергрупп, а про каналы в
   документации сказано иначе. Пробуем первым и не расстраиваемся.

2. **Описание бота на неиспользуемом языке.** `setMyDescription` с
   `language_code`, которого нет ни у кого из наших: описание показывается
   человеку, только если у него в Telegram выбран ИМЕННО этот язык, а
   всем остальным достаётся обычное. 512 знаков — на десяток отметок
   хватает с запасом.

Второе выглядит хитростью, и это она и есть. Оправдание одно: канал —
единственное, что приводит людей, и каждый день его молчания стоит
подписчиков, которых потом не будет. Как только задан `DATABASE_URL`,
всё это перестаёт использоваться, а накопленные отметки переезжают в базу.

**Чем это НЕ является.** Это память на несколько коротких отметок, а не
база. Подписчиков, события и паузы между письмами сюда не положить: там
сотни записей и личные данные людей. Поэтому она открывает ровно одно —
посты в канал. Личные сообщения по-прежнему требуют `DATABASE_URL`, и там
правило не смягчается ни на волос: за повтор в канале отписываются, а за
повтор в личных бота блокируют, и это навсегда.

**Почему ей можно верить.** Не на слово.

- При запуске бот читает своё хранилище. Не ответило — памяти нет,
  канал молчит ровно как молчал.
- **Каждая запись проверяется чтением обратно.** Записали дату, прочли,
  сравнили. Не совпало — считаем, что не записали.
- **Отметка ставится ДО поста, а не после.** Обычно правильно наоборот
  (не сделали — не запомнили), но здесь ошибка обязана играть в сторону
  молчания: сбой отправки стоит одного пропущенного дня, повтор — канала.

Ни одного места, где «наверное, записалось» превращается в «публикуем»,
здесь нет.
"""
import re

# Telegram: имя команды — до 32 знаков, только строчные латинские буквы,
# цифры и подчёркивание. Наши ключи (`post_den`, `kurs_osveshchen`,
# `svodka`) в это укладываются. Проверять всё равно надо: ключ, не
# прошедший правило, Telegram отвергнет вместе со ВСЕЙ записью, то есть
# заодно потеряет и остальные отметки.
IMYA_KLUCHA = re.compile(r"^[a-z0-9_]{1,32}$")

# Значения — даты и номера недель. Разделители внутри значения сломали бы
# разбор, поэтому их там быть не может, и мы это проверяем, а не надеемся.
ZNACHENIE_CHISTOE = re.compile(r"^[0-9A-Za-z_.:\-]{1,40}$")

# Язык описания, на котором лежат отметки. Нужен такой, которого нет ни у
# кого из наших: аудитория продукта — узбекский и русский, английский у
# части. Африкаанс в этом коридоре не встречается, а если однажды
# встретится — человек увидит строку вида `post_den=2026-08-17` вместо
# описания бота. Некрасиво, но не опасно и живёт до первой базы.
YAZYK_TAYNIKA = "af"

DLINA_OPISANIYA = 512


def prigoden(kluch, znachenie):
    """Ляжет ли такая пара в хранилище и вернётся ли обратно целой."""
    return (bool(IMYA_KLUCHA.match(str(kluch)))
            and bool(ZNACHENIE_CHISTOE.match(str(znachenie))))


# ── Способы хранения ─────────────────────────────────────────────────
#
# У каждого два действия: прочитать всё и записать всё. Проверку записи
# чтением делает общий код выше — способ о ней не знает и соврать о
# своём успехе не может.


class VKomandahChata(object):
    """Отметки в списке команд, заданном для одного чата."""

    imya = "команды канала"

    def __init__(self, vyzov, kanal):
        self.vyzov = vyzov
        self.kanal = kanal
        self.pochemu = ""

    def dostupen(self):
        return bool(self.kanal)

    def _oblast(self):
        return {"type": "chat", "chat_id": self.kanal}

    def prochitat(self):
        otvet = self.vyzov("getMyCommands", {"scope": self._oblast()})
        if not otvet or not otvet.get("ok"):
            self.pochemu = _pochemu(otvet)
            return None
        spisok = otvet.get("result")
        if not isinstance(spisok, list):
            self.pochemu = "ответ не похож на список команд"
            return None
        return {str(z["command"]): str(z.get("description") or "")
                for z in spisok if isinstance(z, dict) and z.get("command")}

    def zapisat(self, dannye):
        komandy = [{"command": str(k), "description": str(z)}
                   for k, z in sorted(dannye.items()) if prigoden(k, z)]
        otvet = self.vyzov("setMyCommands",
                           {"scope": self._oblast(), "commands": komandy})
        if not otvet or not otvet.get("ok"):
            self.pochemu = _pochemu(otvet)
            return False
        return True


class VOpisaniiNaChuzhomYazyke(object):
    """Отметки в описании бота на языке, которого нет у наших людей."""

    imya = "описание бота на языке «%s»" % YAZYK_TAYNIKA

    def __init__(self, vyzov, kanal=None):
        self.vyzov = vyzov
        self.pochemu = ""

    def dostupen(self):
        return True

    def prochitat(self):
        otvet = self.vyzov("getMyDescription",
                           {"language_code": YAZYK_TAYNIKA})
        if not otvet or not otvet.get("ok"):
            self.pochemu = _pochemu(otvet)
            return None
        stroka = str((otvet.get("result") or {}).get("description") or "")
        dannye = {}
        for kusok in stroka.split(";"):
            if "=" not in kusok:
                continue
            kluch, _, znachenie = kusok.partition("=")
            kluch, znachenie = kluch.strip(), znachenie.strip()
            if prigoden(kluch, znachenie):
                dannye[kluch] = znachenie
        return dannye

    def zapisat(self, dannye):
        stroka = ";".join("%s=%s" % (k, z) for k, z in sorted(dannye.items())
                          if prigoden(k, z))
        if len(stroka) > DLINA_OPISANIYA:
            self.pochemu = "отметки не влезают в описание"
            return False
        otvet = self.vyzov("setMyDescription",
                           {"description": stroka,
                            "language_code": YAZYK_TAYNIKA})
        if not otvet or not otvet.get("ok"):
            self.pochemu = _pochemu(otvet)
            return False
        return True


SPOSOBY = [VKomandahChata, VOpisaniiNaChuzhomYazyke]


def _pochemu(otvet):
    """Внятная причина отказа из ответа Telegram."""
    if otvet is None:
        return "Telegram не ответил"
    prichina = str(otvet.get("description") or "").strip()
    if prichina:
        return prichina
    return "отказ %s" % (otvet.get("error_code") or "без кода")


# ── Память ───────────────────────────────────────────────────────────


class PamyatTelegrama(object):
    """Ключ-значение на серверах Telegram. Тот способ, который работает."""

    def __init__(self, vyzov, kanal):
        self.vyzov = vyzov
        self.kanal = kanal
        self.sposob = None
        self.pochemu = ""

    def podnyat(self):
        """Ищет рабочий способ хранения. Возвращает True, если нашёлся.

        Только чтение: писать при каждом запуске нельзя. Render на
        бесплатном тарифе перезапускает сервис постоянно, и запись «на
        пробу» каждый раз — это сотни обращений в день там, где по делу
        нужно два. Запись проверяется тогда, когда она случается по делу,
        и до всякого действия наружу.
        """
        prichiny = []
        for klass in SPOSOBY:
            sposob = klass(self.vyzov, self.kanal)
            if not sposob.dostupen():
                continue
            if sposob.prochitat() is not None:
                self.sposob = sposob
                self.pochemu = ""
                print("[память] отметки о постах лежат у Telegram (%s) — "
                      "канал может публиковать без DATABASE_URL" % sposob.imya,
                      flush=True)
                return True
            prichiny.append("%s: %s" % (sposob.imya, sposob.pochemu))

        self.pochemu = "; ".join(prichiny) or "хранить негде"
        print("[память] запасной памяти нет, канал молчит — " + self.pochemu,
              flush=True)
        return False

    def vse(self):
        """Все отметки. **None означает «не смогли прочитать»**.

        Разница принципиальная. Пустой словарь читается как «ничего ещё не
        публиковали» и разрешает пост. Молчание сети — не разрешение:
        именно из такого «не знаю, значит можно» и выходят повторы.
        """
        if self.sposob is None:
            return None
        dannye = self.sposob.prochitat()
        if dannye is None:
            self.pochemu = self.sposob.pochemu
        return dannye

    def zapisat(self, kluch, znachenie):
        """Записывает и ПРОВЕРЯЕТ ЧТЕНИЕМ. False — считать незаписанным."""
        if self.sposob is None:
            return False

        znachenie = str(znachenie)
        if not prigoden(kluch, znachenie):
            self.pochemu = "ключ или значение не годятся: %s=%s" % (kluch,
                                                                    znachenie)
            print("[память] " + self.pochemu, flush=True)
            return False

        bylo = self.sposob.prochitat()
        if bylo is None:
            # Писать поверх непрочитанного нельзя: затрём остальные
            # отметки, и повторы вернутся с другой стороны.
            self.pochemu = "перед записью не удалось прочитать: %s" % (
                self.sposob.pochemu)
            print("[память] " + self.pochemu, flush=True)
            return False

        dannye = dict(bylo)
        dannye[str(kluch)] = znachenie
        if not self.sposob.zapisat(dannye):
            self.pochemu = self.sposob.pochemu
            print("[память] записать не вышло: " + self.pochemu, flush=True)
            return False

        # Главная проверка всего этого хозяйства: Telegram сказал «ок» —
        # а лежит ли там то, что мы просили? Ответ «ок» на запись, после
        # которой читается старое, — ровно тот случай, из-за которого
        # канал и получил семнадцать копий одного поста.
        stalo = self.sposob.prochitat()
        if stalo is None or stalo.get(str(kluch)) != znachenie:
            self.pochemu = "записали, а читается другое — памяти нет"
            print("[память] " + self.pochemu, flush=True)
            return False

        # Проверяем и остальное: запись не должна съедать чужие отметки.
        poteryano = [k for k in bylo if k not in stalo]
        if poteryano:
            self.pochemu = "при записи потерялись отметки: %s" % ", ".join(
                sorted(poteryano))
            print("[память] " + self.pochemu, flush=True)
            return False

        return True
