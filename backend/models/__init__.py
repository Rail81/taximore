from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), nullable=False)  # 'admin', 'driver', 'customer'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Driver(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    telegram_id = db.Column(db.String(100), unique=True)
    car_class = db.Column(db.String(50))
    license_plate = db.Column(db.String(20))
    status = db.Column(db.String(20), default='offline')  # 'offline', 'online', 'busy'
    current_location_lat = db.Column(db.Float)
    current_location_lon = db.Column(db.Float)
    rating = db.Column(db.Float, default=5.0)
    
class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    telegram_id = db.Column(db.String(100), unique=True)
    phone = db.Column(db.String(20))
    rating = db.Column(db.Float, default=5.0)

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    driver_id = db.Column(db.Integer, db.ForeignKey('driver.id'), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey('subscription_plan.id'), nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False)  # 'active', 'expired', 'cancelled'
    auto_renew = db.Column(db.Boolean, default=True)

class SubscriptionPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    duration_days = db.Column(db.Integer, nullable=False)
    features = db.Column(db.JSON)
    is_active = db.Column(db.Boolean, default=True)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    driver_id = db.Column(db.Integer, db.ForeignKey('driver.id'))
    pickup_location_lat = db.Column(db.Float, nullable=False)
    pickup_location_lon = db.Column(db.Float, nullable=False)
    dropoff_location_lat = db.Column(db.Float, nullable=False)
    dropoff_location_lon = db.Column(db.Float, nullable=False)
    pickup_address = db.Column(db.String(200))
    dropoff_address = db.Column(db.String(200))
    status = db.Column(db.String(20), nullable=False)  # 'pending', 'accepted', 'in_progress', 'completed', 'cancelled'
    car_class = db.Column(db.String(50))
    estimated_price = db.Column(db.Float)
    final_price = db.Column(db.Float)
    distance = db.Column(db.Float)  # in kilometers
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    from_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    to_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscription.id'))
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'))
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False)  # 'pending', 'completed', 'failed'
    payment_method = db.Column(db.String(50))
    transaction_id = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class FareRule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    car_class = db.Column(db.String(50), nullable=False)
    base_fare = db.Column(db.Float, nullable=False)
    per_km_city = db.Column(db.Float, nullable=False)
    per_km_suburb = db.Column(db.Float, nullable=False)
    minimum_fare = db.Column(db.Float, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
