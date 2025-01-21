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

## 5. Настройка Redis для кэширования

```bash
# Установка Redis
apt install -y redis-server

# Настройка Redis для работы с внешними подключениями
sed -i 's/bind 127.0.0.1/bind 0.0.0.0/' /etc/redis/redis.conf
sed -i 's/# requirepass foobared/requirepass your_redis_password/' /etc/redis/redis.conf

# Перезапуск Redis
systemctl restart redis-server

# Проверка статуса
systemctl status redis-server

# Создание директории для кэша карт
mkdir -p /var/www/taximore/cache/osm
chown -R www-data:www-data /var/www/taximore/cache
```

Добавьте в .env файл следующие переменные:
```bash
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=your_redis_password
```

## 6. Настройка Nginx

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

## 7. Сборка фронтенда

```bash
cd /var/www/taximore/frontend
npm install
npm run build
```

## 8. Настройка SSL с помощью Certbot

```bash
certbot --nginx -d your_domain.com
```

## 9. Запуск приложения

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

## 10. Настройка платежной системы (YooKassa)

```bash
# Создание директории для логов платежной системы
mkdir -p /var/log/taximore/payments
chown -R www-data:www-data /var/log/taximore/payments
```

Добавьте в .env файл следующие переменные:
```bash
YOOKASSA_SHOP_ID=your_shop_id
YOOKASSA_SECRET_KEY=your_secret_key
PAYMENT_WEBHOOK_URL=https://your-domain.com/api/payment/webhook
```

## 11. Настройка логирования

```bash
# Создание директорий для логов
mkdir -p /var/log/taximore/{app,payments,geo,subscriptions}
chown -R www-data:www-data /var/log/taximore

# Настройка ротации логов
cat > /etc/logrotate.d/taximore << EOF
/var/log/taximore/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 www-data www-data
    sharedscripts
    postrotate
        systemctl reload supervisor
    endscript
}
EOF
```

## 12. Настройка мониторинга

```bash
# Установка Prometheus Node Exporter
apt install -y prometheus-node-exporter

# Установка Prometheus
apt install -y prometheus

# Настройка алертов для критических сервисов
cat > /etc/prometheus/alerts.yml << EOF
groups:
- name: taximore
  rules:
  - alert: ServiceDown
    expr: up == 0
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "Service {{ \$labels.job }} is down"
  - alert: HighErrorRate
    expr: rate(http_requests_total{status=~"5.."}[5m]) > 1
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High error rate detected"
EOF
```

## 13. Настройка резервного копирования

```bash
# Создание скрипта для бэкапа
cat > /usr/local/bin/backup_taximore.sh << EOF
#!/bin/bash
BACKUP_DIR="/var/backups/taximore"
TIMESTAMP=\$(date +%Y%m%d_%H%M%S)

# Бэкап базы данных
pg_dump taximore > "\$BACKUP_DIR/db_\$TIMESTAMP.sql"

# Бэкап конфигурации
tar -czf "\$BACKUP_DIR/config_\$TIMESTAMP.tar.gz" /var/www/taximore/.env /etc/supervisor/conf.d/taximore.conf

# Удаление старых бэкапов (старше 30 дней)
find "\$BACKUP_DIR" -type f -mtime +30 -delete
EOF

chmod +x /usr/local/bin/backup_taximore.sh

# Добавление в cron
echo "0 3 * * * root /usr/local/bin/backup_taximore.sh" > /etc/cron.d/taximore-backup
```

## 14. Проверка развертывания

```bash
# Проверка статуса всех сервисов
systemctl status nginx
systemctl status postgresql
systemctl status supervisor
systemctl status prometheus
systemctl status prometheus-node-exporter

# Проверка логов
tail -f /var/log/taximore/app/app.log
tail -f /var/log/taximore/payments/payment.log
tail -f /var/log/taximore/geo/geo.log
tail -f /var/log/taximore/subscriptions/subscription.log

# Проверка доступности API
curl -I https://your-domain.com/api/health
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
