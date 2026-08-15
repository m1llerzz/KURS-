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
  let posledniyKurs = null;

  const t = window.I18N.t;

  /* ── Форматирование ──────────────────────────────────── */

  function sum(n) {
    return Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  }

  function srok(minut) {
    if (minut < 60) return minut + ' ' + t('time.min');
    if (minut < 1440) return Math.round(minut / 60) + ' ' + t('time.hour');
    return Math.round(minut / 1440) + ' ' + t('time.day');
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
      if (r.ocenochnyi) detali.push(t('detail.est'));
      // Наценка бывает и отрицательной — тогда банк даёт лучше официального курса.
      // Писать «хуже на −1,9%» нельзя, это читается как ошибка.
      // И не показываем вовсе, если данные рассогласованы: курс банка и курс ЦБ
      // от разных дат дают бессмысленную цифру, которая подрывает доверие.
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

      kartochka.innerHTML =
        '<span class="top"><span class="svc">' + r.name + '</span>' + metki.join('') + '</span>' +
        '<span class="sum">' + summa + ' ' + t('unit.sum') + '</span>' +
        '<span class="brk">' + detali.join(' · ') + '</span>';

      kartochka.addEventListener('click', function () { pokazatRazbor(r); });
      el.results.appendChild(kartochka);
    });

    if (raschet.hidden_loss_uzs > 0) {
      el.lossNum.textContent = sum(raschet.hidden_loss_uzs) + ' ' + t('unit.sum');
      el.lossSub.textContent = t('loss.sub', { sum: sum(el.summa.value) });
      el.loss.classList.remove('hidden');
    } else {
      el.loss.classList.add('hidden');
    }

    // disclaimer приходит из calc ключом, а не готовой фразой.
    let podpis = t(raschet.disclaimer);
    if (window.TEST_DATA) podpis = t('test') + podpis;
    el.disclaimer.textContent = podpis;
    el.disclaimer.classList.remove('hidden');

    // Без свежего курса ЦБ расчёт становится ориентировочным — говорим об этом
    // прямо, а не подсовываем цифру как ни в чём не бывало.
    el.kursDate.textContent = kursy.zapas || !kursy.date
      ? t('kurs.fail')
      : t('kurs.date', { d: kursy.date });
    el.share.classList.remove('hidden');
  }

  function pokazatRazbor(r) {
    const stroki = r.razbor.map(function (p) { return t(p[0]) + ': ' + p[1]; }).join('\n');
    const hvost = r.ocenochnyi ? '\n\n' + t('popup.est') : '';
    const text = r.name + '\n\n' + stroki + '\n\n'
      + t('popup.total') + ': ' + sum(r.total_uzs) + ' ' + t('unit.sum') + hvost;
    if (tg && tg.showPopup) tg.showPopup({ title: r.name, message: text });
    else alert(text);
  }

  /* ── Отправка в чат ──────────────────────────────────── */

  /**
   * Пересылка — единственный канал, по которому про нас узнают бесплатно.
   * Поэтому в сообщении обязаны быть три вещи: цифра ради которой смотрят,
   * разница ради которой удивляются, и ссылка ради которой возвращаются.
   * Раньше ссылки не было — расчёт гулял по чатам, а прийти к нам было некуда.
   */
  function sobratTekst() {
    const top = posledniyRaschet.results.slice(0, 3).map(function (r) {
      return r.name + ' — ' + sum(r.total_uzs) + ' ' + t('unit.sum');
    }).join('\n');

    return t('share.title', { sum: sum(el.summa.value) }) + '\n\n' + top +
      '\n\n' + t('share.diff', { loss: sum(posledniyRaschet.hidden_loss_uzs) }) +
      '\n\n' + t('share.cta');
  }

  function otpravitVChat() {
    if (!posledniyRaschet) return;
    const text = sobratTekst();
    const link = window.BOT_LINK || '';

    // Штатный путь: экран выбора чата. Ссылку подставляет сам Telegram
    // отдельным параметром, поэтому в тексте её дублировать не нужно.
    // switchInlineQuery здесь не годится — он требует включённого inline-режима
    // у бота, а его у нас нет и заводить ради одной кнопки незачем.
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

  /* ── Запуск ──────────────────────────────────────────── */

  function zapolnitBanki() {
    // Выбранный банк надо сохранить: смена языка перерисовывает список,
    // и без этого выбор человека молча слетал бы на «не знаю».
    const bylo = el.bank.value;
    const opts = ['<option value="">' + t('bank.any') + '</option>'];
    window.BANKS.forEach(function (b) {
      opts.push('<option value="' + b.id + '">' + b.name + '</option>');
    });
    el.bank.innerHTML = opts.join('');
    if (bylo) el.bank.value = bylo;
  }

  /* ── Язык ────────────────────────────────────────────── */

  function primenitYazyk() {
    document.documentElement.lang = window.I18N.get();

    document.querySelectorAll('[data-i18n]').forEach(function (node) {
      node.textContent = t(node.getAttribute('data-i18n'));
    });
    // Отдельный атрибут для строк с разметкой внутри: подставлять их
    // через textContent нельзя, а гнать через innerHTML всё подряд не нужно.
    document.querySelectorAll('[data-i18n-html]').forEach(function (node) {
      node.innerHTML = t(node.getAttribute('data-i18n-html'));
    });

    document.querySelectorAll('.lang').forEach(function (b) {
      b.classList.toggle('on', b.getAttribute('data-lang') === window.I18N.get());
    });

    zapolnitBanki();
    // Результат на экране тоже надо перевести, иначе половина страницы
    // останется на прежнем языке до следующего нажатия «Посчитать».
    if (posledniyRaschet) narisovat(posledniyRaschet, posledniyKurs);
  }

  function poschitat() {
    const summa = parseFloat(el.summa.value);
    if (!summa || summa < 1000) return;

    zagruzitKursy().then(function (kursy) {
      posledniyKurs = kursy;
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

  primenitYazyk();
  pokazatIntro();

  document.querySelectorAll('.lang').forEach(function (b) {
    b.addEventListener('click', function () {
      window.I18N.set(b.getAttribute('data-lang'));
      primenitYazyk();
    });
  });

  el.introOk.addEventListener('click', zakrytIntro);
  el.schitat.addEventListener('click', poschitat);
  el.share.addEventListener('click', otpravitVChat);
  el.summa.addEventListener('keydown', function (e) { if (e.key === 'Enter') poschitat(); });

})();
