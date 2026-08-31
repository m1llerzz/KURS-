/**
 * ЭКРАН
 *
 * Читает поля, зовёт CALC, рисует результат, отправляет в чат.
 * Здесь НЕТ ни одной формулы. Если понадобилось что-то умножить —
 * значит логика попала не в тот файл, ей место в calc.js.
 *
 * Порядок экрана повторяет порядок денег, а не порядок разработки:
 *
 *     вердикт дня      до 9,5% на переводе   ← стоит первым
 *     курс сервиса        около 4%
 *     банк получателя     около 0,8%         ← скрыт, пока не измерен
 *
 * Раньше первым стоял ввод суммы, и человек уходил, не узнав главного.
 */

(function () {

  const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
  if (tg) { tg.ready(); tg.expand(); }

  const el = {
    intro:      document.getElementById('intro'),
    introOk:    document.getElementById('introOk'),
    summa:      document.getElementById('summa'),
    bank:       document.getElementById('bank'),
    bankBlock:  document.getElementById('bankBlock'),
    schitat:    document.getElementById('schitat'),
    results:    document.getElementById('results'),
    loss:       document.getElementById('loss'),
    lossT:      document.getElementById('lossT'),
    lossNum:    document.getElementById('lossNum'),
    lossSub:    document.getElementById('lossSub'),
    share:      document.getElementById('share'),
    disclaimer: document.getElementById('disclaimer'),
    kursDate:   document.getElementById('kursDate'),
    summaErr:   document.getElementById('summaErr'),
    idle:       document.getElementById('idle'),
    verdict:    document.getElementById('verdict'),
    vHead:      document.getElementById('vHead'),
    vRate:      document.getElementById('vRate'),
    vAvg:       document.getElementById('vAvg'),
    vSpark:     document.getElementById('vSpark'),
    vBadge:     document.getElementById('vBadge'),
    vOsL:       document.getElementById('vOsL'),
    vOsR:       document.getElementById('vOsR'),
    vDot:       document.getElementById('vDot'),
    chips:      document.getElementById('chips'),
    vMeta:      document.getElementById('vMeta'),
    vOnSum:     document.getElementById('vOnSum'),
    vSpread:    document.getElementById('vSpread'),
    vHint:      document.getElementById('vHint'),
    subCta:     document.getElementById('subCta'),
    subBtn:     document.getElementById('subBtn'),
    chLink:     document.getElementById('chLink'),
    srcUpd:     document.getElementById('srcUpd'),
    razbor:     document.getElementById('razbor'),
    rBar:       document.getElementById('rBar'),
    rRows:      document.getElementById('rRows'),
  };

  // Telegram кеширует html и js порознь, и какое-то время после обновления
  // новый скрипт работает со старой разметкой. Место под сообщение об ошибке
  // в таком случае создаём сами — иначе валидация молча падает на null.
  if (!el.summaErr) {
    el.summaErr = document.createElement('p');
    el.summaErr.id = 'summaErr';
    el.summaErr.className = 'err hidden';
    el.summaErr.style.cssText = 'margin:6px 2px 0;font-size:12.5px;color:#c0392b;font-weight:600';
    el.summa.parentNode.parentNode.insertBefore(el.summaErr, el.summa.parentNode.nextSibling);
  }

  /**
   * Границы суммы. Сверху — миллион: больше сервисы не проводят одной
   * операцией. Проверено на живом вводе: без верхней границы приложение
   * спокойно считало пять квинтиллионов рублей.
   */
  const MIN_SUMMA = 1000;
  const MAX_SUMMA = 1000000;

  let posledniyRaschet = null;
  let posledniyKurs = null;
  let ocenkaDnya = null;
  let SERVISY = window.SERVICES || [];
  let BANKI = window.BANKS || [];
  let ISTORIYA = window.HISTORY_ZAPAS || [];
  let dannyeUstareli = null;   // дата, если считаем по запасу

  const t = window.I18N.t;

  /* ── Мелкая память ───────────────────────────────────────
   * Сумма и банк запоминаются не ради удобства, а ради смысла: человек,
   * который однажды ввёл свои 50 000, в следующий раз открывает приложение
   * и сразу видит вердикт В СВОИХ СУМАХ, а не в процентах. Проценты
   * не чувствует никто, свои деньги — все.
   */
  function pomnit(klyuch, znachenie) {
    try {
      if (znachenie === undefined) return localStorage.getItem(klyuch);
      localStorage.setItem(klyuch, znachenie);
    } catch (e) {}
    return null;
  }

  /* ── Учёт ────────────────────────────────────────────────
   *
   * Считаем ровно четыре вещи: открыл, посчитал, переслал, пошёл в сервис.
   * Этого хватает, чтобы понимать продукт, и не хватает, чтобы навредить
   * человеку: ни имени, ни телефона, ни суммы конкретного перевода мы
   * никуда не отправляем — только её порядок.
   *
   * Зачем вообще. Партнёрскую программу не дают под обещание: просят
   * показать поток. Пока никто не считает, сколько людей доходит до
   * выбора способа, разговаривать с Remitly или Wise не о чем.
   *
   * Учёт свой: ни одного внешнего скрипта в приложении, ноль рублей,
   * ноль слежки за человеком по другим сайтам.
   */
  function sobytie(tip, dannye) {
    if (!window.API_URL) return;
    const adres = window.API_URL.replace(/\/api\/rates$/, '/api/event');

    let chatId = null;
    try {
      const u = tg && tg.initDataUnsafe && tg.initDataUnsafe.user;
      if (u && u.id) chatId = u.id;
    } catch (e) {}

    /* Метку источника кладём в КАЖДОЕ событие, а не только в «открыл».
     *
     * Иначе видно «из этого чата пришло сорок человек» — и всё. А вопрос
     * другой: сколько из них дошли до расчёта. Чат с двумя сотнями
     * переходов и нулём расчётов хуже, чем чат с двадцатью переходами и
     * пятнадцатью расчётами, — и по одним переходам их не различить.
     * Ради этой разницы посев и ведётся по одному чату за раз. */
    const otkuda = istochnik();
    const polya = dannye ? Object.assign({}, dannye) : {};
    if (otkuda) polya.istochnik = otkuda;

    const telo = JSON.stringify({
      tip: tip, chat_id: chatId,
      dannye: Object.keys(polya).length ? polya : null,
    });

    try {
      // sendBeacon переживает закрытие приложения — обычный fetch на
      // выходе браузер отменяет, и половина событий терялась бы молча.
      if (navigator.sendBeacon) {
        navigator.sendBeacon(adres, new Blob([telo], { type: 'application/json' }));
        return;
      }
      fetch(adres, {
        method: 'POST', body: telo, keepalive: true,
        headers: { 'Content-Type': 'application/json' },
      }).catch(function () {});
    } catch (e) {}   // учёт никогда не мешает работе приложения
  }

  /* Откуда человек пришёл.
   *
   * Telegram кладёт метку из ссылки `?startapp=МЕТКА` в start_param, а в
   * браузере она видна прямо в адресе. Читаем оба места: внутри Telegram
   * работает первое, при открытии по обычной ссылке — второе.
   *
   * Зачем это нужно ровно настолько, насколько нужен весь маркетинг.
   * Денег на рекламу нет, значит каждый человек приходит из какого-то
   * одного места: из канала, из чата, из чужой пересылки. Без метки все
   * они сливаются в одно число «пришло сорок человек», и понять, что
   * работает, а что впустую, нельзя вообще ничем.
   *
   * Метку чистим: чужой текст из адресной строки попадает к нам в учёт,
   * и пускать его туда как есть нельзя.
   */
  function istochnik() {
    let metka = null;
    try {
      const iz_tg = tg && tg.initDataUnsafe && tg.initDataUnsafe.start_param;
      if (iz_tg) {
        metka = String(iz_tg);
      } else {
        const najdeno = String(window.location.href)
          .match(/(?:startapp|tgWebAppStartParam)=([^&#]+)/);
        if (najdeno) metka = decodeURIComponent(najdeno[1]);
      }
    } catch (e) {}

    if (!metka) return null;
    metka = metka.toLowerCase().replace(/[^a-z0-9_-]/g, '').slice(0, 32);
    return metka || null;
  }

  /** Порядок суммы вместо самой суммы: 50 000 → «50k». */
  function poryadok(n) {
    const v = Math.abs(Number(n) || 0);
    if (v < 10000) return 'до10k';
    if (v < 50000) return '10-50k';
    if (v < 150000) return '50-150k';
    if (v < 500000) return '150-500k';
    return 'от500k';
  }

  /* ── Форматирование ──────────────────────────────────────── */

  /**
   * Число с пробелами по три знака.
   *
   * toString() у больших чисел переключается на запись вида 5e+28, и в
   * пересланном сообщении это выглядело набором символов из спама.
   */
  function sum(n) {
    const chislo = Math.round(Number(n));
    if (!isFinite(chislo)) return '—';
    let stroka;
    try {
      stroka = BigInt(chislo).toString();
    } catch (e) {
      stroka = chislo.toFixed(0);
    }
    return stroka.replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  }

  /**
   * Дробное число так, как его пишут по-русски и по-узбекски: 141,76.
   * JavaScript печатает 141.76, а человек в обеих странах читает через
   * запятую. Мелочь ровно до того момента, пока не поймёшь, что именно
   * из таких мелочей складывается ощущение самоделки.
   */
  function chislo(n, znakov) {
    return Number(n).toFixed(znakov === undefined ? 2 : znakov).replace('.', ',');
  }

  /**
   * Дата словами: 2026-08-14 → «14 августа» / «14 avgust».
   *
   * Машинное «2026-08-14» под курсом читается как отладочный вывод, а не
   * как подпись к числу, которому человек должен поверить. А поверить он
   * должен: дата здесь — половина доказательства, что цифра настоящая.
   *
   * Кривую дату отдаём как есть: показать что-то честнее, чем ничего.
   */
  const MESYACY = {
    uz: ['yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun',
         'iyul', 'avgust', 'sentabr', 'oktabr', 'noyabr', 'dekabr'],
    ru: ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
         'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'],
  };

  /* Сколько дней данные могут быть старыми, прежде чем мы перестанем
   * советовать. То же число живёт в боте под тем же именем, и они
   * обязаны совпадать: разойдутся — один человек получит разные советы
   * в чате и в мини-аппе. За совпадением следит test_parity.py.
   *
   * Порог мягче правила про курсы сервисов (трое суток) намеренно: ЦБ
   * не публикует по выходным и в праздники, длинные каникулы — норма. */
  const PREDEL_SOVETA_DNEY = 5;

  /**
   * Сколько дней прошло с даты курса. Понимает оба формата дат.
   * Не смогли разобрать — считаем свежим: молчать о совете из-за
   * непонятой строки хуже, чем дать его.
   */
  function vozrastDannyhDney(data) {
    const stroka = String(data || '').trim();
    let god, mesyac, den;
    let najdeno = stroka.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (najdeno) {
      god = +najdeno[1]; mesyac = +najdeno[2]; den = +najdeno[3];
    } else {
      najdeno = stroka.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})/);
      if (!najdeno) return 0;
      den = +najdeno[1]; mesyac = +najdeno[2]; god = +najdeno[3];
    }
    const kogda = Date.UTC(god, mesyac - 1, den);
    if (isNaN(kogda)) return 0;
    return (Date.now() - kogda) / 86400000;
  }

  function dataSlovom(iso, lang) {
    const stroka = String(iso || '').trim();

    /* Форматов два, и оба приходят в одном ответе.
     *
     * ЦБ Узбекистана отдаёт «14.08.2026», а история и вердикт считаются
     * в «2026-08-14». Понимать надо оба: разбирать только один — значит
     * однажды показать человеку сырую строку вместо даты и не заметить
     * этого, потому что она всё-таки похожа на дату. */
    let den, mesyac;
    let najdeno = stroka.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (najdeno) {
      den = parseInt(najdeno[3], 10);
      mesyac = parseInt(najdeno[2], 10);
    } else {
      najdeno = stroka.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})/);
      if (!najdeno) return stroka;
      den = parseInt(najdeno[1], 10);
      mesyac = parseInt(najdeno[2], 10);
    }

    const spisok = MESYACY[lang] || MESYACY[window.I18N.get()] || MESYACY.ru;
    const nazvanie = spisok[mesyac - 1];
    if (!nazvanie || !den) return stroka;
    return den + ' ' + nazvanie;
  }

  /**
   * Срок доставки словами. Число подставляется внутрь строки языка,
   * а не приклеивается к ней: по-узбекски время требует окончания.
   */
  function srok(minut) {
    if (minut < 60) return t('time.min', { n: minut });
    if (minut < 1440) return t('time.hour', { n: Math.round(minut / 60) });
    return t('time.day', { n: Math.round(minut / 1440) });
  }

  /* ── Данные: бот → кеш → файл ─────────────────────────────
   *
   * Раньше приложение ходило напрямую в ЦБ, а тарифы лежали в data.js
   * и правились руками. Теперь всё собирает бот: он раз в час обходит
   * ЦБ и bank.uz, считает наценку каждого сервиса к официальному курсу
   * и отдаёт готовый набор. Приложению остаётся нарисовать.
   *
   * Три уровня отступления, и ни на одном мы не показываем цифру без даты:
   *     1. живой ответ бота
   *     2. кеш в браузере, если он моложе суток
   *     3. запас в data.js — с честной пометкой, что данные не свежие
   *
   * И поверх всех трёх — второй слой: официальный курс приложение
   * спрашивает у ЦБ само, напрямую из браузера. Он перекрывает любой из
   * уровней, если его число свежее, и не трогает ни один, если нет.
   */

  function izKesha() {
    try {
      const syroe = localStorage.getItem('dannye');
      if (!syroe) return null;
      const d = JSON.parse(syroe);
      const chasov = (Date.now() - d.saved_at) / 36e5;
      return chasov <= 24 ? d : null;
    } catch (e) { return null; }
  }

  /* Ссылка на канал. Появляется, только если канал заведён: пустой адрес
   * — нормальное рабочее состояние, а не недоделка.
   *
   * Вызывается дважды: при запуске (адрес мог лежать в data.js) и когда
   * пришёл ответ бота. Второй раз обработчик вешать нельзя — иначе на
   * одно нажатие уходило бы два события, и клики по каналу считались бы
   * вдвое. Такое искажение в цифрах не видно ничем, кроме удивления
   * через месяц.
   */
  let kanalPokazan = false;

  function pokazatKanal() {
    if (kanalPokazan || !el.chLink || !window.CHANNEL_LINK) return;
    kanalPokazan = true;

    el.chLink.href = window.CHANNEL_LINK;
    el.chLink.classList.remove('hidden');
    el.chLink.addEventListener('click', function (e) {
      sobytie('kanal_klik');
      // Внутри Telegram ссылку надо открывать его же средствами,
      // иначе она уходит во внешний браузер и человек теряется.
      if (tg && tg.openTelegramLink) {
        e.preventDefault();
        tg.openTelegramLink(window.CHANNEL_LINK);
      }
    });
  }

  function primenit(d) {
    if (d.services && d.services.length) SERVISY = d.services;
    if (d.banks) BANKI = d.banks;
    if (d.history && d.history.length) ISTORIYA = d.history;

    /* Адрес канала приходит от бота, а не лежит в data.js.
     *
     * Иначе после создания канала пришлось бы править код, поднимать
     * версию скриптов и заливать заново — три шага, из которых забудут
     * хотя бы один, и ссылка не появится вообще. Так достаточно задать
     * переменную на Render.
     *
     * Вписанное руками в data.js имеет приоритет: если однажды понадобится
     * увести людей на другой канал, это должно работать без бота. */
    if (d.channel && !window.CHANNEL_LINK) {
      window.CHANNEL_LINK = String(d.channel);
      pokazatKanal();
    }
    if (d.cbu) {
      posledniyKurs = {
        usd_uzs: d.cbu.usd_uzs,
        rub_uzs: d.cbu.rub_uzs,
        date: d.cbu.date,
      };
    }
  }

  /* ── Второй слой курса: прямой запрос в ЦБ ────────────────
   *
   * Официальный курс — главное число продукта, и до сих пор он приходил
   * ровно одним путём: через бота. Путь один, и он уже отказал: с
   * 21 августа Render держит сервис приостановленным, приложение живёт
   * на запасе из data.js, а запас пересобирает GitHub четыре раза в
   * сутки — то есть человек в лучшем случае видит курс шестичасовой
   * давности, а пока запас не залит, не видит совета вовсе.
   *
   * ЦБ Узбекистана отдаёт свой JSON прямо в браузер: `access-control-
   * allow-origin: *` стоит и на витрине, и на архиве с датой (проверено
   * 29 и 31 августа 2026). Значит курс может приходить человеку в момент
   * публикации и вообще без нашего сервера.
   *
   * Слой именно ВТОРОЙ, а не первый. Курсы сервисов из браузера не взять
   * никогда: bank.uz отвечает 403 и без CORS. Здесь только курс ЦБ — и
   * он применяется, лишь когда СВЕЖЕЕ уже известного, иначе страховка
   * начнёт откатывать данные назад.
   */
  const CBU_JSON = 'https://cbu.uz/ru/arkhiv-kursov-valyut/json/';

  function sprositCB(hvost, zaprosheno) {
    return fetch(CBU_JSON + hvost, { cache: 'no-store' })
      .then(function (r) { return r.json(); })
      .then(function (spisok) {
        return window.CALC.razborKursaCB(spisok, zaprosheno);
      })
      // ЦБ недоступен — приложение работает ровно как раньше. Второй слой
      // на то и второй: его отказ не должен быть виден человеку.
      .catch(function () { return null; });
  }

  function zagruzitKursCB() {
    const segodnya = window.CALC.denVTashkente();

    /* Сначала архив за сегодняшнее ташкентское число.
     *
     * Витрина без даты отстаёт от архива в момент публикации: 28 августа
     * в 00:20 по Ташкенту архив уже отдавал курс за 28-е, а витрина всё
     * ещё вчерашний. Если за сегодня ЦБ не публиковал — выходной или
     * праздник — архив ответит последним рабочим курсом с его же датой,
     * и это правильный ответ, а не пустота. */
    return sprositCB('all/' + segodnya + '/', segodnya).then(function (cb) {
      /* Витрина — отступление на случай, когда архив не ответил вовсе.
       * Потолок даты тот же, сегодняшний: у витрины нет даты в запросе,
       * и без потолка она принимала бы любое число, в том числе
       * завтрашнее. Дырой это и оказалось — нашлось прогоном, а не
       * чтением: архив число из будущего отвергал, а витрина за ним
       * тихо его пропускала. */
      return cb || sprositCB('', segodnya);
    });
  }

  /**
   * Применить курс ЦБ, если он свежее известного. @returns {boolean}
   *
   * Сравниваем ДАТЫ ПУБЛИКАЦИИ, а не время ответа: два источника одного
   * курса отличаются не тем, кто ответил позже, а тем, чьё число новее.
   */
  function primenitKursCB(cb) {
    if (!cb || !cb.date) return false;

    const bylo = window.CALC.vISO(posledniyKurs && posledniyKurs.date);
    if (bylo && cb.date <= bylo) return false;

    posledniyKurs = {
      usd_uzs: cb.usd_uzs,
      rub_uzs: cb.rub_uzs,
      date: cb.date,
      source: cb.source,
    };

    /* Ряд обязан получить новую точку.
     *
     * Вердикт считается по ряду, а не по снимку. Оставив ряд прежним, мы
     * поставили бы сегодняшний курс рядом с вердиктом за вчера — на одном
     * экране, друг под другом, и разошлись бы они ровно в тот день, когда
     * курс дёрнулся, то есть когда совет важнее всего. */
    const posledniaya = ISTORIYA.length ? ISTORIYA[ISTORIYA.length - 1] : null;
    if (!posledniaya || cb.date > window.CALC.vISO(posledniaya.date)) {
      ISTORIYA = ISTORIYA.concat([{ date: cb.date, rub_uzs: cb.rub_uzs }]);
    }

    /* Бот молчал, и мы собирались честно сказать «связи нет, данные от
     * такого-то». Теперь официальный курс свежий, и та надпись врёт уже
     * в другую сторону. Свежесть каждого способа при этом считается
     * отдельно, по его `checked_at`: протухшие всё так же не покажутся. */
    dannyeUstareli = null;
    return true;
  }

  function zagruzitDannye() {
    /* Кеш рисует экран мгновенно, но НЕ отменяет запрос.
     *
     * Здесь стоял ранний возврат: есть кеш моложе суток — берём его и в
     * сеть не идём вовсе. На часах это выглядело так: человек открыл
     * приложение в восемь вечера, наутро ЦБ опубликовал новый курс, а он
     * заходит в десять — и видит вчерашний. Кеш моложе суток, запрос не
     * ушёл. Продукт, который отвечает на вопрос «какой курс СЕГОДНЯ»,
     * показывал вчерашний, и заметить это можно было только сверив с
     * cbu.uz.
     *
     * Теперь кеш — это первый кадр, а не ответ. Свежие данные приходят
     * следом и перерисовывают экран. */
    const kesh = izKesha();
    if (kesh) primenit(kesh);

    /* Два запроса уходят разом, а не по очереди: ждать бота, чтобы потом
     * пойти в ЦБ, значит подарить человеку лишние секунды на плохом
     * интернете. А применяется второй слой ПОСЛЕ ответа бота — иначе бот,
     * ответивший последним, перезаписал бы свежий курс своим, собранным
     * шесть часов назад. */
    const otCB = zagruzitKursCB();

    return zagruzitOtBota(kesh).then(function (d) {
      return otCB.then(function (cb) {
        primenitKursCB(cb);
        return d;
      });
    });
  }

  /** Ответ бота: сервисы, история, вердикт. Молчит — отступаем на кеш. */
  function zagruzitOtBota(kesh) {
    if (!window.API_URL) return Promise.resolve(kesh || zapasnoy());

    return fetch(window.API_URL, { cache: 'no-store' })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d || !d.cbu || !d.cbu.rub_uzs) throw new Error('неполный ответ');
        d.saved_at = Date.now();
        try { localStorage.setItem('dannye', JSON.stringify(d)); } catch (e) {}
        primenit(d);
        return d;
      })
      .catch(function () {
        // Бот спит или сети нет. Отдаём последнее, что знаем, и говорим
        // об этом словами — цифра без даты хуже отсутствия цифры.
        const staryi = localStorage.getItem('dannye');
        if (staryi) {
          try {
            const d = JSON.parse(staryi);
            primenit(d);
            dannyeUstareli = (d.cbu && d.cbu.date) || null;
            return d;
          } catch (e) {}
        }
        return zapasnoy();
      });
  }

  function zapasnoy() {
    const d = {
      cbu: window.KURSY_ZAPAS,
      services: window.SERVICES || [],
      banks: window.BANKS || [],
      history: window.HISTORY_ZAPAS || [],
      zapas: true,
    };
    primenit(d);
    posledniyKurs = Object.assign({}, window.KURSY_ZAPAS);
    dannyeUstareli = null;
    return d;
  }

  /* ── Вердикт дня ─────────────────────────────────────────── */

  /* Линия месяца прочерчивается один раз за открытие приложения.
   *
   * Вердикт рисуется дважды подряд: сначала по кешу — чтобы экран не
   * пустовал ни секунды, — потом по живым курсам от бота. Анимация без
   * этой памяти проигрывалась бы оба раза, с интервалом в полсекунды, и
   * читалась бы как сбой отрисовки, а не как замысел. */
  let grafikUzheRisovalsya = false;

  /** Рисует настоящий ряд курсов ЦБ за месяц. */
  function narisovatGrafik(ryad) {
    if (!el.vSpark || !ryad || ryad.length < 2) return;

    /* Поле выросло с 54 до 104: на прежней высоте месячный ход курса
     * укладывался в полтора десятка пикселей и выглядел ровной чертой.
     * То есть картинка, ради которой всё и затевалось, говорила ровно
     * обратное тому, что говорят числа рядом с ней. */
    const W = 300, H = 104, otstup = 11;

    /* Поле шире линии на четырнадцать единиц с каждой стороны.
     *
     * График доходит до самых краёв панели, а панель обрезает всё, что за
     * край вышло. Сегодняшняя точка — крайняя правая, и её кружок с ореолом
     * разрезало ровно пополам: самая важная точка ряда оказалась
     * единственной, которую не видно целиком.
     *
     * Поэтому ЛИНИЯ и точка живут внутри отступов, а ЗАЛИВКА по-прежнему
     * идёт от края до края — её растворяющемуся низу ровные хвосты по бокам
     * не мешают, а панель остаётся без полей. */
    const bok = 14;
    const znacheniya = ryad.map(function (x) { return x.rub_uzs; });
    const mn = Math.min.apply(null, znacheniya);
    const mx = Math.max.apply(null, znacheniya);
    // Ровный курс дал бы деление на ноль и линию за краем поля.
    const razmah = (mx - mn) || 1;

    function X(i) { return bok + (i / (ryad.length - 1)) * (W - bok * 2); }
    function Y(v) { return H - otstup - ((v - mn) / razmah) * (H - otstup * 2); }

    const tochki = znacheniya.map(function (v, i) {
      return X(i).toFixed(1) + ',' + Y(v).toFixed(1);
    });

    const srednee = znacheniya.reduce(function (a, b) { return a + b; }, 0) / znacheniya.length;
    const ySred = Y(srednee).toFixed(1);

    const posledniy = znacheniya.length - 1;
    const cx = X(posledniy).toFixed(1);
    const cy = Y(znacheniya[posledniy]).toFixed(1);

    el.vSpark.setAttribute('viewBox', '0 0 ' + W + ' ' + H);

    el.vSpark.innerHTML =
      // Заливка градиентом, а не плоским цветом: плоская заливка под
      // линией спорит с ней за внимание, растворяющаяся — не спорит.
      /* Гаснет быстро и с самого начала слабее. Заливка в четверть силы
       * на поле в сто пикселей — это уже не тень под линией, а цветное
       * пятно во всю панель: на светлой теме янтарный «плохой курс»
       * перекрашивал в бежевое всё, вплоть до заголовка. */
      '<defs><linearGradient id="zaliv" x1="0" y1="0" x2="0" y2="1">' +
      '<stop offset="0%" stop-color="currentColor" stop-opacity=".22"/>' +
      '<stop offset="55%" stop-color="currentColor" stop-opacity=".05"/>' +
      '<stop offset="100%" stop-color="currentColor" stop-opacity="0"/>' +
      '</linearGradient></defs>' +
      // Заливка от края до края: к ряду добавлены две точки на уровне
      // первого и последнего значения — ровные хвосты у самых бортов.
      '<polygon class="ar" points="0,' + H +
        ' 0,' + Y(znacheniya[0]).toFixed(1) + ' ' + tochki.join(' ') +
        ' ' + W + ',' + Y(znacheniya[znacheniya.length - 1]).toFixed(1) +
        ' ' + W + ',' + H + '"/>' +
      // Пунктир среднего — это якорь. Без него линия просто «какая-то»,
      // с ним человек мгновенно видит, выше он сегодня обычного или ниже.
      '<line class="av" x1="0" y1="' + ySred + '" x2="' + W + '" y2="' + ySred + '"/>' +
      /* Вертикаль от сегодняшней точки до низа поля. На ряду из тридцати
       * значений первый вопрос человека — «где здесь сегодня», и кружок,
       * утонувший в линии, на него не отвечает. */
      '<line class="segodnya" x1="' + cx + '" y1="' + cy + '" x2="' + cx + '" y2="' + H + '"/>' +
      '<polyline class="ln" points="' + tochki.join(' ') + '"/>' +
      '<circle class="dtg" cx="' + cx + '" cy="' + cy + '" r="9"/>' +
      '<circle class="dt" cx="' + cx + '" cy="' + cy + '" r="4"/>';

    if (!grafikUzheRisovalsya) {
      el.vSpark.classList.add('risuetsya');
      grafikUzheRisovalsya = true;
    }
  }

  /* Курс крупно, единицы мелко.
   *
   * Строка курса на обоих языках устроена одинаково: «1 ₽ = {r} сум»,
   * «1 ₽ = {r} so'm». Целиком в сорок шесть пикселей она не помещается ни
   * на один телефон — да и не должна: крупным обязано быть значение, а не
   * подпись к нему.
   *
   * Разбираем строку по МЕСТУ ПОДСТАНОВКИ, а не по словам и не по
   * пробелам: слова в языках разные и завтра могут поменяться от вычитки
   * носителем, а {r} стоит в обоих и никуда не денется. Если шаблон
   * однажды окажется устроен иначе, ставим строку целиком — экран
   * останется правильным, просто без разницы в кегле.
   *
   * Метка нарочно из обычных знаков, а не из служебного символа: невидимый
   * символ в исходнике переживает не всякий редактор и не всякую выгрузку,
   * а поймать его потом нечем — глазами он не виден. */
  const MESTO_CHISLA = '[[#]]';

  function postavitKurs(kurs) {
    if (!el.vRate) return;
    const znachenie = chislo(kurs);
    const chasti = t('v.rate', { r: MESTO_CHISLA }).split(MESTO_CHISLA);

    if (chasti.length !== 2) {
      el.vRate.textContent = t('v.rate', { r: znachenie });
      return;
    }

    // textContent, а не innerHTML: тексты свои, но подставлять их разметкой
    // — привычка, из-за которой однажды приезжает чужая строка с тегами.
    el.vRate.textContent = '';
    const kusok = function (klass, tekst) {
      if (!tekst) return;
      const s = document.createElement('span');
      s.className = klass;
      s.textContent = tekst;
      el.vRate.appendChild(s);
    };
    // Пробелы из шаблона оставляем как есть: они отделяют «1 ₽ =» от числа
    // и число от «сум» не только на экране, но и для экранного диктора —
    // он читает текст, а не отступы, которыми мы бы их заменили.
    kusok('vru', chasti[0]);
    kusok('vrn', znachenie);
    kusok('vru', chasti[1]);
  }

  function pokazatVerdikt() {
    ocenkaDnya = window.CALC.sovet(ISTORIYA);

    if (!ocenkaDnya) {
      // Меньше недели данных — вердикта нет. Молчим, а не гадаем.
      el.verdict.classList.add('hidden');
      // Вступление при этом остаётся на экране, и числа в нём брать
      // неоткуда: обновляем и его — вариантом без чисел.
      pokazatVstuplenie();
      return;
    }

    const o = ocenkaDnya;
    const horosho = o.verdikt === 'otlichno' || o.verdikt === 'horosho';
    const ploho = o.verdikt === 'ploho' || o.verdikt === 'nize_obychnogo';

    el.verdict.classList.remove('hidden', 'good', 'bad');
    if (horosho) el.verdict.classList.add('good');
    else if (ploho) el.verdict.classList.add('bad');

    el.vHead.textContent = t('v.' + o.verdikt);
    postavitKurs(o.segodnya);
    el.vAvg.textContent = t('v.avg', { r: chislo(o.srednee_30) });

    // Значок с отклонением — для тех, кто листает быстро и текст не читает.
    // Знак обязателен: «5,4%» без него можно прочесть в любую сторону.
    if (el.vBadge) {
      const otkl = o.otklonenie_percent;
      el.vBadge.textContent = (otkl > 0 ? '+' : otkl < 0 ? '−' : '')
        + Math.abs(otkl).toFixed(1).replace('.', ',') + '%';
    }

    narisovatGrafik(o.ryad);

    // Подписи под графиком: крайние значения месяца и период. Без них
    // линия красивая, но сравнить её не с чем.
    if (el.vOsL) el.vOsL.textContent = chislo(o.min_30);
    if (el.vOsR) el.vOsR.textContent = chislo(o.max_30) + ' · ' + t('v.days');

    // Точка на шкале месяца. Ставим в следующем кадре, чтобы переход был
    // виден: заданное в тот же кадр значение браузер не анимирует.
    // requestAnimationFrame есть не во всяком окружении — в старых
    // webview его может не быть вовсе, и обращение к нему в лоб роняло
    // весь вердикт. Без него просто ставим сразу, без плавности.
    if (el.vDot) {
      const kuda = Math.max(2, Math.min(98, o.pozicia_percent));
      const postavit = function () { el.vDot.style.left = kuda + '%'; };
      if (typeof requestAnimationFrame === 'function') requestAnimationFrame(postavit);
      else postavit();
    }

    // Положение внутри месяца понятнее процента отклонения: «лучше 12%
    // дней месяца» человек прикладывает к себе сразу.
    const chasti = [];
    if (o.pozicia_percent <= 2) chasti.push(t('v.pos.worst'));
    else if (o.pozicia_percent >= 98) chasti.push(t('v.pos.best'));
    else chasti.push(t('v.pos', { p: o.pozicia_percent }));

    // Направление без величины ни к чему не обязывает: «падает» человек
    // прочитает и пожмёт плечами, «за неделю −2,1%» — уже решение.
    if (o.nedelya_percent !== null && o.nedelya_percent !== undefined
        && Math.abs(o.nedelya_percent) >= 0.1) {
      chasti.push(o.nedelya_percent > 0
        ? t('v.week.up',   { p: o.nedelya_percent.toFixed(1).replace('.', ',') })
        : t('v.week.down', { p: Math.abs(o.nedelya_percent).toFixed(1).replace('.', ',') }));
    } else if (o.trend) {
      chasti.push(t('v.trend.' + o.trend));
    }

    /* Коридор месяца отсюда убран намеренно.
     *
     * Он стоял здесь третьим куском — «за месяц от 138,67 до 153,87», — и
     * ровно те же два числа подписаны по краям графика прямо над этой
     * строкой. Одно и то же, сказанное дважды подряд, читается не как
     * надёжность, а как небрежность, и вместе с положением и недельным
     * сдвигом строка переползала на две. Числа остались там, где им место:
     * у концов оси, которую они и обозначают. */
    el.vMeta.textContent = chasti.join(' · ');

    obnovitVygodu();

    /* Совет берём из deystvie, а не из вердикта: вердикт говорит, каков
     * курс, а совет — что делать, и это разные вещи. В падающем рынке
     * курс ниже обычного, но ждать нельзя: завтра будет ещё меньше.
     *
     * И советуем только по свежим данным. Курсы сервисов старше трёх
     * суток приложение скрывает целиком, а совет при тех же данных
     * продолжал бодро говорить «сегодня хороший день» — по курсу
     * четырёхдневной давности. Это ровно тот же класс вреда, что и
     * совет ждать при падающем рынке: человек послушает и потеряет.
     *
     * Порог здесь мягче — пять дней, а не трое. ЦБ не публикует по
     * выходным и в праздники, и длинные каникулы это норма, а не сбой. */
    const staryeDannye = vozrastDannyhDney(o.data) > PREDEL_SOVETA_DNEY;
    el.vHint.textContent = staryeDannye
      ? t('v.do.stale')
      : t('v.do.' + (o.deystvie || 'obychno'));

    // Вступление считается из тех же данных и обновляется здесь же, чтобы
    // разойтись с панелью было негде: одни данные — один ответ.
    pokazatVstuplenie();
  }

  /**
   * Разница в СУМАХ на сумму человека. Пересчитывается на каждое
   * изменение поля: смысл в том, чтобы он увидел свои деньги, а не общий
   * процент. Абстракция не убеждает, своя сумма убеждает.
   */
  function obnovitVygodu() {
    if (!ocenkaDnya || !el.vOnSum) return;

    const summa = parseFloat(el.summa.value);
    if (!isFinite(summa) || summa < MIN_SUMMA || summa > MAX_SUMMA) {
      el.vOnSum.textContent = '';
      // Размах тоже гасим: он считается от суммы, а суммы сейчас нет.
      // Оставленная строка показывала бы цифру от прошлого ввода.
      if (el.vSpread) el.vSpread.textContent = '';
      return;
    }

    // Размах считаем всегда, когда сумма годная, — он не зависит от того,
    // насколько сегодняшний курс отличается от среднего.
    obnovitRazmah(summa);

    const raznica = window.CALC.vygodaNaSumme(ocenkaDnya, summa);
    // Меньше тысячи сум — это не деньги, а шум округления. Говорить о нём
    // значит обещать выгоду, которой нет.
    if (Math.abs(raznica) < 1000) {
      el.vOnSum.textContent = t('v.onsum.zero');
      return;
    }

    el.vOnSum.textContent = raznica > 0
      ? t('v.onsum.plus',  { sum: sum(summa), n: sum(raznica) })
      : t('v.onsum.minus', { sum: sum(summa), n: sum(-raznica) });
  }

  /**
   * Что стоит выбор дня — в его деньгах.
   *
   * Это самая убедительная цифра продукта. «Курс ходит на 9,5%» не говорит
   * человеку ничего: проценты от курса, которого он не держал в руках,
   * не чувствует никто. «673 000 сум на вашей сумме» чувствуют все.
   */
  function obnovitRazmah(summa) {
    if (!el.vSpread || !ocenkaDnya) return;

    const razmah = Math.round((ocenkaDnya.max_30 - ocenkaDnya.min_30) * summa);
    // Курс месяц простоял ровно — говорить не о чем, и выдумывать повод
    // для тревоги мы не будем.
    if (razmah < 1000) {
      el.vSpread.textContent = '';
      return;
    }
    el.vSpread.innerHTML = t('v.spread', { n: '<b>' + sum(razmah) + '</b>' });
  }

  /**
   * Числа во вступлении и в трёх шагах — из тех же данных, что и вердикт.
   *
   * Они стояли прямо в словаре словами: «от 155 до 141», «9,5%», «670
   * тысяч сум», «примерно на 4%». Это была правда того дня, когда текст
   * писали, и она тихо разошлась с продуктом: к 22 августа окно месяца
   * съехало на 138,67–153,87, то есть 10,96% и 760 000 сум. Человек читал
   * одно число во вступлении и видел другое в панели под ним — на одном
   * экране, без прокрутки.
   *
   * Прогон поймать этого не мог: с точки зрения кода строка словаря
   * подставилась правильно. Видно только глазами и только на снимке.
   *
   * Нет данных за месяц — берём вариант без чисел. Выдуманное число здесь
   * дороже отсутствующего: на нём стоит главное обещание продукта.
   */
  function pokazatVstuplenie() {
    const o = ocenkaDnya;
    const estRazmah = !!o && o.max_30 > o.min_30 && o.min_30 > 0;
    const razmahP = estRazmah ? (o.max_30 - o.min_30) / o.min_30 * 100 : 0;
    const razmahSum = estRazmah ? Math.round((o.max_30 - o.min_30) * 50000) : 0;

    const p1 = document.querySelector('[data-i18n-html="intro.p1"]');
    if (p1) {
      p1.innerHTML = estRazmah
        ? t('intro.p1', {
            mn: chislo(o.min_30), mx: chislo(o.max_30),
            p: chislo(razmahP, 1), n: sum(razmahSum),
          })
        : t('intro.p1.bez');
    }

    const s1 = document.querySelector('[data-i18n="idle.s1"]');
    if (s1) {
      s1.textContent = estRazmah
        ? t('idle.s1', { p: chislo(razmahP, 1) })
        : t('idle.s1.bez');
    }

    // Наценка берётся наименьшая из известных — то есть у сервиса с лучшим
    // курсом. Это нижняя граница потери: у остальных она больше, и
    // обещать человеку меньшее из зол честнее, чем среднее по больнице.
    const nacenki = SERVISY
      .map(function (s) { return s.nacenka_percent; })
      .filter(function (n) { return typeof n === 'number' && n >= 0.1; });
    const s2 = document.querySelector('[data-i18n="idle.s2"]');
    if (s2) {
      s2.textContent = nacenki.length
        ? t('idle.s2', { p: chislo(Math.min.apply(null, nacenki), 1) })
        : t('idle.s2.bez');
    }
  }

  /* ── Отрисовка расчёта ───────────────────────────────────── */

  function narisovat(raschet, kursy) {
    el.results.innerHTML = '';
    if (el.idle) el.idle.classList.add('hidden');

    if (!raschet.results.length) {
      const pusto = document.createElement('p');
      pusto.className = 'note';
      pusto.textContent = t('empty');
      el.results.appendChild(pusto);
      el.loss.classList.add('hidden');
      el.share.classList.add('hidden');
      return;
    }

    raschet.results.forEach(function (r, i) {
      const kartochka = document.createElement('button');
      kartochka.className = 'card' + (i === 0 ? ' best' : '');

      /* Метки не конкурируют за место, их может быть две.
       *
       * Здесь стояло «если первый — лучший, ИНАЧЕ если устарело —
       * устарело». То есть у лучшего способа отметка о вчерашних данных
       * не появлялась никогда — именно у того, который человек и
       * выберет. Данные возрастом от суток до трёх мы показываем, но
       * обязаны об этом сказать, и молчать в самом видном месте —
       * ровно противоположное тому, ради чего правило заводили. */
      const metki = [];
      if (i === 0) metki.push('<span class="tag best">' + t('tag.best') + '</span>');
      if (r.svezhest === 'ustarelo') {
        metki.push('<span class="tag">' + t('tag.stale') + '</span>');
      }

      const detali = [];
      detali.push(srok(r.delivery_minutes));

      // Наценка курса сервиса к официальному. Это второй по величине
      // рычаг после дня отправки — около 4% — и его тоже не показывает
      // ни один сервис. Считает бот, здесь только выводим.
      const servis = SERVISY.filter(function (s) { return s.id === r.service_id; })[0];
      if (servis && typeof servis.nacenka_percent === 'number'
          && Math.abs(servis.nacenka_percent) >= 0.1) {
        // Через запятую, как и все остальные числа на экране. Здесь
        // стоял голый toFixed, и в карточке способа было «4.1%», когда
        // в плашке рядом — «4,1%». Два формата в одном экране читаются
        // как небрежность, а небрежность в денежном продукте — как
        // повод не верить и числам.
        detali.push(t('svc.markup', { p: chislo(servis.nacenka_percent, 1) }));
      }
      // Комиссия не объявлена — говорим прямо, что итог это потолок.
      // Молча выдать верхнюю границу за точную цифру нельзя.
      if (servis && servis.fee_unknown) detali.push(t('svc.fee_unknown'));

      if (r.ocenochnyi) detali.push(t('detail.est'));
      if (r.nacenka_percent !== null && r.dannye_soglasovany && Math.abs(r.nacenka_percent) >= 0.1) {
        detali.push(r.nacenka_percent > 0
          ? t('detail.worse',  { p: chislo(r.nacenka_percent, 1) })
          : t('detail.better', { p: chislo(Math.abs(r.nacenka_percent), 1) }));
      } else if (r.nacenka_percent !== null && !r.dannye_soglasovany) {
        detali.push(t('detail.stale'));
      }
      if (r.vyshe_limita) detali.push(t('detail.limit'));
      if (r.nizhe_minimuma) detali.push(t('detail.min'));

      const summa = r.vilka
        ? sum(r.vilka.ot) + ' – ' + sum(r.vilka.do)
        : sum(r.total_uzs);

      // Полоса, пропорциональная итогу. Шкала начинается не с нуля, а с
      // 92% от лучшего: разница между способами обычно единицы процентов,
      // и от нуля все полосы выглядели бы одинаково полными.
      const luchshee = raschet.results[0].total_uzs || 1;
      const dolya = Math.max(4, Math.min(100,
        ((r.total_uzs / luchshee) - 0.92) / 0.08 * 100));

      kartochka.innerHTML =
        '<span class="top"><span class="svc">' + r.name + '</span>' + metki.join('') + '</span>' +
        '<span class="sum">' + summa + ' ' + t('unit.sum') + '</span>' +
        '<span class="bar"><i style="width:' + dolya.toFixed(0) + '%"></i></span>' +
        '<span class="brk">' + detali.join(' · ') + '</span>';

      kartochka.addEventListener('click', function () { pokazatRazbor(r); });
      el.results.appendChild(kartochka);
    });

    /**
     * Плашка над списком показывает БОЛЬШУЮ из двух потерь.
     *
     * Их всегда две, и они разного порядка. Первая — разница между
     * способами: её видно прямо в списке под плашкой, и человек может на
     * неё повлиять, выбрав другой сервис. Вторая — сколько забрал курс
     * сервиса против официального: она одинакова у всех и потому в списке
     * невидима вовсе.
     *
     * Раньше первая всегда побеждала: есть разница — показываем её. И
     * получалось, что самым громким числом экрана становилось «4 000 сум»,
     * пока курс тихо забирал сто восемьдесят три тысячи. Продукт обещает
     * показать невидимое, а показывал то, что и так на виду, — причём
     * крупнее всего остального.
     *
     * Теперь сравниваем и берём то, что больше. Разница между способами
     * получает плашку, только когда она действительно главная потеря; в
     * остальные дни она остаётся там, где ей место, — в списке.
     */
    const luchshiy = raschet.results[0];
    const raznicaSposobov = raschet.hidden_loss_uzs > 0
      ? Math.round(raschet.hidden_loss_uzs) : 0;

    // Считаем от вилки так же, как разбор, иначе плашка и разбор под ней
    // покажут разные числа за одно и то же.
    //
    // Имя переменной здесь было `poteryaNaKurse`, и оно врало: разность
    // «по курсу ЦБ минус то, что дошло» вбирает В СЕБЯ всё, что забрали по
    // дороге, — и курс сервиса, и комиссию. Пока у лучшего способа комиссии
    // не было, курсовая часть и вся потеря совпадали до сума, и неправду
    // имени нечем было заметить. Разошлись они в первый же день, когда
    // сверху встал сервис с комиссией. Разложение на части — дело разбора.
    const servisLuchshego = luchshiy
      ? SERVISY.filter(function (s) { return s.id === luchshiy.service_id; })[0]
      : null;
    let poOficialnomu = 0;
    let poteryaVsego = 0;
    if (kursy && kursy.rub_uzs && luchshiy
        && servisLuchshego && servisLuchshego.rate_rub_uzs) {
      poOficialnomu = parseFloat(el.summa.value) * kursy.rub_uzs;
      const doshlo = luchshiy.vilka ? luchshiy.vilka.ot : luchshiy.total_uzs;
      poteryaVsego = Math.max(0, Math.round(poOficialnomu - doshlo));
    }

    if (poteryaVsego > 0 && poteryaVsego >= raznicaSposobov) {
      // Процент рядом с суммой обязателен. Само по себе «288 000 сум»
      // не говорит ничего: много это или мало, человек не знает,
      // пока не соотнесёт с переводом. «4,1%» соотносит мгновенно.
      const dolya = (poteryaVsego / poOficialnomu) * 100;
      // Подпись меняется вместе со смыслом числа. Раньше здесь всегда
      // стояло «Разница между способами», а показывалась потеря на
      // курсе: число под чужой подписью в денежном продукте — это
      // не мелочь, а повод не верить всему остальному.
      if (el.lossT) el.lossT.textContent = t('svc.lost.t');
      el.lossNum.innerHTML = sum(poteryaVsego) + ' ' + t('unit.sum') +
        '<small>' + dolya.toFixed(1).replace('.', ',') + '%</small>';
      el.lossSub.textContent = t('svc.official');
      el.loss.classList.remove('hidden');
    } else if (raznicaSposobov > 0) {
      if (el.lossT) el.lossT.textContent = t('loss.t');
      el.lossNum.textContent = sum(raznicaSposobov) + ' ' + t('unit.sum');
      el.lossSub.textContent = t('loss.sub', { sum: sum(el.summa.value) });
      el.loss.classList.remove('hidden');
    } else {
      el.loss.classList.add('hidden');
    }

    let podpis = t(raschet.disclaimer);
    if (window.TEST_DATA) podpis = t('test') + podpis;
    el.disclaimer.textContent = podpis;
    el.disclaimer.classList.remove('hidden');

    el.kursDate.textContent = dannyeUstareli
      ? t('err.net', { d: dataSlovom(dannyeUstareli) })
      : (kursy.zapas || !kursy.date)
        ? t('kurs.fail')
        : t('kurs.date', { d: dataSlovom(kursy.date) });

    narisovatRazbor(luchshiy, kursy);

    el.share.classList.remove('hidden');
    // Просьбу о подписке показываем только теперь — после того, как
    // человек получил цифру, ради которой пришёл. Это не приём, а порядок:
    // сначала польза, потом просьба. Наоборот получаешь отказ.
    if (el.subCta) el.subCta.classList.remove('hidden');
  }

  /**
   * «Куда уходят деньги» — главное обещание продукта на экране.
   *
   * Человек видит три строки: сколько было бы по официальному курсу,
   * сколько забрал курс сервиса, сколько забрала комиссия, и что осталось.
   * Раньше этот разбор жил в попапе, который открывают единицы, — то есть
   * то, ради чего продукт существует, видели единицы.
   *
   * Считаем от курса ЦБ, а не от суммы в рублях: рубли человек и так знает,
   * а вот что он мог бы получить по официальному курсу — не знает никто.
   */
  function narisovatRazbor(luchshiy, kursy) {
    if (!el.razbor || !luchshiy || !kursy || !kursy.rub_uzs) {
      if (el.razbor) el.razbor.classList.add('hidden');
      return;
    }

    const summaRub = parseFloat(el.summa.value);
    const servis = SERVISY.filter(function (s) { return s.id === luchshiy.service_id; })[0];
    if (!isFinite(summaRub) || !servis) {
      el.razbor.classList.add('hidden');
      return;
    }

    const poCB = summaRub * kursy.rub_uzs;
    const itog = luchshiy.vilka ? luchshiy.vilka.ot : luchshiy.total_uzs;

    // Комиссия сервиса в рублях — и та же величина в сумах, чтобы всё
    // в разборе считалось в одних единицах и складывалось на глазах.
    const komissiyaRub = (servis.fee_fixed || 0) + summaRub * ((servis.fee_percent || 0) / 100);
    const komissiya = Math.round(komissiyaRub * kursy.rub_uzs);

    // Остальное съел курс. Считаем вычитанием, а не по формуле: так
    // строки гарантированно сходятся с итогом, и человек не поймает нас
    // на арифметике, которая не бьётся.
    const kurs = Math.max(0, Math.round(poCB - itog - komissiya));

    const stroki = [];
    stroki.push('<span class="rl"><span class="k">' + t('br.cb') +
      '</span><span class="v">' + sum(poCB) + '</span></span>');

    if (kurs > 0) {
      stroki.push('<span class="rl minus"><span class="k">' + t('br.rate') +
        '</span><span class="v">− ' + sum(kurs) + '</span></span>');
    }

    if (servis.fee_unknown) {
      stroki.push('<span class="rl"><span class="k">' + t('br.fee') +
        '</span><span class="v" style="color:var(--muted);font-weight:600">' +
        t('br.fee_unknown') + '</span></span>');
    } else if (komissiya > 0) {
      stroki.push('<span class="rl minus"><span class="k">' + t('br.fee') +
        '</span><span class="v">− ' + sum(komissiya) + '</span></span>');
    }

    stroki.push('<span class="rl itog"><span class="k">' + t('br.total') +
      '</span><span class="v">' + sum(itog) + ' ' + t('unit.sum') + '</span></span>');

    el.rRows.innerHTML = stroki.join('');

    // Полоса: сколько дошло и сколько забрали. Одна картинка вместо абзаца.
    const doshlo = poCB > 0 ? Math.max(0, Math.min(100, (itog / poCB) * 100)) : 100;
    el.rBar.innerHTML =
      '<i class="ost" style="width:' + doshlo.toFixed(1) + '%"></i>' +
      '<i class="pot" style="width:' + (100 - doshlo).toFixed(1) + '%"></i>';

    el.razbor.classList.remove('hidden');
  }

  function pokazatRazbor(r) {
    const stroki = r.razbor.map(function (p) { return t(p[0]) + ': ' + p[1]; }).join('\n');
    const hvost = r.ocenochnyi ? '\n\n' + t('popup.est') : '';
    const text = r.name + '\n\n' + stroki + '\n\n'
      + t('popup.total') + ': ' + sum(r.total_uzs) + ' ' + t('unit.sum') + hvost;

    const servis = SERVISY.filter(function (s) { return s.id === r.service_id; })[0];
    // Партнёрская ссылка, если она есть, иначе обычный адрес сервиса.
    // Порядок в списке от этого не зависит НИКОГДА: сверху всегда тот,
    // где человеку придёт больше. Это правило проекта, а не настройка.
    const ssylka = servis && (servis.partner_url || servis.url);

    if (tg && tg.showPopup) {
      const knopki = [{ id: 'ok', type: 'close' }];
      if (ssylka) knopki.unshift({ id: 'go', type: 'default', text: t('popup.go') });
      tg.showPopup({ title: r.name, message: text, buttons: knopki }, function (nazhal) {
        if (nazhal === 'go' && ssylka) pereyti(r, ssylka);
      });
      return;
    }

    alert(text);
    if (ssylka && window.confirm(t('popup.go'))) pereyti(r, ssylka);
  }

  /** Переход в сервис. Единственное место, где мы уводим человека наружу. */
  function pereyti(r, ssylka) {
    sobytie('perehod', { servis: r.service_id, partner: !!(
      SERVISY.filter(function (s) { return s.id === r.service_id; })[0] || {}
    ).partner_url });
    if (tg && tg.openLink) tg.openLink(ssylka);
    else window.open(ssylka, '_blank');
  }

  /* ── Отправка в чат ──────────────────────────────────────── */

  /**
   * Пересылка — единственный канал, по которому про нас узнают бесплатно.
   *
   * Что в ней есть и почему. Раньше уходила разница между способами —
   * но она бывает нулевой, и тогда сообщение пустело. Теперь первым идёт
   * вердикт дня: он есть всегда, он меняется каждый день, и он полезен
   * читателю независимо от того, какую сумму отправлял автор.
   */
  function blokPeresylki(lang, procent) {
    const stroki = [];

    if (ocenkaDnya) {
      stroki.push(t('v.' + ocenkaDnya.verdikt, null, lang));

      // Числа через запятую. Здесь стоял голый toFixed, и в чужие чаты
      // уходило «141.76» — точка в дробной части не пишется ни по-русски,
      // ни по-узбекски. На экране запятая была, а в самом видимом тексте
      // продукта — нет.
      stroki.push(t('v.rate', { r: chislo(ocenkaDnya.segodnya) }, lang)
        + ' · ' + t('v.avg', { r: chislo(ocenkaDnya.srednee_30) }, lang));

      // Дата курса. Без неё сообщение, попавшее в чат, через неделю
      // становится неправдой, а поправить его там уже нельзя.
      if (ocenkaDnya.data) {
        stroki.push(t('share.date', { d: dataSlovom(ocenkaDnya.data, lang) }, lang));
      }

      // Цена вопроса. Ради этого числа сообщение и пересылают: за месяц
      // курс ходит на 9% с лишним, и это больше, чем даёт выбор сервиса.
      // Раньше в пересылке не было ни одной денежной цифры — то есть не
      // было и причины её пересылать.
      const razmah = ocenkaDnya.max_30 - ocenkaDnya.min_30;
      if (razmah > 0 && ocenkaDnya.min_30 > 0) {
        stroki.push(t('share.spread', {
          p: chislo(razmah / ocenkaDnya.min_30 * 100, 1),
          n: sum(Math.round(razmah * 50000)),
        }, lang));
      }
    } else {
      stroki.push(t('share.title', { sum: sum(el.summa.value) }, lang));
    }

    if (procent !== null) stroki.push(t('share.diff', { p: procent }, lang));
    stroki.push(t('share.cta', null, lang));
    return stroki.join('\n');
  }

  function sobratTekst() {
    // Никаких чужих сумов: у читателя другая сумма и другой банк, а
    // длинные числа в чате читаются как спам. Процент и курс переносятся
    // на любой перевод — потому они и остались.
    /* Способов может не быть вовсе — когда все курсы протухли, а вердикт
     * дня при этом жив: он считается по курсам ЦБ, у которых своя дата.
     * Кнопку пересылки в таком случае прячет `narisovat`, но полагаться
     * на то, что снаружи её никто не нажмёт, нельзя: здесь падало на
     * `luchshiy.vilka`, и падало молча — исключение внутри обработчика
     * никуда не всплывает, человек просто нажимает и ничего не происходит.
     * Вердикт дня переслать можно и без единого способа. */
    const luchshiy = posledniyRaschet.results[0] || null;
    const bazovyi = !luchshiy ? 0
      : luchshiy.vilka ? luchshiy.vilka.ot : luchshiy.total_uzs;

    let procent = null;
    const poterya = posledniyRaschet.hidden_loss_uzs;
    if (poterya > 0 && bazovyi > 0) {
      const dolya = (poterya / bazovyi) * 100;
      if (dolya >= 0.1) procent = dolya.toFixed(1).replace('.', ',');
    }

    // Оба языка сразу. Расчёт пересылают в общие чаты, где сидят и те,
    // кто читает по-узбекски, и те, кто по-русски. Первым идёт язык
    // отправителя — его прочтут те, кому он пишет чаще.
    const svoy = window.I18N.get();
    const chuzhoy = svoy === 'ru' ? 'uz' : 'ru';

    return blokPeresylki(svoy, procent) + '\n\n· · ·\n\n' + blokPeresylki(chuzhoy, procent);
  }

  function otpravitVChat() {
    if (!posledniyRaschet) return;
    const text = sobratTekst();
    const link = window.BOT_LINK || '';

    // Пересылка — единственный бесплатный канал роста, поэтому считаем
    // её отдельно: доля пересылок это метрика номер два после возврата.
    sobytie('share', { verdikt: ocenkaDnya ? ocenkaDnya.verdikt : null });

    const shareUrl = 'https://t.me/share/url?url=' + encodeURIComponent(link) +
                     '&text=' + encodeURIComponent(text);

    if (tg && tg.openTelegramLink) { tg.openTelegramLink(shareUrl); return; }

    // Вне Telegram кнопка тоже должна работать: приложение открывают и в браузере.
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text + '\n' + link);
      alert(text + '\n' + link);
    } else {
      window.open(shareUrl, '_blank');
    }
  }

  /** Подписка живёт у бота: мини-апп сам писать человеку не может. */
  function otkrytPodpisku() {
    sobytie('podpiska_klik');
    const ssylka = window.BOT_CHAT || 'https://t.me/QanchaYetadi_bot';
    if (tg && tg.openTelegramLink) tg.openTelegramLink(ssylka);
    else window.open(ssylka, '_blank');
  }

  /* ── Банки ───────────────────────────────────────────────── */

  function zapolnitBanki() {
    // Проверенных курсов банков нет — поле прячем целиком. Пустой список
    // в выпадашке это обещание данных, которых у нас нет.
    if (!BANKI.length) {
      if (el.bankBlock) el.bankBlock.classList.add('hidden');
      return;
    }
    if (el.bankBlock) el.bankBlock.classList.remove('hidden');

    const bylo = el.bank.value || pomnit('bank') || '';
    const opts = ['<option value="">' + t('bank.any') + '</option>'];
    BANKI.forEach(function (b) {
      opts.push('<option value="' + b.id + '">' + b.name + '</option>');
    });
    el.bank.innerHTML = opts.join('');
    if (bylo) el.bank.value = bylo;
  }

  /**
   * Время последнего сбора данных. Ставится рядом с источниками:
   * названный источник без даты — это половина доверия, а в денежном
   * продукте половины не бывает.
   */
  function pokazatIstochniki() {
    if (!el.srcUpd) return;
    const kogda = (posledniyKurs && posledniyKurs.date)
      || (window.KURSY_ZAPAS && window.KURSY_ZAPAS.date);
    el.srcUpd.textContent = t('src.upd', { d: kogda ? dataSlovom(kogda) : '—' });
  }

  /* ── Язык ────────────────────────────────────────────────── */

  function primenitYazyk() {
    document.documentElement.lang = window.I18N.get();

    document.querySelectorAll('[data-i18n]').forEach(function (node) {
      node.textContent = t(node.getAttribute('data-i18n'));
    });
    document.querySelectorAll('[data-i18n-html]').forEach(function (node) {
      node.innerHTML = t(node.getAttribute('data-i18n-html'));
    });

    document.querySelectorAll('.lang').forEach(function (b) {
      b.classList.toggle('on', b.getAttribute('data-lang') === window.I18N.get());
    });

    zapolnitBanki();
    pokazatIstochniki();
    // Вердикт и результат на экране тоже надо перевести, иначе половина
    // страницы останется на прежнем языке до следующего нажатия.
    pokazatVerdikt();
    if (posledniyRaschet) narisovat(posledniyRaschet, posledniyKurs);
  }

  /* ── Проверка суммы ──────────────────────────────────────── */

  function pokazatOshibku(klyuch, podstanovki) {
    el.summaErr.textContent = klyuch ? t(klyuch, podstanovki) : '';
    el.summaErr.classList.toggle('hidden', !klyuch);
    el.summa.parentNode.classList.toggle('bad', !!klyuch);
    return !klyuch;
  }

  /** @returns {number|null} сумма, если она пригодна для расчёта */
  function proveritSummu() {
    const syroe = String(el.summa.value).trim();
    if (syroe === '') { pokazatOshibku('err.nan'); return null; }

    const summa = parseFloat(syroe);
    if (!isFinite(summa)) { pokazatOshibku('err.nan'); return null; }
    if (summa < MIN_SUMMA) { pokazatOshibku('err.min', { min: sum(MIN_SUMMA) }); return null; }
    if (summa > MAX_SUMMA) { pokazatOshibku('err.max', { max: sum(MAX_SUMMA) }); return null; }
    pokazatOshibku(null);
    return summa;
  }

  /** Прячем прошлый результат: он посчитан по другой сумме и уже врёт. */
  function ochistitRezultat() {
    el.results.innerHTML = '';
    el.loss.classList.add('hidden');
    el.share.classList.add('hidden');
    el.disclaimer.classList.add('hidden');
    if (el.razbor) el.razbor.classList.add('hidden');
    posledniyRaschet = null;
    if (el.idle) el.idle.classList.remove('hidden');
  }

  function poschitat() {
    const summa = proveritSummu();
    if (summa === null) { ochistitRezultat(); return; }

    pomnit('summa', String(summa));
    if (el.bank && el.bank.value) pomnit('bank', el.bank.value);

    const kursy = posledniyKurs || window.KURSY_ZAPAS;
    posledniyRaschet = window.CALC.poschitat(
      { summa: summa, bank_id: (el.bank && el.bank.value) || null, corridor: 'RU-UZ' },
      SERVISY, BANKI, kursy
    );
    narisovat(posledniyRaschet, kursy);
    if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');

    sobytie('raschet', {
      summa: poryadok(summa),
      verdikt: ocenkaDnya ? ocenkaDnya.verdikt : null,
      sposobov: posledniyRaschet.results.length,
    });
  }

  /* ── Первый запуск ───────────────────────────────────────── */

  // Человек, пришедший из чата, не знает, что это. Но экраном-заглушкой
  // объяснение давать нельзя: это лишний тап до цифры, ради которой он
  // пришёл. Поэтому объяснение стоит НАД формой, а форма доступна сразу.
  function pokazatIntro() {
    let videl = false;
    try { videl = localStorage.getItem('intro_pokazan') === '1'; } catch (e) {}
    if (videl) return;
    el.intro.classList.remove('hidden');
  }

  function zakrytIntro() {
    el.intro.classList.add('hidden');
    try { localStorage.setItem('intro_pokazan', '1'); } catch (e) {}
  }

  /* ── Запуск ──────────────────────────────────────────────── */

  // Сумму человека возвращаем сразу: он открывает приложение и видит
  // вердикт в своих деньгах, ничего не вводя.
  const zapomnennaya = pomnit('summa');
  if (zapomnennaya && isFinite(parseFloat(zapomnennaya))) {
    el.summa.value = zapomnennaya;
  }

  primenitYazyk();
  pokazatIntro();

  // Пока идёт запрос — рисуем по запасу, чтобы экран не был пустым
  // ни одной секунды. Ответ придёт и перерисует.
  zapasnoy();
  pokazatVerdikt();

  zagruzitDannye().then(function () {
    zapolnitBanki();
    pokazatIstochniki();
    pokazatVerdikt();
    if (posledniyRaschet) poschitat();

    // Учитываем открытие только после того, как узнали вердикт: иначе
    // в цифрах не будет видно, с каким курсом человек к нам пришёл,
    // а это и есть главный вопрос к продукту.
    const otkuda = istochnik();
    sobytie('otkryt', {
      verdikt: ocenkaDnya ? ocenkaDnya.verdikt : null,
      // Откуда пришёл: kanal_den, kanal_nedelya, chat_moskva, share…
      // Без этого весь посев превращается в гадание.
      istochnik: otkuda,
      // Пришёл ли по чужой пересылке. Отдельным полем, хотя оно выводится
      // из метки: пересылка — единственный бесплатный источник роста, и
      // считать её надо, даже если разметку источников однажды поменяют.
      iz_peresylki: otkuda === 'share',
    });
  });

  document.querySelectorAll('.lang').forEach(function (b) {
    b.addEventListener('click', function () {
      window.I18N.set(b.getAttribute('data-lang'));
      primenitYazyk();
    });
  });

  /* ── Быстрый выбор суммы ─────────────────────────────────
   * Набрать «50000» на телефоне — это пять точных попаданий и клавиатура
   * поверх половины экрана. Одно нажатие вместо этого убирает главное
   * трение перед цифрой, ради которой человек и пришёл.
   */
  function podsvetitFishki() {
    if (!el.chips) return;
    const tekushchaya = String(parseFloat(el.summa.value) || '');
    el.chips.querySelectorAll('.chip').forEach(function (c) {
      c.classList.toggle('on', c.getAttribute('data-sum') === tekushchaya);
    });
  }

  if (el.chips) {
    el.chips.addEventListener('click', function (e) {
      const knopka = e.target.closest ? e.target.closest('.chip') : null;
      if (!knopka) return;
      el.summa.value = knopka.getAttribute('data-sum');
      // Нажатие на готовую сумму — это уже намерение посчитать.
      // Заставлять после него жать вторую кнопку незачем.
      podsvetitFishki();
      poschitat();
      if (tg && tg.HapticFeedback) tg.HapticFeedback.selectionChanged();
    });
  }

  el.introOk.addEventListener('click', zakrytIntro);
  el.schitat.addEventListener('click', poschitat);
  el.share.addEventListener('click', otpravitVChat);
  if (el.subBtn) el.subBtn.addEventListener('click', otkrytPodpisku);

  pokazatKanal();
  el.summa.addEventListener('keydown', function (e) { if (e.key === 'Enter') poschitat(); });

  // Пока человек правит сумму, ошибку показываем сразу, но расчёт не
  // пересчитываем: дёргать список на каждый набранный ноль незачем.
  // А вот вердикт в сумах обновляем — он и есть причина смотреть сюда.
  el.summa.addEventListener('input', function () {
    if (posledniyRaschet) ochistitRezultat();
    proveritSummu();
    obnovitVygodu();
    podsvetitFishki();
  });

  podsvetitFishki();

})();
