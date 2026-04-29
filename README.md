# ButterCafe

Сайт кафе ButterCafe на Django с PostgreSQL.

## Установка

Рекомендуемая версия Python: 3.12 или 3.13. Если вы используете Python 3.13, нужны более свежие версии зависимостей, чем в старых примерах установки.

1. Создайте виртуальное окружение:
```bash
python -m venv venv
```

2. Активируйте виртуальное окружение:
- Windows:
```bash
.\venv\Scripts\Activate.ps1
```

Если PowerShell блокирует запуск сценариев, выполните сначала:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Или используйте cmd:
```bat
venv\Scripts\activate.bat
```
- Linux/Mac:
```bash
source venv/bin/activate
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

4. Создайте файл .env в корневой директории проекта и добавьте следующие переменные:
```
DEBUG=True
SECRET_KEY=replace-with-local-secret-key
DB_NAME=buttercafe
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432

# Локальная папка для выгрузок с персональными данными.
# По умолчанию используется private_data_lake/, она исключена из git.
ANALYTICS_EXPORT_ROOT=private_data_lake

# SMTP для ежедневного отчета
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_HOST_USER=report@example.com
EMAIL_HOST_PASSWORD=your_password
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=report@example.com
OWNER_REPORT_EMAIL=owner@example.com

# Metabase API (опционально, если хотим забирать метрики оттуда)
METABASE_URL=http://localhost:3000
METABASE_USERNAME=admin@example.com
METABASE_PASSWORD=metabase_password
METABASE_DASHBOARD_ID=
METABASE_EMBED_SECRET=
METABASE_EMBED_THEME=light
METABASE_REVENUE_CARD_ID=
METABASE_ORDERS_CARD_ID=
METABASE_AVG_CHECK_CARD_ID=
METABASE_NEW_CLIENTS_CARD_ID=
METABASE_TOP_PRODUCTS_CARD_ID=
```

5. Создайте базу данных PostgreSQL с именем buttercafe

6. Примените миграции:
```bash
python manage.py migrate
```

7. Создайте суперпользователя:
```bash
python manage.py createsuperuser
```

8. Запустите сервер разработки:
```bash
python manage.py runserver
```

## Локальная аналитика

### Ежедневная выгрузка данных

```bash
python manage.py export_daily_analytics
```

Файлы создаются в папке:

```
private_data_lake/YYYY/MM/DD/orders.csv
private_data_lake/YYYY/MM/DD/orders.json
private_data_lake/YYYY/MM/DD/events.csv
```

### Ежедневный email-отчет

```bash
python manage.py generate_daily_report
```

Команда пытается получить метрики из Metabase API. Если Metabase не настроен или недоступен,
автоматически используется fallback на локальные данные PostgreSQL.

### Metabase дашборды

1. Поднимите Metabase локально:

```bash
docker run -d --name metabase -p 3000:3000 metabase/metabase
```

2. Подключите PostgreSQL базу проекта в интерфейсе Metabase.
3. Создайте карточки для дашбордов, используя SQL из файла:

`docs/metabase_dashboard_queries.sql`

4. В Metabase включите embedding, скопируйте embed secret и ID основного дашборда в `.env`:

```
METABASE_DASHBOARD_ID=1
METABASE_EMBED_SECRET=your-metabase-embed-secret
```

5. Встроенный BI-раздел доступен в Django Admin:

`/admin/metabase/`

Карточки `METABASE_REVENUE_CARD_ID`, `METABASE_ORDERS_CARD_ID`, `METABASE_AVG_CHECK_CARD_ID`, `METABASE_NEW_CLIENTS_CARD_ID`, `METABASE_TOP_PRODUCTS_CARD_ID` используются командой `generate_daily_report`. Если они не заданы или Metabase недоступен, отчет строится по локальной PostgreSQL базе.

### Диаграммы в админке

Для просмотра ключевых графиков прямо в Django Admin откройте:

`/admin/analytics/`

Скачать аналитический отчет в PDF можно по адресу:

`/admin/analytics/pdf/`

Доступ только для staff/superuser.
