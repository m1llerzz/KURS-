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
      // Число потери убрано 15 августа: «3–5%» и «400 000 so'm» были взяты
      // из аналитики и никем не проверены. Открытые курсы банков дали 0,84%.
      // Пока разброс не измерен на живых переводах, цифры здесь не будет.
      'intro.big.v':     'Kursni bank belgilaydi',
      'intro.big.k':     'Xizmat emas, qabul qiluvchi bank — pul tushgan kuni. Qancha ekanini oldindan hech kim ko’rsatmaydi',
      'intro.p2':        'Biz komissiya, kurs va qabul qiluvchi bankni hisobga olib, kartaga tushadigan summani hisoblaymiz. Pul o’tkazmaymiz va qabul qilmaymiz — faqat raqamni ko’rsatamiz.',
      'intro.ok':        'Tushunarli, yopish',

      'lbl.send':        'Yuboraman',
      'hint.rub':        'rubl, Rossiyadan',
      'lbl.bank':        'Qabul qiluvchi bank',
      'hint.bank':       'bilmasangiz - oraliqni ko’rsatamiz',
      'bank.any':        'Bilmayman',
      'btn.calc':        'Hisoblash',
      'btn.share':       'Yaqinlaringizga yuborish',

      'idle.rate':       '1 ₽ = {r} so’m',
      'idle.rate.sub':   'Markaziy bank kursi, {d} — hisob shundan boshlanadi',
      'idle.rate.old':   'Markaziy bank kursi yangilanmadi — raqamlar taxminiy',
      'idle.s1':         'Xizmat komissiyani darrov summangizdan ushlab qoladi',
      'idle.s2':         'Qolganini O’zbekistondagi bank so’mga almashtiradi. Kursni bank o’zi, pul tushgan kuni belgilaydi',
      'idle.s3':         'Biz kartaga oxirida qancha tushishini va usullar qanchaga farq qilishini hisoblaymiz',

      'err.min':         'Eng kami {min} ₽ — kichikroq summani hech kim yubormaydi',
      'err.max':         'Eng ko’pi {max} ₽ — bundan katta o’tkazmani xizmatlar bir amalda qabul qilmaydi',
      'err.nan':         'Summani raqam bilan kiriting',

      'loss.t':          'Usullar orasidagi farq',
      'loss.sub':        '{sum} ₽ da eng yaxshi usul shuncha qo’shadi',

      'tag.best':        'Eng ko’p',
      'tag.stale':       'kecha yangilangan',

      'unit.sum':        'so’m',
      'time.min':        '{n} daqiqada',
      'time.hour':       '{n} soatda',
      'time.day':        '{n} kunda',

      'detail.est':      'bank kursi taxminiy',
      'detail.worse':    'bank kursi rasmiydan {p}% past',
      'detail.better':   'bank kursi rasmiydan {p}% yuqori',
      'detail.stale':    'bank kursi aniqlanmoqda',
      'detail.limit':    'limitdan yuqori - hujjat tekshiruvi kerak',

      'empty':           'Ma’lumotlar yangilanmoqda. Bir soatdan keyin kiring — noto’g’ri raqam ko’rsatmaymiz.',
      'test':            'TEST MA’LUMOT, raqamlar o’ylab topilgan. ',
      'disclaimer.main': 'Biz pul o’tkazmaymiz. Qabul qiluvchi bank kursi taxminiy — bank uni pul tushgan kuni belgilaydi, yakuniy summa farq qilishi mumkin.',

      'kurs.fail':       'Markaziy bank kursini yangilab bo’lmadi — zaxira qiymatlar bo’yicha, raqamlar taxminiy',
      'kurs.date':       'Markaziy bank kursi {d} holatiga',

      'popup.total':     'Kartaga tushadi',
      'popup.est':       'Qabul qiluvchi bank kursi taxminiy — bank uni pul tushgan kuni belgilaydi.',
      'popup.go':        'Xizmatga o’tish',

      'razbor.sent':        'Yuborildi',
      'razbor.fee':         'Xizmat komissiyasi',
      'razbor.toconv':      'Konvertatsiyaga',
      'razbor.rate_serv':   'Xizmat kursi',
      'razbor.rate_rubusd': 'Rubl → dollar kursi',
      'razbor.in_currency': 'Valyutada ketdi',
      'razbor.rate_bank':   'Bank kursi → so’m',

      // ── Verdikt: bugun yubormoqmi yoki kutmoqmi ──────────────────
      // Mahsulotning asosiy ekrani. Oyda kurs 9,5% ga o‘zgardi — bu
      // servis tanlashdan ham, bank tanlashdan ham ko‘proq pul.
      'v.otlichno':       'Bugun kurs odatdagidan sezilarli yaxshi',
      'v.horosho':        'Bugun kurs odatdagidan yaxshiroq',
      'v.obychno':        'Bugun kurs odatdagidek',
      'v.nize_obychnogo': 'Bugun kurs odatdagidan pastroq',
      'v.ploho':          'Bugun kurs odatdagidan sezilarli yomon',

      'v.rate':          '1 ₽ = {r} so’m',
      'v.avg':           'oydagi o’rtacha {r}',
      'v.pos':           'oyning {p}% kunidan yaxshi',
      'v.pos.worst':     'oyning eng yomon kuni',
      'v.pos.best':      'oyning eng yaxshi kuni',
      'v.trend.rastet':  'kurs ko’tarilmoqda',
      'v.trend.padaet':  'kurs tushmoqda',
      'v.trend.stoit':   'kurs turibdi',
      'v.onsum.plus':    '{sum} ₽ uchun odatdagidan {n} so’m ko’p olasiz',
      'v.onsum.minus':   '{sum} ₽ uchun odatdagidan {n} so’m kam olasiz',
      'v.onsum.zero':    'Kurs odatdagidek — shoshilishning hojati yo’q',
      'v.hint.good':     'Yubormoqchi bo’lsangiz — bugun yaxshi kun.',
      'v.hint.bad':      'Shoshilinch bo’lmasa, kutgan ma’qul.',
      'v.hint.normal':   'Kurs odatdagidek. Quyida — kartaga qancha tushishi.',
      'v.range':         'oyda {mn} dan {mx} gacha',
      'v.days':          '30 kun',

      // ── Servis kursi rasmiy kursga nisbatan ──────────────────────
      'svc.markup':      'kurs rasmiydan {p}% past',
      'svc.fee_unknown': 'komissiya e’lon qilinmagan — bu yuqori chegara',
      'svc.lost.t':      'O’tkazma kursi olib qoldi',
      'svc.official':    'Markaziy bank kursi bilan solishtirganda',
      'svc.lost':        'Kurs farqi: {n} so’m',

      // ── Xabarnomaga obuna ────────────────────────────────────────
      'sub.t':           'Kurs yaxshilanganda aytaymi?',
      'sub.p':           'Faqat kurs odatdagidan yaxshi bo’lganda yozaman — ya’ni jim turishim sizga pulga tushadigan paytda. Uch kunda bir martadan ko’p emas.',
      'sub.btn':         'Ha, xabar bering',

      // ── Pul qayerga ketadi ───────────────────────────────────────
      'br.t':            'Pul qayerga ketadi',
      'br.cb':           'Markaziy bank kursi bo‘yicha',
      'br.rate':         'Xizmat kursi',
      'br.fee':          'Komissiya',
      'br.fee_unknown':  'e’lon qilinmagan',
      'br.total':        'Kartaga tushadi',

      'err.net':         'Yangi kurslarni olib bo’lmadi — {d} holatidagi ma’lumot bilan hisobladim',

      // Пересылка — главный способ, которым про нас узнают. Поэтому здесь
      // не только цифры: нужна строка, объясняющая чужому человеку, что он видит.
      'share.title':     '{sum} ₽ yuboryapman — qaysi usulda ko’proq yetib borishini tekshirdim.',
      'share.diff':      'Farq {p}% chiqdi. Komissiya emas — uydagi bank kursi tufayli.',
      'share.cta':       'Yuborishdan oldin o’zingiznikini hisoblang.',
    },

    ru: {
      'app.name':        'Сколько дойдёт',

      'intro.h1':        'Сколько денег реально дойдёт до карты',
      'intro.p1':        'Перевод уходит в рублях или долларах. В сумы его превращает <b>банк получателя</b> — по своему курсу в день зачисления. Этого курса отправитель не видит нигде.',
      'intro.big.v':     'Курс ставит банк',
      'intro.big.k':     'Не сервис, а банк получателя — в день зачисления. Сколько именно, заранее не показывает никто',
      'intro.p2':        'Мы считаем итог на карту с учётом комиссии, курса и банка получателя. Деньги не переводим и не принимаем — только показываем цифру.',
      'intro.ok':        'Понятно, скрыть',

      'lbl.send':        'Отправляю',
      'hint.rub':        'рублей из России',
      'lbl.bank':        'Банк получателя',
      'hint.bank':       'не знаете - покажем от и до',
      'bank.any':        'Не знаю',
      'btn.calc':        'Посчитать',
      'btn.share':       'Отправить своим',

      'idle.rate':       '1 ₽ = {r} сум',
      'idle.rate.sub':   'Курс ЦБ, {d} — с него начинается расчёт',
      'idle.rate.old':   'Курс ЦБ обновить не удалось — цифры ориентировочные',
      'idle.s1':         'Сервис снимает комиссию — сразу, с вашей суммы',
      'idle.s2':         'Остаток меняет на сумы банк в Узбекистане. Курс он ставит сам, в день зачисления',
      'idle.s3':         'Мы считаем, сколько в итоге ляжет на карту и насколько расходятся способы',

      'err.min':         'Минимум {min} ₽ — меньше никто не отправляет',
      'err.max':         'Максимум {max} ₽ — больше сервисы не проводят одной операцией',
      'err.nan':         'Введите сумму цифрами',

      'loss.t':          'Разница между способами',
      'loss.sub':        'на {sum} ₽ · столько добавит лучший способ',

      'tag.best':        'Больше всего',
      'tag.stale':       'обновлено вчера',

      'unit.sum':        'сум',
      'time.min':        'за {n} мин',
      'time.hour':       'за {n} ч',
      'time.day':        'за {n} дн',

      'detail.est':      'курс банка примерный',
      'detail.worse':    'курс банка ниже официального на {p}%',
      'detail.better':   'курс банка выше официального на {p}%',
      'detail.stale':    'курс банка уточняется',
      'detail.limit':    'выше лимита - нужна проверка документов',

      'empty':           'Данные обновляются. Загляните через час — показывать неверные цифры мы не будем.',
      'test':            'ТЕСТОВЫЕ ДАННЫЕ, цифры выдуманы. ',
      'disclaimer.main': 'Мы не переводим деньги. Курс банка получателя оценочный — банк ставит его в день зачисления, итог может отличаться.',

      'kurs.fail':       'Курс ЦБ обновить не удалось — считаем по запасным значениям, цифры ориентировочные',
      'kurs.date':       'Курс ЦБ на {d}',

      'popup.total':     'Придёт на карту',
      'popup.est':       'Курс банка получателя оценочный — банк ставит его в день зачисления.',
      'popup.go':        'Перейти в сервис',

      'razbor.sent':        'Отправлено',
      'razbor.fee':         'Комиссия сервиса',
      'razbor.toconv':      'К конвертации',
      'razbor.rate_serv':   'Курс сервиса',
      'razbor.rate_rubusd': 'Курс рубль → доллар',
      'razbor.in_currency': 'Ушло в валюте',
      'razbor.rate_bank':   'Курс банка → сум',

      // ── Вердикт: отправлять сегодня или подождать ────────────────
      // Главный экран продукта. За месяц курс прошёл 9,5% — это больше
      // денег, чем выбор сервиса и выбор банка вместе взятые.
      'v.otlichno':       'Сегодня курс заметно лучше обычного',
      'v.horosho':        'Сегодня курс лучше обычного',
      'v.obychno':        'Сегодня курс обычный',
      'v.nize_obychnogo': 'Сегодня курс ниже обычного',
      'v.ploho':          'Сегодня курс заметно хуже обычного',

      'v.rate':          '1 ₽ = {r} сум',
      'v.avg':           'в среднем за месяц {r}',
      'v.pos':           'лучше {p}% дней месяца',
      'v.pos.worst':     'худший день месяца',
      'v.pos.best':      'лучший день месяца',
      'v.trend.rastet':  'курс растёт',
      'v.trend.padaet':  'курс падает',
      'v.trend.stoit':   'курс стоит',
      'v.onsum.plus':    'На {sum} ₽ вы получите на {n} сум больше обычного',
      'v.onsum.minus':   'На {sum} ₽ вы получите на {n} сум меньше обычного',
      'v.onsum.zero':    'Курс как обычно — спешить некуда',
      'v.hint.good':     'Если собирались отправлять — сегодня хороший день.',
      'v.hint.bad':      'Если дело не срочное, есть смысл подождать.',
      'v.hint.normal':   'Курс обычный. Ниже — сколько дойдёт до карты.',
      'v.range':         'за месяц от {mn} до {mx}',
      'v.days':          '30 дней',

      // ── Курс сервиса против официального ─────────────────────────
      'svc.markup':      'курс на {p}% ниже официального',
      'svc.fee_unknown': 'комиссию не публикуют — это верхняя граница',
      'svc.lost.t':      'Забрал курс перевода',
      'svc.official':    'по сравнению с официальным курсом ЦБ',
      'svc.lost':        'Разница на курсе: {n} сум',

      // ── Подписка на оповещения ───────────────────────────────────
      'sub.t':           'Написать, когда курс станет лучше?',
      'sub.p':           'Пишу только когда курс выше обычного — то есть когда моё молчание стоило бы вам денег. Не чаще раза в трое суток.',
      'sub.btn':         'Да, пишите',

      // ── Куда уходят деньги ───────────────────────────────────────
      'br.t':            'Куда уходят деньги',
      'br.cb':           'По официальному курсу ЦБ',
      'br.rate':         'Курс сервиса',
      'br.fee':          'Комиссия',
      'br.fee_unknown':  'не объявлена',
      'br.total':        'Придёт на карту',

      'err.net':         'Свежие курсы не получены — считаю по данным на {d}',

      'share.title':     'Отправляю {sum} ₽ — проверил, каким способом дойдёт больше.',
      'share.diff':      'Разница вышла {p}%. Не из-за комиссии — из-за курса банка дома.',
      'share.cta':       'Посчитай свой, пока не отправил.',
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

  /**
   * @param {string} klyuch
   * @param {object} [podstanovki]
   * @param {string} [drugoyYazyk] — взять строку на другом языке, не меняя
   *        текущий. Нужно пересылке: она уходит в чат сразу на двух языках,
   *        и переключать язык всего приложения ради этого нельзя.
   */
  function t(klyuch, podstanovki, drugoyYazyk) {
    const slovar = TEKSTY[drugoyYazyk] || TEKSTY[yazyk];
    let stroka = slovar[klyuch];
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
