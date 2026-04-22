-- Dashboard 1: Sales
-- Revenue by day
SELECT DATE(created_at) AS day, SUM(total) AS revenue
FROM cafe_order
GROUP BY DATE(created_at)
ORDER BY day;

-- Orders count by day
SELECT DATE(created_at) AS day, COUNT(*) AS orders_count
FROM cafe_order
GROUP BY DATE(created_at)
ORDER BY day;

-- Average check by day
SELECT DATE(created_at) AS day, AVG(total) AS avg_check
FROM cafe_order
GROUP BY DATE(created_at)
ORDER BY day;

-- Dashboard 2: Products
-- Top products by revenue
SELECT p.name AS product_name, SUM(oi.quantity * oi.price) AS revenue
FROM cafe_orderitem oi
JOIN cafe_product p ON p.id = oi.product_id
GROUP BY p.name
ORDER BY revenue DESC
LIMIT 10;

-- Top products by quantity
SELECT p.name AS product_name, SUM(oi.quantity) AS quantity
FROM cafe_orderitem oi
JOIN cafe_product p ON p.id = oi.product_id
GROUP BY p.name
ORDER BY quantity DESC
LIMIT 10;

-- Product margin (price - cost_price)
SELECT name, price, cost_price, (price - COALESCE(cost_price, 0)) AS margin
FROM cafe_product
ORDER BY margin DESC;

-- Dashboard 3: Clients
-- New clients by day
SELECT DATE(date_joined) AS day, COUNT(*) AS new_clients
FROM auth_user
GROUP BY DATE(date_joined)
ORDER BY day;

-- Repeat purchases by customer
SELECT u.username, COUNT(o.id) AS orders_count, SUM(o.total) AS total_spent
FROM cafe_order o
JOIN auth_user u ON u.id = o.user_id
WHERE o.user_id IS NOT NULL
GROUP BY u.username
HAVING COUNT(o.id) > 1
ORDER BY orders_count DESC, total_spent DESC;

-- Simple RFM source
SELECT
    u.id AS user_id,
    u.username,
    MAX(o.created_at) AS last_order_at,
    COUNT(o.id) AS frequency,
    SUM(o.total) AS monetary
FROM auth_user u
LEFT JOIN cafe_order o ON o.user_id = u.id
GROUP BY u.id, u.username;

-- Dashboard 4: Time
-- Peak hours by orders
SELECT EXTRACT(HOUR FROM created_at) AS hour_of_day, COUNT(*) AS orders_count
FROM cafe_order
GROUP BY hour_of_day
ORDER BY hour_of_day;

-- Revenue by day of week
SELECT EXTRACT(DOW FROM created_at) AS day_of_week, SUM(total) AS revenue
FROM cafe_order
GROUP BY day_of_week
ORDER BY day_of_week;
