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
      // Raqamlar jonli maʼlumotdan qoʻyiladi, soʻz bilan yozilmaydi.
      // Bu yerda «155 dan 141 gacha, 9,5% — 670 ming soʻm» turardi: matn
      // yozilgan kunning haqiqati. 22 avgustga kelib oyna surilib,
      // 138,67–153,87 boʻldi — yaʼni 10,96% va 760 000 soʻm, — va odam
      // birinchi oʻqigan gap pastdagi panel bilan bir ekranda ziddiyatga
      // tushdi.
      'intro.p1':        'Oy ichida rubl kursi <b>{mn} dan {mx} gacha</b> yurdi. Bu {p}% — 50 000 rublda {n} soʻm. Qaysi servis emas, qaysi <b>kun</b> — asosiy pul shunda.',
      'intro.p1.bez':    'Oy ichida rubl kursi sezilarli yoʻl bosadi, va oʻtkazmada bu servislar orasidagi farqdan koʻproq. Qaysi servis emas, qaysi <b>kun</b> — asosiy pul shunda.',
      'intro.big.v':     'Kun servisdan koʻra koʻproq hal qiladi',
      'intro.big.k':     'Servislar buni aytmaydi: ular aylanmadan ishlaydi va ularga «hozir yuboring» kerak',
      'intro.p2':        'Biz bugungi kursni oyning oʻrtachasi bilan solishtiramiz va kartaga qancha yetib borishini hisoblaymiz. Kelajakni bashorat qilmaymiz — faqat faktni koʻrsatamiz. Pul oʻtkazmaymiz va qabul qilmaymiz.',
      'intro.ok':        'Tushunarli, yopish',

      'lbl.send':        'Yuboraman',
      'hint.rub':        'rubl, Rossiyadan',
      'lbl.bank':        'Qabul qiluvchi bank',
      'hint.bank':       'bilmasangiz - oraliqni koʻrsatamiz',
      'bank.any':        'Bilmayman',
      'btn.calc':        'Hisoblash',
      'btn.share':       'Yaqinlaringizga yuborish',

      'idle.rate':       '1 ₽ = {r} soʻm',
      'idle.rate.sub':   'Markaziy bank kursi, {d} — hisob shundan boshlanadi',
      'idle.rate.old':   'Markaziy bank kursi yangilanmadi — raqamlar taxminiy',
      'idle.s1':         'Eng koʻpini kun kursi hal qiladi — oyda {p}%',
      'idle.s1.bez':     'Eng koʻpini kun kursi hal qiladi',
      'idle.s2':         'Servis kursi rasmiydan yana {p}% ga past',
      'idle.s2.bez':     'Servis kursi rasmiydan past',
      'idle.s3':         'Hammasini birga hisoblab, kartaga qancha tushishini koʻrsatamiz',

      'err.min':         'Eng kami {min} ₽ — kichikroq summani hech kim yubormaydi',
      'err.max':         'Eng koʻpi {max} ₽ — bundan katta oʻtkazmani xizmatlar bir amalda qabul qilmaydi',
      'err.nan':         'Summani raqam bilan kiriting',

      'loss.t':          'Usullar orasidagi farq',
      'loss.sub':        '{sum} ₽ da eng yaxshi usul shuncha qoʻshadi',

      'tag.best':        'Eng koʻp',
      'tag.stale':       'kecha yangilangan',

      'unit.sum':        'soʻm',
      'time.min':        '{n} daqiqada',
      'time.hour':       '{n} soatda',
      'time.day':        '{n} kunda',

      'detail.est':      'bank kursi taxminiy',
      'detail.worse':    'bank kursi rasmiydan {p}% past',
      'detail.better':   'bank kursi rasmiydan {p}% yuqori',
      'detail.stale':    'bank kursi aniqlanmoqda',
      'detail.limit':    'limitdan yuqori - hujjat tekshiruvi kerak',
      // Pastki chegara ham bor: Yubor 100 dollardan kam oʻtkazmani
      // qabul qilmaydi. Buni aytmasak, odam buni servisning oʻzidan
      // bilib oladi — biz hisoblab bergandan keyin.
      'detail.min':      'bu summa uchun juda kam - servis qabul qilmaydi',

      'empty':           'Maʼlumotlar yangilanmoqda. Bir soatdan keyin kiring — notoʻgʻri raqam koʻrsatmaymiz.',
      'test':            'TEST MAʼLUMOT, raqamlar oʻylab topilgan. ',
      'disclaimer.main': 'Biz pul oʻtkazmaymiz. Qabul qiluvchi bank kursi taxminiy — bank uni pul tushgan kuni belgilaydi, yakuniy summa farq qilishi mumkin.',

      'kurs.fail':       'Markaziy bank kursini yangilab boʻlmadi — zaxira qiymatlar boʻyicha, raqamlar taxminiy',
      'kurs.date':       'Markaziy bank kursi {d} holatiga',

      'popup.total':     'Kartaga tushadi',
      'popup.est':       'Qabul qiluvchi bank kursi taxminiy — bank uni pul tushgan kuni belgilaydi.',
      'popup.go':        'Xizmatga oʻtish',

      'razbor.sent':        'Yuborildi',
      'razbor.fee':         'Xizmat komissiyasi',
      'razbor.toconv':      'Konvertatsiyaga',
      'razbor.rate_serv':   'Xizmat kursi',
      'razbor.rate_rubusd': 'Rubl → dollar kursi',
      'razbor.in_currency': 'Valyutada ketdi',
      'razbor.rate_bank':   'Bank kursi → soʻm',

      // ── Verdikt: bugun yubormoqmi yoki kutmoqmi ──────────────────
      // Mahsulotning asosiy ekrani. Oyda kurs 9,5% ga oʻzgardi — bu
      // servis tanlashdan ham, bank tanlashdan ham koʻproq pul.
      // Verdikt KURSNI tasvirlaydi, kunni emas — shuning uchun «bugun»
      // soʻzisiz. Markaziy bank dam olish kunlari kurs eʼlon qilmaydi, va
      // dushanba kuni eng yangi kurs — juma kuniniki. «Bugungi kurs»
      // deyish haftada uch kun yolgʻon boʻlardi. Sana yonida turadi.
      'v.otlichno':       'Kurs odatdagidan sezilarli yaxshi',
      'v.horosho':        'Kurs odatdagidan yaxshiroq',
      'v.obychno':        'Kurs odatdagidek',
      'v.nize_obychnogo': 'Kurs odatdagidan pastroq',
      'v.ploho':          'Kurs odatdagidan sezilarli yomon',

      'v.rate':          '1 ₽ = {r} soʻm',
      'v.avg':           'oydagi oʻrtacha {r}',
      'v.pos':           'oyning {p}% kunidan yaxshi',
      'v.pos.worst':     'oyning eng yomon kuni',
      'v.pos.best':      'oyning eng yaxshi kuni',
      'v.trend.rastet':  'kurs koʻtarilmoqda',
      'v.trend.padaet':  'kurs tushmoqda',
      'v.trend.stoit':   'kurs turibdi',
      'v.onsum.plus':    '{sum} ₽ uchun odatdagidan {n} soʻm koʻp olasiz',
      'v.onsum.minus':   '{sum} ₽ uchun odatdagidan {n} soʻm kam olasiz',
      'v.onsum.zero':    'Kurs odatdagidek — shoshilishning hojati yoʻq',
      'v.do.otpravlyat':   'Yubormoqchi boʻlsangiz — bugun yaxshi kun.',
      'v.do.mozhno_zhdat': 'Kurs odatdagidan past, lekin koʻtarilmoqda — kutish maʼnoli.',
      'v.do.ne_zhdat':     'Kurs tushmoqda — qancha kutsangiz, shuncha kam yetadi.',
      'v.do.obychno':      'Kurs odatdagidek. Quyida — kartaga qancha tushishi.',
      // Ma'lumotlar eski bo'lsa, maslahat bermaymiz. To'rt kunlik kurs
      // bo'yicha «bugun yaxshi kun» deyish — odamga pul yo'qotish
      // maslahatini berish bilan barobar.
      'v.do.stale':        'Maʼlumotlar eski — bugun uchun maslahat bermayman. Kursni tekshiring.',
      'v.days':          '30 kun',
      'v.week.up':       'haftada +{p}%',
      'v.week.down':     'haftada −{p}%',
      'v.spread':        'Oyning eng yaxshi va eng yomon kuni orasida — sizning summangizda {n} soʻm',

      // ── Raqamlar qayerdan ────────────────────────────────────────
      'src.t':           'Raqamlar qayerdan',
      'src.cb':          'Rasmiy kurs — Oʻzbekiston Markaziy bankining ochiq API si',
      // bank.uz oʻz sahifasida kurs QAY KUNGI ekanini yozmaydi. Biz faqat
      // qachon oʻqiganimizni bilamiz — buni aytib qoʻyish kerak, chunki
      // «sana yoʻq raqam — bu yolgʻon» qoidasi bizga ham tegishli.
      'src.svc':         'Oʻtkazma kurslari — bank.uz (u yerda eʼlon sanasi koʻrsatilmagan)',
      // Ikki xil narsani chalkashtirmaslik kerak: MA'LUMOT har soatda
      // yigʻiladi, KURS esa Markaziy bank e'lon qilgan kunga tegishli.
      // Ilgari bu yerda «har soatda yangilanadi, oxirgi marta 14.08» deb
      // yozilgan edi — ya'ni «ikki kundan beri yangilanmagan» degandek
      // oʻqilardi, holbuki hammasi joyida edi.
      'src.upd':         'Har soatda yigʻamiz. Markaziy bank kursi — {d} holatiga',
      // Odam roʻyxatni toʻliq deb oʻylamasligi kerak. Koridorda Zolotaya
      // Korona, Contact, Unistream va banklar ham ishlaydi — lekin ular
      // kurslarini ochiq eʼlon qilmaydi, shuning uchun bizda yoʻq.
      'src.chastichno':  'Kurslarini ochiq eʼlon qiladiganlarni koʻrsatamiz. Koridorda boshqa servislar ham bor.',
      'src.no':          'Biz pul oʻtkazmaymiz va qabul qilmaymiz. Faqat hisoblaymiz.',

      // ── Servis kursi rasmiy kursga nisbatan ──────────────────────
      'svc.markup':      'kurs rasmiydan {p}% past',
      'svc.fee_unknown': 'komissiya eʼlon qilinmagan — bu yuqori chegara',
      // Sarlavha raqamda nima borligini aytadi: kurs ham, komissiya ham.
      // Ilgari 'Oʻtkazma kursi olib qoldi' turardi, raqamda esa ikkalasi
      // ham hisoblangan — eng yaxshi usulda komissiya paydo boʻlgan kuni
      // sarlavha yolgʻon boʻlib qoldi. Pastdagi izoh — Markaziy bank kursi.
      'svc.lost.t':      'Oʻtkazma olib qoldi',
      'svc.official':    'Markaziy bank kursi bilan solishtirganda',
      'svc.lost':        'Kurs farqi: {n} soʻm',

      // ── Xabarnomaga obuna ────────────────────────────────────────
      'sub.t':           'Kurs yaxshilanganda aytaymi?',
      'sub.p':           'Faqat kurs odatdagidan yaxshi boʻlganda yozaman — yaʼni jim turishim sizga pulga tushadigan paytda. Uch kunda bir martadan koʻp emas.',
      'sub.btn':         'Ha, xabar bering',
      'sub.ch':          'Yoki har kuni ertalab kanalda kurs',

      // ── Pul qayerga ketadi ───────────────────────────────────────
      'br.t':            'Pul qayerga ketadi',
      'br.cb':           'Markaziy bank kursi boʻyicha',
      'br.rate':         'Xizmat kursi',
      'br.fee':          'Komissiya',
      'br.fee_unknown':  'eʼlon qilinmagan',
      'br.total':        'Kartaga tushadi',

      'err.net':         'Yangi kurslarni olib boʻlmadi — {d} holatidagi maʼlumot bilan hisobladim',

      // Пересылка — главный способ, которым про нас узнают. Поэтому здесь
      // не только цифры: нужна строка, объясняющая чужому человеку, что он видит.
      'share.title':     '{sum} ₽ yuboryapman — avval kursni tekshirdim.',
      'share.diff':      'Usullar orasidagi farq {p}% chiqdi.',
      // Xabar ketadigan raqam. Bu — mahsulotning butun maʼnosi: kunni
      // tanlash servisni tanlashdan koʻproq pul hal qiladi. Ilgari bu yerda
      // birorta ham pul raqami yoʻq edi, yaʼni xabarni uzatishga sabab
      // ham yoʻq edi.
      'share.spread':    'Oy davomida kurs {p}% ga oʻzgardi — 50 000 rublda bu {n} soʻm.',
      // Sana majburiy: raqam sanasiz — bu yolgʻon, va bu xabar begona
      // chatlarga ketadi, u yerda uni tuzatib boʻlmaydi.
      'share.date':      'Markaziy bank kursi, {d}',
      'share.cta':       'Yuborishdan oldin kursga qarang.',
    },

    ru: {
      'app.name':        'Сколько дойдёт',

      'intro.h1':        'Отправлять сегодня или подождать',
      // Числа сюда подставляются из живых данных, а не пишутся словами.
      // Здесь стояло «от 155 до 141, это 9,5% — 670 тысяч сум»: правда
      // того дня, когда текст писали. К 22 августа окно съехало на
      // 138,67–153,87, то есть 10,96% и 760 000 сум, и первое, что читал
      // человек, расходилось с панелью прямо под ним — на одном экране
      // два разных ответа на один вопрос. Прогон этого поймать не мог:
      // числа были в словаре, а не в расчёте.
      'intro.p1':        'За месяц курс рубля прошёл путь <b>от {mn} до {mx}</b>. Это {p}% — на 50 000 ₽ это {n} сум. Не какой сервис, а какой <b>день</b> — вот где основные деньги.',
      // Данных за месяц нет — говорим без чисел. Выдуманное число здесь
      // хуже отсутствующего: на нём стоит всё обещание продукта.
      'intro.p1.bez':    'За месяц курс рубля успевает пройти заметный путь, и на переводе это больше, чем разница между сервисами. Не какой сервис, а какой <b>день</b> — вот где основные деньги.',
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
      'idle.s1':         'Курс дня решает больше всего — {p}% за месяц',
      'idle.s1.bez':     'Курс дня решает больше всего',
      'idle.s2':         'Курс сервиса ниже официального ещё на {p}%',
      'idle.s2.bez':     'Курс сервиса ниже официального',
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
      // Нижняя граница тоже бывает: Yubor не принимает переводы меньше
      // ста долларов. Не сказать значит дать человеку посчитать и
      // отправить его получать отказ в самом сервисе.
      'detail.min':      'меньше минимума - сервис не примет',

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
      // bank.uz не пишет, на какой день курс. Мы знаем только, когда сами
      // его прочитали, и обязаны это сказать: правило «цифра без даты —
      // это ложь» распространяется и на нас самих.
      'src.svc':         'Курсы переводов — bank.uz (дата публикации там не указана)',
      // Здесь смешивались две разные вещи: ДАННЫЕ собираются каждый час,
      // а КУРС относится к тому дню, когда его опубликовал ЦБ. Стояло
      // «обновляется каждый час, последний раз 14.08» — и это читалось
      // как «два дня не обновлялось», хотя всё работало исправно.
      'src.upd':         'Собираем каждый час. Курс ЦБ — на {d}',
      // Человек не должен считать список полным. В коридоре работают ещё
      // Золотая Корона, Contact, Юнистрим и банки — но они не публикуют
      // курсы открыто, поэтому их у нас нет. Умолчать об этом значит
      // выдать два сервиса за весь рынок.
      'src.chastichno':  'Показываем тех, кто публикует курс открыто. В коридоре есть и другие сервисы.',
      'src.no':          'Мы не переводим и не принимаем деньги. Только считаем.',

      // ── Курс сервиса против официального ─────────────────────────
      'svc.markup':      'курс на {p}% ниже официального',
      'svc.fee_unknown': 'комиссию не публикуют — это верхняя граница',
      // Заголовок называет ровно то, что стоит в числе: курс И комиссию.
      // Здесь было «Забрал курс перевода», а число всё это время равнялось
      // «по курсу ЦБ минус то, что дошло», то есть включало и комиссию.
      // Пока у лучшего способа комиссии не было, эти два совпадали; в день,
      // когда сверху встал сервис с комиссией, заголовок стал неправдой.
      // Из чего сложилась потеря — говорит разбор строкой ниже.
      'svc.lost.t':      'Перевод забрал',
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
