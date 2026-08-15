/**
 * КАРТОЧКА ДЛЯ ПЕРЕСЫЛКИ
 *
 * Рисует расчёт картинкой на canvas. Ничего не грузит из сети,
 * никаких библиотек, никакого сервера.
 *
 * ВАЖНО ПРО ОТПРАВКУ. Мини-апп не может сам положить картинку в чужой чат:
 * для этого нужен бот с серверной частью, а её у нас нет и пока не нужно.
 * Поэтому здесь: картинка рисуется, пользователь сохраняет её и отправляет сам.
 * Текстовая отправка в app.js работает без этого и пересылается не хуже —
 * картинка нужна там, где важно, чтобы репост выглядел прилично.
 *
 * Подключается отдельной строкой в index.html и включается по желанию.
 * В неделях 1–3 не трогать: сначала цифры, потом красота.
 */

window.CARD = (function () {

  const SHIRINA = 1080;
  const VYSOTA = 1080;

  // Цвета зашиты, а не берутся из темы: картинку смотрят вне Telegram,
  // где переменных темы нет.
  const C = {
    fon: '#0f1720',
    karta: '#17222d',
    tekst: '#eef4f9',
    tusklyy: '#8fa3b5',
    akcent: '#4fb0d4',
    trevoga: '#e07a7a',
    liniya: '#25323f',
  };

  function probely(n) {
    return Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  }

  /**
   * @param {object} raschet — результат CALC.poschitat
   * @param {number} summa — сколько отправляют, в рублях
   * @param {string} imyaBota — подпись внизу
   * @returns {HTMLCanvasElement}
   */
  function narisovat(raschet, summa, imyaBota) {
    const cv = document.createElement('canvas');
    cv.width = SHIRINA;
    cv.height = VYSOTA;
    const g = cv.getContext('2d');

    g.fillStyle = C.fon;
    g.fillRect(0, 0, SHIRINA, VYSOTA);

    const pole = 80;
    let y = 130;

    // Шапка
    g.fillStyle = C.tusklyy;
    g.font = '600 34px -apple-system, "Segoe UI", Roboto, sans-serif';
    g.fillText('Перевод ' + probely(summa) + ' ₽ в Узбекистан', pole, y);

    y += 78;
    g.fillStyle = C.tekst;
    g.font = '800 62px -apple-system, "Segoe UI", Roboto, sans-serif';
    g.fillText('Сколько придёт на карту', pole, y);

    // Способы — не больше трёх, иначе текст мельчает
    y += 70;
    const spisok = raschet.results.slice(0, 3);

    spisok.forEach(function (r, i) {
      const vysotaKarty = 150;
      g.fillStyle = C.karta;
      skruglennyy(g, pole, y, SHIRINA - pole * 2, vysotaKarty, 24);
      g.fill();

      if (i === 0) {
        g.strokeStyle = C.akcent;
        g.lineWidth = 3;
        skruglennyy(g, pole, y, SHIRINA - pole * 2, vysotaKarty, 24);
        g.stroke();
      }

      g.fillStyle = i === 0 ? C.akcent : C.tusklyy;
      g.font = '700 32px -apple-system, "Segoe UI", Roboto, sans-serif';
      g.fillText(r.name, pole + 40, y + 56);

      g.fillStyle = C.tekst;
      g.font = '800 60px -apple-system, "Segoe UI", Roboto, sans-serif';
      const stroka = r.vilka
        ? probely(r.vilka.ot) + ' – ' + probely(r.vilka.do)
        : probely(r.total_uzs);
      g.fillText(stroka + ' сум', pole + 40, y + 118);

      y += vysotaKarty + 22;
    });

    // Разница — главное число картинки
    if (raschet.hidden_loss_uzs > 0) {
      y += 18;
      g.fillStyle = C.tusklyy;
      g.font = '600 34px -apple-system, "Segoe UI", Roboto, sans-serif';
      g.fillText('Разница между способами', pole, y + 20);

      g.fillStyle = C.trevoga;
      g.font = '800 84px -apple-system, "Segoe UI", Roboto, sans-serif';
      g.fillText(probely(raschet.hidden_loss_uzs) + ' сум', pole, y + 110);
      y += 140;
    }

    // Подвал: дата и оговорка — обязательны, см. LEGAL.md
    g.strokeStyle = C.liniya;
    g.lineWidth = 2;
    g.beginPath();
    g.moveTo(pole, VYSOTA - 150);
    g.lineTo(SHIRINA - pole, VYSOTA - 150);
    g.stroke();

    const data = new Date().toLocaleDateString('ru-RU');
    g.fillStyle = C.tusklyy;
    g.font = '500 28px -apple-system, "Segoe UI", Roboto, sans-serif';
    g.fillText(data + ' · курс банка получателя оценочный', pole, VYSOTA - 100);
    g.fillStyle = C.akcent;
    g.fillText(imyaBota || '', pole, VYSOTA - 56);

    return cv;
  }

  /** Прямоугольник со скруглением — путь, без заливки. */
  function skruglennyy(g, x, y, w, h, r) {
    g.beginPath();
    g.moveTo(x + r, y);
    g.arcTo(x + w, y, x + w, y + h, r);
    g.arcTo(x + w, y + h, x, y + h, r);
    g.arcTo(x, y + h, x, y, r);
    g.arcTo(x, y, x + w, y, r);
    g.closePath();
  }

  /** Сохранить картинку в галерею — дальше человек отправляет сам. */
  function sohranit(raschet, summa, imyaBota) {
    const cv = narisovat(raschet, summa, imyaBota);
    cv.toBlob(function (blob) {
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'raschet-' + Date.now() + '.png';
      a.click();
      setTimeout(function () { URL.revokeObjectURL(url); }, 5000);
    }, 'image/png');
  }

  return { narisovat: narisovat, sohranit: sohranit };

})();
