# ButterCafe: короткая инструкция

## 1. Что нужно

На Windows-компьютере установите:

- Docker Desktop
- Git, если проект переносится через репозиторий

После установки откройте Docker Desktop и дождитесь, пока он полностью запустится.

Проверка в PowerShell:

```powershell
docker --version
docker compose version
```

## 2. Первый запуск проекта

Откройте PowerShell в папке проекта:

```powershell
cd "C:\путь\к\ButterCafe_Analyz"
```

Создайте `.env`:

```powershell
Copy-Item .env.docker.example .env
```

Запустите проект:

```powershell
docker compose up -d --build
```

Откройте сайт:

```text
http://localhost:8000
```

Откройте Metabase:

```text
http://localhost:3000
```

Metabase хранит свои дашборды и настройки в PostgreSQL внутри Docker, в базе:

```text
metabase
```

## 3. Создать администратора

```powershell
docker compose exec web python manage.py createsuperuser
```

Админка Django:

```text
http://localhost:8000/admin/
```

## 4. Подключить Metabase к базе проекта

В Metabase при добавлении базы укажите:

```text
Host: db
Port: 5432
Database name: buttercafe
Username: postgres
Password: значение DB_PASSWORD из .env
```

## 5. Перенести дашборды Metabase на другой компьютер

На старом компьютере:

```powershell
.\docker\export-metabase.ps1
```

Появится папка:

```text
metabase-transfer/
```

Внутри будет файл `metabase.dump`. Это дамп PostgreSQL-базы Metabase.

Скопируйте её на новый компьютер в корень проекта.

На новом компьютере:

```powershell
.\docker\import-metabase.ps1
```

Скрипт восстановит дашборды в PostgreSQL-базу `metabase` внутри Docker. Если в папке лежит старый H2-файл `metabase.db.mv.db`, скрипт попробует мигрировать его в PostgreSQL.

После этого откройте:

```text
http://localhost:3000
```

Если дашборды открылись, но графики пустые, проверьте подключение базы в Metabase: host должен быть `db`, port `5432`.

## 6. Что копировать на другой компьютер

Минимально:

```text
код проекта
.env
metabase-transfer/   # если нужны старые дашборды Metabase
media/               # если нужны картинки товаров
private_data_lake/   # если нужны локальные отчёты/выгрузки
```

Не обязательно копировать:

```text
staticfiles/
venv/
docker_data/metabase/
```

Базу ButterCafe можно не переносить, если нужна новая пустая база.

## 7. Частые команды

Запустить:

```powershell
docker compose up -d
```

Остановить:

```powershell
docker compose down
```

Пересобрать после изменений в коде:

```powershell
docker compose build --no-cache web
docker compose up -d
```

Посмотреть логи:

```powershell
docker compose logs -f web
docker compose logs -f metabase
```

Проверить контейнеры:

```powershell
docker compose ps
```

## 8. Быстрые проверки

Проверить стили:

```powershell
Invoke-WebRequest http://localhost:8000/static/css/style.css -UseBasicParsing
```

Проверить картинку сайта:

```powershell
Invoke-WebRequest http://localhost:8000/static/images/logo.svg -UseBasicParsing
```

Проверить картинку товара:

```powershell
Invoke-WebRequest http://localhost:8000/media/products/photo_2026-04-24_17-25-37.jpg -UseBasicParsing
```

Нормальный результат: `StatusCode : 200`.

## 9. Если что-то не работает

Docker не запускается:

```text
Откройте Docker Desktop и дождитесь статуса, что Docker запущен.
```

Порт занят:

```env
WEB_PORT=8001
METABASE_PORT=3001
```

После изменения `.env`:

```powershell
docker compose up -d
```

Стили или JS старые:

```text
Нажмите Ctrl+F5 в браузере.
```

Нужна подробная инструкция:

```text
DOCKER.md
```
