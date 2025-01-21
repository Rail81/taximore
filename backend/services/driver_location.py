from datetime import datetime, timedelta
import redis
import json
import logging
from typing import List, Dict, Optional
from geopy.distance import geodesic
import numpy as np
from ..config import Config
from .osm_service import OSMService

logger = logging.getLogger(__name__)

class DriverLocationService:
    def __init__(self):
        self.redis = redis.Redis(
            host=Config.REDIS_HOST,
            port=Config.REDIS_PORT,
            db=Config.REDIS_DB,
            password=Config.REDIS_PASSWORD
        )
        self.osm_service = OSMService()
        
        # Константы для работы с локациями
        self.LOCATION_EXPIRE = 300  # 5 минут
        self.LOCATION_HISTORY_SIZE = 10
        self.MAX_SEARCH_RADIUS = 10  # км
        self.DRIVER_TYPES = {
            'economy': {'max_distance': 3, 'speed': 30},
            'comfort': {'max_distance': 5, 'speed': 35},
            'business': {'max_distance': 7, 'speed': 40}
        }

    async def update_driver_location(self, driver_id: int, lat: float, lon: float, 
                                   status: str = 'available', car_type: str = 'economy') -> bool:
        """Обновить местоположение водителя"""
        try:
            timestamp = datetime.now().timestamp()
            location_data = {
                'driver_id': driver_id,
                'lat': lat,
                'lon': lon,
                'status': status,
                'car_type': car_type,
                'timestamp': timestamp
            }
            
            # Сохраняем текущую локацию
            self.redis.geoadd(
                'driver_locations',
                [lon, lat, f'driver:{driver_id}']
            )
            
            # Сохраняем детальную информацию о водителе
            self.redis.setex(
                f'driver_info:{driver_id}',
                self.LOCATION_EXPIRE,
                json.dumps(location_data)
            )
            
            # Добавляем в историю перемещений
            history_key = f'driver_history:{driver_id}'
            self.redis.lpush(history_key, json.dumps({
                'lat': lat,
                'lon': lon,
                'timestamp': timestamp
            }))
            self.redis.ltrim(history_key, 0, self.LOCATION_HISTORY_SIZE - 1)
            
            return True
        except Exception as e:
            logger.error(f"Error updating driver location: {str(e)}")
            return False

    async def find_nearest_drivers(self, lat: float, lon: float, radius: float = 5.0,
                                 car_type: str = None, limit: int = 10) -> List[Dict]:
        """Найти ближайших водителей с учетом типа автомобиля и радиуса"""
        try:
            # Получаем всех водителей в радиусе
            drivers = self.redis.georadius(
                'driver_locations',
                lon, lat,
                radius,
                unit='km',
                withcoord=True,
                withdist=True,
                sort='ASC'
            )
            
            result = []
            for driver in drivers[:limit]:
                driver_id = driver[0].decode('utf-8').split(':')[1]
                distance = driver[2]  # в километрах
                driver_lon, driver_lat = driver[1]
                
                # Получаем информацию о водителе
                info = self.redis.get(f'driver_info:{driver_id}')
                if info:
                    driver_info = json.loads(info)
                    
                    # Фильтруем по типу автомобиля если указан
                    if car_type and driver_info['car_type'] != car_type:
                        continue
                        
                    # Проверяем статус и максимальную дистанцию для типа авто
                    if (driver_info['status'] == 'available' and
                        distance <= self.DRIVER_TYPES[driver_info['car_type']]['max_distance']):
                        
                        # Рассчитываем примерное время прибытия
                        speed = self.DRIVER_TYPES[driver_info['car_type']]['speed']
                        eta_minutes = (distance / speed) * 60
                        
                        result.append({
                            'driver_id': int(driver_id),
                            'distance': round(distance, 2),
                            'eta_minutes': round(eta_minutes),
                            'car_type': driver_info['car_type'],
                            'location': {
                                'lat': driver_lat,
                                'lon': driver_lon
                            }
                        })
            
            return result
        except Exception as e:
            logger.error(f"Error finding nearest drivers: {str(e)}")
            return []

    async def get_driver_route_history(self, driver_id: int) -> List[Dict]:
        """Получить историю маршрута водителя"""
        try:
            history_key = f'driver_history:{driver_id}'
            history = self.redis.lrange(history_key, 0, -1)
            
            points = []
            for point in history:
                point_data = json.loads(point)
                points.append(point_data)
            
            return sorted(points, key=lambda x: x['timestamp'])
        except Exception as e:
            logger.error(f"Error getting driver route history: {str(e)}")
            return []

    async def calculate_optimal_driver(self, customer_lat: float, customer_lon: float,
                                    destination_lat: float, destination_lon: float,
                                    car_type: str = None) -> Optional[Dict]:
        """Найти оптимального водителя с учетом маршрута"""
        try:
            # Находим ближайших водителей
            nearest_drivers = await self.find_nearest_drivers(
                customer_lat, customer_lon,
                radius=self.MAX_SEARCH_RADIUS,
                car_type=car_type,
                limit=5
            )
            
            if not nearest_drivers:
                return None
            
            best_driver = None
            min_total_time = float('inf')
            
            for driver in nearest_drivers:
                # Рассчитываем маршрут от водителя до клиента
                pickup_route = await self.osm_service.calculate_routes(
                    {'lat': driver['location']['lat'], 'lon': driver['location']['lon']},
                    {'lat': customer_lat, 'lon': customer_lon}
                )
                
                if not pickup_route:
                    continue
                
                # Рассчитываем маршрут от клиента до места назначения
                destination_route = await self.osm_service.calculate_routes(
                    {'lat': customer_lat, 'lon': customer_lon},
                    {'lat': destination_lat, 'lon': destination_lon}
                )
                
                if not destination_route:
                    continue
                
                # Общее время поездки (подача + маршрут до назначения)
                total_time = pickup_route[0]['duration'] + destination_route[0]['duration']
                
                if total_time < min_total_time:
                    min_total_time = total_time
                    best_driver = {
                        **driver,
                        'pickup_route': pickup_route[0],
                        'destination_route': destination_route[0],
                        'total_time': round(total_time),
                        'total_distance': round(
                            pickup_route[0]['distance'] + destination_route[0]['distance'],
                            2
                        )
                    }
            
            return best_driver
        except Exception as e:
            logger.error(f"Error calculating optimal driver: {str(e)}")
            return None

    async def get_driver_analytics(self, driver_id: int, 
                                 start_date: datetime = None) -> Dict:
        """Получить аналитику по водителю"""
        try:
            if not start_date:
                start_date = datetime.now() - timedelta(days=1)
                
            history = await self.get_driver_route_history(driver_id)
            if not history:
                return {}
                
            # Фильтруем точки по дате
            points = [p for p in history if datetime.fromtimestamp(p['timestamp']) >= start_date]
            if len(points) < 2:
                return {}
                
            # Рассчитываем пройденное расстояние
            total_distance = 0
            for i in range(len(points) - 1):
                p1 = points[i]
                p2 = points[i + 1]
                total_distance += geodesic(
                    (p1['lat'], p1['lon']),
                    (p2['lat'], p2['lon'])
                ).kilometers
                
            # Рассчитываем среднюю скорость
            time_diff = points[-1]['timestamp'] - points[0]['timestamp']
            avg_speed = (total_distance / (time_diff / 3600)) if time_diff > 0 else 0
            
            # Определяем часы активности
            timestamps = [datetime.fromtimestamp(p['timestamp']) for p in points]
            active_hours = len(set([t.hour for t in timestamps]))
            
            return {
                'total_distance': round(total_distance, 2),
                'average_speed': round(avg_speed, 2),
                'active_hours': active_hours,
                'points_count': len(points),
                'start_time': datetime.fromtimestamp(points[0]['timestamp']).isoformat(),
                'end_time': datetime.fromtimestamp(points[-1]['timestamp']).isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting driver analytics: {str(e)}")
            return {}
