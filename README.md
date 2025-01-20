# TaxiMore

Комплексная платформа для такси-сервиса, включающая Telegram-боты для клиентов и водителей, а также веб-панель администратора.

## Основные компоненты

### 1. Telegram-бот для клиентов
- Определение местоположения
- Ввод пункта назначения
- Расчет стоимости поездки
- Выбор класса автомобиля
- Отслеживание заказа
- История поездок
- Система отзывов

### 2. Telegram-бот для водителей
- Доступ по подписке
- Управление заказами
- Интеграция с навигацией
- Система отчетности
- Управление статусом
- Автоматическое продление подписки
- Уведомления о заказах

### 3. Веб-панель администратора
- Управление заказами
- Управление водителями
- Управление тарифами
- Система отчетности
- Мониторинг местоположения водителей
- Управление подписками
- Интеграция с платежной системой

## Технический стек

- **Backend**: Python (Flask)
- **Frontend**: React
- **Database**: PostgreSQL
- **Bots**: python-telegram-bot
- **Maps**: Google Maps API / Yandex Maps API
- **Payments**: YooKassa

## Project Structure

```
taximore/
├── backend/
│   ├── api/
│   ├── models/
│   ├── services/
│   └── utils/
├── bots/
│   ├── customer_bot/
│   └── driver_bot/
├── frontend/
│   ├── public/
│   └── src/
└── migrations/
```

## Setup Instructions

1. Clone the repository
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up environment variables:
   ```bash
   cp .env.example .env
   ```
4. Initialize the database:
   ```bash
   flask db upgrade
   ```
5. Start the services:
   ```bash
   # Start backend
   flask run
   
   # Start bots
   python bots/customer_bot/main.py
   python bots/driver_bot/main.py
   
   # Start frontend (in development)
   cd frontend && npm start
   ```

## Environment Variables

Create a `.env` file with the following variables:

```
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/taximore

# Telegram Bots
CUSTOMER_BOT_TOKEN=your_customer_bot_token
DRIVER_BOT_TOKEN=your_driver_bot_token

# Maps API
GOOGLE_MAPS_API_KEY=your_google_maps_api_key
YANDEX_MAPS_API_KEY=your_yandex_maps_api_key

# Payment System
YOOKASSA_SHOP_ID=your_shop_id
YOOKASSA_SECRET_KEY=your_secret_key

# Flask
FLASK_SECRET_KEY=your_secret_key
```

## License

MIT License
