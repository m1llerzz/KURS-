/**
 * ДАННЫЕ ПРИЛОЖЕНИЯ
 *
 * ВНИМАНИЕ: сейчас здесь тестовые числа. Они выдуманы.
 * Реальные приносит Видадий в этом же формате — см. DATA-SOURCES.md раздел 5.
 * Пока TEST_DATA = true, приложение показывает пометку «тестовые данные».
 *
 * Обновлять просто: поправил числа, сохранил, залил файл. Ничего пересобирать не надо.
 */

window.TEST_DATA = true;

/**
 * Ссылка на мини-апп. Уходит в каждое пересланное сообщение — без неё
 * расчёт гуляет по чатам, а вернуться к нам человеку некуда.
 *
 * ПОСЛЕ BotFather ПРИВЕСТИ В СООТВЕТСТВИЕ: здесь имя бота из /newbot и
 * короткое имя из /newapp. Если они выйдут другими — поправить эту строку,
 * иначе ссылка в пересылке ведёт в никуда.
 *
 * startapp=share помечает переходы, пришедшие из чужой пересылки: на третьей
 * неделе по нему станет видно, сколько людей приводит один расчёт.
 */
window.BOT_LINK = 'https://t.me/QanchaYetadi_bot/calc?startapp=share';

window.SERVICES = [
  {
    id: 'servis-a',
    name: 'Способ A',
    route: 'A',                  // A — сервис объявляет курс сам
    corridors: ['RU-UZ'],
    fee_fixed: 199,              // рублей
    fee_percent: 0,
    rate_rub_uzs: 149.0,         // сум за рубль
    limit_per_operation: 150000,
    delivery_minutes: 10,
    incoming_fee: 0,
    checked_at: '2026-08-14T09:00:00Z',
    verified_by_receipt: false,
  },
  {
    id: 'servis-b',
    name: 'Способ B',
    route: 'B',                  // B — конвертирует банк получателя
    corridors: ['RU-UZ'],
    fee_fixed: 0,
    fee_percent: 1,
    rate_rub_uzs: null,
    limit_per_operation: 300000,
    delivery_minutes: 60,
    incoming_fee: 0,
    checked_at: '2026-08-14T09:00:00Z',
    verified_by_receipt: false,
  },
  {
    id: 'servis-c',
    name: 'Способ C',
    route: 'A',
    corridors: ['RU-UZ'],
    fee_fixed: 29,
    fee_percent: 0,
    rate_rub_uzs: 141.2,
    limit_per_operation: 200000,
    delivery_minutes: 1440,
    incoming_fee: 0,
    checked_at: '2026-08-13T09:00:00Z',   // ЛОВУШКА: вчерашние — должна появиться метка
    verified_by_receipt: false,
  },
  {
    id: 'servis-d',
    name: 'Способ D',
    route: 'A',
    corridors: ['RU-UZ'],
    fee_fixed: 0,
    fee_percent: 0.5,
    rate_rub_uzs: 152.0,
    limit_per_operation: 100000,
    delivery_minutes: 15,
    incoming_fee: 0,
    checked_at: '2026-08-05T09:00:00Z',   // ЛОВУШКА: старше 72 ч — НЕ должен появиться совсем
    verified_by_receipt: false,
  },
];

window.BANKS = [
  { id: 'bank-1', name: 'Банк 1', rate_usd_uzs: 13250, incoming_fee: 0, checked_at: '2026-08-14T09:00:00Z' },
  { id: 'bank-2', name: 'Банк 2', rate_usd_uzs: 13100, incoming_fee: 0, checked_at: '2026-08-14T09:00:00Z' },
  { id: 'bank-3', name: 'Банк 3', rate_usd_uzs: 12850, incoming_fee: 0, checked_at: '2026-08-14T09:00:00Z' },
];

/**
 * Запасные курсы ЦБ — используются, если сеть недоступна и кеша ещё нет.
 * Флаг zapas говорит приложению честно предупредить человека: без свежего
 * курса весь расчёт становится ориентировочным.
 */
window.KURSY_ZAPAS = { usd_uzs: 13000, rub_uzs: 143, zapas: true };
