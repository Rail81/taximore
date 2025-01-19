from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from functools import wraps
from ..models import db, User, Driver, Customer, Order, Subscription, SubscriptionPlan

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            return jsonify({'message': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Get dashboard statistics"""
    total_orders = Order.query.count()
    total_drivers = Driver.query.count()
    total_customers = Customer.query.count()
    active_subscriptions = Subscription.query.filter_by(status='active').count()
    
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()
    
    return jsonify({
        'statistics': {
            'total_orders': total_orders,
            'total_drivers': total_drivers,
            'total_customers': total_customers,
            'active_subscriptions': active_subscriptions
        },
        'recent_orders': [{
            'id': order.id,
            'status': order.status,
            'created_at': order.created_at.isoformat()
        } for order in recent_orders]
    })

@admin_bp.route('/subscription-plans', methods=['GET', 'POST'])
@login_required
@admin_required
def subscription_plans():
    """Manage subscription plans"""
    if request.method == 'GET':
        plans = SubscriptionPlan.query.all()
        return jsonify([{
            'id': plan.id,
            'name': plan.name,
            'price': plan.price,
            'duration_days': plan.duration_days,
            'features': plan.features,
            'is_active': plan.is_active
        } for plan in plans])
    
    data = request.json
    plan = SubscriptionPlan(
        name=data['name'],
        price=data['price'],
        duration_days=data['duration_days'],
        features=data['features']
    )
    db.session.add(plan)
    db.session.commit()
    
    return jsonify({'message': 'Subscription plan created successfully'})

@admin_bp.route('/drivers/<int:driver_id>', methods=['GET', 'PUT'])
@login_required
@admin_required
def manage_driver(driver_id):
    """Manage individual driver"""
    driver = Driver.query.get_or_404(driver_id)
    
    if request.method == 'GET':
        return jsonify({
            'id': driver.id,
            'user_id': driver.user_id,
            'status': driver.status,
            'car_class': driver.car_class,
            'rating': driver.rating,
            'subscription': {
                'active': bool(driver.subscription and driver.subscription.status == 'active'),
                'end_date': driver.subscription.end_date.isoformat() if driver.subscription else None
            }
        })
    
    data = request.json
    for key, value in data.items():
        setattr(driver, key, value)
    
    db.session.commit()
    return jsonify({'message': 'Driver updated successfully'})

@admin_bp.route('/reports')
@login_required
@admin_required
def get_reports():
    """Generate system reports"""
    # Add your report generation logic here
    return jsonify({
        'message': 'Reports generated successfully',
        'reports': []
    })
