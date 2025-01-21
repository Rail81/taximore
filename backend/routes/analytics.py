from flask import Blueprint, jsonify, request, send_file
from datetime import datetime, timedelta
from ..services.analytics import AnalyticsService
from ..services.prediction import DemandPredictionService
from ..services.order import OrderService
from ..services.driver_location import DriverLocationService
from flask_login import login_required
import logging

logger = logging.getLogger(__name__)

analytics_bp = Blueprint('analytics', __name__)
analytics_service = AnalyticsService()
prediction_service = DemandPredictionService()
order_service = OrderService()
driver_service = DriverLocationService()

@analytics_bp.route('/api/analytics/heatmap', methods=['GET'])
@login_required
def get_heatmap():
    """Получить тепловую карту активности"""
    try:
        # Получаем параметры
        hours = int(request.args.get('hours', 24))
        type = request.args.get('type', 'orders')  # orders или drivers
        
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        
        points = []
        if type == 'orders':
            # Получаем заказы
            orders = order_service.get_orders_in_timeframe(start_time, end_time)
            points = [
                {
                    'lat': order['pickup_lat'],
                    'lon': order['pickup_lon'],
                    'weight': float(order['price'])
                }
                for order in orders
            ]
        else:
            # Получаем локации водителей
            drivers = driver_service.get_all_active_drivers()
            points = [
                {
                    'lat': driver['lat'],
                    'lon': driver['lon'],
                    'weight': 1.0
                }
                for driver in drivers
            ]
        
        # Генерируем карту
        map_path = analytics_service.generate_heatmap(points)
        if not map_path:
            return jsonify({'error': 'Failed to generate heatmap'}), 500
            
        return send_file(map_path)
        
    except Exception as e:
        logger.error(f"Error generating heatmap: {str(e)}")
        return jsonify({'error': str(e)}), 500

@analytics_bp.route('/api/analytics/demand', methods=['GET'])
@login_required
def get_demand_analytics():
    """Получить аналитику спроса"""
    try:
        # Получаем параметры
        days = int(request.args.get('days', 7))
        
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        # Получаем заказы
        orders = order_service.get_orders_in_timeframe(start_time, end_time)
        
        # Создаем графики
        charts = analytics_service.create_demand_charts(orders)
        if not charts:
            return jsonify({'error': 'Failed to create demand charts'}), 500
            
        return jsonify({
            'hourly_chart': charts['hourly_chart'],
            'daily_chart': charts['daily_chart']
        })
        
    except Exception as e:
        logger.error(f"Error getting demand analytics: {str(e)}")
        return jsonify({'error': str(e)}), 500

@analytics_bp.route('/api/analytics/driver/<int:driver_id>', methods=['GET'])
@login_required
def get_driver_analytics(driver_id):
    """Получить аналитику водителя"""
    try:
        dashboard = analytics_service.create_driver_analytics_dashboard(driver_id)
        if not dashboard:
            return jsonify({'error': 'Failed to create driver dashboard'}), 500
            
        return jsonify(dashboard)
        
    except Exception as e:
        logger.error(f"Error getting driver analytics: {str(e)}")
        return jsonify({'error': str(e)}), 500

@analytics_bp.route('/api/analytics/predict', methods=['GET'])
@login_required
def predict_demand():
    """Прогноз спроса"""
    try:
        # Получаем параметры
        hours = int(request.args.get('hours', 24))
        
        # Получаем текущие данные для прогноза
        current_data = order_service.get_current_demand_features()
        
        # Делаем прогноз
        predictions = prediction_service.predict_demand(current_data, hours)
        if not predictions:
            return jsonify({'error': 'Failed to make predictions'}), 500
            
        # Визуализируем прогноз
        chart_path = prediction_service.visualize_predictions(predictions)
        
        return jsonify({
            'predictions': predictions,
            'chart': chart_path
        })
        
    except Exception as e:
        logger.error(f"Error predicting demand: {str(e)}")
        return jsonify({'error': str(e)}), 500

@analytics_bp.route('/api/analytics/train', methods=['POST'])
@login_required
def train_model():
    """Обучить модель прогнозирования"""
    try:
        # Получаем исторические данные
        days = int(request.json.get('days', 30))
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        orders = order_service.get_orders_in_timeframe(start_time, end_time)
        
        # Обучаем модель
        success = prediction_service.train_model(orders)
        if not success:
            return jsonify({'error': 'Failed to train model'}), 500
            
        return jsonify({'message': 'Model trained successfully'})
        
    except Exception as e:
        logger.error(f"Error training model: {str(e)}")
        return jsonify({'error': str(e)}), 500
