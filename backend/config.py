import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Flask
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'your-secret-key')
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'postgresql://localhost/taximore')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Telegram
    CUSTOMER_BOT_TOKEN = os.getenv('CUSTOMER_BOT_TOKEN')
    DRIVER_BOT_TOKEN = os.getenv('DRIVER_BOT_TOKEN')
    
    # City Boundaries (example for Moscow)
    CITY_BOUNDS = {
        'north': 56.0,
        'south': 55.5,
        'west': 37.0,
        'east': 38.0
    }
    
    # YooKassa
    YOOKASSA_SHOP_ID = os.getenv('YOOKASSA_SHOP_ID')
    YOOKASSA_SECRET_KEY = os.getenv('YOOKASSA_SECRET_KEY')
    
    # Application Settings
    DEFAULT_LANGUAGE = 'ru'
    TIMEZONE = 'Europe/Moscow'
    
    # Subscription Settings
    SUBSCRIPTION_GRACE_PERIOD_DAYS = 3
    
    # Cache Settings
    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 300
    
    # Security Settings
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-jwt-secret-key')
    JWT_ACCESS_TOKEN_EXPIRES = 3600  # 1 hour
    PASSWORD_SALT = os.getenv('PASSWORD_SALT', 'your-password-salt')
    
    # Rate Limiting
    RATELIMIT_ENABLED = True
    RATELIMIT_DEFAULT = "100/hour"
    RATELIMIT_STORAGE_URL = "memory://"
    
    # CORS Settings
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*').split(',')
    CORS_METHODS = ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
    CORS_ALLOW_HEADERS = ['Content-Type', 'Authorization']
    
    # Security Headers
    SECURITY_HEADERS = {
        'X-Frame-Options': 'SAMEORIGIN',
        'X-XSS-Protection': '1; mode=block',
        'X-Content-Type-Options': 'nosniff',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Content-Security-Policy': "default-src 'self'"
    }
    
    # Logging
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_DIR = '/var/log/taximore'
