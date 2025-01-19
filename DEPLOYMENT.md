# Развертывание TaxiMore на VPS/VDS

## 1. Подготовка сервера

```bash
# Обновление системы
apt update
apt upgrade -y

# Установка необходимых пакетов
apt install -y python3 python3-pip python3-venv postgresql nginx supervisor git certbot python3-certbot-nginx

# Установка Node.js и npm для фронтенда
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt install -y nodejs
```

## 2. Настройка PostgreSQL

```bash
# Создание базы данных и пользователя
sudo -u postgres psql

CREATE DATABASE taximore;
CREATE USER taximoreuser WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE taximore TO taximoreuser;
\q
```

## 3. Клонирование и настройка приложения

```bash
# Клонирование репозитория
cd /var/www
git clone https://github.com/Rail81/taximore.git
cd taximore

# Создание виртуального окружения
python3 -m venv venv
source venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt

# Создание и настройка .env файла
cp .env.example .env
# Отредактируйте .env файл, добавив необходимые токены и настройки
```

## 4. Настройка Supervisor

Создайте файл `/etc/supervisor/conf.d/taximore.conf`:

```ini
[program:taximore_backend]
directory=/var/www/taximore
command=/var/www/taximore/venv/bin/gunicorn -w 4 -b 127.0.0.1:8000 backend.app:create_app()
user=www-data
autostart=true
autorestart=true
stderr_logfile=/var/log/taximore/backend.err.log
stdout_logfile=/var/log/taximore/backend.out.log

[program:taximore_customer_bot]
directory=/var/www/taximore
command=/var/www/taximore/venv/bin/python bots/customer_bot/main.py
user=www-data
autostart=true
autorestart=true
stderr_logfile=/var/log/taximore/customer_bot.err.log
stdout_logfile=/var/log/taximore/customer_bot.out.log

[program:taximore_driver_bot]
directory=/var/www/taximore
command=/var/www/taximore/venv/bin/python bots/driver_bot/main.py
user=www-data
autostart=true
autorestart=true
stderr_logfile=/var/log/taximore/driver_bot.err.log
stdout_logfile=/var/log/taximore/driver_bot.out.log
```

## 5. Настройка Nginx

Создайте файл `/etc/nginx/sites-available/taximore`:

```nginx
server {
    server_name your_domain.com;

    location / {
        root /var/www/taximore/frontend/build;
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    listen 443 ssl;
    ssl_certificate /etc/letsencrypt/live/your_domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your_domain.com/privkey.pem;
}

server {
    if ($host = your_domain.com) {
        return 301 https://$host$request_uri;
    }
    listen 80;
    server_name your_domain.com;
    return 404;
}
```

## 6. Сборка фронтенда

```bash
cd /var/www/taximore/frontend
npm install
npm run build
```

## 7. Настройка SSL с помощью Certbot

```bash
certbot --nginx -d your_domain.com
```

## 8. Запуск приложения

```bash
# Создание директории для логов
mkdir -p /var/log/taximore
chown -R www-data:www-data /var/log/taximore

# Перезапуск supervisor
supervisorctl reread
supervisorctl update
supervisorctl start all

# Перезапуск nginx
systemctl restart nginx
```

## Проверка работоспособности

1. Проверьте статус сервисов:
```bash
supervisorctl status
systemctl status nginx
```

2. Проверьте логи:
```bash
tail -f /var/log/taximore/*.log
```

## Обновление приложения

```bash
cd /var/www/taximore
git pull
source venv/bin/activate
pip install -r requirements.txt
cd frontend
npm install
npm run build
supervisorctl restart all
```
