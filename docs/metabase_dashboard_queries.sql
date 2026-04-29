-- Дашборд 1: Продажи
-- Выручка по дням
-- Рекомендация Metabase: линейный график. X = Дата, Y = Выручка.
SELECT DATE(created_at) AS "Дата", SUM(total) AS "Выручка"
FROM cafe_order
WHERE status <> 'cancelled'
GROUP BY DATE(created_at)
ORDER BY "Дата";

-- Количество заказов по дням
-- Рекомендация Metabase: столбчатая диаграмма. X = Дата, Y = Количество заказов.
SELECT DATE(created_at) AS "Дата", COUNT(*) AS "Количество заказов"
FROM cafe_order
WHERE status <> 'cancelled'
GROUP BY DATE(created_at)
ORDER BY "Дата";

-- Средний чек по дням
-- Рекомендация Metabase: линейный график или комбинированный график рядом с выручкой. X = Дата, Y = Средний чек.
SELECT DATE(created_at) AS "Дата", AVG(total) AS "Средний чек"
FROM cafe_order
WHERE status <> 'cancelled'
GROUP BY DATE(created_at)
ORDER BY "Дата";

-- Дашборд 2: Товары
-- Топ товаров по выручке
-- Рекомендация Metabase: горизонтальная столбчатая диаграмма. X = Выручка, Y = Товар.
SELECT p.name AS "Товар", SUM(oi.quantity * oi.price) AS "Выручка"
FROM cafe_orderitem oi
JOIN cafe_product p ON p.id = oi.product_id
JOIN cafe_order o ON o.id = oi.order_id
WHERE o.status <> 'cancelled'
GROUP BY p.name
ORDER BY "Выручка" DESC
LIMIT 10;

-- Топ товаров по количеству продаж
-- Рекомендация Metabase: горизонтальная столбчатая диаграмма. X = Продано, шт., Y = Товар.
SELECT p.name AS "Товар", SUM(oi.quantity) AS "Продано, шт."
FROM cafe_orderitem oi
JOIN cafe_product p ON p.id = oi.product_id
JOIN cafe_order o ON o.id = oi.order_id
WHERE o.status <> 'cancelled'
GROUP BY p.name
ORDER BY "Продано, шт." DESC
LIMIT 10;

-- Маржинальность товаров: цена минус себестоимость
-- Рекомендация Metabase: таблица с сортировкой по Марже или горизонтальная столбчатая диаграмма. X = Маржа, Y = Товар.
SELECT
    name AS "Товар",
    price AS "Цена",
    cost_price AS "Себестоимость",
    (price - COALESCE(cost_price, 0)) AS "Маржа"
FROM cafe_product
ORDER BY "Маржа" DESC;

-- Дашборд 3: Клиенты
-- Новые клиенты по дням
-- Рекомендация Metabase: столбчатая диаграмма. X = Дата, Y = Новые клиенты.
SELECT DATE(date_joined) AS "Дата", COUNT(*) AS "Новые клиенты"
FROM auth_user
GROUP BY DATE(date_joined)
ORDER BY "Дата";

-- Повторные покупки по клиентам
-- Рекомендация Metabase: таблица. Сортировка по Количеству заказов и Сумме покупок.
SELECT
    u.username AS "Клиент",
    COUNT(o.id) AS "Количество заказов",
    SUM(o.total) AS "Сумма покупок"
FROM cafe_order o
JOIN auth_user u ON u.id = o.user_id
WHERE o.user_id IS NOT NULL
  AND o.status <> 'cancelled'
GROUP BY u.username
HAVING COUNT(o.id) > 1
ORDER BY "Количество заказов" DESC, "Сумма покупок" DESC;

-- Источник для простого RFM-анализа
-- Рекомендация Metabase: таблица. Используйте для сегментации клиентов по давности, частоте и сумме покупок.
SELECT
    u.id AS "ID клиента",
    u.username AS "Клиент",
    MAX(o.created_at) AS "Последний заказ",
    COUNT(o.id) AS "Частота покупок",
    SUM(o.total) AS "Сумма покупок"
FROM auth_user u
LEFT JOIN cafe_order o ON o.user_id = u.id AND o.status <> 'cancelled'
GROUP BY u.id, u.username;

-- Дашборд 4: Время
-- Пиковые часы по заказам
-- Рекомендация Metabase: столбчатая диаграмма. X = Час дня, Y = Количество заказов.
SELECT EXTRACT(HOUR FROM created_at) AS "Час дня", COUNT(*) AS "Количество заказов"
FROM cafe_order
WHERE status <> 'cancelled'
GROUP BY "Час дня"
ORDER BY "Час дня";

-- Выручка по дням недели
-- Рекомендация Metabase: столбчатая диаграмма. X = День недели, Y = Выручка.
SELECT EXTRACT(DOW FROM created_at) AS "День недели", SUM(total) AS "Выручка"
FROM cafe_order
WHERE status <> 'cancelled'
GROUP BY "День недели"
ORDER BY "День недели";

-- Дашборд 5: Операции
-- Заказы по статусам
-- Рекомендация Metabase: круговая диаграмма или столбчатая диаграмма. Категория = Статус, значение = Количество заказов.
SELECT
    status AS "Статус",
    COUNT(*) AS "Количество заказов",
    SUM(CASE WHEN status <> 'cancelled' THEN total ELSE 0 END) AS "Выручка"
FROM cafe_order
GROUP BY status
ORDER BY "Количество заказов" DESC;

-- Доставка и самовывоз
-- Рекомендация Metabase: круговая диаграмма для долей или столбчатая диаграмма для сравнения выручки.
SELECT
    delivery_type AS "Способ получения",
    COUNT(*) AS "Количество заказов",
    SUM(total) AS "Выручка",
    AVG(total) AS "Средний чек"
FROM cafe_order
WHERE status <> 'cancelled'
GROUP BY delivery_type
ORDER BY "Количество заказов" DESC;

-- Воронка событий по дням
-- Рекомендация Metabase: stacked bar chart. X = Дата, серия = Тип события, Y = Количество событий.
SELECT
    DATE(timestamp) AS "Дата",
    event_type AS "Тип события",
    COUNT(*) AS "Количество событий"
FROM cafe_eventlog
GROUP BY DATE(timestamp), event_type
ORDER BY "Дата", "Тип события";

-- Добавления в корзину по товарам
-- Рекомендация Metabase: горизонтальная столбчатая диаграмма. X = Добавлений в корзину, Y = Товар.
SELECT
    p.name AS "Товар",
    COUNT(*) AS "Добавлений в корзину"
FROM cafe_eventlog e
JOIN cafe_product p ON p.id = CAST(e.metadata_json ->> 'product_id' AS integer)
WHERE e.event_type = 'added_to_cart'
  AND e.metadata_json ? 'product_id'
GROUP BY p.name
ORDER BY "Добавлений в корзину" DESC
LIMIT 10;

-- Карточки для ежедневного email-отчета
-- Важно: используем Europe/Moscow, чтобы Metabase и Django одинаково понимали "вчера".
-- Эти запросы сохраняются отдельными карточками и их ID записываются в .env.

-- METABASE_REVENUE_CARD_ID: выручка за вчера
-- Рекомендация Metabase: число.
SELECT COALESCE(SUM(total), 0) AS "Выручка"
FROM cafe_order
WHERE DATE(created_at AT TIME ZONE 'Europe/Moscow') =
      ((CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Moscow')::date - INTERVAL '1 day')
  AND status <> 'cancelled';

-- METABASE_ORDERS_CARD_ID: количество заказов за вчера
-- Рекомендация Metabase: число.
SELECT COUNT(*) AS "Количество заказов"
FROM cafe_order
WHERE DATE(created_at AT TIME ZONE 'Europe/Moscow') =
      ((CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Moscow')::date - INTERVAL '1 day')
  AND status <> 'cancelled';

-- METABASE_AVG_CHECK_CARD_ID: средний чек за вчера
-- Рекомендация Metabase: число.
SELECT COALESCE(AVG(total), 0) AS "Средний чек"
FROM cafe_order
WHERE DATE(created_at AT TIME ZONE 'Europe/Moscow') =
      ((CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Moscow')::date - INTERVAL '1 day')
  AND status <> 'cancelled';

-- METABASE_NEW_CLIENTS_CARD_ID: новые клиенты за вчера
-- Рекомендация Metabase: число.
SELECT COUNT(*) AS "Новые клиенты"
FROM auth_user
WHERE DATE(date_joined AT TIME ZONE 'Europe/Moscow') =
      ((CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Moscow')::date - INTERVAL '1 day');

-- METABASE_TOP_PRODUCTS_CARD_ID: топ-3 товара за вчера
-- Рекомендация Metabase: таблица.
SELECT
    p.name AS "Товар",
    SUM(oi.quantity) AS "Количество"
FROM cafe_orderitem oi
JOIN cafe_product p ON p.id = oi.product_id
JOIN cafe_order o ON o.id = oi.order_id
WHERE DATE(o.created_at AT TIME ZONE 'Europe/Moscow') =
      ((CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Moscow')::date - INTERVAL '1 day')
  AND o.status <> 'cancelled'
GROUP BY p.name
ORDER BY "Количество" DESC
LIMIT 3;
