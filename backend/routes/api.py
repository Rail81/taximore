from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from ..models import db, Order, Driver, Customer, FareRule, Subscription
from datetime import datetime

api_bp = Blueprint('api', __name__)

@api_bp.route('/orders', methods=['GET'])
@login_required
def get_orders():
    """Get list of orders with filtering"""
    status = request.args.get('status')
    query = Order.query
    
    if status:
        query = query.filter_by(status=status)
    
    orders = query.order_by(Order.created_at.desc()).all()
    return jsonify([{
        'id': order.id,
        'customer_id': order.customer_id,
        'driver_id': order.driver_id,
        'status': order.status,
        'pickup_address': order.pickup_address,
        'dropoff_address': order.dropoff_address,
        'estimated_price': order.estimated_price,
        'final_price': order.final_price,
        'created_at': order.created_at.isoformat()
    } for order in orders])

@api_bp.route('/drivers', methods=['GET'])
@login_required
def get_drivers():
    """Get list of drivers with their current status"""
    drivers = Driver.query.all()
    return jsonify([{
        'id': driver.id,
        'user_id': driver.user_id,
        'status': driver.status,
        'car_class': driver.car_class,
        'rating': driver.rating,
        'current_location': {
            'lat': driver.current_location_lat,
            'lon': driver.current_location_lon
        } if driver.current_location_lat and driver.current_location_lon else None
    } for driver in drivers])

@api_bp.route('/fare-rules', methods=['GET', 'POST'])
@login_required
def fare_rules():
    """Get or create fare rules"""
    if request.method == 'GET':
        rules = FareRule.query.filter_by(is_active=True).all()
        return jsonify([{
            'id': rule.id,
            'car_class': rule.car_class,
            'base_fare': rule.base_fare,
            'per_km_city': rule.per_km_city,
            'per_km_suburb': rule.per_km_suburb,
            'minimum_fare': rule.minimum_fare
        } for rule in rules])
    
    data = request.json
    rule = FareRule(
        car_class=data['car_class'],
        base_fare=data['base_fare'],
        per_km_city=data['per_km_city'],
        per_km_suburb=data['per_km_suburb'],
        minimum_fare=data['minimum_fare']
    )
    db.session.add(rule)
    db.session.commit()
    return jsonify({'message': 'Fare rule created successfully'})

@api_bp.route('/subscriptions', methods=['GET'])
@login_required
def get_subscriptions():
    """Get list of active subscriptions"""
    subscriptions = Subscription.query.filter_by(status='active').all()
    return jsonify([{
        'id': sub.id,
        'driver_id': sub.driver_id,
        'plan_id': sub.plan_id,
        'start_date': sub.start_date.isoformat(),
        'end_date': sub.end_date.isoformat(),
        'status': sub.status
    } for sub in subscriptions])

@api_bp.route('/statistics', methods=['GET'])
@login_required
def get_statistics():
    """Get system statistics"""
    total_orders = Order.query.count()
    active_drivers = Driver.query.filter_by(status='online').count()
    completed_orders = Order.query.filter_by(status='completed').count()
    active_subscriptions = Subscription.query.filter_by(status='active').count()
    
    return jsonify({
        'total_orders': total_orders,
        'active_drivers': active_drivers,
        'completed_orders': completed_orders,
        'active_subscriptions': active_subscriptions,
        'completion_rate': (completed_orders / total_orders * 100) if total_orders > 0 else 0
    })
