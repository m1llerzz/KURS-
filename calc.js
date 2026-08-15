/**
 * ФОРМУЛЫ
 *
 * Здесь только чистые функции: получают числа — возвращают числа.
 * Ничего не знают про кнопки, экран и Telegram. Именно поэтому их можно
 * проверять построчно, и это главная работа Семёна как QA.
 *
 * Правила, зашитые в код намеренно, чтобы не зависеть от памяти:
 *  — итог округляется ВНИЗ до тысяч сум;
 *  — способ с данными старше 72 часов не попадает в выдачу вовсе;
 *  — маршрут B всегда помечен как оценочный.
 */

window.CALC = (function () {

  const PREDEL_TOCHNOSTI_CHASOV = 24;   // до 24 ч — точная цифра
  const PREDEL_VILKI_CHASOV = 72;       // после 72 ч — скрываем совсем

  /**
   * Кросс-курс рубль → доллар из курсов ЦБ.
   * Внешний источник котировок не нужен: ЦБ отдаёт обе валюты в сумах.
   */
  function krossKursRubUsd(kursUsdUzs, kursRubUzs) {
    if (!kursRubUzs) throw new Error('Нет курса рубля от ЦБ');
    return kursUsdUzs / kursRubUzs;
  }

  /** Сумма после вычета комиссии сервиса. */
  function posleKomissii(summa, feeFixed, feePercent) {
    return summa - (feeFixed || 0) - summa * ((feePercent || 0) / 100);
  }

  /** Округление ВНИЗ до тысяч. Никогда не вверх. */
  function okruglitVniz(summa) {
    return Math.floor(summa / 1000) * 1000;
  }

  /** Наценка банка против официального курса ЦБ, в процентах. */
  function nacenkaBanka(kursBanka, kursCB) {
    if (!kursCB) return null;
    return ((kursCB - kursBanka) / kursCB) * 100;
  }

  /**
   * Проверка согласованности данных.
   *
   * Реальный разброс курсов банков против ЦБ — 3–5%. Если насчиталось больше,
   * это почти наверняка не «выгодный банк», а рассогласованные данные:
   * курс банка от одной даты, курс ЦБ от другой.
   *
   * Найдено на живом прогоне: тестовые курсы банков против настоящего курса ЦБ
   * дали «банк лучше ЦБ на 7,6%» — цифра бессмысленная и подрывающая доверие.
   * Показывать такое нельзя, лучше промолчать.
   *
   * Порог 6%: документированный разброс между банками 3–5%, всё что выше —
   * признак того, что курсы взяты за разные дни. См. ANALYTICS.md раздел 1.
   */
  const PREDEL_NACENKI = 6;

  function nacenkaPravdopodobna(procent) {
    return procent !== null && procent !== undefined && Math.abs(procent) <= PREDEL_NACENKI;
  }

  /** Возраст данных в часах. */
  function vozrastChasov(checkedAt) {
    return (Date.now() - new Date(checkedAt).getTime()) / 36e5;
  }

  /** 'tochno' | 'ustarelo' | 'skryt' */
  function statusSvezhesti(checkedAt) {
    const chasov = vozrastChasov(checkedAt);
    if (chasov <= PREDEL_TOCHNOSTI_CHASOV) return 'tochno';
    if (chasov <= PREDEL_VILKI_CHASOV) return 'ustarelo';
    return 'skryt';
  }

  /** Маршрут A: итог = (сумма − комиссия) × курс_сервиса − зачисление */
  function marshrutA(summa, servis) {
    const baza = posleKomissii(summa, servis.fee_fixed, servis.fee_percent);
    const itog = baza * servis.rate_rub_uzs - (servis.incoming_fee || 0);
    return {
      total_uzs: okruglitVniz(itog),
      ocenochnyi: false,
      // Первым элементом пары идёт ключ перевода, а не готовая подпись:
      // язык — забота экрана, формулы про него знать не должны.
      razbor: [
        ['razbor.sent',      summa + ' ₽'],
        ['razbor.fee',       '− ' + Math.round(summa - baza) + ' ₽'],
        ['razbor.toconv',    Math.round(baza) + ' ₽'],
        ['razbor.rate_serv', '× ' + servis.rate_rub_uzs],
      ],
    };
  }

  /** Маршрут B: перевод уходит в валюте, конвертирует банк получателя. */
  function marshrutB(summa, servis, bank, kursy) {
    const baza = posleKomissii(summa, servis.fee_fixed, servis.fee_percent);
    const kursRubUsd = krossKursRubUsd(kursy.usd_uzs, kursy.rub_uzs);
    const vValute = baza / kursRubUsd;
    const itog = vValute * bank.rate_usd_uzs - (bank.incoming_fee || 0);

    return {
      total_uzs: okruglitVniz(itog),
      ocenochnyi: true,
      bank_name: bank.name,
      nacenka_percent: nacenkaBanka(bank.rate_usd_uzs, kursy.usd_uzs),
      razbor: [
        ['razbor.sent',        summa + ' ₽'],
        ['razbor.fee',         '− ' + Math.round(summa - baza) + ' ₽'],
        ['razbor.toconv',      Math.round(baza) + ' ₽'],
        ['razbor.rate_rubusd', '÷ ' + kursRubUsd.toFixed(2)],
        ['razbor.in_currency', vValute.toFixed(2) + ' $'],
        ['razbor.rate_bank',   '× ' + bank.rate_usd_uzs],
      ],
    };
  }

  /**
   * Главная функция. Считает все способы и скрытую потерю.
   *
   * @param {{summa:number, bank_id:string|null, corridor:string}} vvod
   * @param {Array} servisy
   * @param {Array} banki
   * @param {{usd_uzs:number, rub_uzs:number}} kursy
   */
  function poschitat(vvod, servisy, banki, kursy) {
    // Курс банка недельной давности — такая же ложь, как устаревший тариф
    // сервиса, и цена ошибки здесь выше: на курсе банка построен весь продукт.
    // Раньше свежесть проверялась только у сервисов, и расчёт спокойно шёл
    // по курсу двухлетней давности.
    const svezhieBanki = (banki || []).filter(function (b) {
      return !b.checked_at || statusSvezhesti(b.checked_at) !== 'skryt';
    });

    const vybranniy = vvod.bank_id
      ? svezhieBanki.find(function (b) { return b.id === vvod.bank_id; })
      : null;
    // Если выбранный банк протух, ведём себя как при невыбранном: показываем
    // вилку по свежим. Молча считать по старому курсу нельзя.
    const bank = vybranniy || null;
    const rezultaty = [];

    servisy.forEach(function (servis) {
      const svezhest = statusSvezhesti(servis.checked_at);
      if (svezhest === 'skryt') return;                                  // протухшее не показываем
      if (servis.corridors.indexOf(vvod.corridor) === -1) return;

      let itog;
      let vilka = null;

      if (servis.route === 'A') {
        itog = marshrutA(vvod.summa, servis);
      } else if (bank) {
        itog = marshrutB(vvod.summa, servis, bank, kursy);
      } else {
        // Банк не выбран — считаем по всем известным и показываем вилку.
        // За основу берём ХУДШИЙ банк, а не лучший: обещать больше, чем придёт,
        // нельзя. Тот же принцип, что и округление вниз.
        //
        // Пустой список ронял весь расчёт: reduce без начального значения
        // на пустом массиве бросает TypeError, и приложение молча переставало
        // считать. Способ, который не по чему посчитать, просто не показываем.
        if (!svezhieBanki.length) return;

        const vse = svezhieBanki.map(function (b) { return marshrutB(vvod.summa, servis, b, kursy); });
        const hudshiy = vse.reduce(function (a, b) { return a.total_uzs < b.total_uzs ? a : b; });
        const luchshiy = vse.reduce(function (a, b) { return a.total_uzs > b.total_uzs ? a : b; });
        itog = hudshiy;
        if (vse.length > 1) vilka = { ot: hudshiy.total_uzs, do: luchshiy.total_uzs };
      }

      // Комиссия съела перевод целиком. Показывать минус на экране нельзя:
      // человек читает это как «я должен банку». Проверено запуском —
      // отправка 1 000 ₽ при комиссии 2 000 ₽ рисовала −149 000 сум.
      if (itog.total_uzs <= 0) return;

      rezultaty.push({
        service_id: servis.id,
        name: servis.name,
        route: servis.route,
        delivery_minutes: servis.delivery_minutes,
        svezhest: svezhest,
        vyshe_limita: vvod.summa > servis.limit_per_operation,
        vilka: vilka,
        total_uzs: itog.total_uzs,
        ocenochnyi: itog.ocenochnyi,
        // Именно !== undefined, а не «|| null»: наценка ровно ноль означает,
        // что банк даёт точно по курсу ЦБ — это правда, которую надо показать,
        // а короткая запись превращала её в «данных нет».
        nacenka_percent: itog.nacenka_percent === undefined ? null : itog.nacenka_percent,
        dannye_soglasovany: itog.nacenka_percent === undefined
          ? true
          : nacenkaPravdopodobna(itog.nacenka_percent),
        razbor: itog.razbor,
      });
    });

    // Сначала те, которыми человек может воспользоваться прямо сейчас.
    // Раньше сверху с меткой «больше всего» вставал способ, помеченный
    // «выше лимита»: он показывал сумму, которую по нему не отправить.
    rezultaty.sort(function (a, b) {
      if (a.vyshe_limita !== b.vyshe_limita) return a.vyshe_limita ? 1 : -1;
      return b.total_uzs - a.total_uzs;
    });

    // Разницу считаем только среди доступных способов. Иначе она надувается
    // за счёт варианта, которым всё равно нельзя воспользоваться, и обещает
    // выгоду, которой у человека нет.
    const dostupnye = rezultaty.filter(function (r) { return !r.vyshe_limita; });
    const skrytaya_poterya = dostupnye.length > 1
      ? dostupnye[0].total_uzs - dostupnye[dostupnye.length - 1].total_uzs
      : 0;

    return {
      results: rezultaty,
      hidden_loss_uzs: skrytaya_poterya,
      calculated_at: new Date().toISOString(),
      // Обязательная строка интерфейса. Не убирать — см. LEGAL.md.
      disclaimer: 'disclaimer.main',
    };
  }

  /* ── Вердикт дня: отправлять сегодня или подождать ──────────────────
   *
   * Почему это главная функция приложения, а не украшение. Замер 15.08.2026
   * по курсам ЦБ за 30 дней:
   *
   *     размах курса рубля           9,49%   (155,22 → 141,76)
   *     курс перевода против ЦБ      4,06%   (136 против 141,76)
   *     разброс банков-получателей   0,84%
   *
   * День отправки решает больше денег, чем выбор сервиса и банка вместе.
   * На 50 000 ₽ это 673 000 сум против 288 000 и 55 000.
   *
   * Считается здесь, а не берётся у бота, ровно по одной причине: вердикт
   * обязан работать при мёртвой сети, по запасной истории из data.js.
   * Терять главную ценность продукта из-за плохого интернета в метро нельзя.
   *
   * Тот же расчёт есть у бота в sovet.py — он нужен ему для оповещений.
   * Две реализации проверяются одинаковыми наборами чисел, см. test.html
   * и bot/test_sovet.py: разойдясь, они покажут человеку разные советы.
   */

  const PORAG_ZAMETNOSTI = 1.0;   // ниже — разница тонет в комиссии
  const PORAG_SILNYY = 3.0;       // выше — стоит менять планы
  const OKNO_DNEY = 30;

  function srednee(chisla) {
    if (!chisla.length) return null;
    return chisla.reduce(function (a, b) { return a + b; }, 0) / chisla.length;
  }

  /**
   * Что человеку делать. Это НЕ то же самое, что вердикт.
   *
   * Ошибка, которую здесь чинили: раньше совет выводился только из
   * отклонения от среднего. Курс ниже обычного — значит «подожди».
   *
   * На живых данных это оказалось вредным. Рубль падал весь месяц: каждый
   * день был ниже среднего, каждый день приложение говорило «подожди», и
   * каждый следующий день курс был ХУЖЕ предыдущего. Совет стоил человеку
   * денег ровно столько раз, сколько он его послушал.
   *
   * Ждать имеет смысл только тогда, когда курс РАСТЁТ.
   *
   * Тот же расчёт есть у бота в sovet.py — совпадение проверяет
   * bot/test_parity.py. Разойдясь, они дадут человеку разные советы.
   */
  function deystvie(verdikt, trend) {
    const nizhe = verdikt === 'ploho' || verdikt === 'nize_obychnogo';
    const vyshe = verdikt === 'otlichno' || verdikt === 'horosho';

    if (trend === 'padaet') return vyshe ? 'otpravlyat' : 'ne_zhdat';
    if (trend === 'rastet') return nizhe ? 'mozhno_zhdat' : 'otpravlyat';

    if (vyshe) return 'otpravlyat';
    if (nizhe) return 'mozhno_zhdat';
    return 'obychno';
  }

  /**
   * @param {Array<{date:string, rub_uzs:number}>} istoriya
   * @returns {object|null} null — если данных меньше недели: на трёх днях
   *          «среднее» это случайность, а совет человеку про его деньги
   *          на случайности строить нельзя.
   */
  function sovet(istoriya) {
    if (!istoriya || istoriya.length < 7) return null;

    const ryad = istoriya.slice().sort(function (a, b) {
      return a.date < b.date ? -1 : a.date > b.date ? 1 : 0;
    });
    const kursy = ryad.map(function (x) { return x.rub_uzs; });
    const segodnya = kursy[kursy.length - 1];

    const okno = kursy.slice(-OKNO_DNEY);
    const sred = srednee(okno);
    const minimum = Math.min.apply(null, okno);
    const maksimum = Math.max.apply(null, okno);

    const otklonenie = ((segodnya - sred) / sred) * 100;

    // Где сегодняшний курс внутри коридора месяца: 0 — худший день,
    // 100 — лучший. Понятнее процентов: «лучше 80% дней месяца».
    const pozicia = maksimum > minimum
      ? ((segodnya - minimum) / (maksimum - minimum)) * 100
      : 50;

    // Куда движется: три последних дня против трёх предыдущих. Не «вчера
    // против сегодня» — один день это шум, а человек по нему решает.
    let trend = null;
    if (kursy.length >= 6) {
      const svezhie = srednee(kursy.slice(-3));
      const proshlye = srednee(kursy.slice(-6, -3));
      if (proshlye) {
        const izm = ((svezhie - proshlye) / proshlye) * 100;
        trend = izm > 0.3 ? 'rastet' : izm < -0.3 ? 'padaet' : 'stoit';
      }
    }

    // Вердикт честен в обе стороны. Продукт, который всегда говорит
    // «отправляй», — это реклама, а не советник, и это видно с первого раза.
    let verdikt;
    if (otklonenie >= PORAG_SILNYY) verdikt = 'otlichno';
    else if (otklonenie >= PORAG_ZAMETNOSTI) verdikt = 'horosho';
    else if (otklonenie <= -PORAG_SILNYY) verdikt = 'ploho';
    else if (otklonenie <= -PORAG_ZAMETNOSTI) verdikt = 'nize_obychnogo';
    else verdikt = 'obychno';

    return {
      verdikt: verdikt,
      deystvie: deystvie(verdikt, trend),
      segodnya: Math.round(segodnya * 100) / 100,
      srednee_30: Math.round(sred * 100) / 100,
      min_30: Math.round(minimum * 100) / 100,
      max_30: Math.round(maksimum * 100) / 100,
      otklonenie_percent: Math.round(otklonenie * 100) / 100,
      pozicia_percent: Math.round(pozicia),
      trend: trend,
      tochek: okno.length,
      // Сколько человек выигрывает или теряет на каждую тысячу рублей
      // против обычного курса. Умножить на свою сумму умеет каждый,
      // а процент от абстрактного курса не чувствует никто.
      raznica_na_1000_rub: Math.round((segodnya - sred) * 1000),
      ryad: ryad.slice(-OKNO_DNEY),
    };
  }

  /** Сколько сум даёт (или отнимает) сегодняшний курс против обычного. */
  function vygodaNaSumme(ocenka, summaRub) {
    if (!ocenka || !summaRub) return 0;
    return Math.round((ocenka.segodnya - ocenka.srednee_30) * summaRub);
  }

  return {
    poschitat: poschitat,
    marshrutA: marshrutA,
    marshrutB: marshrutB,
    krossKursRubUsd: krossKursRubUsd,
    nacenkaBanka: nacenkaBanka,
    okruglitVniz: okruglitVniz,
    statusSvezhesti: statusSvezhesti,
    nacenkaPravdopodobna: nacenkaPravdopodobna,
    sovet: sovet,
    vygodaNaSumme: vygodaNaSumme,
  };

})();
