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

      // Вступление переписано 16 августа. Прежнее рассказывало про курс
      // банка получателя — гипотезу, которая на замере не подтвердилась
      // (0,84%). Первое, что читает человек, обязано быть правдой.
      'intro.h1':        'Bugun yuborishmi yoki kutishmi',
      'intro.p1':        'Oy ichida rubl kursi <b>155 dan 141 gacha</b> tushdi. Bu 9,5% — 50 000 rublda 670 ming so’m. Qaysi servis emas, qaysi <b>kun</b> — asosiy pul shunda.',
      'intro.big.v':     'Kun servisdan ko’ra ko’proq hal qiladi',
      'intro.big.k':     'Servislar buni aytmaydi: ular aylanmadan ishlaydi va ularga «hozir yuboring» kerak',
      'intro.p2':        'Biz bugungi kursni oyning o’rtachasi bilan solishtiramiz va kartaga qancha yetib borishini hisoblaymiz. Kelajakni bashorat qilmaymiz — faqat faktni ko’rsatamiz. Pul o’tkazmaymiz va qabul qilmaymiz.',
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
      'idle.s1':         'Eng ko’pini kun kursi hal qiladi — oyda 9,5% gacha',
      'idle.s2':         'Servis kursi rasmiydan yana 4% ga past',
      'idle.s3':         'Hammasini birga hisoblab, kartaga qancha tushishini ko’rsatamiz',

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
      // Verdikt KURSNI tasvirlaydi, kunni emas — shuning uchun «bugun»
      // so‘zisiz. Markaziy bank dam olish kunlari kurs e’lon qilmaydi, va
      // dushanba kuni eng yangi kurs — juma kuniniki. «Bugungi kurs»
      // deyish haftada uch kun yolg‘on bo‘lardi. Sana yonida turadi.
      'v.otlichno':       'Kurs odatdagidan sezilarli yaxshi',
      'v.horosho':        'Kurs odatdagidan yaxshiroq',
      'v.obychno':        'Kurs odatdagidek',
      'v.nize_obychnogo': 'Kurs odatdagidan pastroq',
      'v.ploho':          'Kurs odatdagidan sezilarli yomon',

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
      'v.do.otpravlyat':   'Yubormoqchi bo’lsangiz — bugun yaxshi kun.',
      'v.do.mozhno_zhdat': 'Kurs odatdagidan past, lekin ko’tarilmoqda — kutish ma’noli.',
      'v.do.ne_zhdat':     'Kurs tushmoqda — qancha kutsangiz, shuncha kam yetadi.',
      'v.do.obychno':      'Kurs odatdagidek. Quyida — kartaga qancha tushishi.',
      // Ma'lumotlar eski bo'lsa, maslahat bermaymiz. To'rt kunlik kurs
      // bo'yicha «bugun yaxshi kun» deyish — odamga pul yo'qotish
      // maslahatini berish bilan barobar.
      'v.do.stale':        'Ma’lumotlar eski — bugun uchun maslahat bermayman. Kursni tekshiring.',
      'v.range':         'oyda {mn} dan {mx} gacha',
      'v.days':          '30 kun',
      'v.week.up':       'haftada +{p}%',
      'v.week.down':     'haftada −{p}%',
      'v.spread':        'Oyning eng yaxshi va eng yomon kuni orasida — sizning summangizda {n} so’m',

      // ── Raqamlar qayerdan ────────────────────────────────────────
      'src.t':           'Raqamlar qayerdan',
      'src.cb':          'Rasmiy kurs — O‘zbekiston Markaziy bankining ochiq API si',
      'src.svc':         'O‘tkazma kurslari — bank.uz, pul o‘tkazmalari sahifasi',
      // Ikki xil narsani chalkashtirmaslik kerak: MA'LUMOT har soatda
      // yig‘iladi, KURS esa Markaziy bank e'lon qilgan kunga tegishli.
      // Ilgari bu yerda «har soatda yangilanadi, oxirgi marta 14.08» deb
      // yozilgan edi — ya'ni «ikki kundan beri yangilanmagan» degandek
      // o‘qilardi, holbuki hammasi joyida edi.
      'src.upd':         'Har soatda yig‘amiz. Markaziy bank kursi — {d} holatiga',
      'src.no':          'Biz pul o‘tkazmaymiz va qabul qilmaymiz. Faqat hisoblaymiz.',

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
      'sub.ch':          'Yoki har kuni ertalab kanalda kurs',

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
      'share.title':     '{sum} ₽ yuboryapman — avval kursni tekshirdim.',
      'share.diff':      'Usullar orasidagi farq {p}% chiqdi.',
      // Xabar ketadigan raqam. Bu — mahsulotning butun ma’nosi: kunni
      // tanlash servisni tanlashdan ko‘proq pul hal qiladi. Ilgari bu yerda
      // birorta ham pul raqami yo‘q edi, ya’ni xabarni uzatishga sabab
      // ham yo‘q edi.
      'share.spread':    'Oy davomida kurs {p}% ga o‘zgardi — 50 000 rublda bu {n} so‘m.',
      // Sana majburiy: raqam sanasiz — bu yolg‘on, va bu xabar begona
      // chatlarga ketadi, u yerda uni tuzatib bo‘lmaydi.
      'share.date':      'Markaziy bank kursi, {d}',
      'share.cta':       'Yuborishdan oldin kursga qarang.',
    },

    ru: {
      'app.name':        'Сколько дойдёт',

      'intro.h1':        'Отправлять сегодня или подождать',
      'intro.p1':        'За месяц курс рубля прошёл путь <b>от 155 до 141</b>. Это 9,5% — на 50 000 ₽ это 670 тысяч сум. Не какой сервис, а какой <b>день</b> — вот где основные деньги.',
      'intro.big.v':     'День решает больше, чем сервис',
      'intro.big.k':     'Сервисы об этом молчат: они зарабатывают на объёме, и им нужно «отправьте сейчас»',
      'intro.p2':        'Мы сравниваем сегодняшний курс со средним за месяц и считаем, сколько дойдёт до карты. Будущее не предсказываем — показываем факт. Деньги не переводим и не принимаем.',
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
      'idle.s1':         'Курс дня решает больше всего — до 9,5% за месяц',
      'idle.s2':         'Курс сервиса ниже официального ещё примерно на 4%',
      'idle.s3':         'Считаем всё вместе и показываем, сколько ляжет на карту',

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
      // Вердикт описывает КУРС, а не день, и потому обходится без слова
      // «сегодня». ЦБ не публикует курс по выходным: в понедельник
      // свежайшая точка — за пятницу, и «сегодня курс такой-то» было бы
      // неправдой три дня в неделю. Дата стоит рядом с числом.
      'v.otlichno':       'Курс заметно лучше обычного',
      'v.horosho':        'Курс лучше обычного',
      'v.obychno':        'Курс обычный',
      'v.nize_obychnogo': 'Курс ниже обычного',
      'v.ploho':          'Курс заметно хуже обычного',

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
      // Совет говорит, что ДЕЛАТЬ, и учитывает направление курса.
      // Раньше здесь было просто «ниже обычного — подожди», и в падающем
      // рынке это советовало ждать, когда каждый следующий день хуже.
      'v.do.otpravlyat':   'Если собирались отправлять — сегодня хороший день.',
      'v.do.mozhno_zhdat': 'Курс ниже обычного и растёт — есть смысл подождать.',
      'v.do.ne_zhdat':     'Курс падает — чем дольше ждёте, тем меньше дойдёт.',
      'v.do.obychno':      'Курс обычный. Ниже — сколько дойдёт до карты.',
      // По старым данным советов не даём. «Сегодня хороший день» по
      // курсу четырёхдневной давности — это совет потерять деньги,
      // такой же по сути, как «подождите» в падающем рынке.
      'v.do.stale':        'Данные устарели — совет на сегодня не даю. Проверьте курс.',
      'v.range':         'за месяц от {mn} до {mx}',
      'v.days':          '30 дней',
      'v.week.up':       'за неделю +{p}%',
      'v.week.down':     'за неделю −{p}%',
      // Самая убедительная цифра продукта: что стоит выбор дня, в его
      // деньгах. Абстрактные 9,5% не чувствует никто.
      'v.spread':        'Между лучшим и худшим днём месяца — {n} сум на вашей сумме',

      // ── Откуда цифры ─────────────────────────────────────────────
      // В денежном продукте это не мелкий шрифт внизу, а причина верить
      // всему остальному. Источники называем поимённо и проверяемо.
      'src.t':           'Откуда цифры',
      'src.cb':          'Официальный курс — открытый API Центрального банка Узбекистана',
      'src.svc':         'Курсы переводов — bank.uz, страница денежных переводов',
      // Здесь смешивались две разные вещи: ДАННЫЕ собираются каждый час,
      // а КУРС относится к тому дню, когда его опубликовал ЦБ. Стояло
      // «обновляется каждый час, последний раз 14.08» — и это читалось
      // как «два дня не обновлялось», хотя всё работало исправно.
      'src.upd':         'Собираем каждый час. Курс ЦБ — на {d}',
      'src.no':          'Мы не переводим и не принимаем деньги. Только считаем.',

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
      'sub.ch':          'Или курс каждое утро в канале',

      // ── Куда уходят деньги ───────────────────────────────────────
      'br.t':            'Куда уходят деньги',
      'br.cb':           'По официальному курсу ЦБ',
      'br.rate':         'Курс сервиса',
      'br.fee':          'Комиссия',
      'br.fee_unknown':  'не объявлена',
      'br.total':        'Придёт на карту',

      'err.net':         'Свежие курсы не получены — считаю по данным на {d}',

      'share.title':     'Отправляю {sum} ₽ — сначала проверил курс.',
      'share.diff':      'Разница между способами вышла {p}%.',
      // Число, ради которого пересылают. В нём весь смысл продукта: день
      // отправки решает больше денег, чем выбор сервиса. Раньше в
      // пересылке не было ни одной денежной цифры — то есть не было и
      // причины её пересылать.
      'share.spread':    'За месяц курс менялся на {p}% — это {n} сум на переводе 50 000 ₽.',
      // Дата обязательна: число без даты — ложь, а это сообщение уходит
      // в чужие чаты, где его уже не поправишь.
      'share.date':      'Курс ЦБ на {d}',
      'share.cta':       'Посмотри курс, прежде чем отправлять.',
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
