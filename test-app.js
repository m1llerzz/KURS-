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

let JSDOM;
try {
  JSDOM = require('jsdom').JSDOM;
} catch (e) {
  console.log('jsdom не установлен. Поставь его: npm install jsdom');
  console.log('Проверки НЕ выполнены.');
  process.exit(2);
}

const KORNI = __dirname;
const proshlo = [];
const upalo = [];

function proverka(imya, uslovie, podskazka) {
  if (uslovie) proshlo.push(imya);
  else upalo.push(imya + (podskazka ? '  << ' + podskazka : ''));
}

/**
 * Поднимает приложение с нуля. otvet — что «вернёт бот», null — сбой сети.
 * pamyat — что лежит в localStorage ДО запуска: у каждого окна jsdom своё
 * хранилище, и без этого прошлый визит человека не воспроизвести.
 */
function podnyat(otvet, pamyat) {
  const html = fs.readFileSync(path.join(KORNI, 'index.html'), 'utf8')
    // Внешний скрипт Telegram в проверке не нужен и тянуть его неоткуда.
    .replace(/<script src="https:\/\/telegram[^<]*<\/script>/, '');

  // runScripts обязателен: без него window.eval выполняет код в пустом
  // окружении, где нет даже window, и все четыре файла падают на первой
  // строке. 'outside-only' даёт нам eval, но не запускает скрипты из html —
  // мы грузим их сами, по одному, в нужном порядке.
  const dom = new JSDOM(html, {
    url: 'https://m1llerzz.github.io/KURS-/',
    runScripts: 'outside-only',
  });
  const w = dom.window;

  // Настоящего Telegram здесь нет: приложение обязано работать и в браузере.
  w.fetch = function () {
    return otvet
      ? Promise.resolve({ json: function () { return Promise.resolve(otvet); } })
      : Promise.reject(new Error('сети нет'));
  };

  Object.keys(pamyat || {}).forEach(function (k) {
    w.localStorage.setItem(k, pamyat[k]);
  });

  ['i18n.js', 'data.js', 'calc.js', 'app.js'].forEach(function (f) {
    w.eval(fs.readFileSync(path.join(KORNI, f), 'utf8'));
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
  proverka('в вердикте есть курс', /141[.,]76/.test(tekst(w, 'vRate')),
    tekst(w, 'vRate'));
  proverka('в вердикте есть среднее', /1\d\d[.,]\d\d/.test(tekst(w, 'vAvg')),
    tekst(w, 'vAvg'));
  proverka('вердикт помечен как плохой день',
    w.document.getElementById('verdict').classList.contains('bad'),
    'курс 141,76 против среднего 149,83 — это ниже обычного');

  const grafik = w.document.getElementById('vSpark');
  const liniya = grafik.querySelector('polyline');
  proverka('график нарисован', !!liniya);
  proverka('в графике 30 точек',
    liniya && liniya.getAttribute('points').trim().split(/\s+/).length === 30,
    liniya ? String(liniya.getAttribute('points').trim().split(/\s+/).length) : 'нет');
  proverka('в графике есть линия среднего', !!grafik.querySelector('line.av'),
    'без якоря человек не понимает, много это или мало');
  proverka('на графике отмечен сегодняшний день', !!grafik.querySelector('circle.dt'));

  proverka('разница показана в сумах', /\d/.test(tekst(w, 'vOnSum')), tekst(w, 'vOnSum'));
  proverka('на 50 000 ₽ разница около 400 тысяч',
    /40[0-9]\s?\d{3}/.test(tekst(w, 'vOnSum')), tekst(w, 'vOnSum'));
  proverka('есть совет подождать', tekst(w, 'vHint').length > 5, tekst(w, 'vHint'));

  proverka('банк спрятан, пока курсов банков нет', !vidno(w, 'bankBlock'),
    'пустой список в выпадашке обещает данные, которых нет');

  /* ── 1a. Словари двух языков ───────────────────────────────────── */

  // Ключи правятся руками в двух местах файла, и забытый перевод виден
  // не сразу: t() тихо подставляет русскую строку. Для узбека, который
  // и есть основная аудитория, это выглядит поломкой.
  const KLYUCHI = [
    'v.otlichno', 'v.horosho', 'v.obychno', 'v.nize_obychnogo', 'v.ploho',
    'v.rate', 'v.avg', 'v.pos', 'v.pos.worst', 'v.pos.best',
    'v.trend.rastet', 'v.trend.padaet', 'v.trend.stoit',
    'v.onsum.plus', 'v.onsum.minus', 'v.onsum.zero',
    'v.hint.good', 'v.hint.bad', 'v.hint.normal', 'v.range', 'v.days',
    'svc.markup', 'svc.fee_unknown', 'svc.official', 'svc.lost',
    'sub.t', 'sub.p', 'sub.btn', 'popup.go', 'err.net',
  ];

  const zabytye = [];
  const odinakovye = [];
  KLYUCHI.forEach(function (k) {
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
  proverka('в карточке видна наценка сервиса',
    kartochki.length > 0 && /4[.,]1|4[.,]0/.test(kartochki[0].textContent),
    'курс сервиса ниже официального на 4% — это второй рычаг после дня');
  proverka('в карточке оговорка про комиссию',
    kartochki.length > 0 && kartochki[0].textContent.length > 30);

  proverka('кнопка пересылки появилась', vidno(w, 'share'));
  proverka('подписка предложена после пользы', vidno(w, 'subCta'),
    'сначала цифра, потом просьба писать');
  proverka('дисклеймер показан', vidno(w, 'disclaimer'));
  proverka('нет пометки о тестовых данных',
    !/ТЕСТ|TEST/i.test(tekst(w, 'disclaimer')),
    'данные настоящие, пометка врала бы');
  proverka('три шага спрятались после расчёта', !vidno(w, 'idle'));

  proverka('плашка потери показана', vidno(w, 'loss'),
    'курсы сервисов совпали, но потеря к официальному курсу осталась');
  proverka('в плашке есть число', /\d{3}/.test(tekst(w, 'lossNum')), tekst(w, 'lossNum'));

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

  vvesti(100000);
  proverka('верная сумма — ошибки нет', !vidno(w, 'summaErr'), tekst(w, 'summaErr'));
  proverka('разница пересчиталась на новую сумму',
    /8\d\d\s?\d{3}|80[0-9]\s?\d{3}/.test(tekst(w, 'vOnSum')), tekst(w, 'vOnSum'));

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
  proverka('в пересылке нет чужих сумов',
    !!ushlo && !/\d{1,2}\s\d{3}\s\d{3}\s*(сум|so)/i.test(ushlo),
    'у читателя другая сумма, чужой итог ему бесполезен');

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
