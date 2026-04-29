# Docker deployment

Проект можно перенести на другой компьютер вместе с локальными данными через Docker Compose.

## Первый запуск

1. Подготовьте переменные окружения:

```bash
cp .env.docker.example .env
```

Поменяйте `SECRET_KEY`, `DB_PASSWORD`, `ALLOWED_HOSTS` и, если нужен реальный домен, `CSRF_TRUSTED_ORIGINS`.

2. Соберите и запустите контейнеры:

```bash
docker compose up --build
```

Приложение будет доступно по адресу:

```text
http://localhost:8000
```

3. Создайте администратора:

```bash
docker compose exec web python manage.py createsuperuser
```

## Перенос без потери данных

Копируйте на другой компьютер весь проект и эти папки:

```text
docker_data/
media/
private_data_lake/
```

`docker_data/postgres` хранит базу PostgreSQL, `media` хранит загруженные изображения, `private_data_lake` хранит выгрузки и локальные отчеты.

Остановить контейнеры без удаления данных:

```bash
docker compose down
```

Не запускайте `docker compose down -v`, если хотите сохранить базу.

## Перенос существующей локальной PostgreSQL базы в Docker

Если до Docker проект уже работал с PostgreSQL на компьютере, база не лежит в папке проекта. Сначала сделайте дамп:

```bash
pg_dump -h localhost -p 5432 -U postgres -Fc -d buttercafe -f buttercafe.dump
```

Запустите Docker-базу:

```bash
docker compose up -d db
```

Скопируйте дамп в контейнер и восстановите:

```bash
docker compose cp buttercafe.dump db:/tmp/buttercafe.dump
docker compose exec db pg_restore -U postgres -d buttercafe --clean --if-exists /tmp/buttercafe.dump
```

После этого запускайте приложение:

```bash
docker compose up --build
```

## Полезные команды

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py collectstatic --noinput
docker compose exec web python manage.py createsuperuser
docker compose logs -f web
```
