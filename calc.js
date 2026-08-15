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
      razbor: [
        ['Отправлено', summa + ' ₽'],
        ['Комиссия сервиса', '− ' + Math.round(summa - baza) + ' ₽'],
        ['К конвертации', Math.round(baza) + ' ₽'],
        ['Курс сервиса', '× ' + servis.rate_rub_uzs],
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
        ['Отправлено', summa + ' ₽'],
        ['Комиссия сервиса', '− ' + Math.round(summa - baza) + ' ₽'],
        ['К конвертации', Math.round(baza) + ' ₽'],
        ['Курс рубль → доллар', '÷ ' + kursRubUsd.toFixed(2)],
        ['Ушло в валюте', vValute.toFixed(2) + ' $'],
        ['Курс банка → сум', '× ' + bank.rate_usd_uzs],
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
    const bank = vvod.bank_id ? banki.find(function (b) { return b.id === vvod.bank_id; }) : null;
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
        const vse = banki.map(function (b) { return marshrutB(vvod.summa, servis, b, kursy); });
        const hudshiy = vse.reduce(function (a, b) { return a.total_uzs < b.total_uzs ? a : b; });
        const luchshiy = vse.reduce(function (a, b) { return a.total_uzs > b.total_uzs ? a : b; });
        itog = hudshiy;
        if (vse.length > 1) vilka = { ot: hudshiy.total_uzs, do: luchshiy.total_uzs };
      }

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
        nacenka_percent: itog.nacenka_percent || null,
        dannye_soglasovany: itog.nacenka_percent === undefined
          ? true
          : nacenkaPravdopodobna(itog.nacenka_percent),
        razbor: itog.razbor,
      });
    });

    rezultaty.sort(function (a, b) { return b.total_uzs - a.total_uzs; });

    const skrytaya_poterya = rezultaty.length > 1
      ? rezultaty[0].total_uzs - rezultaty[rezultaty.length - 1].total_uzs
      : 0;

    return {
      results: rezultaty,
      hidden_loss_uzs: skrytaya_poterya,
      calculated_at: new Date().toISOString(),
      // Обязательная строка интерфейса. Не убирать — см. LEGAL.md.
      disclaimer: 'Мы не переводим деньги. Курс банка получателя оценочный — банк ставит его в день зачисления, итог может отличаться.',
    };
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
  };

})();
