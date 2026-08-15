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
    vHint:      document.getElementById('vHint'),
    subCta:     document.getElementById('subCta'),
    subBtn:     document.getElementById('subBtn'),
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

    const telo = JSON.stringify({ tip: tip, chat_id: chatId, dannye: dannye || null });

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

  function primenit(d) {
    if (d.services && d.services.length) SERVISY = d.services;
    if (d.banks) BANKI = d.banks;
    if (d.history && d.history.length) ISTORIYA = d.history;
    if (d.cbu) {
      posledniyKurs = {
        usd_uzs: d.cbu.usd_uzs,
        rub_uzs: d.cbu.rub_uzs,
        date: d.cbu.date,
      };
    }
  }

  function zagruzitDannye() {
    const kesh = izKesha();
    if (kesh) { primenit(kesh); return Promise.resolve(kesh); }

    if (!window.API_URL) return Promise.resolve(zapasnoy());

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

  /** Рисует настоящий ряд курсов ЦБ за месяц. */
  function narisovatGrafik(ryad) {
    if (!el.vSpark || !ryad || ryad.length < 2) return;

    const W = 300, H = 54, otstup = 5;
    const znacheniya = ryad.map(function (x) { return x.rub_uzs; });
    const mn = Math.min.apply(null, znacheniya);
    const mx = Math.max.apply(null, znacheniya);
    // Ровный курс дал бы деление на ноль и линию за краем поля.
    const razmah = (mx - mn) || 1;

    function X(i) { return (i / (ryad.length - 1)) * W; }
    function Y(v) { return H - otstup - ((v - mn) / razmah) * (H - otstup * 2); }

    const tochki = znacheniya.map(function (v, i) {
      return X(i).toFixed(1) + ',' + Y(v).toFixed(1);
    });

    const srednee = znacheniya.reduce(function (a, b) { return a + b; }, 0) / znacheniya.length;
    const ySred = Y(srednee).toFixed(1);

    const posledniy = znacheniya.length - 1;
    const cx = X(posledniy).toFixed(1);
    const cy = Y(znacheniya[posledniy]).toFixed(1);

    el.vSpark.innerHTML =
      // Заливка градиентом, а не плоским цветом: плоская заливка под
      // линией спорит с ней за внимание, растворяющаяся — не спорит.
      '<defs><linearGradient id="zaliv" x1="0" y1="0" x2="0" y2="1">' +
      '<stop offset="0%" stop-color="currentColor" stop-opacity=".28"/>' +
      '<stop offset="100%" stop-color="currentColor" stop-opacity="0"/>' +
      '</linearGradient></defs>' +
      '<polygon class="ar" points="0,' + H + ' ' + tochki.join(' ') + ' ' + W + ',' + H + '"/>' +
      // Пунктир среднего — это якорь. Без него линия просто «какая-то»,
      // с ним человек мгновенно видит, выше он сегодня обычного или ниже.
      '<line class="av" x1="0" y1="' + ySred + '" x2="' + W + '" y2="' + ySred + '"/>' +
      '<polyline class="ln" points="' + tochki.join(' ') + '"/>' +
      '<circle class="dtg" cx="' + cx + '" cy="' + cy + '" r="7"/>' +
      '<circle class="dt" cx="' + cx + '" cy="' + cy + '" r="3.4"/>';
  }

  function pokazatVerdikt() {
    ocenkaDnya = window.CALC.sovet(ISTORIYA);

    if (!ocenkaDnya) {
      // Меньше недели данных — вердикта нет. Молчим, а не гадаем.
      el.verdict.classList.add('hidden');
      return;
    }

    const o = ocenkaDnya;
    const horosho = o.verdikt === 'otlichno' || o.verdikt === 'horosho';
    const ploho = o.verdikt === 'ploho' || o.verdikt === 'nize_obychnogo';

    el.verdict.classList.remove('hidden', 'good', 'bad');
    if (horosho) el.verdict.classList.add('good');
    else if (ploho) el.verdict.classList.add('bad');

    el.vHead.textContent = t('v.' + o.verdikt);
    el.vRate.textContent = t('v.rate', { r: o.segodnya.toFixed(2) });
    el.vAvg.textContent = t('v.avg', { r: o.srednee_30.toFixed(2) });

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
    if (el.vOsL) el.vOsL.textContent = o.min_30.toFixed(2);
    if (el.vOsR) el.vOsR.textContent = o.max_30.toFixed(2) + ' · ' + t('v.days');

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
    if (o.trend) chasti.push(t('v.trend.' + o.trend));
    chasti.push(t('v.range', { mn: o.min_30.toFixed(2), mx: o.max_30.toFixed(2) }));
    el.vMeta.textContent = chasti.join(' · ');

    obnovitVygodu();

    // Совет берём из deystvie, а не из вердикта: вердикт говорит, каков
    // курс, а совет — что делать, и это разные вещи. В падающем рынке
    // курс ниже обычного, но ждать нельзя: завтра будет ещё меньше.
    el.vHint.textContent = t('v.do.' + (o.deystvie || 'obychno'));
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
      return;
    }

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

      const metki = [];
      if (i === 0) metki.push('<span class="tag best">' + t('tag.best') + '</span>');
      else if (r.svezhest === 'ustarelo') metki.push('<span class="tag">' + t('tag.stale') + '</span>');

      const detali = [];
      detali.push(srok(r.delivery_minutes));

      // Наценка курса сервиса к официальному. Это второй по величине
      // рычаг после дня отправки — около 4% — и его тоже не показывает
      // ни один сервис. Считает бот, здесь только выводим.
      const servis = SERVISY.filter(function (s) { return s.id === r.service_id; })[0];
      if (servis && typeof servis.nacenka_percent === 'number'
          && Math.abs(servis.nacenka_percent) >= 0.1) {
        detali.push(t('svc.markup', { p: servis.nacenka_percent.toFixed(1) }));
      }
      // Комиссия не объявлена — говорим прямо, что итог это потолок.
      // Молча выдать верхнюю границу за точную цифру нельзя.
      if (servis && servis.fee_unknown) detali.push(t('svc.fee_unknown'));

      if (r.ocenochnyi) detali.push(t('detail.est'));
      if (r.nacenka_percent !== null && r.dannye_soglasovany && Math.abs(r.nacenka_percent) >= 0.1) {
        detali.push(r.nacenka_percent > 0
          ? t('detail.worse',  { p: r.nacenka_percent.toFixed(1) })
          : t('detail.better', { p: Math.abs(r.nacenka_percent).toFixed(1) }));
      } else if (r.nacenka_percent !== null && !r.dannye_soglasovany) {
        detali.push(t('detail.stale'));
      }
      if (r.vyshe_limita) detali.push(t('detail.limit'));

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
     * Плашка над списком. Когда способов несколько — разница между ними.
     * Когда способ один (а сейчас курсы сервисов совпадают) — показываем
     * то, что действительно есть: сколько съел курс против официального.
     *
     * Раньше при одинаковых курсах плашка просто исчезала, и главная
     * потеря человека оставалась невидимой. Она никуда не делась —
     * её просто не с чем было сравнивать внутри списка.
     */
    const luchshiy = raschet.results[0];
    if (raschet.hidden_loss_uzs > 0) {
      if (el.lossT) el.lossT.textContent = t('loss.t');
      el.lossNum.textContent = sum(raschet.hidden_loss_uzs) + ' ' + t('unit.sum');
      el.lossSub.textContent = t('loss.sub', { sum: sum(el.summa.value) });
      el.loss.classList.remove('hidden');
    } else if (kursy && kursy.rub_uzs && luchshiy) {
      const servis = SERVISY.filter(function (s) { return s.id === luchshiy.service_id; })[0];
      if (servis && servis.rate_rub_uzs) {
        const poOficialnomu = parseFloat(el.summa.value) * kursy.rub_uzs;
        const poteryano = Math.round(poOficialnomu - luchshiy.total_uzs);
        if (poteryano > 0) {
          // Процент рядом с суммой обязателен. Само по себе «288 000 сум»
          // не говорит ничего: много это или мало, человек не знает,
          // пока не соотнесёт с переводом. «4,1%» соотносит мгновенно.
          const dolya = (poteryano / poOficialnomu) * 100;
          // Подпись меняется вместе со смыслом числа. Раньше здесь всегда
          // стояло «Разница между способами», а показывалась потеря на
          // курсе: число под чужой подписью в денежном продукте — это
          // не мелочь, а повод не верить всему остальному.
          if (el.lossT) el.lossT.textContent = t('svc.lost.t');
          el.lossNum.innerHTML = sum(poteryano) + ' ' + t('unit.sum') +
            '<small>' + dolya.toFixed(1).replace('.', ',') + '%</small>';
          el.lossSub.textContent = t('svc.official');
          el.loss.classList.remove('hidden');
        } else {
          el.loss.classList.add('hidden');
        }
      } else {
        el.loss.classList.add('hidden');
      }
    } else {
      el.loss.classList.add('hidden');
    }

    let podpis = t(raschet.disclaimer);
    if (window.TEST_DATA) podpis = t('test') + podpis;
    el.disclaimer.textContent = podpis;
    el.disclaimer.classList.remove('hidden');

    el.kursDate.textContent = dannyeUstareli
      ? t('err.net', { d: dannyeUstareli })
      : (kursy.zapas || !kursy.date)
        ? t('kurs.fail')
        : t('kurs.date', { d: kursy.date });

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
      stroki.push(t('v.rate', { r: ocenkaDnya.segodnya.toFixed(2) }, lang)
        + ' · ' + t('v.avg', { r: ocenkaDnya.srednee_30.toFixed(2) }, lang));
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
    const luchshiy = posledniyRaschet.results[0];
    const bazovyi = luchshiy.vilka ? luchshiy.vilka.ot : luchshiy.total_uzs;

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
    pokazatVerdikt();
    if (posledniyRaschet) poschitat();

    // Учитываем открытие только после того, как узнали вердикт: иначе
    // в цифрах не будет видно, с каким курсом человек к нам пришёл,
    // а это и есть главный вопрос к продукту.
    sobytie('otkryt', {
      verdikt: ocenkaDnya ? ocenkaDnya.verdikt : null,
      // Пришёл ли человек по чужой пересылке. Без этой отметки нельзя
      // посчитать, сколько людей приводит один расчёт, — а это
      // единственный бесплатный источник роста.
      iz_peresylki: /startapp=share|tgWebAppStartParam=share/.test(
        String(window.location.href)) ||
        !!(tg && tg.initDataUnsafe && tg.initDataUnsafe.start_param === 'share'),
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
