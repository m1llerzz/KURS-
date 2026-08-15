/**
 * ЯЗЫКИ
 *
 * Два языка: узбекский (латиница) и русский. Узбекский первый — отправитель
 * почти всегда узбек, живущий в России, и родной язык он читает быстрее.
 *
 * Язык выбирается сам по языку Telegram, но переключатель есть всегда:
 * у многих мигрантов интерфейс телефона русский, а читать они хотят на своём.
 * Выбор запоминается.
 *
 * Здесь ТОЛЬКО тексты. Ни одной формулы, ни одного обращения к экрану.
 * Подстановки вида {sum} заменяются вторым аргументом t().
 *
 * Кириллический узбекский сознательно не делаем: официальная письменность
 * в Узбекистане латинская, а мини-аппами пользуются те, кому до 45.
 */

window.I18N = (function () {

  const TEKSTY = {

    uz: {
      'app.name':        'Qancha yetadi',

      'intro.h1':        'Kartaga qancha pul yetib boradi',
      'intro.p1':        'Pul rubl yoki dollarda ketadi. Uni so’mga <b>qabul qiluvchi bank</b> aylantiradi — pul tushgan kundagi o’z kursi bo’yicha. Yuboruvchi bu kursni hech qayerda ko’rmaydi.',
      'intro.big.v':     '400 000 so’mgacha',
      'intro.big.k':     '50 000 ₽ o’tkazmada faqat usul tanlash tufayli yo’qoladi',
      'intro.p2':        'Biz komissiya, kurs va qabul qiluvchi bankni hisobga olib, kartaga tushadigan summani hisoblaymiz. Pul o’tkazmaymiz va qabul qilmaymiz — faqat raqamni ko’rsatamiz.',
      'intro.ok':        'Tushunarli, yopish',

      'lbl.send':        'Yuboraman',
      'hint.rub':        'rubl, Rossiyadan',
      'lbl.bank':        'Qabul qiluvchi bank',
      'hint.bank':       'tanlanmasa, oraliqni ko’rsatamiz',
      'bank.any':        'Bilmayman',
      'btn.calc':        'Hisoblash',
      'btn.share':       'Chatga yuborish',

      'err.min':         'Eng kami {min} ₽ — kichikroq summani hech kim yubormaydi',
      'err.max':         'Eng ko’pi {max} ₽ — bundan katta o’tkazmani xizmatlar bir amalda qabul qilmaydi',
      'err.nan':         'Summani raqam bilan kiriting',

      'loss.t':          'Eng yaxshi va eng yomon usul farqi',
      'loss.sub':        '{sum} ₽ dan · usul tanlashda shuncha yo’qoladi',

      'tag.best':        'Eng ko’p',
      'tag.stale':       'Kechagi ma’lumot',

      'unit.sum':        'so’m',
      'time.min':        'daq',
      'time.hour':       'soat',
      'time.day':        'kun',

      'detail.est':      'bank kursi taxminiy',
      'detail.worse':    'bank Markaziy bank kursidan {p}% yomonroq',
      'detail.better':   'bank Markaziy bank kursidan {p}% yaxshiroq',
      'detail.stale':    'bank kursi yangilanishi kerak',
      'detail.limit':    'limitdan yuqori, tasdiqlash kerak',

      'empty':           'Ma’lumotlar yangilanmoqda. Bir soatdan keyin kiring — noto’g’ri raqam ko’rsatmaymiz.',
      'test':            'TEST MA’LUMOT, raqamlar o’ylab topilgan. ',
      'disclaimer.main': 'Biz pul o’tkazmaymiz. Qabul qiluvchi bank kursi taxminiy — bank uni pul tushgan kuni belgilaydi, yakuniy summa farq qilishi mumkin.',

      'kurs.fail':       'Markaziy bank kursini yangilab bo’lmadi — zaxira qiymatlar bo’yicha, raqamlar taxminiy',
      'kurs.date':       'Markaziy bank kursi {d} holatiga',

      'popup.total':     'Kartaga tushadi',
      'popup.est':       'Qabul qiluvchi bank kursi taxminiy — bank uni pul tushgan kuni belgilaydi.',

      'razbor.sent':        'Yuborildi',
      'razbor.fee':         'Xizmat komissiyasi',
      'razbor.toconv':      'Konvertatsiyaga',
      'razbor.rate_serv':   'Xizmat kursi',
      'razbor.rate_rubusd': 'Rubl → dollar kursi',
      'razbor.in_currency': 'Valyutada ketdi',
      'razbor.rate_bank':   'Bank kursi → so’m',

      // Пересылка — главный способ, которым про нас узнают. Поэтому здесь
      // не только цифры: нужна строка, объясняющая чужому человеку, что он видит.
      'share.title':     '{sum} ₽ O’zbekistonga o’tkazma',
      'share.diff':      'Usullar orasidagi farq: {loss} so’m',
      'share.cta':       'O’zingiznikini hisoblang:',
    },

    ru: {
      'app.name':        'Сколько дойдёт',

      'intro.h1':        'Сколько денег реально дойдёт до карты',
      'intro.p1':        'Перевод уходит в рублях или долларах. В сумы его превращает <b>банк получателя</b> — по своему курсу в день зачисления. Этого курса отправитель не видит нигде.',
      'intro.big.v':     'до 400 000 сум',
      'intro.big.k':     'теряется на переводе 50 000 ₽ только из-за выбора способа',
      'intro.p2':        'Мы считаем итог на карту с учётом комиссии, курса и банка получателя. Деньги не переводим и не принимаем — только показываем цифру.',
      'intro.ok':        'Понятно, скрыть',

      'lbl.send':        'Отправляю',
      'hint.rub':        'рублей из России',
      'lbl.bank':        'Банк получателя',
      'hint.bank':       'без него покажем вилку',
      'bank.any':        'Не знаю',
      'btn.calc':        'Посчитать',
      'btn.share':       'Отправить в чат',

      'err.min':         'Минимум {min} ₽ — меньше никто не отправляет',
      'err.max':         'Максимум {max} ₽ — больше сервисы не проводят одной операцией',
      'err.nan':         'Введите сумму цифрами',

      'loss.t':          'Разница между лучшим и худшим',
      'loss.sub':        'на {sum} ₽ · столько теряется на выборе способа',

      'tag.best':        'Больше всего',
      'tag.stale':       'Данные вчера',

      'unit.sum':        'сум',
      'time.min':        'мин',
      'time.hour':       'ч',
      'time.day':        'дн',

      'detail.est':      'курс банка оценочный',
      'detail.worse':    'банк хуже курса ЦБ на {p}%',
      'detail.better':   'банк лучше курса ЦБ на {p}%',
      'detail.stale':    'курс банка требует обновления',
      'detail.limit':    'выше лимита, нужна верификация',

      'empty':           'Данные обновляются. Загляните через час — показывать неверные цифры мы не будем.',
      'test':            'ТЕСТОВЫЕ ДАННЫЕ, цифры выдуманы. ',
      'disclaimer.main': 'Мы не переводим деньги. Курс банка получателя оценочный — банк ставит его в день зачисления, итог может отличаться.',

      'kurs.fail':       'Курс ЦБ обновить не удалось — считаем по запасным значениям, цифры ориентировочные',
      'kurs.date':       'Курс ЦБ на {d}',

      'popup.total':     'Придёт на карту',
      'popup.est':       'Курс банка получателя оценочный — банк ставит его в день зачисления.',

      'razbor.sent':        'Отправлено',
      'razbor.fee':         'Комиссия сервиса',
      'razbor.toconv':      'К конвертации',
      'razbor.rate_serv':   'Курс сервиса',
      'razbor.rate_rubusd': 'Курс рубль → доллар',
      'razbor.in_currency': 'Ушло в валюте',
      'razbor.rate_bank':   'Курс банка → сум',

      'share.title':     'Перевод {sum} ₽ в Узбекистан',
      'share.diff':      'Разница между способами: {loss} сум',
      'share.cta':       'Посчитать свой:',
    },

  };

  /** Язык Telegram даёт подсказку, сохранённый выбор её перебивает. */
  function opredelit() {
    try {
      const sohranen = localStorage.getItem('lang');
      if (sohranen && TEKSTY[sohranen]) return sohranen;
    } catch (e) {}

    const tg = window.Telegram && window.Telegram.WebApp;
    // Если язык определить нечем — узбекский, а не русский: он здесь основной,
    // и промах в его сторону дешевле промаха в другую.
    const kod = tg && tg.initDataUnsafe && tg.initDataUnsafe.user
      ? tg.initDataUnsafe.user.language_code
      : (navigator.language || 'uz');

    // Русский только при явном ru. Всё остальное, включая узбекский,
    // английский и любой другой, ведём на узбекский: аудитория коридора одна.
    return String(kod).slice(0, 2) === 'ru' ? 'ru' : 'uz';
  }

  let yazyk = opredelit();

  function t(klyuch, podstanovki) {
    let stroka = TEKSTY[yazyk][klyuch];
    if (stroka === undefined) stroka = TEKSTY.ru[klyuch];
    if (stroka === undefined) return klyuch;   // ключ забыли — видно сразу
    if (!podstanovki) return stroka;
    return stroka.replace(/\{(\w+)\}/g, function (_, imya) {
      return podstanovki[imya] !== undefined ? podstanovki[imya] : '{' + imya + '}';
    });
  }

  function ustanovit(noviy) {
    if (!TEKSTY[noviy]) return;
    yazyk = noviy;
    try { localStorage.setItem('lang', noviy); } catch (e) {}
  }

  return {
    t: t,
    set: ustanovit,
    get: function () { return yazyk; },
    languages: Object.keys(TEKSTY),
  };

})();
