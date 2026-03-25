# My Cube

Базовый каркас Django-платформы для соревновательной сборки кубика Рубика.

Сейчас в проекте готовы:
- авторизация и регистрация;
- редирект на главную после входа;
- dashboard с полноэкранным canvas-задником;
- левое выезжающее меню;
- базовые анимации загрузки интерфейса;
- подготовка к дальнейшей интеграции Three.js.

## Стек

- Python 3.11
- Django 5.2
- PostgreSQL
- обычные Django templates + static files

## База данных

Проект настроен на **PostgreSQL 14** (порт 5433). Настройки берутся из переменных окружения:

- POSTGRES_DB
- POSTGRES_USER
- POSTGRES_PASSWORD
- POSTGRES_HOST
- POSTGRES_PORT

Значения по умолчанию в [config/settings.py](config/settings.py):

- база: my_cube
- пользователь: postgres
- пароль: postgres
- хост: localhost
- порт: 5433

**Предварительно требуется:**
1. PostgreSQL 14+ должна быть установлена и запущена на порту 5433.
2. Пользователь `postgres` с паролем `postgres` должен существовать.
3. База `my_cube` должна быть создана.

Пример создания базы:

```bash
psql -h localhost -p 5433 -U postgres -d postgres -c "CREATE DATABASE my_cube;"
```

## Запуск

1. Активировать виртуальное окружение.
2. Установить зависимости: `pip install -r requirements.txt`.
3. Убедиться, что PostgreSQL запущена и база создана.
4. Выполнить миграции:

```bash
python manage.py migrate
```

5. Запустить сервер:

```bash
python manage.py runserver
```

Сервер запустится на `http://localhost:8000/`.

## Запуск через Docker

В репозитории есть `Dockerfile` и `docker-compose.yml`.

Особенность: контейнер backend автоматически подтягивает фронтовые файлы из соседнего репозитория:

- `../frontend_repo/templates/main` → `main/templates/main`
- `../frontend_repo/static/main` → `main/static/main`

То есть структура папок должна быть такой:

```text
my_cube_split/
  frontend_repo/
  backend_repo/
```

### Команды

Из папки `backend_repo`:

```bash
docker compose up --build
```

После старта:

- Django: `http://localhost:8000/`
- PostgreSQL внутри compose: порт `5433` на хосте

Остановка:

```bash
docker compose down
```

## Текущая структура интерфейса

### Авторизация и регистрация

- Шаблон: [main/templates/main/auth.html](main/templates/main/auth.html)
- Формы: [main/forms.py](main/forms.py)
- Валидация на регистрации:
  - **Серверная:** класс `RegisterForm.clean_password1()` проверяет требования к паролю.
  - **Клиентская:** интерактивная подсветка требований при вводе в поле пароля (см. [main/static/main/js/app.js](main/static/main/js/app.js)).
  - Требования: минимум 8 символов, заглавная буква, строчная буква, цифра.
- Анимация при загрузке: плавное появление форм и фона.

### Главная страница (Dashboard)

- Шаблон: [main/templates/main/dashboard.html](main/templates/main/dashboard.html)
- Стили: [main/static/main/css/styles.css](main/static/main/css/styles.css)
- Скрипты: [main/static/main/js/app.js](main/static/main/js/app.js)

На главной:
- **Canvas фоном:** полноэкранный canvas занимает весь viewport и лежит под всеми UI-элементами.
- **Все элементы поверх canvas:**
  - Левый верхний угол: кнопка открытия меню (иконка 3×3) с hover-анимацией.
  - Правый верхний угол: профиль (буква пользователя в кружке) и таймер (иконка + цифры).
  - Левое меню: выезжает справа налево, содержит вкладки "Сборка кубика", "Управление", "Комнаты", "Обучение" и кнопку "Выйти".
  - Нижний правый угол: статус сборки.
- **Анимации загрузки:** все элементы появляются с плавным переходом, canvas разворачивается из zoom-state.

## Реализованные требования

✅ **PostgreSQL:** проект полностью переведен на PostgreSQL 14 (порт 5433).  
✅ **Документация:** этот README и комментарии в коде описывают архитектуру.  
✅ **Валидация пароля:** серверная + клиентская с визуальной подсветкой требований.  
✅ **Canvas фоном:** полноэкранный, все UI поверх него.  
✅ **Анимации загрузки:** при загрузке страниц все элементы плавно появляются.

## Ближайшие логичные шаги

1. **Three.js интеграция:** подключить Three.js и заменить заглушку canvas на реальную 3D-сцену кубика.
2. **Таймер реальный:** сделать работающий таймер сборки с запуском/остановкой.
3. **Профиль:** создать модель профиля, статистику пользователя, страницу редактирования.
4. **Комнаты:** реализовать комнаты для соревнований, механику присоединения/создания.
5. **Обучение:** добавить страницу обучения с формулами сборки.
6. **Управление:** настройки аккаунта, язык, уведомления.

## Troubleshooting

### PostgreSQL 14 на порту 5433 не подключается

Если видите ошибку подключения:

```
psycopg.OperationalError: connection failed: connection to server at "localhost", port 5433 failed
```

Проверьте:
1. PostgreSQL 14 запущена: `Get-Service postgresql-x64-14`
2. Пользователь `postgres` с паролем `postgres` существует.
3. База `my_cube` создана: `psql -h localhost -p 5433 -U postgres -d postgres -c "CREATE DATABASE my_cube;"`

Если пароль забыли, см. инструкцию ниже.

### Сброс пароля postgres на Windows

1. Откройте `pg_hba.conf` для PostgreSQL 14 (обычно `C:\Program Files\PostgreSQL\14\data\pg_hba.conf`).
2. Найдите строку `host    all    all    127.0.0.1/32    scram-sha-256` и измените на `trust`:

```conf
host    all    all    127.0.0.1/32    trust
```

3. Перезапустите сервис (требует права администратора):

```powershell
Restart-Service postgresql-x64-14 -Force
```

4. Подключитесь и установите новый пароль:

```powershell
& 'C:\Program Files\PostgreSQL\14\bin\psql.exe' -h localhost -p 5433 -U postgres -d postgres
```

В интерпретаторе выполните:

```sql
ALTER USER postgres WITH PASSWORD 'postgres';
\q
```

5. Измените `pg_hba.conf` обратно на `scram-sha-256`.
6. Перезапустите сервис снова.