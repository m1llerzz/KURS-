/**
 * СКВОЗНОЙ ПРОГОН ПРИЛОЖЕНИЯ
 *
 * Правило проекта: дефекты находятся запуском, а не чтением. Все
 * шестнадцать найденных до сих пор — из запуска. Этот файл открывает
 * приложение так, как его открывает человек, и проверяет, что он видит.
 *
 * Нужен jsdom. Он не входит в проект (у приложения зависимостей нет и не
 * будет — оно должно оставаться четырьмя статическими файлами), поэтому
 * ставится отдельно и только для проверок:
 *
 *     npm install jsdom
 *     node test-app.js
 *
 * Если jsdom нет — скрипт честно скажет об этом и выйдет, а не притворится,
 * что всё хорошо.
 */
const fs = require('fs');
const path = require('path');

let JSDOM, VirtualConsole;
try {
  JSDOM = require('jsdom').JSDOM;
  VirtualConsole = require('jsdom').VirtualConsole;
} catch (e) {
  console.log('jsdom не установлен. Поставь его: npm install jsdom');
  console.log('Проверки НЕ выполнены.');
  process.exit(2);
}

/* Ошибки, которые приложение выдало в консоль за весь прогон.
 *
 * Пункт чек-листа приёмки «в консоли ноль ошибок» проверялся глазами —
 * то есть один раз и на одном телефоне. Ошибка в скрипте не обязана
 * ронять экран целиком: чаще она тихо ломает одну ветку, и человек
 * видит пустое место там, где должно быть число. */
const oshibkiKonsoli = [];

const KORNI = __dirname;
const proshlo = [];
const upalo = [];

function proverka(imya, uslovie, podskazka) {
  if (uslovie) proshlo.push(imya);
  else upalo.push(imya + (podskazka ? '  << ' + podskazka : ''));
}

/* Текст, у которого все виды апострофа сведены к одному.
 *
 * В узбекской латинице `oʻ` — не буква с апострофом, а буква целиком, и
 * набрать её можно четырьмя разными кодами. Проверка, которая ищет слово
 * вместе с конкретным кодом, краснеет от правки типографики и молчит о
 * том, ради чего написана. 22 августа так уже вышло с подписью на плашке:
 * слово в проверке пережило ровно до смены формулировки. */
function bezApostrofa(tekst) {
  return String(tekst).replace(/[ʻʼ‘’´`]/g, "'");
}

/**
 * Поднимает приложение с нуля. otvet — что «вернёт бот», null — сбой сети.
 * pamyat — что лежит в localStorage ДО запуска: у каждого окна jsdom своё
 * хранилище, и без этого прошлый визит человека не воспроизвести.
 */
function podnyat(otvet, pamyat, startParam, otvetCB, bezFetch, bezPamyati) {
  const html = fs.readFileSync(path.join(KORNI, 'index.html'), 'utf8')
    // Внешний скрипт Telegram в проверке не нужен и тянуть его неоткуда.
    .replace(/<script src="https:\/\/telegram[^<]*<\/script>/, '');

  // runScripts обязателен: без него window.eval выполняет код в пустом
  // окружении, где нет даже window, и все четыре файла падают на первой
  // строке. 'outside-only' даёт нам eval, но не запускает скрипты из html —
  // мы грузим их сами, по одному, в нужном порядке.
  const konsol = new VirtualConsole();
  konsol.on('jsdomError', function (e) {
    oshibkiKonsoli.push('jsdomError: ' + (e && e.message));
  });
  konsol.on('error', function () {
    oshibkiKonsoli.push('console.error: ' +
      Array.prototype.join.call(arguments, ' ').slice(0, 200));
  });

  const dom = new JSDOM(html, {
    url: 'https://m1llerzz.github.io/KURS-/',
    runScripts: 'outside-only',
    virtualConsole: konsol,
  });
  const w = dom.window;

  // Необработанное исключение в обработчике события тоже считается.
  w.addEventListener('error', function (e) {
    oshibkiKonsoli.push('window.onerror: ' + (e && e.message));
  });

  // Настоящего Telegram здесь нет: приложение обязано работать и в браузере.
  //
  // Адресов теперь два, и различать их обязательно: приложение спрашивает
  // курс у ЦБ напрямую, помимо бота. Общий на оба ответ означал бы, что
  // проверка «бот молчит» на самом деле молчащего бота не проверяет —
  // курс всё равно приезжал бы, только из другой двери.
  // Браузер без fetch — не выдумка: в старых webview его нет вовсе.
  // Тогда мы его и не заводим, чтобы приложение встретило ровно то же
  // самое, что встретит там.
  w.fetch = bezFetch ? undefined : function (adres) {
    const vCB = String(adres || '').indexOf('cbu.uz') !== -1;
    const chto = vCB ? otvetCB : otvet;
    return chto
      ? Promise.resolve({ json: function () { return Promise.resolve(chto); } })
      : Promise.reject(new Error('сети нет'));
  };

  Object.keys(pamyat || {}).forEach(function (k) {
    w.localStorage.setItem(k, pamyat[k]);
  });

  /* Браузер с запрещёнными данными сайта бросает исключение на самом
     обращении к localStorage — не возвращает пусто, а именно бросает.
     Подменяем ДО запуска скриптов: подмена после запуска проверяет не то,
     приложение к этому моменту уже прочитало хранилище. */
  if (bezPamyati) {
    Object.defineProperty(w, 'localStorage', {
      configurable: true,
      get: function () { throw new Error('данные сайта запрещены'); },
    });
  }

  /* Метка источника кладётся ДО запуска приложения — так же, как её
   * кладёт Telegram при переходе по ссылке из чата или канала.
   * Поставить её после значит поднять приложение второй раз поверх
   * первого и мерить не то. */
  if (startParam) {
    w.Telegram = {
      WebApp: {
        initDataUnsafe: { start_param: startParam },
        ready: function () {}, expand: function () {},
        MainButton: { hide: function () {} }, themeParams: {},
      },
    };
  }

  ['i18n.js', 'data.js', 'calc.js', 'app.js'].forEach(function (f) {
    w.eval(fs.readFileSync(path.join(KORNI, f), 'utf8'));

    /* Запасу проставляем сегодняшнее время сбора — сразу после data.js и
     * до того, как приложение его прочитает.
     *
     * Зачем. В запасе `checked_at` записан днём пересборки, а правило
     * продукта скрывает способы старше 72 часов. То есть ровно через трое
     * суток после `obnovit_vsyo.py` весь этот прогон краснел сам собой:
     * способов ноль, плашки нет, разбора нет, пересылка падает. Код при
     * этом исправен, и ведёт себя он правильно — просто данные состарились.
     * Такая проверка не находит дефекты, а раз в три дня зовёт нас чинить
     * календарь; правило проекта про такие бомбы записано отдельно.
     *
     * Возраст запаса — свойство файла, а не поведение кода. Поведение на
     * протухших курсах проверяется ниже честнее: отдельным набором данных
     * с точным возрастом (2, 30 и 100 часов), где ни один час не зависит
     * от того, когда прогон запустили. */
    if (f === 'data.js' && Array.isArray(w.SERVICES)) {
      const teper = new Date().toISOString();
      w.SERVICES.forEach(function (s) { s.checked_at = teper; });
    }
  });

  return w;
}

function vidno(w, id) {
  const n = w.document.getElementById(id);
  return !!n && !n.classList.contains('hidden');
}

function tekst(w, id) {
  const n = w.document.getElementById(id);
  return n ? n.textContent.trim() : '';
}

/** Ждём, пока отработают промисы загрузки данных. */
function dozhdatsya() {
  return new Promise(function (r) { setTimeout(r, 30); });
}

(async function () {

  /* ── 1. Открытие без сети: работаем по запасу ──────────────────── */

  let w = podnyat(null);
  await dozhdatsya();

  proverka('вердикт виден сразу', vidno(w, 'verdict'),
    'это главный экран продукта, он не должен ждать сети');
  /* Ожидаемые числа берём из тех же данных, а не пишем в проверке.
   *
   * Здесь стояло «в вердикте есть 141,76» — курс из запаса на день,
   * когда проверку писали. Первое же обновление запаса делает её
   * красной, хотя код исправен, а красное на исправном коде обесценивает
   * весь прогон. */
  /* Берём из ИСТОРИИ, а не из KURSY_ZAPAS: вердикт говорит про ряд, и
   * курс на нём — последняя точка ряда. Это выяснилось, когда проверку
   * прогнали на подменённых данных: два источника разошлись, и стало
   * видно, какой из них на экране. */
  const kursNaEkrane = String(w.CALC.sovet(w.HISTORY_ZAPAS).segodnya)
    .replace('.', ',');
  proverka('в вердикте показан курс из данных',
    tekst(w, 'vRate').indexOf(kursNaEkrane) !== -1,
    tekst(w, 'vRate') + ' — ждали ' + kursNaEkrane);
  proverka('в вердикте есть среднее', /1\d\d[.,]\d\d/.test(tekst(w, 'vAvg')),
    tekst(w, 'vAvg'));

  /* Каким должен быть вердикт — тоже считаем, а не помним. Запас
   * пересобирается из живых курсов, и однажды он окажется не «плохим»
   * днём, а обычным или хорошим: тогда проверка на класс `bad` начала бы
   * краснеть на совершенно исправном экране. */
  const ocenkaDlyaKlassa = w.CALC.sovet(w.HISTORY_ZAPAS);
  const zhdemKlass = ['ploho', 'nize_obychnogo'].indexOf(ocenkaDlyaKlassa.verdikt) !== -1
    ? 'bad'
    : ['otlichno', 'horosho'].indexOf(ocenkaDlyaKlassa.verdikt) !== -1 ? 'good' : '';
  const klassyVerdikta = w.document.getElementById('verdict').className;
  proverka('вердикт помечен по своему же расчёту',
    !zhdemKlass || klassyVerdikta.indexOf(zhdemKlass) !== -1,
    'вердикт ' + ocenkaDlyaKlassa.verdikt + ' ждёт класс «' + zhdemKlass +
      '», а стоит «' + klassyVerdikta + '»');

  const grafik = w.document.getElementById('vSpark');
  const liniya = grafik.querySelector('polyline');
  proverka('график нарисован', !!liniya);
  /* Точек в графике ровно столько, сколько в ряде, который рисуется.
   *
   * Числом это прибивать нельзя — здесь уже стояло «ровно 30», и оно
   * покраснело, как только сборщик перестал дублировать пятничный курс
   * под субботу и воскресенье: за тридцать календарных дней ЦБ публикует
   * около двадцати одного раза, и сколько именно — решает календарь.
   *
   * Сравнивать с длиной ЗАПАСА тоже нельзя, и это выяснилось так же —
   * покраснением на исправном экране. В запасе лежит чуть больше месяца
   * (сегодня 22 курса за 31 день), а график рисует окно в тридцать дней
   * (21 точку): окно применяется внутри вердикта, и это правильно —
   * подписи под графиком тоже про тридцать дней. Проверка же
   * утверждала, что запас и окно — одно и то же, и держалась только
   * пока собранный ряд не перерос месяц.
   *
   * Сравниваем с тем самым рядом, из которого рисуется линия. Тогда
   * проверка ловит настоящую поломку «график потерял точки», а не
   * длинный уикенд и не лишний день в запасе. */
  const tochekVGrafike = liniya
    ? liniya.getAttribute('points').trim().split(/\s+/).length : 0;
  const ryadGrafika = w.CALC.sovet(w.HISTORY_ZAPAS).ryad || [];
  proverka('в графике столько точек, сколько в его ряде',
    tochekVGrafike === ryadGrafika.length,
    tochekVGrafike + ' против ' + ryadGrafika.length);
  proverka('ряд графика — окно внутри запаса, а не что-то своё',
    ryadGrafika.length > 0
      && ryadGrafika.length <= (w.HISTORY_ZAPAS || []).length
      && ryadGrafika[ryadGrafika.length - 1].date
         === w.HISTORY_ZAPAS[w.HISTORY_ZAPAS.length - 1].date,
    'последняя точка графика обязана быть самым свежим курсом запаса');
  proverka('точек хватает на месячный график', ryadGrafika.length >= 15,
    ryadGrafika.length + ' — за тридцать дней ЦБ публикует около двадцати одного раза');
  proverka('в графике есть линия среднего', !!grafik.querySelector('line.av'),
    'без якоря человек не понимает, много это или мало');
  proverka('на графике отмечен сегодняшний день', !!grafik.querySelector('circle.dt'));

  /* Отметка сегодняшнего дня обязана стоять в КОНЦЕ линии, а не рядом.
   * Отступы по бокам поля появились ради того, чтобы кружок не срезало
   * краем панели, и разъехаться этим двум местам теперь есть от чего:
   * координата точки и координаты линии считаются в разных строках. */
  const krug = grafik.querySelector('circle.dt');
  const vseTochki = liniya ? liniya.getAttribute('points').trim().split(/\s+/) : [];
  proverka('отметка дня стоит на конце линии',
    !!krug && vseTochki.length > 0
      && krug.getAttribute('cx') + ',' + krug.getAttribute('cy')
         === vseTochki[vseTochki.length - 1],
    (krug ? krug.getAttribute('cx') + ',' + krug.getAttribute('cy') : 'нет отметки')
      + ' против ' + (vseTochki[vseTochki.length - 1] || 'нет линии'));

  /* Линию месяца нельзя показывать штрихом.
   *
   * jsdom не рисует, и эту поломку прогон поймать не мог: на снимке
   * настоящего браузера линия обрывалась, не доходя до сегодняшней точки —
   * то есть пропадали последние дни, самое важное место графика.
   * Причина: `stroke-dasharray` вместе с `vector-effect: non-scaling-stroke`
   * считается в пикселях экрана, а не в долях длины пути, и хвост линии
   * оставался ненарисованным. Раскрытие поля слева направо делает то же
   * самое и ничего не прячет.
   *
   * У пунктиров среднего и вертикали сегодняшнего дня штрих законный —
   * поэтому смотрим ровно на правило самой линии. */
  const stili = fs.readFileSync(path.join(KORNI, 'index.html'), 'utf8');
  const praviloLinii = stili.match(/\.spark[^{]*\.ln\s*\{[^}]*\}/g) || [];
  proverka('линия месяца рисуется не штрихом',
    praviloLinii.every(function (p) { return p.indexOf('stroke-dasharray') === -1; }),
    'stroke-dasharray на .ln прячет конец линии в настоящем браузере');

  proverka('разница показана в сумах', /\d/.test(tekst(w, 'vOnSum')), tekst(w, 'vOnSum'));

  /* Ожидаемое считаем из тех же данных, а не пишем числом.
   *
   * Здесь стояло «разница около 400 тысяч» — и проверка покраснела в
   * первый же день, когда запас пересобрали настоящими курсами. Тест,
   * который краснеет от нормальной работы, перестают открывать, а вместе
   * с ним перестают замечать и настоящие поломки. */
  function summaIzTeksta(stroka) {
    const najdeno = String(stroka).replace(/\s| | /g, '').match(/\d+/g);
    // Берём НАИБОЛЬШЕЕ число строки, а не первое: строка выглядит как
    // «50 000 ₽ uchun odatdagidan 381 000 so'm kam olasiz», и первое
    // число в ней — сумма перевода из подписи, а не ответ.
    const chisla = (najdeno || []).map(function (ch) {
      return parseInt(ch, 10);
    }).filter(function (ch) { return !isNaN(ch); });
    return chisla.length ? Math.max.apply(null, chisla) : NaN;
  }

  const ocenkaZapasa = w.CALC.sovet(w.HISTORY_ZAPAS);
  const zhdem50 = Math.abs(Math.round(
    (ocenkaZapasa.segodnya - ocenkaZapasa.srednee_30) * 50000));
  proverka('разница на 50 000 ₽ совпадает с расчётом по тем же данным',
    Math.abs(summaIzTeksta(tekst(w, 'vOnSum')) - zhdem50) <= 1,
    tekst(w, 'vOnSum') + ' — ждали ' + zhdem50);
  /* Совет проверяем НЕ на запасе, а на данных с сегодняшними датами.
   *
   * Запас лежит с фиксированными датами и стареет сам по себе: через
   * пять дней после последней пересборки приложение перестаёт по нему
   * советовать — и правильно делает. Проверка, привязанная к тексту
   * совета на запасе, начала бы краснеть в календарный срок, без единой
   * правки кода. Такие бомбы обесценивают весь прогон: их принимают за
   * «опять что-то моргнуло».
   *
   * Здесь ряд строится от сегодняшнего дня и падает — как в тот август,
   * когда «подожди» стоило человеку денег каждый день. */
  const segodnyashniy_padayushchiy = [];
  for (let i = 20; i >= 0; i--) {
    segodnyashniy_padayushchiy.push({
      date: new Date(Date.now() - i * 86400000).toISOString().slice(0, 10),
      rub_uzs: 155 - (20 - i) * 0.7,
    });
  }
  const wSovet = podnyat({
    ok: true,
    cbu: { usd_uzs: 11937.89, rub_uzs: 141.0,
           date: segodnyashniy_padayushchiy[20].date },
    services: [{
      id: 'yubor', name: 'Yubor', route: 'A', corridors: ['RU-UZ'],
      fee_fixed: 0, fee_percent: 0, rate_rub_uzs: 136.0,
      limit_per_operation: 1000000, delivery_minutes: 60, incoming_fee: 0,
      checked_at: new Date().toISOString(), fee_unknown: true,
      nacenka_percent: 4.06,
    }],
    banks: [], history: segodnyashniy_padayushchiy, sovet: null,
  }, { intro_pokazan: '1' });
  await dozhdatsya();

  proverka('совет учитывает направление курса',
    /падает|tushmoqda/i.test(tekst(wSovet, 'vHint')),
    tekst(wSovet, 'vHint') + ' — при падающем курсе советовать ждать нельзя');

  /* А на старом запасе совета быть НЕ должно — и это тоже правило, а не
   * случайность. Проверяем его прямо, чтобы никто не «починил» молчание
   * обратно в бодрый совет по позапрошлому курсу. */
  const vozrastZapasa = (Date.now()
    - Date.parse(w.HISTORY_ZAPAS[w.HISTORY_ZAPAS.length - 1].date)) / 86400000;
  if (vozrastZapasa > 5) {
    proverka('на устаревшем запасе совет не даётся',
      /устарел|eski/i.test(tekst(w, 'vHint')),
      tekst(w, 'vHint') + ' — запасу ' + Math.round(vozrastZapasa) + ' дней');
  } else {
    proverka('запас свежий — совет по нему даётся',
      !/устарел|eski/i.test(tekst(w, 'vHint')),
      tekst(w, 'vHint') + ' — запасу ' + Math.round(vozrastZapasa) + ' дней');
  }

  proverka('банк спрятан, пока курсов банков нет', !vidno(w, 'bankBlock'),
    'пустой список в выпадашке обещает данные, которых нет');

  /* Направление курса названо всегда, величина — когда она есть.
   *
   * Недельный сдвиг меньше 0,1% приложение считает шумом и вместо него
   * называет тренд — так и задумано. Проверка же требовала слово «неделя»
   * при любых данных и 24 августа покраснела на исправном продукте: сдвиг
   * вышел 0,02%. Дефект 99, того же рода, что и всякая проверка, прибитая
   * к содержимому запаса, — она краснеет сама собой, когда мир меняется.
   *
   * Теперь проверка идёт по тому же правилу, что и код, и сверяется со
   * словарём, а не с выученным словом: переформулируют строку — проверка
   * поедет за ней, а не переживёт правку молча. */
  const nedelyaZapasa = w.CALC.sovet(w.HISTORY_ZAPAS).nedelya_percent;
  const meta = tekst(w, 'vMeta');
  const podpis = meta + '  (за неделю ' + nedelyaZapasa + '%)';
  if (nedelyaZapasa !== null && nedelyaZapasa !== undefined
      && Math.abs(nedelyaZapasa) >= 0.1) {
    // Строку собираем словарём и теми же данными, что у приложения: так
    // проверяется не только формулировка, но и само число в ней.
    const ozhidaem = w.I18N.t(nedelyaZapasa > 0 ? 'v.week.up' : 'v.week.down',
      { p: Math.abs(nedelyaZapasa).toFixed(1).replace('.', ',') });
    proverka('заметный сдвиг за неделю показан числом',
      meta.indexOf(ozhidaem) !== -1, podpis + ' — ждали «' + ozhidaem + '»');
  } else {
    const trendy = ['rastet', 'padaet', 'stoit'].map(function (k) {
      return w.I18N.t('v.trend.' + k);
    });
    proverka('при ровной неделе названо направление курса',
      trendy.some(function (s) { return meta.indexOf(s) !== -1; }), podpis);
  }

  // Самая убедительная цифра продукта: что стоит выбор дня, в его деньгах.
  proverka('показан размах месяца в его деньгах',
    /\d{3}\s\d{3}/.test(tekst(w, 'vSpread')), tekst(w, 'vSpread'));
  // Тоже из данных, а не «около 670 тысяч»: размах меняется вместе с
  // курсом, и однажды он выйдет за шестьсот тысяч сам собой.
  const zhdemRazmah = Math.round(
    (ocenkaZapasa.max_30 - ocenkaZapasa.min_30) * 50000);
  proverka('размах месяца совпадает с расчётом по тем же данным',
    Math.abs(summaIzTeksta(tekst(w, 'vSpread')) - zhdemRazmah) <= 1,
    tekst(w, 'vSpread') + ' — ждали ' + zhdemRazmah);
  proverka('числа на экране через запятую',
    !/\d\.\d/.test(tekst(w, 'vRate') + tekst(w, 'vAvg') + tekst(w, 'vOsL') + tekst(w, 'vOsR')),
    'по-русски и по-узбекски дробная часть отделяется запятой');

  // Источники — причина верить всему остальному.
  // Вступление — первое, что читает новый человек. Оно рассказывало
  // историю про курс банка получателя, которая на замере не подтвердилась
  // (0,84%). Первое впечатление обязано быть правдой.
  const intro = w.document.getElementById('intro');
  proverka('во вступлении новая история, про день',
    /день|kun/i.test(intro.textContent),
    intro.textContent.slice(0, 120));

  /* Числа вступления сверяем с панелью, а не с константами.
   *
   * Здесь стояло /9,5|155|141/ — те самые числа, что были написаны в
   * словаре словами. Проверка и текст ссылались друг на друга и вместе
   * отстали от продукта: к 22 августа окно месяца съехало на 138,67–
   * 153,87, а вступление всё ещё открывалось словами «от 155 до 141».
   * Человек читал одно число и видел другое в панели под ним, на том же
   * экране. Прогон был зелёный: строка словаря подставилась правильно.
   *
   * Теперь сверяем с концами оси — они считаются из данных. Разойтись
   * вступлению с панелью больше негде, какими бы числа ни стали. */
  proverka('нижняя граница месяца во вступлении та же, что у оси',
    intro.textContent.indexOf(tekst(w, 'vOsL')) !== -1,
    'у оси ' + tekst(w, 'vOsL') + ', во вступлении: ' +
    intro.textContent.slice(0, 120));
  // Подпись правого конца оси — «153,87 · 30 дней», поэтому число берём
  // из данных и форматируем так же, как это делает экран.
  const verhMesyaca = ocenkaZapasa.max_30.toFixed(2).replace('.', ',');
  proverka('верхняя граница месяца во вступлении та же, что у оси',
    intro.textContent.indexOf(verhMesyaca) !== -1
      && tekst(w, 'vOsR').indexOf(verhMesyaca) !== -1,
    'ждали ' + verhMesyaca + ', во вступлении: ' +
    intro.textContent.slice(0, 120));
  proverka('размах в сумах во вступлении тот же, что в панели',
    summaIzTeksta(intro.textContent) === summaIzTeksta(tekst(w, 'vSpread')),
    'во вступлении ' + summaIzTeksta(intro.textContent) + ', в панели ' +
    summaIzTeksta(tekst(w, 'vSpread')) +
    ' — одно и то же число на одном экране');
  proverka('во вступлении нет опровергнутой истории про банк получателя',
    !/банк получателя|qabul qiluvchi bank/i.test(intro.textContent),
    'разброс банков 0,84% — это не то, чем открывают продукт');
  proverka('во вступлении сказано, что мы не предсказываем',
    /не предсказыва|bashorat qilmaymiz/i.test(intro.textContent));

  const src = w.document.querySelector('details.src');
  proverka('блок источников есть', !!src);
  proverka('названы оба источника поимённо',
    src && /Центрального банка|Markaziy bank/.test(src.textContent)
        && /bank\.uz/.test(src.textContent),
    'источник без имени доверия не добавляет');
  proverka('у источников есть дата',
    /\d{2}\.\d{2}\.\d{4}|—/.test(tekst(w, 'srcUpd')), tekst(w, 'srcUpd'));
  proverka('сказано, что мы не переводим деньги',
    src && /не переводим|o'tkazmaymiz/.test(bezApostrofa(src.textContent)));
  proverka('источники свёрнуты по умолчанию', src && !src.open,
    'тому, кому достаточно цифры, это мешать не должно');

  /* ── 1b. Элементы интерфейса вердикта ──────────────────────────── */

  proverka('значок отклонения показан', /%/.test(tekst(w, 'vBadge')), tekst(w, 'vBadge'));
  proverka('у отклонения есть знак',
    /^[+−]/.test(tekst(w, 'vBadge')), tekst(w, 'vBadge') + ' — без знака читается в любую сторону');
  proverka('значок при плохом курсе показывает минус',
    tekst(w, 'vBadge').charAt(0) === '−', tekst(w, 'vBadge'));

  proverka('подписана нижняя граница месяца', /1\d\d[.,]\d\d/.test(tekst(w, 'vOsL')), tekst(w, 'vOsL'));
  proverka('подписана верхняя граница месяца', /1\d\d[.,]\d\d/.test(tekst(w, 'vOsR')), tekst(w, 'vOsR'));
  proverka('указан период графика', /30/.test(tekst(w, 'vOsR')), tekst(w, 'vOsR'));

  proverka('в графике есть градиентная заливка',
    !!w.document.getElementById('vSpark').querySelector('linearGradient'));
  proverka('сегодняшняя точка выделена ореолом',
    !!w.document.getElementById('vSpark').querySelector('circle.dtg'),
    'на ряду из тридцати значений простой кружок теряется');

  const tochka = w.document.getElementById('vDot');
  proverka('точка на шкале месяца стоит', !!tochka && !!tochka.style.left,
    tochka ? tochka.style.left : 'нет');

  /* ── 1c. Быстрый выбор суммы ───────────────────────────────────── */

  const fishki = w.document.querySelectorAll('#chips .chip');
  proverka('быстрые суммы есть', fishki.length === 4, 'штук: ' + fishki.length);
  proverka('текущая сумма подсвечена',
    Array.prototype.some.call(fishki, function (c) { return c.classList.contains('on'); }),
    'человек должен видеть, что выбрано');

  fishki[0].click();          // 10 000
  await dozhdatsya();
  proverka('нажатие подставляет сумму',
    w.document.getElementById('summa').value === '10000',
    w.document.getElementById('summa').value);
  proverka('нажатие сразу считает, без второй кнопки',
    w.document.querySelectorAll('#results .card').length > 0,
    'сумма выбрана — намерение уже понятно');
  proverka('подсветка переехала на нажатую',
    fishki[0].classList.contains('on') && !fishki[2].classList.contains('on'));

  // Возвращаем 50 000 — дальше проверки рассчитаны на неё.
  fishki[2].click();
  await dozhdatsya();
  proverka('возврат к 50 000 работает',
    w.document.getElementById('summa').value === '50000');

  /* ── 1a. Словари двух языков ───────────────────────────────────── */

  // Ключи правятся руками в двух местах файла, и забытый перевод виден
  // не сразу: t() тихо подставляет русскую строку. Для узбека, который
  // и есть основная аудитория, это выглядит поломкой.
  const KLYUCHI = [
    'v.otlichno', 'v.horosho', 'v.obychno', 'v.nize_obychnogo', 'v.ploho',
    'v.rate', 'v.avg', 'v.pos', 'v.pos.worst', 'v.pos.best',
    'v.trend.rastet', 'v.trend.padaet', 'v.trend.stoit',
    'v.onsum.plus', 'v.onsum.minus', 'v.onsum.zero',
    'v.do.otpravlyat', 'v.do.mozhno_zhdat', 'v.do.ne_zhdat', 'v.do.obychno',
    'v.days', 'v.week.up', 'v.week.down', 'v.spread',
    'src.t', 'src.cb', 'src.svc', 'src.upd', 'src.no',
    'svc.markup', 'svc.fee_unknown', 'svc.official', 'svc.lost',
    'sub.t', 'sub.p', 'sub.btn', 'popup.go', 'err.net',
    'svc.lost.t', 'br.t', 'br.cb', 'br.rate', 'br.fee', 'br.fee_unknown', 'br.total',
  ];

  /* Список выше — не источник правды, а страховка на случай, если
   * разбор словаря однажды сломается. Настоящий список берём из самого
   * i18n.js: перечисленный руками отстаёт от файла, и новый ключ,
   * забытый в узбекском, просто не попадёт в проверку. */
  const istochnikI18n = fs.readFileSync(path.join(KORNI, 'i18n.js'), 'utf8');
  const klyuchiIzFayla = Array.from(
    new Set((istochnikI18n.match(/^\s*'([a-z][\w.]*)':/gm) || [])
      .map(function (s) { return s.trim().replace(/^'|':$/g, ''); }))
  );

  proverka('ключи вычитаны из самого словаря', klyuchiIzFayla.length > 40,
    'нашлось ' + klyuchiIzFayla.length + ' — разбор i18n.js сломался');
  proverka('список в проверке не отстал от файла',
    KLYUCHI.every(function (k) { return klyuchiIzFayla.indexOf(k) !== -1; }),
    'в проверке есть ключи, которых нет в i18n.js: ' +
      KLYUCHI.filter(function (k) {
        return klyuchiIzFayla.indexOf(k) === -1;
      }).join(', '));

  const zabytye = [];
  const odinakovye = [];
  klyuchiIzFayla.forEach(function (k) {
    const u = w.I18N.t(k, null, 'uz');
    const r = w.I18N.t(k, null, 'ru');
    // t() возвращает сам ключ, если строки нет вовсе.
    if (u === k || r === k) zabytye.push(k);
    // Одинаковый текст на двух языках почти всегда значит, что узбекский
    // забыли и подставился русский. Для основной аудитории это поломка.
    else if (u === r) odinakovye.push(k);
  });

  proverka('ни один ключ не забыт в словарях', zabytye.length === 0,
    'нет строк: ' + zabytye.join(', '));
  proverka('узбекский не подменён русским', odinakovye.length === 0,
    'совпали: ' + odinakovye.join(', '));

  /* У каждого вердикта и совета, какие умеет выдавать calc.js, обязана
   * быть подпись в словаре. Иначе человек увидит на главном экране
   * служебное имя вроде «v.novyy» — и это будет выглядеть поломкой,
   * потому что поломкой и является.
   *
   * Имена вычитываем из самого calc.js: список, набранный здесь руками,
   * отстанет от кода ровно тогда, когда появится шестой вердикт. */
  const istochnikCalc = fs.readFileSync(path.join(KORNI, 'calc.js'), 'utf8');

  const verdiktyIzKoda = Array.from(new Set(
    (istochnikCalc.match(/verdikt = '([a-z_]+)'/g) || [])
      .map(function (s) { return s.replace(/.*'([a-z_]+)'.*/, '$1'); })));
  proverka('вердикты вычитаны из calc.js', verdiktyIzKoda.length === 5,
    'нашлось: ' + verdiktyIzKoda.join(', '));

  const bezPodpisi = verdiktyIzKoda.filter(function (v) {
    return w.I18N.t('v.' + v, null, 'uz') === 'v.' + v
      || w.I18N.t('v.' + v, null, 'ru') === 'v.' + v;
  });
  proverka('у каждого вердикта есть подпись на обоих языках',
    bezPodpisi.length === 0,
    'без подписи: ' + bezPodpisi.join(', ') +
      ' — человек увидит служебное имя на главном экране');

  /* Ищем по всему файлу, а не по `return '…'`: половина советов
   * возвращается тернарным оператором, и на нём проверка находила три
   * из четырёх — то есть один совет мог остаться без подписи незаметно. */
  const sovetyIzKoda = Array.from(new Set(
    (istochnikCalc.match(/'(otpravlyat|mozhno_zhdat|ne_zhdat|obychno)'/g)
      || []).map(function (s) { return s.replace(/'/g, ''); })));
  const sovetyBezPodpisi = sovetyIzKoda.filter(function (d) {
    return w.I18N.t('v.do.' + d, null, 'uz') === 'v.do.' + d
      || w.I18N.t('v.do.' + d, null, 'ru') === 'v.do.' + d;
  });
  proverka('у каждого совета есть подпись на обоих языках',
    sovetyIzKoda.length === 4 && sovetyBezPodpisi.length === 0,
    'найдено советов ' + sovetyIzKoda.length +
      ', без подписи: ' + sovetyBezPodpisi.join(', '));

  /* ── 2. Расчёт ─────────────────────────────────────────────────── */

  w.document.getElementById('schitat').click();
  await dozhdatsya();

  const kartochki = w.document.querySelectorAll('#results .card');
  proverka('способы посчитаны', kartochki.length === 2, 'карточек: ' + kartochki.length);
  proverka('первый способ помечен лучшим',
    kartochki.length > 0 && kartochki[0].classList.contains('best'));
  proverka('в карточке есть сумма',
    kartochki.length > 0 && /\d{1,2}\s\d{3}\s\d{3}/.test(kartochki[0].textContent),
    kartochki.length ? kartochki[0].textContent : '');
  /* Наценку ждём ту, что лежит в данных, а не «около четырёх процентов».
   * Здесь стояло /4[.,]1|4[.,]0/ — курс сервиса относительно ЦБ в тот день.
   * Курсы ходят: на пересборке запаса наценка стала 2,65%, и проверка
   * покраснела на совершенно исправной карточке. Такое красное учит не
   * доверять прогону, а это дороже любого дефекта, который он ловит.
   *
   * И берём наценку ТОГО сервиса, что стоит в карточке, а не первого из
   * данных. Здесь стояло `w.SERVICES[0]`, и держалось это на совпадении:
   * у Yubor и Avosend курс был одинаковый, значит сверху вставал первый же
   * из списка. 22 августа курсы разъехались впервые — 136,0 против 137,0, —
   * сверху встал второй, и проверка сравнила наценку одного сервиса с
   * карточкой другого. Ищем по имени, которое карточка и печатает. */
  const imyaVKartochke = kartochki.length
    ? kartochki[0].querySelector('.svc').textContent : '';
  const naProverke = w.SERVICES.filter(function (s) {
    return s.name === imyaVKartochke;
  })[0];
  const zhdemNacenku = naProverke
    ? String(naProverke.nacenka_percent.toFixed(1)).replace('.', ',') : null;
  proverka('в карточке видна наценка сервиса',
    kartochki.length > 0 && !!naProverke
      && kartochki[0].textContent.indexOf(zhdemNacenku) !== -1,
    'ждали ' + zhdemNacenku + '% — курс сервиса ниже официального, и это ' +
    'второй рычаг после дня; в карточке: ' +
    (kartochki.length ? kartochki[0].textContent.replace(/\s+/g, ' ') : 'нет карточки'));
  proverka('в карточке оговорка про комиссию',
    kartochki.length > 0 && kartochki[0].textContent.length > 30);

  /* Одна проверка на ВЕСЬ видимый экран вместо перечисления элементов.
   *
   * Точку в дробной части ловили уже трижды и каждый раз в новом месте:
   * в пересылке, в карточке способа, в разборе. Причина одна — числа
   * форматируются там, где выводятся, и следующее место найдётся снова.
   * Проверка по всему тексту закрывает весь класс сразу.
   *
   * Дата пропускается отдельно: «14.08.2026» это тоже цифра-точка-цифра,
   * но формат ЦБ, а не наша небрежность. */
  function vidimyyTekst(korn) {
    const kuski = [];
    (function obhod(el) {
      for (const d of el.childNodes) {
        if (d.nodeType === 3) kuski.push(d.textContent);
        else if (d.nodeType === 1) {
          if (d.classList && d.classList.contains('hidden')) continue;
          if (d.hasAttribute && d.hasAttribute('hidden')) continue;
          obhod(d);
        }
      }
    })(korn);
    return kuski.join(' ');
  }

  const vesTekst = vidimyyTekst(w.document.body)
    .replace(/\d{1,2}\.\d{1,2}\.\d{4}/g, ' ');
  const sTochkoy = vesTekst.match(/\d+\.\d+/g);
  proverka('на всём экране числа через запятую',
    !sTochkoy,
    'через точку: ' + (sTochkoy || []).join(', ') +
      ' — дробная часть не пишется точкой ни по-русски, ни по-узбекски');

  // Дата под курсом — половина доказательства, что цифра настоящая.
  // Машинное «2026-08-14» читается как отладочный вывод, а не как
  // подпись к числу, которому человек должен поверить.
  proverka('дата курса написана словами, а не по-машинному',
    !/\d{4}-\d{2}-\d{2}/.test(tekst(w, 'kursDate')),
    tekst(w, 'kursDate'));

  /* Форматов дат приходит два, и оба в одном ответе бота: ЦБ отдаёт
   * «14.08.2026», а история и вердикт считаются в «2026-08-14».
   * Разбирать только один — значит однажды показать человеку сырую
   * строку вместо даты и не заметить: она ведь тоже похожа на дату. */
  proverka('строка источников не показывает сырую дату',
    !/\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2}/.test(tekst(w, 'srcUpd')),
    tekst(w, 'srcUpd'));
  proverka('в строке источников есть месяц словом',
    /август|avgust|январ|yanvar|феврал|fevral|март|mart|апрел|aprel|ма[йя]|may|июн|iyun|июл|iyul|сентябр|sentabr|октябр|oktabr|ноябр|noyabr|декабр|dekabr/i
      .test(tekst(w, 'srcUpd')),
    tekst(w, 'srcUpd'));

  /* Здесь смешивались две разные вещи: ДАННЫЕ собираются каждый час, а
   * КУРС относится к дню публикации ЦБ. Строка говорила «обновляется
   * каждый час, последний раз 14.08» — то есть «два дня не обновлялось»,
   * хотя всё работало исправно. */
  proverka('частота сбора и дата курса не смешаны',
    !/последний раз|oxirgi marta/i.test(tekst(w, 'srcUpd')),
    tekst(w, 'srcUpd') + ' — дата курса это не время последнего сбора');

  /* У запаса обязана быть дата. Он показывается человеку именно тогда,
   * когда бот спит, — и без даты это цифра без даты, ровно то, что
   * правило проекта запрещает. Здесь её не было, и в такие минуты
   * приложение честно рисовало прочерк вместо дня. */
  proverka('у запасных курсов есть дата',
    !!(w.KURSY_ZAPAS && w.KURSY_ZAPAS.date),
    'пересобери запас: cd bot && py obnovit_zapas.py');

  proverka('кнопка пересылки появилась', vidno(w, 'share'));
  proverka('подписка предложена после пользы', vidno(w, 'subCta'),
    'сначала цифра, потом просьба писать');
  proverka('ссылка на канал скрыта, пока канала нет', !vidno(w, 'chLink'),
    'пустой CHANNEL_LINK — рабочее состояние, а не недоделка');
  proverka('дисклеймер показан', vidno(w, 'disclaimer'));
  proverka('нет пометки о тестовых данных',
    !/ТЕСТ|TEST/i.test(tekst(w, 'disclaimer')),
    'данные настоящие, пометка врала бы');
  proverka('три шага спрятались после расчёта', !vidno(w, 'idle'));

  /* Плашка показывает БОЛЬШУЮ из двух потерь, и это зависит от данных, а
   * не от нашей памяти.
   *
   * Потерь всегда две. Разница между способами видна прямо в списке под
   * плашкой, и на неё можно повлиять. Потеря на курсе одинакова у всех и
   * потому в списке невидима — а она обычно в десятки раз больше.
   *
   * Правило было другим: есть разница между способами — показываем её. И
   * самым громким числом экрана становилось «4 000 сум», пока курс тихо
   * забирал сто восемьдесят три тысячи.
   *
   * Проверяем не ветку, а СООТВЕТСТВИЕ подписи числу и то, что выбрано
   * действительно большее. Оба числа берём с экрана: разницу — из
   * карточек, потерю против ЦБ — из строк разбора.
   *
   * Подпись сверяем с самим словарём, а не с наличием слова «курс» в
   * тексте. Слово держало проверку ровно до дня, когда подпись перестала
   * называть один только курс: число под ней всегда было шире — курс И
   * комиссия, — и заголовок пришлось поправить. Сравнение с ключом
   * переживает любую правку формулировки и ловит ровно то, ради чего
   * проверка стоит: число под чужой подписью. */
  function podpisIzSlovarya(klyuch) {
    return [w.I18N.t(klyuch, null, 'ru'), w.I18N.t(klyuch, null, 'uz')];
  }
  proverka('плашка потери показана', vidno(w, 'loss'),
    'потеря есть всегда: либо между способами, либо к официальному курсу');
  proverka('в плашке есть число', /\d{3}/.test(tekst(w, 'lossNum')), tekst(w, 'lossNum'));

  const podpisPlashki = tekst(w, 'lossT');
  const proMezhduSposobami = /между способами|usullar orasidagi/i.test(podpisPlashki);
  const raznicaSposobov = kartochki.length > 1
    ? summaIzTeksta(kartochki[0].textContent) - summaIzTeksta(kartochki[1].textContent)
    : 0;

  /* Плашка показывает ВСЮ потерю против официального курса, а разбор
   * разносит её по строкам вычитания: курс сервиса, комиссия. Значит и
   * сверять надо с их суммой, а не с одной строкой.
   *
   * Здесь бралась только строка курса, и это держалось на том, что у
   * лучшего способа комиссии не было: сумма из одного слагаемого равна
   * слагаемому. 22 августа сверху впервые встал сервис с комиссией — и
   * плашка разошлась с разбором на её величину. Сумма строк не зависит
   * от того, сколько их сегодня. */
  const strokiVychet = Array.prototype.map.call(
    w.document.querySelectorAll('#rRows .rl.minus'),
    function (r) { return summaIzTeksta(r.querySelector('.v').textContent); });
  const poteryaVsego = strokiVychet.reduce(function (a, b) { return a + b; }, 0);

  if (proMezhduSposobami) {
    proverka('подпись «между способами» стоит при реальной разнице',
      raznicaSposobov > 0,
      'способы дают одинаково, а подпись обещает разницу: ' + podpisPlashki);
    proverka('между способами попало в плашку только как большее',
      raznicaSposobov >= poteryaVsego,
      'разница способов ' + raznicaSposobov + ', а перевод забрал ' + poteryaVsego +
      ' — в плашке обязано стоять большее');
  } else {
    proverka('подпись про потерю к ЦБ стоит, когда она и есть главная',
      podpisIzSlovarya('svc.lost.t').indexOf(podpisPlashki) !== -1
        && poteryaVsego >= raznicaSposobov,
      podpisPlashki + ' — перевод забрал ' + poteryaVsego +
      ', разница способов ' + raznicaSposobov);
    // Процент нужен только у потери к ЦБ: там он крупный и осмысленный.
    proverka('у потери на курсе показан процент', /%/.test(tekst(w, 'lossNum')),
      tekst(w, 'lossNum') + ' — без процента непонятно, много это или мало');
    proverka('число в плашке — та же потеря, что в разборе',
      Math.abs(summaIzTeksta(tekst(w, 'lossNum')) - poteryaVsego) <= 1,
      'в плашке ' + summaIzTeksta(tekst(w, 'lossNum')) + ', в разборе ' +
      strokiVychet.join(' + ') + ' = ' + poteryaVsego +
      ' — одно и то же число, посчитанное дважды по-разному, ловится только так');
  }

  const polosy = w.document.querySelectorAll('#results .card .bar i');
  proverka('у каждой карточки есть полоса', polosy.length === kartochki.length,
    'полос: ' + polosy.length + ' карточек: ' + kartochki.length);
  proverka('полосы имеют ширину',
    Array.prototype.every.call(polosy, function (p) { return /%$/.test(p.style.width); }),
    Array.prototype.map.call(polosy, function (p) { return p.style.width; }).join(', '));
  /* Полосы следуют за итогами: равные итоги — равные полосы, больший
   * итог — полоса не короче. Раньше здесь стояло «полосы одинаковы»,
   * потому что оба сервиса давали одно и то же; появилась комиссия —
   * появилась и разница, а проверка осталась в прошлом дне. */
  const shiriny = Array.prototype.map.call(polosy, function (p) {
    return parseFloat(p.style.width) || 0;
  });
  proverka('полоса лучшего способа не короче остальных',
    shiriny.length < 2 || shiriny[0] >= shiriny[1],
    shiriny.join('% / ') + '% — сверху тот, где придёт больше');
  proverka('равные итоги дают равные полосы',
    raznicaSposobov !== 0 || shiriny.length < 2
      || Math.abs(shiriny[0] - shiriny[1]) < 0.01,
    'итоги равны, а полосы разной длины: ' + shiriny.join('% / ') + '%');

  /* ── Куда уходят деньги ────────────────────────────────────────── */

  proverka('разбор показан', vidno(w, 'razbor'),
    'это главное обещание продукта — показать невидимое');

  const strokiRazbora = w.document.querySelectorAll('#rRows .rl');
  proverka('в разборе есть строки', strokiRazbora.length >= 3,
    'строк: ' + strokiRazbora.length);
  proverka('первая строка — курс ЦБ',
    strokiRazbora.length > 0 && /ЦБ|Markaziy/.test(strokiRazbora[0].textContent),
    strokiRazbora.length ? strokiRazbora[0].textContent : '');
  proverka('есть строка про курс сервиса',
    Array.prototype.some.call(strokiRazbora, function (s) {
      return s.classList.contains('minus');
    }), 'потеря на курсе обязана быть видна отдельной строкой');
  proverka('последняя строка — итог',
    strokiRazbora.length > 0 &&
    strokiRazbora[strokiRazbora.length - 1].classList.contains('itog'));

  // Арифметика разбора обязана сходиться: человек проверит её на калькуляторе.
  const chisla = Array.prototype.map.call(strokiRazbora, function (s) {
    const v = s.querySelector('.v').textContent.replace(/[^\d]/g, '');
    return v ? parseInt(v, 10) : null;
  });
  const verh = chisla[0];
  const niz = chisla[chisla.length - 1];
  const vychety = chisla.slice(1, -1).filter(function (x) { return x !== null && x > 0; })
    .reduce(function (a, b) { return a + b; }, 0);
  proverka('строки разбора сходятся с итогом',
    Math.abs(verh - vychety - niz) <= 1000,
    'сверху ' + verh + ' минус ' + vychety + ' должно дать ' + niz);

  const dolya = w.document.querySelectorAll('#rBar i');
  proverka('полоса потерь нарисована', dolya.length === 2,
    'частей: ' + dolya.length);
  proverka('полоса потерь не пустая',
    dolya.length === 2 && parseFloat(dolya[0].style.width) > 50,
    'дошло должно быть большей частью, иначе что-то посчитано не так');

  proverka('результат объявляется голосом',
    w.document.getElementById('results').getAttribute('aria-live') === 'polite',
    'иначе незрячий нажимает «Посчитать» и не узнаёт, что что-то изменилось');

  /* ── 3. Проверка ввода ─────────────────────────────────────────── */

  const pole = w.document.getElementById('summa');
  function vvesti(v) {
    pole.value = String(v);
    pole.dispatchEvent(new w.Event('input'));
  }

  vvesti(500);
  proverka('слишком малая сумма — ошибка', vidno(w, 'summaErr'), tekst(w, 'summaErr'));
  proverka('старый результат убран', w.document.querySelectorAll('#results .card').length === 0,
    'он посчитан по другой сумме и уже врёт');

  vvesti(99999999);
  proverka('слишком большая сумма — ошибка', vidno(w, 'summaErr'), tekst(w, 'summaErr'));

  vvesti('');
  proverka('пустое поле — ошибка', vidno(w, 'summaErr'));
  proverka('при ошибке разница в сумах не показывается', tekst(w, 'vOnSum') === '',
    'считать выгоду от несуществующей суммы нельзя');
  proverka('при ошибке размах тоже гаснет', tekst(w, 'vSpread') === '',
    'оставленная строка показывала бы цифру от прошлого ввода');

  vvesti(100000);
  proverka('верная сумма — ошибки нет', !vidno(w, 'summaErr'), tekst(w, 'summaErr'));
  // Вдвое большая сумма обязана дать вдвое большую разницу. Проверяем
  // соотношение, а не число: числа приходят из живых данных и меняются.
  proverka('разница пересчиталась на новую сумму',
    Math.abs(summaIzTeksta(tekst(w, 'vOnSum')) - 2 * zhdem50) <= 2,
    tekst(w, 'vOnSum') + ' — на 100 000 ₽ ждали ' + 2 * zhdem50);

  w.document.getElementById('schitat').click();
  await dozhdatsya();
  proverka('после исправления расчёт снова идёт',
    w.document.querySelectorAll('#results .card').length === 2);

  /* ── 4. Языки ──────────────────────────────────────────────────── */

  const doPereklyucheniya = tekst(w, 'vHead');
  const knopkiYazyka = w.document.querySelectorAll('.lang');
  const ru = Array.prototype.filter.call(knopkiYazyka, function (b) {
    return b.getAttribute('data-lang') === 'ru';
  })[0];
  const uz = Array.prototype.filter.call(knopkiYazyka, function (b) {
    return b.getAttribute('data-lang') === 'uz';
  })[0];

  ru.click();
  const poRusski = tekst(w, 'vHead');
  proverka('русский текст вердикта', /курс/i.test(poRusski), poRusski);
  proverka('результат тоже перевёлся',
    w.document.querySelectorAll('#results .card').length === 2,
    'смена языка не должна стирать расчёт');

  uz.click();
  const poUzbekski = tekst(w, 'vHead');
  proverka('узбекский текст вердикта', /kurs/i.test(poUzbekski), poUzbekski);
  proverka('языки дают разный текст', poRusski !== poUzbekski);
  proverka('вердикт не потерялся при переключениях', vidno(w, 'verdict'));
  void doPereklyucheniya;

  /* ── 5. Пересылка ──────────────────────────────────────────────── */

  let ushlo = null;
  w.open = function (u) { ushlo = u; };
  Object.defineProperty(w.navigator, 'clipboard', {
    value: { writeText: function (x) { ushlo = x; } }, configurable: true,
  });
  w.alert = function () {};

  w.document.getElementById('share').click();
  proverka('пересылка что-то собрала', !!ushlo && ushlo.length > 20);
  proverka('в пересылке есть ссылка на нас', !!ushlo && ushlo.indexOf('t.me/') !== -1,
    'без ссылки расчёт гуляет по чатам, а вернуться некуда');
  proverka('в пересылке два языка', !!ushlo && ushlo.indexOf('· · ·') !== -1);
  proverka('в пересылке есть вердикт дня',
    !!ushlo && (/курс/i.test(ushlo) && /kurs/i.test(ushlo)),
    'вердикт есть всегда, а разница между способами бывает нулевой');
  proverka('в пересылке нет ИТОГА автора',
    !!ushlo && !/\d{1,2}\s\d{3}\s\d{3}\s*(сум|so)/i.test(ushlo),
    'у читателя другая сумма, чужой итог ему бесполезен; ' +
      'размах месяца на эталонных 50 000 — другое дело, он переносится');

  /* Пересылка — единственный бесплатный источник роста, и это самый
   * видимый текст продукта: он уходит в чужие чаты, где его уже не
   * поправишь. Всё, что ниже, там однажды было сломано. */

  proverka('в пересылке числа через запятую',
    !!ushlo && !/\d\.\d/.test(ushlo),
    'уходило «141.76» — точка не пишется ни по-русски, ни по-узбекски; ' +
      'на экране запятая была, а в пересылке нет');

  proverka('в пересылке есть дата курса',
    !!ushlo && /\d{1,2}\s(август|avgust|январ|yanvar|феврал|fevral|март|mart|апрел|aprel|ма[йя]|may|июн|iyun|июл|iyul|сентябр|sentabr|октябр|oktabr|ноябр|noyabr|декабр|dekabr)/i.test(ushlo),
    'число без даты — ложь, а сообщение живёт в чате неделями');

  proverka('в пересылке есть цена вопроса в сумах',
    !!ushlo && /\d{3}\s\d{3}/.test(ushlo),
    'раньше в пересылке не было ни одной денежной цифры — ' +
      'то есть не было и причины её пересылать');

  proverka('в пересылке не сказано «сегодня»',
    !!ushlo && !/сегодня|bugun/i.test(ushlo),
    'ЦБ не публикует по выходным: в понедельник свежайший курс — ' +
      'за пятницу, и «сегодня» было бы неправдой три дня в неделю');

  /* ── 3в. Партнёрская выплата не поднимает способ вверх ─────────── */
  //
  // Главное правило проекта, и единственное, которое можно нарушить
  // одной строкой сортировки так, что никто не заметит: сверху всегда
  // тот способ, где человеку придёт больше, — не тот, кто нам платит.
  //
  // Проверяем на подставных данных: у худшего способа есть партнёрская
  // ссылка, у лучшего нет.

  const sPartnerom = [
    {
      id: 'platit', name: 'Платит нам', route: 'A', corridors: ['RU-UZ'],
      fee_fixed: 0, fee_percent: 0, rate_rub_uzs: 130.0,
      limit_per_operation: 1000000, delivery_minutes: 10, incoming_fee: 0,
      checked_at: new Date().toISOString(),
      partner_url: 'https://example.com/partner?ref=my',
    },
    {
      id: 'ne_platit', name: 'Не платит', route: 'A', corridors: ['RU-UZ'],
      fee_fixed: 0, fee_percent: 0, rate_rub_uzs: 140.0,
      limit_per_operation: 1000000, delivery_minutes: 60, incoming_fee: 0,
      checked_at: new Date().toISOString(),
    },
  ];

  const sPartnerskim = w.CALC.poschitat(
    { summa: 50000, bank_id: null, corridor: 'RU-UZ' },
    sPartnerom, [], { usd_uzs: 11937.89, rub_uzs: 141.76 });

  proverka('сверху тот, где человеку придёт больше',
    sPartnerskim.results[0].service_id === 'ne_platit',
    'первым идёт ' + sPartnerskim.results[0].service_id +
      ' — порядок задаёт только итог, который получит человек');
  proverka('способ с выплатой не выброшен, а просто ниже',
    sPartnerskim.results.length === 2,
    'мы не прячем платящих, мы просто не двигаем их вверх');

  /* И главное: партнёрской ссылки вообще нет в том, что уходит на
   * сортировку. Правило, которое держится на дисциплине, однажды
   * нарушат; правило, которое держится на отсутствии данных, — нет.
   * Сортировать по выплате нельзя не потому, что мы договорились, а
   * потому, что сортировщику её просто неоткуда взять. */
  proverka('партнёрская ссылка не доезжает до расчёта',
    sPartnerskim.results.every(function (r) {
      return !('partner_url' in r);
    }),
    Object.keys(sPartnerskim.results[0]).join(', ') +
      ' — пока поля нет, отсортировать по нему невозможно');

  /* ── 3г. Недоступный способ не встаёт первым ───────────────────── */
  //
  // У сервисов есть обе границы. Yubor не принимает переводы меньше ста
  // долларов и больше тысячи двухсот; у Avosend потолок 200 000 ₽.
  // Способ, которым человек не может воспользоваться, не должен стоять
  // сверху с меткой «больше всего» — он показывает сумму, которую по
  // нему не отправить, и человек узнает об этом уже в самом сервисе.

  const sGranicami = [
    {
      id: 'uzkiy', name: 'Узкий', route: 'A', corridors: ['RU-UZ'],
      fee_fixed: 0, fee_percent: 0, rate_rub_uzs: 140.0,
      limit_min: 9000, limit_per_operation: 100000,
      delivery_minutes: 60, incoming_fee: 0,
      checked_at: new Date().toISOString(),
    },
    {
      id: 'shirokiy', name: 'Широкий', route: 'A', corridors: ['RU-UZ'],
      fee_fixed: 0, fee_percent: 0, rate_rub_uzs: 135.0,
      limit_per_operation: 500000,
      delivery_minutes: 60, incoming_fee: 0,
      checked_at: new Date().toISOString(),
    },
  ];

  function schitat(summa) {
    return w.CALC.poschitat({ summa: summa, bank_id: null, corridor: 'RU-UZ' },
      sGranicami, [], { usd_uzs: 11937.89, rub_uzs: 141.76 });
  }

  const malo = schitat(3000);
  proverka('ниже минимума способ помечен',
    malo.results.some(function (r) { return r.nizhe_minimuma; }),
    'Yubor не принимает меньше ста долларов, и молчать об этом нельзя');
  proverka('при малой сумме сверху доступный способ',
    malo.results[0].service_id === 'shirokiy',
    'первым идёт ' + malo.results[0].service_id +
      ' — недоступный не должен стоять с меткой «больше всего»');

  const mnogo = schitat(300000);
  proverka('выше лимита способ помечен',
    mnogo.results.some(function (r) { return r.vyshe_limita; }));
  proverka('при крупной сумме сверху доступный способ',
    mnogo.results[0].service_id === 'shirokiy',
    'первым идёт ' + mnogo.results[0].service_id);

  const vsamyyraz = schitat(50000);
  proverka('в рабочем диапазоне сверху тот, где придёт больше',
    vsamyyraz.results[0].service_id === 'uzkiy',
    'курс 140 против 135 — выигрывает узкий, если он доступен');

  /* ── 4а. Кеш не заслоняет свежие данные ────────────────────────── */
  //
  // Здесь стоял ранний возврат: есть кеш моложе суток — берём его и в
  // сеть не идём вовсе. Человек, открывший приложение вечером, наутро
  // видел вчерашний курс, хотя ЦБ уже опубликовал новый. Продукт,
  // отвечающий на вопрос «какой курс СЕГОДНЯ», показывал вчерашний.

  const vcherashniy = {
    ok: true,
    cbu: { usd_uzs: 11900, rub_uzs: 130.00, date: '2026-08-10' },
    services: [{
      id: 'yubor', name: 'Yubor', route: 'A', corridors: ['RU-UZ'],
      fee_fixed: 0, fee_percent: 0, rate_rub_uzs: 125.0,
      limit_per_operation: 1000000, delivery_minutes: 60, incoming_fee: 0,
      checked_at: new Date().toISOString(), fee_unknown: true,
      nacenka_percent: 3.8,
    }],
    banks: [],
    history: (function () {
      const r = [];
      for (let i = 29; i >= 0; i--) {
        r.push({
          date: new Date(Date.now() - i * 86400000).toISOString().slice(0, 10),
          rub_uzs: 130.0,
        });
      }
      return r;
    })(),
    sovet: null,
    saved_at: Date.now() - 3600000,     // час назад: кеш заведомо «свежий»
  };

  const svezhiy = JSON.parse(JSON.stringify(vcherashniy));
  svezhiy.cbu.rub_uzs = 160.00;
  svezhiy.cbu.date = '2026-08-16';
  svezhiy.history[svezhiy.history.length - 1].rub_uzs = 160.0;
  delete svezhiy.saved_at;

  const wKesh = podnyat(svezhiy, {
    intro_pokazan: '1',
    dannye: JSON.stringify(vcherashniy),
  });
  await dozhdatsya();

  proverka('свежий курс перебивает кеш',
    /160/.test(tekst(wKesh, 'vRate')),
    tekst(wKesh, 'vRate') + ' — кеш моложе суток не должен отменять запрос');
  proverka('в кеше лежал другой курс',
    JSON.parse(wKesh.localStorage.getItem('dannye')).cbu.rub_uzs === 160,
    'после ответа бота кеш обязан обновиться');

  /* ── 4б. Обещания, которых мы не даём ──────────────────────────── */
  //
  // Пункты чек-листа приёмки, которые до сих пор проверялись глазами.
  // Глазами их проверяют один раз, а нарушают потом — когда правят текст
  // и хочется написать поярче.
  //
  // «Самый выгодный» — мы не знаем всех сервисов. «Придёт ровно» — не
  // знаем комиссий. «Курс вырастет» — за предсказание курса нужна
  // лицензия ЦБ, и это не фигура речи, а закон.

  const ZAPRESHCHENO = [
    ['«самый выгодный»', /самый выгодн|самый лучш|eng foydali|eng yaxshi kurs/i,
      'мы не знаем всех сервисов коридора и не можем называть лучший'],
    ['«придёт ровно столько»', /придёт ровно|точно придёт|aniq keladi/i,
      'комиссии не объявлены, наш итог — верхняя граница'],
    ['«экономьте»', /экономьте|сэконом|tejang/i,
      'обещание экономии — это обещание, а мы только считаем'],
    ['«гарантируем»', /гарантир|кафолат|kafolat/i, 'мы ничего не гарантируем'],
    ['предсказание курса', /курс вырастет|курс упадёт|kurs ko'tariladi|kurs tushadi/i,
      'за предсказание курса нужна лицензия ЦБ — это закон, а не осторожность'],
    ['«без комиссии»', /без комисси|komissiyasiz/i,
      'комиссии сервисов как раз и неизвестны'],
  ];

  /* Ищем по исходнику словаря, а не по видимому экрану: на экране в
   * каждый момент только часть строк, а запрещённое обещание может
   * лежать в ветке, которая всплывёт через месяц при другом курсе. */
  const vseTeksty = bezApostrofa(fs.readFileSync(path.join(KORNI, 'i18n.js'), 'utf8'))
    // Комментарии выбрасываем: в них эти слова как раз и объясняются,
    // и проверка ловила бы собственное объяснение.
    .replace(/\/\*[\s\S]*?\*\//g, ' ')
    .replace(/^\s*\/\/.*$/gm, ' ')
    + ' ' + bezApostrofa(vidimyyTekst(w.document.body));

  ZAPRESHCHENO.forEach(function (para) {
    const najdeno = vseTeksty.match(para[1]);
    proverka('в текстах нет ' + para[0], !najdeno,
      (najdeno ? 'нашлось «' + najdeno[0] + '»: ' : '') + para[2]);
  });

  // Чужих логотипов нет: ни одной картинки со стороны. Это и правовой
  // вопрос, и вопрос доверия — логотип банка на нашем экране читается
  // как «мы с ними заодно».
  const kartinki = Array.from(w.document.querySelectorAll('img'));
  proverka('чужих логотипов на экране нет',
    kartinki.every(function (i) {
      const src = i.getAttribute('src') || '';
      return !/^https?:/.test(src);
    }),
    kartinki.map(function (i) { return i.getAttribute('src'); }).join(', '));

  /* ── 4в. Свежесть данных ───────────────────────────────────────── */

  function starye(dneyNazad, chasovSbora) {
    const den = function (n) {
      return new Date(Date.now() - n * 86400000).toISOString().slice(0, 10);
    };
    const istoriya = [];
    for (let i = 29; i >= 0; i--) {
      istoriya.push({ date: den(i + dneyNazad), rub_uzs: 150 - i * 0.3 });
    }
    return {
      ok: true,
      cbu: { usd_uzs: 11937.89, rub_uzs: 141.76, date: den(dneyNazad) },
      services: [{
        id: 'yubor', name: 'Yubor', route: 'A', corridors: ['RU-UZ'],
        fee_fixed: 0, fee_percent: 0, rate_rub_uzs: 136.0,
        limit_per_operation: 1000000, delivery_minutes: 60, incoming_fee: 0,
        checked_at: new Date(Date.now() - chasovSbora * 3600000).toISOString(),
        fee_unknown: true, nacenka_percent: 4.06,
      }],
      banks: [], history: istoriya, sovet: null,
    };
  }

  async function posle_rascheta(dannye) {
    const okno = podnyat(dannye, { intro_pokazan: '1' });
    await dozhdatsya();
    okno.document.getElementById('summa').value = '50000';
    okno.document.getElementById('schitat').click();
    await dozhdatsya();
    return okno;
  }

  // Свежее: способ показан без отметок об устаревании.
  const wSvezh = await posle_rascheta(starye(0, 2));
  proverka('свежие данные — способ показан',
    wSvezh.document.querySelectorAll('#results .card').length === 1);

  /* Данные от суток до трёх мы показываем, но обязаны сказать об этом.
   * Отметка ставилась «если первый — лучший, ИНАЧЕ если устарело», то
   * есть у лучшего способа не появлялась никогда — именно у того,
   * который человек и выберет. Молчать в самом видном месте — ровно
   * противоположное тому, ради чего правило заводили. */
  const wVchera = await posle_rascheta(starye(1, 30));
  const kartochkaVchera = wVchera.document.querySelector('#results .card');
  proverka('вчерашние данные помечены прямо у лучшего способа',
    !!kartochkaVchera && /вчера|kecha/i.test(kartochkaVchera.textContent),
    kartochkaVchera ? kartochkaVchera.textContent.replace(/\s+/g, ' ') : 'нет карточки');
  proverka('и метка «больше всего» при этом на месте',
    !!kartochkaVchera && kartochkaVchera.classList.contains('best'),
    'две метки не конкурируют за одно место');

  // Старше трёх суток — способ не показываем вовсе.
  const wStar = await posle_rascheta(starye(4, 100));
  proverka('протухшие курсы сервисов скрыты целиком',
    wStar.document.querySelectorAll('#results .card').length === 0,
    'правило проекта: старше 72 часов не показываем');

  /* А ЧТО человек видит вместо списка — вопрос отдельный, и до сих пор
   * он видел «данные обновляются, загляните через час». Это обещание,
   * которого продукт в этом состоянии выполнить не может: курсы скрыты
   * ровно потому, что обновлять их некому. С 24 по 29 августа так и
   * было — пять дней подряд, каждый час. */
  const pustoStar = tekst(wStar, 'results');
  proverka('вместо списка названа дата последнего сбора',
    /\b\d{1,2}\s+\S/.test(pustoStar), pustoStar);
  proverka('и никакого «через час», которого мы не выполним',
    !/час|soat/i.test(pustoStar), pustoStar);

  /* А когда сервисов нет вовсе — сбор идёт, и прежний текст верен. */
  const wPusto = await posle_rascheta((function () {
    const d = starye(0, 2);
    d.services = [];
    return d;
  })());
  proverka('без сервисов текст прежний: данные собираются',
    /час|soat/i.test(tekst(wPusto, 'results')), tekst(wPusto, 'results'));

  /* А вот СОВЕТ при тех же данных продолжал бодро говорить «сегодня
   * хороший день» — по курсу многодневной давности. Это ровно тот же
   * класс вреда, что и совет ждать в падающем рынке: человек послушает
   * и потеряет. Порог здесь мягче трёх суток: ЦБ не публикует по
   * выходным и в праздники, длинные каникулы это норма. */
  const wOchenStar = await posle_rascheta(starye(8, 200));
  proverka('по старым данным совет не даётся',
    /устарел|eski/i.test(tekst(wOchenStar, 'vHint')),
    tekst(wOchenStar, 'vHint') + ' — совет по курсу недельной давности '
      + 'это совет потерять деньги');
  proverka('на свежих данных совет по-прежнему даётся',
    !/устарел|eski/i.test(tekst(wSvezh, 'vHint')),
    tekst(wSvezh, 'vHint'));

  /* ── 5a. Учёт ──────────────────────────────────────────────────── */

  // Учёт — это то, ради чего партнёрская программа вообще станет
  // возможной: без доказанного потока разговаривать не о чем.
  const sobytiya = [];
  const w4 = podnyat(null, { intro_pokazan: '1' });
  w4.navigator.sendBeacon = function (adres, telo) {
    sobytiya.push({ adres: adres, telo: String(telo && telo._buffer || telo) });
    return true;
  };
  // Blob в jsdom не отдаёт содержимое синхронно, поэтому подменяем его
  // на прозрачную обёртку — нам важен факт и адрес, а не байты.
  w4.Blob = function (chasti) { return { toString: function () { return chasti.join(''); } }; };
  await dozhdatsya();

  w4.document.getElementById('schitat').click();
  await dozhdatsya();

  proverka('события уходят на бота', sobytiya.length > 0,
    'отправлено: ' + sobytiya.length);
  proverka('события идут на /api/event',
    sobytiya.every(function (s) { return /\/api\/event$/.test(s.adres); }),
    sobytiya.length ? sobytiya[0].adres : 'нет');
  proverka('расчёт учтён',
    sobytiya.some(function (s) { return s.telo.indexOf('raschet') !== -1; }),
    sobytiya.map(function (s) { return s.telo.slice(0, 60); }).join(' | '));
  proverka('точная сумма человека наружу не уходит',
    sobytiya.every(function (s) { return s.telo.indexOf('"summa":100000') === -1
                                     && s.telo.indexOf('"summa":50000') === -1; }),
    'отправляем только порядок суммы, не саму сумму');

  /* Метка источника — в КАЖДОМ событии, а не только в «открыл».
   *
   * По одним переходам источники не различить: чат с двумя сотнями
   * заходов и нулём расчётов хуже, чем чат с двадцатью заходами и
   * пятнадцатью расчётами. Первое — зеваки, второе — люди с деньгами
   * в руках, и ради этой разницы посев ведётся по одному чату за раз. */
  const sMetkoy = [];
  const wMetka = podnyat(null, { intro_pokazan: '1' }, 'chat_moskva1');
  wMetka.navigator.sendBeacon = function (adres, telo) {
    sMetkoy.push(String(telo)); return true;
  };
  wMetka.Blob = function (chasti) {
    return { toString: function () { return chasti.join(''); } };
  };
  await dozhdatsya();
  wMetka.document.getElementById('summa').value = '50000';
  wMetka.document.getElementById('schitat').click();
  await dozhdatsya();

  const sRaschetom = sMetkoy.filter(function (s) {
    return s.indexOf('raschet') !== -1;
  });
  proverka('расчёт учтён при переходе из чата', sRaschetom.length > 0,
    'событий: ' + sMetkoy.length);
  proverka('метка источника есть и в расчёте, а не только в открытии',
    sRaschetom.every(function (s) { return s.indexOf('chat_moskva1') !== -1; }),
    sRaschetom.join(' | ').slice(0, 200));

  /* ── 6. Живой ответ бота перекрывает запас ─────────────────────── */

  const otvetBota = {
    ok: true,
    cbu: { usd_uzs: 12000, rub_uzs: 160.0, date: '20.08.2026' },
    services: [{
      id: 'test-servis', name: 'Test Servis', route: 'A', corridors: ['RU-UZ'],
      fee_fixed: 0, fee_percent: 0, rate_rub_uzs: 155.0,
      limit_per_operation: 1000000, delivery_minutes: 30, incoming_fee: 0,
      checked_at: new Date().toISOString(), nacenka_percent: 3.13,
    }],
    banks: [{ id: 'b1', name: 'Test Bank', rate_usd_uzs: 11900,
              incoming_fee: 0, checked_at: new Date().toISOString() }],
    history: Array.from({ length: 30 }, function (_, i) {
      return { date: '2026-08-' + String(i + 1).padStart(2, '0'), rub_uzs: 150 };
    }).concat([{ date: '2026-09-01', rub_uzs: 160 }]),
  };

  const w2 = podnyat(otvetBota);
  await dozhdatsya();

  proverka('данные бота применились', /160/.test(tekst(w2, 'vRate')), tekst(w2, 'vRate'));
  proverka('вердикт по данным бота — хороший день',
    w2.document.getElementById('verdict').classList.contains('good'),
    '160 против среднего 150 — заметно лучше обычного');
  proverka('банк появился, когда курсы банков пришли', vidno(w2, 'bankBlock'),
    'поле обязано появляться само, без правки кода');

  // Канал заведён — ссылка обязана появиться сама, без правки кода.
  const w2ch = podnyat(null, { intro_pokazan: '1' });
  w2ch.CHANNEL_LINK = 'https://t.me/proverka_kanala';
  w2ch.eval("window.CHANNEL_LINK = 'https://t.me/proverka_kanala';"
    + require('fs').readFileSync(require('path').join(KORNI, 'app.js'), 'utf8'));
  await dozhdatsya();
  const ssylka = w2ch.document.getElementById('chLink');
  proverka('ссылка на канал появляется, когда канал заведён',
    !!ssylka && !ssylka.classList.contains('hidden'),
    'вписать адрес должно быть достаточно');
  proverka('ссылка ведёт на указанный канал',
    ssylka && ssylka.getAttribute('href') === 'https://t.me/proverka_kanala',
    ssylka ? String(ssylka.getAttribute('href')) : 'нет');

  w2.document.getElementById('schitat').click();
  await dozhdatsya();
  const kartochki2 = w2.document.querySelectorAll('#results .card');
  proverka('считается по сервису от бота',
    kartochki2.length === 1 && /Test Servis/.test(kartochki2[0].textContent),
    kartochki2.length ? kartochki2[0].textContent.slice(0, 60) : 'пусто');

  /* ── 7. Память о человеке ──────────────────────────────────────── */

  // Запись: расчёт обязан отложить сумму человека.
  proverka('сумма записана в память', w.localStorage.getItem('summa') === '100000',
    'в памяти: ' + w.localStorage.getItem('summa'));

  // Чтение: следующий визит начинается с его суммы, а не с нашей.
  const w3 = podnyat(null, { summa: '100000', intro_pokazan: '1' });
  await dozhdatsya();
  proverka('сумма возвращается при следующем заходе',
    w3.document.getElementById('summa').value === '100000',
    'значение: ' + w3.document.getElementById('summa').value);
  proverka('вердикт сразу в его деньгах, без единого нажатия',
    /\d{3}/.test(tekst(w3, 'vOnSum')), tekst(w3, 'vOnSum'));
  proverka('объяснение не повторяется тому, кто его закрыл',
    !vidno(w3, 'intro'));

  /* ── Канал приходит от бота ──────────────────────────────────────
   *
   * Адрес канала едет в ответе /api/rates. Иначе после создания канала
   * пришлось бы править data.js, поднимать версию скриптов и заливать
   * заново — три шага, из которых забудут хотя бы один, и ссылки не
   * будет вообще.
   */

  const otvetSKanalom = Object.assign({}, otvetBota, {
    channel: 'https://t.me/rublkursi',
  });
  const wk = podnyat(otvetSKanalom, { intro_pokazan: '1' });
  await dozhdatsya();

  const ssylkaOtBota = wk.document.getElementById('chLink');
  proverka('ссылка на канал появилась из ответа бота',
    !!ssylkaOtBota && !ssylkaOtBota.classList.contains('hidden'),
    'задать CHANNEL_ID на Render должно быть достаточно');
  proverka('адрес канала взят из ответа',
    ssylkaOtBota && ssylkaOtBota.getAttribute('href') === 'https://t.me/rublkursi',
    ssylkaOtBota ? ssylkaOtBota.getAttribute('href') : 'нет');

  // Обработчик вешается один раз. Иначе на одно нажатие уходило бы два
  // события, и переходы в канал считались бы вдвое — искажение, которое
  // не видно ничем, кроме удивления через месяц.
  let klikovPoKanalu = 0;
  const bylOtpravitel = wk.navigator.sendBeacon;
  wk.navigator.sendBeacon = function (adres, telo) {
    if (String(telo) .indexOf('kanal_klik') !== -1) klikovPoKanalu++;
    return true;
  };
  // Blob в jsdom не отдаёт содержимое строкой — подменяем на прозрачную
  // обёртку, как в проверке учёта выше.
  wk.Blob = function (chasti) {
    return { toString: function () { return chasti.join(''); } };
  };
  ssylkaOtBota.click();
  await dozhdatsya();
  proverka('переход в канал считается один раз', klikovPoKanalu === 1,
    'засчитано: ' + klikovPoKanalu);
  wk.navigator.sendBeacon = bylOtpravitel;

  // Вписанное руками имеет приоритет: увести людей на другой канал должно
  // быть можно и без бота.
  const wkRuchnoy = podnyat(otvetSKanalom, { intro_pokazan: '1' });
  wkRuchnoy.eval("window.CHANNEL_LINK = 'https://t.me/svoy_kanal';"
    + fs.readFileSync(path.join(KORNI, 'app.js'), 'utf8'));
  await dozhdatsya();
  proverka('вписанный руками канал не затирается ботом',
    wkRuchnoy.document.getElementById('chLink').getAttribute('href')
      === 'https://t.me/svoy_kanal',
    wkRuchnoy.document.getElementById('chLink').getAttribute('href'));

  /* ── Страница под поиск: kurs.html ───────────────────────────────
   *
   * Её никто не открывает — и именно поэтому она сломается молча.
   * Числа там переписывает bot/obnovit_zapas.py по меткам data-zapas:
   * стоит переименовать метку, и страница застынет с числами
   * полугодовой давности, продолжая выглядеть исправной.
   */

  const kursHtml = fs.readFileSync(path.join(KORNI, 'kurs.html'), 'utf8');
  const kursDom = new JSDOM(kursHtml, {
    url: 'https://m1llerzz.github.io/KURS-/kurs.html',
  });
  const kd = kursDom.window.document;

  proverka('страница поиска парсится', !!kd.querySelector('h1'));
  proverka('заголовок отвечает на запрос про курс',
    /курс рубля/i.test(kd.querySelector('title').textContent),
    kd.querySelector('title').textContent);
  proverka('описание для выдачи на месте',
    !!kd.querySelector('meta[name="description"]'));
  proverka('канонический адрес указан',
    !!kd.querySelector('link[rel="canonical"]'));

  /* Дорога поисковика до страницы под поиск.
   *
   * robots.txt читается роботами только из корня домена, а наш лежит в
   * папке проекта — значит директива Sitemap оттуда не работает вовсе.
   * Пока Search Console не подана, единственный путь на kurs.html — это
   * ссылка с корня. Без неё страница написана в пустоту. */
  const indexHtml = fs.readFileSync(path.join(KORNI, 'index.html'), 'utf8');
  const indexDom = new JSDOM(indexHtml);
  const naKurs = indexDom.window.document.querySelector('a[href="kurs.html"]');
  proverka('с приложения есть ссылка на страницу поиска', !!naKurs,
    'иначе робот дойдёт до kurs.html только через sitemap, о котором ему никто не сказал');
  if (naKurs) {
    /* Слова в ссылке — это то, по каким запросам страницу находят. Пустая
     * ссылка или «читать далее» не значат для поисковика ничего, и текст
     * обязан лежать в разметке: подставленный скриптом робот не увидит. */
    const slova = naKurs.textContent.trim();
    proverka('в ссылке есть слова, а не пустота', slova.length > 10, slova);
    proverka('ссылка названа обоими языками',
      /kurs/i.test(slova) && /курс/i.test(slova), slova);
  }

  /* Карта сайта: дата обязана совпадать с датой курса на странице.
   *
   * lastmod — единственная отметка, по которой поисковик решает, стоит ли
   * заходить снова; changefreq он считает пожеланием. Дата, обогнавшая
   * числа на странице, — это обещание свежести, которого страница не
   * выполняет, а отставшая означает, что робот не придёт за новыми. */
  const sitemap = fs.readFileSync(path.join(KORNI, 'sitemap.xml'), 'utf8');
  const datyKarty = (sitemap.match(/<lastmod>([^<]+)<\/lastmod>/g) || [])
    .map(function (s) { return s.replace(/<\/?lastmod>/g, ''); });
  proverka('в карте сайта есть даты обновления', datyKarty.length > 0,
    'без lastmod страницу переобходят раз в несколько недель');
  proverka('все адреса карты помечены датой',
    datyKarty.length === (sitemap.match(/<loc>/g) || []).length,
    datyKarty.length + ' дат на ' + (sitemap.match(/<loc>/g) || []).length + ' адресов');

  const dataNaStranice = kd.querySelector('[data-zapas="data_ru"]');
  if (dataNaStranice && datyKarty.length) {
    /* «14 августа 2026» -> «2026-08-14». Сверяем по-настоящему: карта и
     * страница обновляются одним скриптом, и разойтись они могут только
     * если кто-то правил одно из двух руками. */
    const MES = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля',
                 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
    const kuski = dataNaStranice.textContent.trim().split(/\s+/);
    const nomer = MES.indexOf(kuski[1]) + 1;
    const iso = kuski.length === 3 && nomer
      ? kuski[2] + '-' + String(nomer).padStart(2, '0')
        + '-' + String(parseInt(kuski[0], 10)).padStart(2, '0')
      : null;
    proverka('дата на странице разбирается', !!iso,
      dataNaStranice.textContent);
    if (iso) {
      proverka('дата карты сайта совпадает с датой курса',
        datyKarty.every(function (d) { return d === iso; }),
        datyKarty.join(', ') + ' против ' + iso);
    }
  }

  /* Картинка карточки. Ссылка на приложение уходит в каждой пересылке, а
   * пересылка — единственный бесплатный источник роста, который у нас
   * есть. Карточка без картинки выглядит в чате бледной строкой, и её
   * пролистывают, не прочитав. */
  ['index.html', 'kurs.html'].forEach(function (imya) {
    const dom = new JSDOM(fs.readFileSync(path.join(KORNI, imya), 'utf8'));
    const kartinka = dom.window.document.querySelector('meta[property="og:image"]');
    proverka('у ' + imya + ' есть картинка карточки', !!kartinka,
      'без неё ссылка в чате читается как обычный текст');
    if (kartinka) {
      const adres = kartinka.getAttribute('content');
      proverka('адрес картинки ' + imya + ' абсолютный',
        /^https:\/\//.test(adres), adres + ' — относительный адрес соцсети не примут');
      // Версию из адреса отбрасываем: на диске файл лежит без неё.
      const imyaFayla = adres.split('/').pop().split('?')[0];
      proverka('картинка карточки ' + imya + ' лежит на месте',
        fs.existsSync(path.join(KORNI, imyaFayla)),
        adres + ' — файла нет, карточка будет пустой');

      /* Версия в адресе обязательна. Telegram и соцсети кешируют превью
       * по АДРЕСУ и держат его неделями: пересобранная обложка с новым
       * числом просто не доедет, в чатах останется висеть прошлое. */
      proverka('у картинки карточки ' + imya + ' есть версия',
        /\?v=\d{8}/.test(adres),
        adres + ' — без версии Telegram будет показывать старое число');
    }
  });

  // Оба языка обязательны — это решение проекта, и страница поиска
  // ловит запросы обоих: «курс рубля к суму» и «rubl kursi bugun».
  proverka('на странице оба языка',
    !!kd.querySelector('section[lang="ru"]') && !!kd.querySelector('section[lang="uz"]'),
    'узбекский первый по важности, русский обязателен');

  // Метки должны совпадать с теми, что подставляет обновлятор. Список
  // здесь продублирован намеренно: он и есть договор между страницей и
  // скриптом, и расхождение обязано быть красным, а не тихим.
  const METKI = ['kurs', 'data_ru', 'data_uz', 'kurs_min', 'kurs_max',
                 'razmah_percent', 'razmah_sum', 'period_ru', 'period_uz',
                 'kurs_servisa', 'nacenka_percent', 'nacenka_sum', 'itog_50k'];
  METKI.forEach(function (m) {
    proverka('метка ' + m + ' есть на странице',
      !!kd.querySelector('[data-zapas="' + m + '"]'),
      'обновлятор её подставляет, а подставлять некуда');
  });

  const obnovlyator = fs.readFileSync(
    path.join(KORNI, 'bot', 'obnovit_zapas.py'), 'utf8');
  const metkiNaStranice = Array.from(kd.querySelectorAll('[data-zapas]'))
    .map(function (el) { return el.getAttribute('data-zapas'); });
  proverka('обновлятор знает все метки страницы',
    metkiNaStranice.every(function (m) {
      return obnovlyator.indexOf('"' + m + '"') !== -1;
    }),
    'метка есть на странице, но её никто не обновляет: ' +
      metkiNaStranice.filter(function (m) {
        return obnovlyator.indexOf('"' + m + '"') === -1;
      }).join(', '));

  // Ни одного пустого места: страница читается поисковиком как есть,
  // без выполнения скриптов, и пустой span стал бы дырой в тексте.
  proverka('все числа заполнены',
    Array.from(kd.querySelectorAll('[data-zapas]')).every(function (el) {
      return el.textContent.trim().length > 0;
    }));

  proverka('вместо чисел нигде не стоит прочерк',
    Array.from(kd.querySelectorAll('[data-zapas]')).every(function (el) {
      return el.textContent.trim() !== '—';
    }),
    'прочерк на странице поиска — это дыра в тексте, который читает робот');

  // Числа обязаны сходиться между собой: человек проверит на
  // калькуляторе, и разошедшаяся строка стоит дороже, чем кажется.
  function chisloSoStranicy(metka) {
    const el = kd.querySelector('[data-zapas="' + metka + '"]');
    if (!el) return NaN;
    return parseFloat(el.textContent.replace(/\s/g, '').replace(',', '.'));
  }

  const kursCB = chisloSoStranicy('kurs');
  const kursServisa = chisloSoStranicy('kurs_servisa');
  const nacenka = chisloSoStranicy('nacenka_percent');
  proverka('наценка сходится с курсами на странице',
    Math.abs((kursCB - kursServisa) / kursCB * 100 - nacenka) < 0.05,
    kursCB + ' и ' + kursServisa + ' дают не ' + nacenka + '%');

  const nacenkaSum = chisloSoStranicy('nacenka_sum');
  proverka('наценка в сумах сходится с курсами',
    Math.abs((kursCB - kursServisa) * 50000 - nacenkaSum) < 100,
    'на 50 000 ₽ это ' + Math.round((kursCB - kursServisa) * 50000) +
      ', а написано ' + nacenkaSum);

  const kursMin = chisloSoStranicy('kurs_min');
  const kursMax = chisloSoStranicy('kurs_max');
  proverka('размах в сумах сходится с коридором месяца',
    Math.abs((kursMax - kursMin) * 50000 - chisloSoStranicy('razmah_sum')) < 100,
    'коридор ' + kursMin + '–' + kursMax);
  proverka('размах в процентах сходится с коридором',
    Math.abs((kursMax - kursMin) / kursMin * 100 - chisloSoStranicy('razmah_percent')) < 0.05);
  proverka('минимум месяца не больше максимума', kursMin <= kursMax);
  proverka('курс перевода ниже официального', kursServisa < kursCB,
    'иначе наценка отрицательная, и весь смысл строки теряется');

  // Разметка для поисковика. Расхождение с видимым текстом Google
  // считает обманом и понижает страницу целиком.
  const ldEl = kd.querySelector('script[type="application/ld+json"]');
  proverka('разметка вопрос-ответ есть', !!ldEl);
  let ld = null;
  try { ld = JSON.parse(ldEl.textContent); } catch (e) { ld = null; }
  proverka('разметка вопрос-ответ разбирается', !!ld,
    'сломанный JSON-LD поисковик просто выбрасывает');
  if (ld) {
    proverka('разметка объявлена как FAQPage', ld['@type'] === 'FAQPage');
    const vidimyy = kd.body.textContent.replace(/\s+/g, ' ');
    proverka('каждый вопрос из разметки виден на странице',
      (ld.mainEntity || []).every(function (v) {
        return vidimyy.indexOf(v.name) !== -1;
      }),
      'разметка с невидимыми вопросами считается обманом');
    proverka('в разметке нет курса, который меняется',
      !(ld.mainEntity || []).some(function (v) {
        return /\d{3},\d{2}/.test(v.acceptedAnswer.text);
      }),
      'обновлятор до разметки не дотягивается, и такое число протухнет');
  }

  // Метка источника: без неё непонятно, приводит ли поиск людей вообще.
  const ssylki = Array.from(kd.querySelectorAll('a[href*="t.me"]'));
  proverka('на странице есть ссылка в приложение', ssylki.length > 0);
  proverka('все ссылки в приложение помечены источником',
    ssylki.every(function (a) { return /startapp=poisk/.test(a.href); }),
    'иначе переходы из поиска сольются с остальными и посчитать их нечем');

  // Блок канала спрятан, пока канала нет: пустая ссылка на странице,
  // которую читает поисковик, — это битая ссылка в его глазах.
  const kanalBlok = kd.getElementById('kanalBlok');
  proverka('блок канала на странице есть', !!kanalBlok);
  proverka('блок канала спрятан, пока канала нет',
    kanalBlok && kanalBlok.hasAttribute('hidden'),
    'ссылка на # в выдаче читается как поломка');

  /* ── Второй слой курса: ЦБ напрямую, без бота ──────────────────
   *
   * Бот один, и он уже приостанавливался на неделю: приложение осталось
   * с запасом в файле и погасло, когда запасу стало больше трёх суток.
   * Теперь официальный курс приложение спрашивает у ЦБ само. Проверяем
   * не «функция вернула объект», а то, ради чего слой написан: человек
   * при молчащем боте видит СЕГОДНЯШНИЙ курс и вердикт по нему.
   */

  function otvetCBna(data, kursRub) {
    return [
      { Ccy: 'USD', Rate: '11801.23', Nominal: '1', Date: data },
      { Ccy: 'RUB', Rate: String(kursRub), Nominal: '1', Date: data },
    ];
  }

  // Дата берётся от сегодняшнего дня, а не пишется числом: проверка,
  // прибитая к календарю, краснеет сама собой через сутки.
  const segodnyaUZ = new Date(Date.now() + 5 * 3600000).toISOString().slice(0, 10);
  const segodnyaRu = segodnyaUZ.slice(8, 10).replace(/^0/, '')
    + '.' + segodnyaUZ.slice(5, 7) + '.' + segodnyaUZ.slice(0, 4);

  // Курс заведомо отличный от запаса: иначе не видно, чей он на экране.
  const KURS_CB = 149.55;

  const wCB = podnyat(null, { intro_pokazan: '1' }, null,
    otvetCBna(segodnyaRu, KURS_CB));
  await dozhdatsya();

  proverka('при молчащем боте курс приезжает прямо из ЦБ',
    tekst(wCB, 'vRate').indexOf('149,55') !== -1,
    tekst(wCB, 'vRate') + ' — ждали 149,55');
  /* Ждали не «какой-нибудь вердикт», а тот, который даёт ряд СО СВЕЖЕЙ
     точкой. Считаем ожидаемое из тех же данных, а не пишем числом:
     запас пересобирается, и записанное число покраснеет само собой. */
  const ozhidaemo = wCB.CALC.sovet(
    wCB.HISTORY_ZAPAS.concat([{ date: segodnyaUZ, rub_uzs: KURS_CB }]));
  proverka('среднее месяца посчитано по ряду со свежей точкой',
    tekst(wCB, 'vAvg').indexOf(String(ozhidaemo.srednee_30).replace('.', ',')) !== -1,
    tekst(wCB, 'vAvg') + ' — ждали ' + ozhidaemo.srednee_30);
  proverka('отклонение на значке — от свежего курса',
    tekst(wCB, 'vBadge').indexOf(
      Math.abs(ozhidaemo.otklonenie_percent).toFixed(1).replace('.', ',')) !== -1,
    tekst(wCB, 'vBadge') + ' — ждали ' + ozhidaemo.otklonenie_percent);

  // Дату показываем ту, которой ЦБ подписал курс. Число без даты в этом
  // продукте не показывается вовсе, а чужая дата хуже отсутствия даты.
  wCB.document.getElementById('summa').value = '50000';
  wCB.document.getElementById('schitat').click();
  await dozhdatsya();
  proverka('дата курса на экране — дата публикации ЦБ',
    !/\d{4}-\d{2}-\d{2}|\d{2}\.\d{2}\.\d{4}/.test(tekst(wCB, 'kursDate'))
      && tekst(wCB, 'kursDate').length > 0,
    tekst(wCB, 'kursDate'));
  proverka('при живом ЦБ приложение не жалуется на связь',
    tekst(wCB, 'kursDate').toLowerCase().indexOf('связ') === -1,
    tekst(wCB, 'kursDate'));

  /* Старый курс из ЦБ не откатывает свежий от бота.
   *
   * Страховка, которая иногда делает хуже, — это не страховка. Бот отдаёт
   * снимок с курсом за сегодня, ЦБ по какой-то причине отвечает позавчерашним
   * (кеш на их стороне, запрос не за тот день) — на экране обязан остаться
   * сегодняшний. */
  const vchera = new Date(Date.now() + 5 * 3600000 - 2 * 86400000)
    .toISOString().slice(0, 10);
  const otBota = {
    cbu: { usd_uzs: 11801.23, rub_uzs: 138.88, date: segodnyaUZ },
    services: [{ id: 'a', name: 'Способ А', route: 'A', corridors: ['RU-UZ'],
      fee_fixed: 0, fee_percent: 0, rate_rub_uzs: 135, limit_per_operation: 200000,
      delivery_minutes: 60, incoming_fee: 0, checked_at: new Date().toISOString() }],
    banks: [],
    history: w.HISTORY_ZAPAS.concat([{ date: segodnyaUZ, rub_uzs: 138.88 }]),
  };
  const wStaryiCB = podnyat(otBota, { intro_pokazan: '1' }, null,
    otvetCBna('01.07.2026', 111.11));
  await dozhdatsya();
  proverka('старый курс из ЦБ не откатывает свежий от бота',
    tekst(wStaryiCB, 'vRate').indexOf('111,11') === -1
      && tekst(wStaryiCB, 'vRate').indexOf('138,88') !== -1,
    tekst(wStaryiCB, 'vRate'));

  /* Откат виден не только в вердикте.
   *
   * Вердикт считается по РЯДУ, и точку в ряд старая дата не добавит в
   * любом случае — то есть проверка выше на снятой защите оставалась бы
   * зелёной. А курс, по которому считаются деньги, и дата под ним живут
   * отдельно: вот там откат и был бы виден человеку. Поэтому смотрим на
   * дату курса — июльскую в этом наборе видеть не должны. */
  wStaryiCB.document.getElementById('summa').value = '50000';
  wStaryiCB.document.getElementById('schitat').click();
  await dozhdatsya();
  proverka('дата курса не откатывается на старую',
    !/июл|iyul/i.test(tekst(wStaryiCB, 'kursDate')),
    tekst(wStaryiCB, 'kursDate'));

  // Дата из будущего — признак сломавшегося источника, а не свежести.
  const zavtra = new Date(Date.now() + 5 * 3600000 + 3 * 86400000)
    .toISOString().slice(0, 10);
  const zavtraRu = zavtra.slice(8, 10) + '.' + zavtra.slice(5, 7) + '.' + zavtra.slice(0, 4);
  const wBudushchee = podnyat(null, { intro_pokazan: '1' }, null,
    otvetCBna(zavtraRu, 199.99));
  await dozhdatsya();
  proverka('курс с датой из будущего на экран не попадает',
    tekst(wBudushchee, 'vRate').indexOf('199,99') === -1,
    tekst(wBudushchee, 'vRate'));

  // Молчащий ЦБ не должен ломать то, что работало без него.
  const wBezCB = podnyat(null, { intro_pokazan: '1' });
  await dozhdatsya();
  proverka('молчащий ЦБ не роняет приложение',
    vidno(wBezCB, 'verdict') && tekst(wBezCB, 'vRate').length > 0,
    tekst(wBezCB, 'vRate'));

  /* ── Браузера без fetch тоже хватает ───────────────────────────
   *
   * В старом webview `fetch` отсутствует целиком, и обращение к нему
   * бросает исключение, а не отказывает промисом. Загрузка падала бы
   * вместе с ним — и человек видел бы пустой экран вместо запаса,
   * который лежит рядом и работает вообще без сети. Ровно ради этого
   * случая запас в файле и существует.
   */
  /* Поднимаем в try: без защиты приложение бросает исключение прямо на
     старте, и весь прогон умирает вместе с ним — красное без имени и без
     остальных проверок. Пойманное исключение краснеет одной строкой и
     называет причину. */
  let wBezSeti = null;
  let upalNaStarte = '';
  try {
    wBezSeti = podnyat(null, { intro_pokazan: '1' }, null, null, true);
  } catch (e) {
    upalNaStarte = String(e && e.message).slice(0, 120);
  }
  proverka('без fetch приложение вообще поднимается', !!wBezSeti,
    upalNaStarte || 'исключение на старте');
  if (wBezSeti) await dozhdatsya();

  proverka('без fetch вердикт всё равно на экране',
    !!wBezSeti && vidno(wBezSeti, 'verdict') && tekst(wBezSeti, 'vRate').length > 0,
    wBezSeti ? tekst(wBezSeti, 'vRate') : 'приложение не поднялось');

  if (wBezSeti) {
    wBezSeti.document.getElementById('summa').value = '50000';
    wBezSeti.document.getElementById('schitat').click();
    await dozhdatsya();
  }
  proverka('без fetch расчёт по запасу считается',
    !!wBezSeti && (wBezSeti.document.querySelectorAll('#results .card').length > 0
      || tekst(wBezSeti, 'results').length > 0),
    'пустой экран вместо запаса — худшее, что можно показать');

  /* ── Браузер с запрещёнными данными сайта ──────────────────────
   *
   * Обращение к localStorage там бросает исключение, а не возвращает
   * пусто. Приложение обязано пережить это молча: запас лежит в файле и
   * работает вообще без хранилища.
   */
  let wBezPamyati = null;
  let upalBezPamyati = '';
  try {
    // Бот молчит, хранилище запрещено, ЦБ отвечает: именно здесь видно,
    // доезжает ли свежий курс. Оборванная цепочка загрузки не дошла бы до
    // второго слоя, и на экране остался бы курс из запаса.
    wBezPamyati = podnyat(null, null, null,
      otvetCBna(segodnyaRu, KURS_CB), false, true);
  } catch (e) {
    upalBezPamyati = String(e && e.message).slice(0, 120);
  }
  proverka('без хранилища приложение поднимается', !!wBezPamyati,
    upalBezPamyati || 'исключение на старте');
  if (wBezPamyati) await dozhdatsya();
  if (wBezPamyati) {
    wBezPamyati.document.getElementById('summa').value = '50000';
    wBezPamyati.document.getElementById('schitat').click();
    await dozhdatsya();
  }
  proverka('без хранилища вердикт на экране',
    !!wBezPamyati && vidno(wBezPamyati, 'verdict')
      && tekst(wBezPamyati, 'vRate').length > 0,
    wBezPamyati ? tekst(wBezPamyati, 'vRate') : 'приложение не поднялось');
  proverka('без хранилища расчёт считается',
    !!wBezPamyati
      && wBezPamyati.document.querySelectorAll('#results .card').length > 0,
    'запас лежит в файле и от хранилища не зависит');
  proverka('без хранилища свежий курс ЦБ всё равно доезжает',
    !!wBezPamyati && tekst(wBezPamyati, 'vRate').indexOf('149,55') !== -1,
    wBezPamyati ? tekst(wBezPamyati, 'vRate') : 'приложение не поднялось');


  //
  // Считаем за весь прогон: все сценарии выше, включая мёртвую сеть,
  // протухшие данные, пустые поля и переходы по меткам. Ошибка в
  // скрипте не обязана ронять экран целиком — чаще она тихо ломает одну
  // ветку, и человек видит пустое место там, где должно быть число.

  proverka('за весь прогон ни одной ошибки в консоли',
    oshibkiKonsoli.length === 0,
    oshibkiKonsoli.slice(0, 3).join(' | '));

  /* ── Итог ──────────────────────────────────────────────────────── */

  console.log('Пройдено: ' + proshlo.length);
  proshlo.forEach(function (p) { console.log('  + ' + p); });

  if (upalo.length) {
    console.log('\nПРОВАЛЕНО: ' + upalo.length);
    upalo.forEach(function (p) { console.log('  - ' + p); });
    process.exit(1);
  }
  console.log('\nВсе проверки зелёные.');
})();
