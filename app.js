/**
 * ЭКРАН
 *
 * Читает поля, зовёт CALC, рисует результат, отправляет в чат.
 * Здесь НЕТ ни одной формулы. Если понадобилось что-то умножить —
 * значит логика попала не в тот файл, ей место в calc.js.
 */

(function () {

  const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
  if (tg) { tg.ready(); tg.expand(); }

  const el = {
    intro:      document.getElementById('intro'),
    introOk:    document.getElementById('introOk'),
    calcUI:     document.getElementById('calcUI'),
    summa:      document.getElementById('summa'),
    bank:       document.getElementById('bank'),
    schitat:    document.getElementById('schitat'),
    results:    document.getElementById('results'),
    loss:       document.getElementById('loss'),
    lossNum:    document.getElementById('lossNum'),
    lossSub:    document.getElementById('lossSub'),
    share:      document.getElementById('share'),
    disclaimer: document.getElementById('disclaimer'),
    kursDate:   document.getElementById('kursDate'),
  };

  let posledniyRaschet = null;

  /* ── Форматирование ──────────────────────────────────── */

  function sum(n) {
    return Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  }

  function srok(minut) {
    if (minut < 60) return minut + ' мин';
    if (minut < 1440) return Math.round(minut / 60) + ' ч';
    return Math.round(minut / 1440) + ' дн';
  }

  /* ── Курс ЦБ: сеть → кеш на сутки → запасные значения ── */

  function kursIzKesha() {
    try {
      const syroe = localStorage.getItem('kursy');
      if (!syroe) return null;
      const dannye = JSON.parse(syroe);
      const chasov = (Date.now() - dannye.saved_at) / 36e5;
      return chasov <= 24 ? dannye : null;
    } catch (e) { return null; }
  }

  function zagruzitKursy() {
    const kesh = kursIzKesha();
    if (kesh) return Promise.resolve(kesh);

    return fetch('https://cbu.uz/ru/arkhiv-kursov-valyut/json/')
      .then(function (r) { return r.json(); })
      .then(function (spisok) {
        function nayti(kod) {
          const v = spisok.find(function (x) { return x.Ccy === kod; });
          if (!v) return null;
          return parseFloat(v.Rate) / (parseInt(v.Nominal, 10) || 1);
        }
        const kursy = {
          usd_uzs: nayti('USD'),
          rub_uzs: nayti('RUB'),
          date: new Date().toLocaleDateString('ru-RU'),
          saved_at: Date.now(),
        };
        if (!kursy.usd_uzs || !kursy.rub_uzs) throw new Error('ЦБ вернул неполные данные');
        localStorage.setItem('kursy', JSON.stringify(kursy));
        return kursy;
      })
      .catch(function () {
        // Сеть недоступна — берём что есть и честно пишем дату.
        const staryi = localStorage.getItem('kursy');
        return staryi ? JSON.parse(staryi) : window.KURSY_ZAPAS;
      });
  }

  /* ── Отрисовка ───────────────────────────────────────── */

  function narisovat(raschet, kursy) {
    el.results.innerHTML = '';

    if (!raschet.results.length) {
      el.results.innerHTML = '<p class="note">Данные обновляются. Загляните через час — показывать неверные цифры мы не будем.</p>';
      el.loss.classList.add('hidden');
      el.share.classList.add('hidden');
      return;
    }

    raschet.results.forEach(function (r, i) {
      const kartochka = document.createElement('button');
      kartochka.className = 'card' + (i === 0 ? ' best' : '');

      const metki = [];
      if (i === 0) metki.push('<span class="tag best">Больше всего</span>');
      else if (r.svezhest === 'ustarelo') metki.push('<span class="tag">Данные вчера</span>');

      const detali = [];
      detali.push(srok(r.delivery_minutes));
      if (r.ocenochnyi) detali.push('курс банка оценочный');
      // Наценка бывает и отрицательной — тогда банк даёт лучше официального курса.
      // Писать «хуже на −1,9%» нельзя, это читается как ошибка.
      // И не показываем вовсе, если данные рассогласованы: курс банка и курс ЦБ
      // от разных дат дают бессмысленную цифру, которая подрывает доверие.
      if (r.nacenka_percent !== null && r.dannye_soglasovany && Math.abs(r.nacenka_percent) >= 0.1) {
        detali.push(r.nacenka_percent > 0
          ? 'банк хуже курса ЦБ на ' + r.nacenka_percent.toFixed(1) + '%'
          : 'банк лучше курса ЦБ на ' + Math.abs(r.nacenka_percent).toFixed(1) + '%');
      } else if (r.nacenka_percent !== null && !r.dannye_soglasovany) {
        detali.push('курс банка требует обновления');
      }
      if (r.vyshe_limita) detali.push('выше лимита, нужна верификация');

      const summa = r.vilka
        ? sum(r.vilka.ot) + ' – ' + sum(r.vilka.do)
        : sum(r.total_uzs);

      kartochka.innerHTML =
        '<span class="top"><span class="svc">' + r.name + '</span>' + metki.join('') + '</span>' +
        '<span class="sum">' + summa + ' сум</span>' +
        '<span class="brk">' + detali.join(' · ') + '</span>';

      kartochka.addEventListener('click', function () { pokazatRazbor(r); });
      el.results.appendChild(kartochka);
    });

    if (raschet.hidden_loss_uzs > 0) {
      el.lossNum.textContent = sum(raschet.hidden_loss_uzs) + ' сум';
      el.lossSub.textContent = 'на ' + sum(el.summa.value) + ' ₽ · столько теряется на выборе способа';
      el.loss.classList.remove('hidden');
    } else {
      el.loss.classList.add('hidden');
    }

    let podpis = raschet.disclaimer;
    if (window.TEST_DATA) podpis = 'ТЕСТОВЫЕ ДАННЫЕ, цифры выдуманы. ' + podpis;
    el.disclaimer.textContent = podpis;
    el.disclaimer.classList.remove('hidden');

    // Без свежего курса ЦБ расчёт становится ориентировочным — говорим об этом
    // прямо, а не подсовываем цифру как ни в чём не бывало.
    el.kursDate.textContent = kursy.zapas || !kursy.date
      ? 'Курс ЦБ обновить не удалось — считаем по запасным значениям, цифры ориентировочные'
      : 'Курс ЦБ на ' + kursy.date;
    el.share.classList.remove('hidden');
  }

  function pokazatRazbor(r) {
    const stroki = r.razbor.map(function (p) { return p[0] + ': ' + p[1]; }).join('\n');
    const hvost = r.ocenochnyi
      ? '\n\nКурс банка получателя оценочный — банк ставит его в день зачисления.'
      : '';
    const text = r.name + '\n\n' + stroki + '\n\nПридёт на карту: ' + sum(r.total_uzs) + ' сум' + hvost;
    if (tg && tg.showPopup) tg.showPopup({ title: r.name, message: text });
    else alert(text);
  }

  /* ── Отправка в чат (этап 1: текстом) ────────────────── */

  function otpravitVChat() {
    if (!posledniyRaschet) return;
    const top = posledniyRaschet.results.slice(0, 3).map(function (r) {
      return r.name + ' — ' + sum(r.total_uzs) + ' сум';
    }).join('\n');

    const text =
      'Перевод ' + sum(el.summa.value) + ' ₽ в Узбекистан\n\n' + top +
      '\n\nРазница: ' + sum(posledniyRaschet.hidden_loss_uzs) + ' сум';

    if (tg && tg.switchInlineQuery) tg.switchInlineQuery(text, ['users', 'groups']);
    else if (navigator.clipboard) {
      navigator.clipboard.writeText(text);
      alert('Расчёт скопирован — вставьте в чат.');
    }
  }

  /* ── Запуск ──────────────────────────────────────────── */

  function zapolnitBanki() {
    const opts = ['<option value="">Не знаю</option>'];
    window.BANKS.forEach(function (b) {
      opts.push('<option value="' + b.id + '">' + b.name + '</option>');
    });
    el.bank.innerHTML = opts.join('');
  }

  function poschitat() {
    const summa = parseFloat(el.summa.value);
    if (!summa || summa < 1000) return;

    zagruzitKursy().then(function (kursy) {
      posledniyRaschet = window.CALC.poschitat(
        { summa: summa, bank_id: el.bank.value || null, corridor: 'RU-UZ' },
        window.SERVICES, window.BANKS, kursy
      );
      narisovat(posledniyRaschet, kursy);
      if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
    });
  }

  /* ── Первый запуск ───────────────────────────────────── */

  // Человек, пришедший из чата, не знает, что это — объяснение нужно.
  // Но экраном-заглушкой его давать нельзя: это лишний тап до цифры,
  // ради которой человек и пришёл. Поэтому объяснение стоит НАД формой,
  // а форма доступна сразу. Проверено прогоном: заглушка добавляла шаг.
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

  zapolnitBanki();
  pokazatIntro();
  el.introOk.addEventListener('click', zakrytIntro);
  el.schitat.addEventListener('click', poschitat);
  el.share.addEventListener('click', otpravitVChat);
  el.summa.addEventListener('keydown', function (e) { if (e.key === 'Enter') poschitat(); });

})();
