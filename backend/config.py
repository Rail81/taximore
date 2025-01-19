import os
from dotenv import load_load_dotenv

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
    
    # Maps API
    GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')
    YANDEX_MAPS_API_KEY = os.getenv('YANDEX_MAPS_API_KEY')
    
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
