# Salon API — онлайн-запис до салону краси

Лабораторна робота №2: шарова архітектура та доменна модель.

REST API для запису клієнтів до майстрів салону: реєстрація та вхід (JWT), керування майстрами та їхнім графіком роботи, створення, перенесення, скасування і завершення записів з перевіркою бізнес-правил.

Порівняно з лабою 1 API не змінився — змінилася внутрішня архітектура: 4 шари, доменна модель окремо від ORM, фабрики, доменні помилки.

| Документ | Опис |
|---|---|
| [docs/use-cases.md](docs/use-cases.md) | сценарії використання та бізнес-правила |
| [docs/adr/0001-rich-domain-model.md](docs/adr/0001-rich-domain-model.md) | ADR: чому Rich Domain Model |
| [docs/analysis/lab2.md](docs/analysis/lab2.md) | аналіз: порівняння з лабою 1 |

## Стек

| Що | Чим |
|---|---|
| Мова | Python 3.13 |
| Веб-фреймворк | FastAPI |
| База даних | MySQL 8 |
| ORM | SQLAlchemy 2 (драйвер PyMySQL) |
| Валідація | Pydantic |
| Автентифікація | JWT (PyJWT), паролі — bcrypt |
| Тести | pytest, FastAPI TestClient |

## Архітектура

```
Presentation  →  Application  →  Domain  ←  Infrastructure
 (FastAPI)       (use cases)    (бізнес-     (MySQL, ORM,
                                 логіка)      bcrypt, JWT)
```

Домен не залежить ні від чого: ні від БД, ні від фреймворку. Він визначає інтерфейси (порти), а Infrastructure їх реалізує (DIP). Правило залежностей перевіряє тест `tests/unit/test_architecture.py`.

```
salon.lab2/
├── app/
│   ├── main.py                     # точка входу, збирання шарів
│   ├── domain/                     # ── Domain: не імпортує нічого з інших шарів
│   │   ├── entities.py             #    Client, Specialist (+WorkingDay), Appointment
│   │   ├── value_objects.py        #    Email, Phone, TimeRange, WorkingHours
│   │   ├── factories.py            #    ClientFactory, AppointmentFactory, BookingPolicy
│   │   ├── ports.py                #    інтерфейси репозиторіїв, PasswordHasher, Clock, UnitOfWork
│   │   └── errors.py               #    DomainError та нащадки
│   ├── application/                # ── Application: use cases
│   │   └── services.py             #    AuthService, SpecialistService, AppointmentService
│   ├── infrastructure/             # ── Infrastructure: реалізації портів
│   │   ├── config.py               #    налаштування з .env
│   │   ├── security.py             #    bcrypt, JWT, системний годинник
│   │   └── db/
│   │       ├── database.py         #    підключення до MySQL
│   │       ├── orm_models.py       #    таблиці (ClientORM, SpecialistORM, …)
│   │       ├── mappers.py          #    ORM ↔ домен
│   │       └── repositories.py     #    SQLAlchemy-репозиторії, UnitOfWork
│   └── presentation/api/           # ── Presentation: HTTP
│       ├── routers/                #    контролери: auth, specialists, appointments
│       ├── schemas.py              #    DTO запитів і відповідей
│       ├── errors.py               #    доменні помилки → HTTP-статуси
│       └── dependencies.py         #    DI: збирання сервісів, поточний користувач
├── tests/
│   ├── fakes.py                    # in-memory репозиторії, FixedClock
│   ├── unit/                       # без БД і HTTP: domain, application, архітектура
│   └── integration/                # HTTP-ендпоінти з базою salon_test
└── docs/
```

### Доменні помилки → HTTP

| Доменна помилка | HTTP |
|---|---|
| `InvariantViolation` | 400 |
| `AuthenticationFailed` | 401 |
| `PermissionDenied` | 403 |
| `NotFound` | 404 |
| `Conflict` | 409 |

## Запуск

### 1. Підготувати MySQL

Потрібен запущений MySQL 8. Створіть дві бази — робочу і для тестів (наприклад, у MySQL Workbench):

```sql
CREATE DATABASE salon CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE salon_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Таблиці створюються автоматично під час першого запуску сервера.

### 2. Встановити залежності

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # Windows (PowerShell)
# source .venv/bin/activate         # Linux / macOS
pip install -r requirements.txt
```

### 3. Налаштувати `.env`

Скопіюйте `.env.example` у `.env` і впишіть свої значення:

| Змінна | Опис |
|---|---|
| `DB_HOST`, `DB_PORT` | адреса MySQL (за замовчуванням `127.0.0.1:3306`) |
| `DB_USER`, `DB_PASSWORD` | користувач і пароль MySQL |
| `DB_NAME` | робоча база (`salon`) |
| `TEST_DB_NAME` | база для тестів (`salon_test`) |
| `JWT_SECRET` | секрет для підпису токенів — довгий випадковий рядок |
| `JWT_EXPIRE_MINUTES` | час життя токена |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | адміністратор, який створюється під час старту |

### 4. Запустити сервер

```powershell
uvicorn app.main:app --reload
```

- API: http://127.0.0.1:8000
- Інтерактивна документація (Swagger): http://127.0.0.1:8000/docs
- Перевірка стану: http://127.0.0.1:8000/health

## Як користуватися

1. Зареєструйтеся: `POST /auth/register` (роль — клієнт) або увійдіть як адміністратор з `.env`.
2. Отримайте токен: `POST /auth/login`.
3. У Swagger натисніть **Authorize** і вставте токен. Без токена всі ендпоінти, крім реєстрації та входу, повертають **401**.

## Тестування

```powershell
pytest                    # усі тести (140)
pytest tests/unit         # unit-тести — працюють БЕЗ MySQL і без HTTP-сервера
pytest tests/integration  # integration-тести — потрібна база salon_test
```

| Рівень | Що перевіряють | К-сть |
|---|---|---|
| Unit: domain | value objects, поведінка сутностей, фабрики з in-memory репозиторіями | 61 |
| Unit: application | use cases з in-memory репозиторіями та фіксованим годинником | 18 |
| Unit: infrastructure, архітектура | bcrypt, JWT; правило залежностей між шарами | 9 |
| Integration | усі ендпоінти через HTTP з реальною MySQL | 52 |

Unit-тести не потребують бази: репозиторії замінено in-memory реалізаціями тих самих інтерфейсів (`tests/fakes.py`), а поточний час — `FixedClock`.

## API

| Метод і шлях | Доступ | Опис |
|---|---|---|
| `POST /auth/register` | усі | реєстрація клієнта |
| `POST /auth/login` | усі | вхід, повертає JWT |
| `GET /clients/me` | авторизовані | профіль поточного користувача |
| `GET /specialists` | авторизовані | список майстрів (`?specialization=`) |
| `GET /specialists/{id}` | авторизовані | майстер з графіком |
| `POST /specialists` | адмін | створити майстра |
| `PUT /specialists/{id}` | адмін | змінити майстра |
| `PATCH /specialists/{id}/deactivate` | адмін | деактивувати майстра |
| `DELETE /specialists/{id}` | адмін | видалити майстра |
| `POST /specialists/{id}/schedule` | адмін | додати робочий день |
| `PUT /schedules/{id}` | адмін | змінити робочий день |
| `DELETE /schedules/{id}` | адмін | видалити робочий день |
| `POST /appointments` | авторизовані | записатися до майстра |
| `GET /appointments` | авторизовані | свої записи (адмін — усі); `?status=&specialist_id=&day=` |
| `GET /appointments/{id}` | авторизовані | деталі запису |
| `PATCH /appointments/{id}` | власник / адмін | перенести або змінити коментар |
| `POST /appointments/{id}/cancel` | власник / адмін | скасувати |
| `POST /appointments/{id}/complete` | адмін | позначити виконаним |

### Коди відповідей

| Код | Коли |
|---|---|
| 200 / 201 / 204 | успіх / створено / видалено |
| 400 | невалідні дані або порушення бізнес-правила (час у минулому, поза графіком тощо) |
| 401 | немає токена, токен невалідний або прострочений, невірний логін |
| 403 | дія доступна лише адміністратору |
| 404 | ресурс не існує (або це чужий запис) |
| 409 | конфлікт: email зайнятий, час зайнятий, неприпустима зміна статусу |

## Бізнес-правила (інваріанти)

- email валідний (400) і унікальний (409); пароль — від 8 символів;
- у графіку початок раніше за кінець; один запис графіка на день тижня для майстра (409);
- запис: початок раніше за кінець, в один день, не в минулому;
- запис лише до активного майстра і в межах його робочих годин;
- запис не перетинається з іншими активними записами майстра (409);
- змінити або скасувати можна лише запис у статусі `booked`; клієнт — не пізніше ніж за 2 години до початку;
- не можна видалити майстра з майбутніми активними записами (409).

Повний перелік з посиланнями на юзкейси — у [docs/use-cases.md](docs/use-cases.md).
