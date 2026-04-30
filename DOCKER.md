# Docker на Windows

Эта инструкция рассчитана на перенос проекта ButterCafe на другой Windows-компьютер через Docker Desktop.

## Что установить

1. Установите Docker Desktop for Windows.
2. Включите WSL 2 backend, если Docker Desktop попросит это сделать.
3. Перезагрузите компьютер после установки Docker/WSL.
4. Откройте Docker Desktop и дождитесь статуса `Docker Desktop is running`.

Проверка в PowerShell:

```powershell
docker --version
docker compose version
```

## Первый запуск на новом компьютере

Откройте PowerShell в папке проекта:

```powershell
cd "C:\путь\к\ButterCafe_Analyz"
```

Создайте локальный `.env` для Docker:

```powershell
Copy-Item .env.docker.example .env
```

Для локального запуска оставьте эти значения:

```env
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://localhost:8000
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
```

Запустите проект:

```powershell
docker compose up --build
```

Сайт будет доступен здесь:

```text
http://localhost:8000
```

Metabase будет доступен здесь:

```text
http://localhost:3000
```

Metabase хранит свои собственные данные не в H2-файле, а в PostgreSQL внутри Docker, в отдельной базе `metabase`.

При первичной настройке Metabase подключите базу ButterCafe так:

```text
Host: db
Port: 5432
Database name: buttercafe
Username: postgres
Password: значение DB_PASSWORD из .env
```

Если нужен администратор:

```powershell
docker compose exec web python manage.py createsuperuser
```

## Обычный запуск после первого раза

```powershell
docker compose up -d
```

Логи:

```powershell
docker compose logs -f web
docker compose logs -f db
```

Остановить без удаления данных:

```powershell
docker compose down
```

Не используйте `docker compose down -v`, если хотите сохранить базу.

## Перенос данных на другой Windows-компьютер

Надёжнее переносить PostgreSQL не копированием папки `docker_data/postgres`, а дампом базы. Копирование папки с базой часто ломается из-за прав Windows, незавершённой работы контейнера или отличий Docker Desktop.

На старом компьютере:

```powershell
New-Item -ItemType Directory -Force backups
docker compose exec db pg_dump -U postgres -d buttercafe -Fc -f /tmp/buttercafe.dump
docker compose cp db:/tmp/buttercafe.dump .\backups\buttercafe.dump
```

Скопируйте на новый компьютер:

```text
backups/buttercafe.dump
media/
private_data_lake/
.env
```

На новом компьютере запустите только базу:

```powershell
docker compose up -d db
```

Восстановите дамп:

```powershell
docker compose cp .\backups\buttercafe.dump db:/tmp/buttercafe.dump
docker compose exec db pg_restore -U postgres -d buttercafe --clean --if-exists /tmp/buttercafe.dump
```

Затем поднимите весь проект:

```powershell
docker compose up -d --build
```

## Если нужно перенести только Metabase

Можно оставить базу ButterCafe новой, а перенести только Metabase: пользователей, карточки, дашборды, коллекции и embed secret. Metabase хранит эти данные в отдельной PostgreSQL-базе `metabase` внутри Docker.

На старом компьютере:

```powershell
.\docker\export-metabase.ps1
```

Скрипт создаст папку:

```text
metabase-transfer/
```

Внутри будет файл:

```text
metabase.dump
```

Скопируйте на новый компьютер:

```text
metabase-transfer/
.env
media/              # если нужны картинки товаров
private_data_lake/  # если нужны локальные отчёты
```

На новом компьютере положите `metabase-transfer/` в корень проекта и выполните:

```powershell
.\docker\import-metabase.ps1
```

Скрипт восстановит дамп в PostgreSQL-базу `metabase` внутри Docker. Если в `metabase-transfer/` лежит старый H2-файл `metabase.db.mv.db`, скрипт попробует мигрировать его в PostgreSQL.

После импорта откройте:

```text
http://localhost:3000
```

Если дашборды открылись, но графики пустые или база недоступна, в Metabase откройте `Admin settings` -> `Databases` -> база ButterCafe и поставьте:

```text
Host: db
Port: 5432
Database name: buttercafe
Username: postgres
Password: значение DB_PASSWORD из .env
```

## Частые ошибки и решения

### `Docker daemon is not running`

Docker Desktop не запущен или ещё стартует. Откройте Docker Desktop, дождитесь полного запуска и повторите команду.

### `exec /app/docker/entrypoint.sh: no such file or directory`

На Windows это часто вызвано CRLF-окончаниями строк в shell-скрипте. В Dockerfile уже добавлена очистка CRLF при сборке. Пересоберите образ:

```powershell
docker compose build --no-cache web
docker compose up
```

### Порт `8000` уже занят

В `.env` поменяйте порт:

```env
WEB_PORT=8001
```

И откройте:

```text
http://localhost:8001
```

### Сайт перекидывает на HTTPS или не входит в админку

Для локального Docker должны быть выключены HTTPS-флаги:

```env
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
SECURE_HSTS_SECONDS=0
```

После изменения `.env` перезапустите:

```powershell
docker compose up -d --force-recreate web
```

### Не загружаются стили или админка выглядит без CSS

В Docker приложение запускается через Gunicorn, а Gunicorn сам не раздаёт Django static files. Для этого в проект добавлен WhiteNoise. После обновления проекта на другом компьютере пересоберите образ:

```powershell
docker compose down
docker compose up -d --build
```

В `docker-compose.yml` папка `staticfiles` не пробрасывается с Windows в контейнер. Это сделано специально: собранная статика должна жить внутри контейнера, а не зависеть от локальной Windows-папки.

Проверьте, что внутри контейнера выполнился `collectstatic`:

```powershell
docker compose logs web
```

Быстрая проверка CSS:

```powershell
Invoke-WebRequest http://localhost:8000/static/css/style.css -UseBasicParsing
```

В ответе должен быть код `200`, а не `404`.

Если в браузере всё ещё старый вид без CSS, откройте страницу с жёстким обновлением: `Ctrl+F5`.

### Не загружаются картинки товаров

Картинки из дизайна сайта лежат в `cafe/static/images` и попадают в Docker-образ вместе с кодом. Картинки товаров, загруженные через админку, лежат в папке `media/` и открываются по адресам `/media/...`.

Для локального Docker включена раздача media-файлов через Django:

```env
SERVE_MEDIA_FILES=True
```

При переносе на другой компьютер скопируйте папку:

```text
media/
```

Проверьте конкретную картинку:

```powershell
Invoke-WebRequest http://localhost:8000/media/products/photo_2026-04-24_17-25-37.jpg -UseBasicParsing
```

В ответе должен быть код `200`. Если код `404`, значит файл не скопирован в `media/products/` или в базе указан другой путь к картинке.

### `database files are incompatible` или PostgreSQL не стартует после копирования `docker_data`

Не переносите папку `docker_data/postgres` между компьютерами. Сделайте дамп через `pg_dump` на старом компьютере и восстановите его через `pg_restore` на новом.

### `password authentication failed for user "postgres"`

Пароль в `.env` не совпадает с паролем, с которым уже была создана база. Для новой пустой базы можно остановить проект, удалить локальную папку `docker_data/postgres` и запустить заново. Для базы с нужными данными используйте правильный старый `DB_PASSWORD`.

### Ошибка сборки после переноса проекта из архива

Пересоберите без кэша:

```powershell
docker compose down
docker compose build --no-cache
docker compose up
```

## Полезные команды

```powershell
docker compose ps
docker compose exec web python manage.py migrate
docker compose exec web python manage.py collectstatic --noinput
docker compose exec web python manage.py createsuperuser
docker compose logs -f web
```
