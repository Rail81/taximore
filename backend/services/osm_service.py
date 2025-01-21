import osmnx as ox
import networkx as nx
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import folium
import math
import logging
from datetime import datetime, timedelta
import json
import os
from functools import lru_cache
from typing import Dict, List, Tuple, Optional
import redis
from ..config import Config
import numpy as np

logger = logging.getLogger(__name__)

# Initialize Redis for caching
redis_client = redis.Redis(
    host=Config.REDIS_HOST,
    port=Config.REDIS_PORT,
    db=Config.REDIS_DB
)

class OSMService:
    def __init__(self):
        self.geocoder = Nominatim(user_agent='taximore', timeout=10)
        # Настройка для сохранения кэша графов
        self.cache_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'cache', 'osm')
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Настройки для расчета маршрутов
        self.speed_limits = {
            'motorway': 110,
            'trunk': 90,
            'primary': 60,
            'secondary': 50,
            'tertiary': 40,
            'residential': 30,
            'living_street': 20
        }
        
        # Коэффициенты пробок по времени суток
        self.traffic_coefficients = {
            'morning_rush': 1.5,  # 7:00-10:00
            'evening_rush': 1.7,  # 17:00-20:00
            'night': 0.8,         # 23:00-5:00
            'normal': 1.0         # остальное время
        }

    @lru_cache(maxsize=1000)
    def get_coordinates(self, address: str) -> Optional[Dict]:
        """Get coordinates from address with caching"""
        cache_key = f'geocode:{address}'
        cached = redis_client.get(cache_key)
        
        if cached:
            return json.loads(cached)
            
        try:
            location = self.geocoder.geocode(address)
            if location:
                result = {
                    'lat': location.latitude,
                    'lon': location.longitude,
                    'address': location.address
                }
                # Кэшируем на 24 часа
                redis_client.setex(cache_key, 86400, json.dumps(result))
                return result
            return None
        except Exception as e:
            logger.error(f"Error geocoding address: {str(e)}")
            return None

    def get_traffic_coefficient(self, time: datetime = None) -> float:
        """Get traffic coefficient based on time"""
        if time is None:
            time = datetime.now()
            
        hour = time.hour
        
        if 7 <= hour < 10:
            return self.traffic_coefficients['morning_rush']
        elif 17 <= hour < 20:
            return self.traffic_coefficients['evening_rush']
        elif 23 <= hour or hour < 5:
            return self.traffic_coefficients['night']
        else:
            return self.traffic_coefficients['normal']

    def get_cached_graph(self, bbox: Tuple[float, float, float, float]) -> Optional[nx.MultiDiGraph]:
        """Get cached street network graph"""
        cache_key = f"graph:{':'.join(map(str, bbox))}"
        graph_path = os.path.join(self.cache_dir, f"{cache_key}.graphml")
        
        if os.path.exists(graph_path):
            try:
                return ox.load_graphml(graph_path)
            except Exception as e:
                logger.error(f"Error loading cached graph: {str(e)}")
                
        try:
            graph = ox.graph_from_bbox(
                bbox[0], bbox[2], bbox[1], bbox[3],
                network_type='drive',
                simplify=True
            )
            # Добавляем информацию о скорости и времени проезда
            for _, _, data in graph.edges(data=True):
                highway = data.get('highway', 'residential')
                length = data.get('length', 0)
                speed = self.speed_limits.get(highway, 30)
                data['speed'] = speed
                data['time'] = length / (speed * 1000 / 3600)  # время в часах
                
            # Сохраняем граф в кэш
            ox.save_graphml(graph, graph_path)
            return graph
        except Exception as e:
            logger.error(f"Error creating graph: {str(e)}")
            return None

    async def calculate_routes(self, origin: Dict, destination: Dict, 
                           alternatives: int = 3) -> Optional[List[Dict]]:
        """Calculate multiple routes between two points using OSM"""
        try:
            # Конвертируем координаты
            origin_point = (origin['lat'], origin['lon'])
            destination_point = (destination['lat'], destination['lon'])

            # Рассчитываем bbox
            min_lat = min(origin_point[0], destination_point[0])
            max_lat = max(origin_point[0], destination_point[0])
            min_lon = min(origin_point[1], destination_point[1])
            max_lon = max(origin_point[1], destination_point[1])

            buffer_deg = 0.02
            bbox = (
                min_lat - buffer_deg,
                min_lon - buffer_deg,
                max_lat + buffer_deg,
                max_lon + buffer_deg
            )

            # Получаем граф
            graph = self.get_cached_graph(bbox)
            if not graph:
                return None

            # Находим ближайшие узлы
            orig_node = ox.nearest_nodes(graph, origin_point[1], origin_point[0])
            dest_node = ox.nearest_nodes(graph, destination_point[1], destination_point[0])

            # Получаем коэффициент пробок
            traffic_coef = self.get_traffic_coefficient()

            routes = []
            # Рассчитываем основной и альтернативные маршруты
            for k in range(alternatives):
                try:
                    if k == 0:
                        # Основной маршрут (кратчайший по времени)
                        route = nx.shortest_path(graph, orig_node, dest_node, weight='time')
                    else:
                        # Альтернативные маршруты с избеганием части рёбер основного маршрута
                        temp_graph = graph.copy()
                        # Увеличиваем вес некоторых рёбер основного маршрута
                        for i in range(len(route)-1):
                            if temp_graph.has_edge(route[i], route[i+1]):
                                temp_graph[route[i]][route[i+1]][0]['time'] *= 1.5
                        route = nx.shortest_path(temp_graph, orig_node, dest_node, weight='time')

                    # Рассчитываем детали маршрута
                    edge_lengths = ox.utils_graph.get_route_edge_attributes(graph, route, 'length')
                    edge_times = ox.utils_graph.get_route_edge_attributes(graph, route, 'time')
                    
                    total_length = sum(edge_lengths) / 1000  # км
                    total_time = sum(edge_times) * traffic_coef  # часы

                    route_coords = [[graph.nodes[node]['y'], graph.nodes[node]['x']] for node in route]

                    routes.append({
                        'distance': round(total_length, 2),
                        'duration': round(total_time * 60, 1),  # минуты
                        'traffic_level': traffic_coef,
                        'start_location': {'lat': origin_point[0], 'lng': origin_point[1]},
                        'end_location': {'lat': destination_point[0], 'lng': destination_point[1]},
                        'route_coordinates': route_coords,
                        'start_address': self.geocoder.reverse((origin_point[0], origin_point[1])).address,
                        'end_address': self.geocoder.reverse((destination_point[0], destination_point[1])).address
                    })

                except nx.NetworkXNoPath:
                    logger.warning(f"No alternative route {k} found")
                    continue

            return routes if routes else None

        except Exception as e:
            logger.error(f"Error calculating routes: {str(e)}")
            return None

    def generate_map(self, routes: List[Dict], zoom: int = 13) -> str:
        """Generate map with multiple routes"""
        try:
            if not routes:
                return None

            # Создаем карту с центром на начальной точке
            start_location = routes[0]['start_location']
            m = folium.Map(
                location=[start_location['lat'], start_location['lng']],
                zoom_start=zoom
            )

            # Цвета для разных маршрутов
            colors = ['blue', 'red', 'green', 'purple', 'orange']

            # Добавляем маршруты на карту
            for i, route in enumerate(routes):
                coordinates = route['route_coordinates']
                color = colors[i % len(colors)]
                
                # Добавляем маршрут
                folium.PolyLine(
                    coordinates,
                    weight=4,
                    color=color,
                    opacity=0.8,
                    popup=f"Маршрут {i+1}: {route['distance']}км, {route['duration']}мин"
                ).add_to(m)

                # Добавляем маркеры начала и конца
                if i == 0:  # Только для первого маршрута
                    folium.Marker(
                        [start_location['lat'], start_location['lng']],
                        popup='Начало',
                        icon=folium.Icon(color='green')
                    ).add_to(m)
                    
                    end_location = route['end_location']
                    folium.Marker(
                        [end_location['lat'], end_location['lng']],
                        popup='Конец',
                        icon=folium.Icon(color='red')
                    ).add_to(m)

            # Сохраняем карту
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            map_path = os.path.join(self.cache_dir, f'route_map_{timestamp}.html')
            m.save(map_path)
            return map_path

        except Exception as e:
            logger.error(f"Error generating map: {str(e)}")
            return None

    def is_point_in_city(self, lat: float, lon: float, city_bounds: Dict) -> bool:
        """Check if point is within city bounds"""
        return (city_bounds['south'] <= lat <= city_bounds['north'] and
                city_bounds['west'] <= lon <= city_bounds['east'])

    def calculate_distance(self, point1: Dict, point2: Dict) -> float:
        """Calculate straight-line distance between two points in kilometers"""
        return geodesic(
            (point1['lat'], point1['lon']),
            (point2['lat'], point2['lon'])
        ).kilometers

    def calculate_area_coverage(self, points: List[Dict], radius_km: float = 1.0) -> Dict:
        """Рассчитать покрытие области точками (например, водителями)"""
        try:
            if not points:
                return {}
                
            # Находим границы области
            lats = [p['lat'] for p in points]
            lons = [p['lon'] for p in points]
            
            min_lat, max_lat = min(lats), max(lats)
            min_lon, max_lon = min(lons), max(lons)
            
            # Добавляем буфер
            buffer_deg = radius_km / 111  # примерно 1 градус = 111 км
            bbox = (
                min_lat - buffer_deg,
                min_lon - buffer_deg,
                max_lat + buffer_deg,
                max_lon + buffer_deg
            )
            
            # Создаем сетку для анализа покрытия
            grid_size = 50
            lat_grid = np.linspace(bbox[0], bbox[2], grid_size)
            lon_grid = np.linspace(bbox[1], bbox[3], grid_size)
            
            coverage_matrix = np.zeros((grid_size, grid_size))
            
            # Рассчитываем покрытие
            for i, lat in enumerate(lat_grid):
                for j, lon in enumerate(lon_grid):
                    for point in points:
                        distance = geodesic(
                            (lat, lon),
                            (point['lat'], point['lon'])
                        ).kilometers
                        if distance <= radius_km:
                            coverage_matrix[i, j] = 1
                            break
            
            coverage_percentage = (coverage_matrix.sum() / (grid_size * grid_size)) * 100
            
            return {
                'bbox': bbox,
                'coverage_percentage': round(coverage_percentage, 2),
                'total_points': len(points),
                'covered_area_km2': round(coverage_percentage * (
                    geodesic((bbox[0], bbox[1]), (bbox[0], bbox[3])).kilometers *
                    geodesic((bbox[0], bbox[1]), (bbox[2], bbox[1])).kilometers
                ) / 100, 2)
            }
        except Exception as e:
            logger.error(f"Error calculating area coverage: {str(e)}")
            return {}

    def find_optimal_points(self, area_bbox: Tuple[float, float, float, float],
                          num_points: int = 10) -> List[Dict]:
        """Найти оптимальные точки для размещения водителей"""
        try:
            # Получаем граф дорог для области
            graph = self.get_cached_graph(area_bbox)
            if not graph:
                return []
            
            # Получаем все узлы графа
            nodes = list(graph.nodes(data=True))
            
            # Рассчитываем центральность узлов
            centrality = nx.betweenness_centrality(graph)
            
            # Сортируем узлы по центральности
            sorted_nodes = sorted(
                centrality.items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            # Выбираем топ N узлов с учетом минимального расстояния между ними
            selected_points = []
            min_distance_km = 0.5  # Минимальное расстояние между точками
            
            for node_id, _ in sorted_nodes:
                node = graph.nodes[node_id]
                point = {
                    'lat': node['y'],
                    'lon': node['x']
                }
                
                # Проверяем расстояние до уже выбранных точек
                too_close = False
                for selected in selected_points:
                    distance = geodesic(
                        (point['lat'], point['lon']),
                        (selected['lat'], selected['lon'])
                    ).kilometers
                    if distance < min_distance_km:
                        too_close = True
                        break
                
                if not too_close:
                    selected_points.append(point)
                    if len(selected_points) >= num_points:
                        break
            
            return selected_points
        except Exception as e:
            logger.error(f"Error finding optimal points: {str(e)}")
            return []

    def analyze_area_demand(self, orders: List[Dict], 
                          time_window: Tuple[datetime, datetime] = None) -> Dict:
        """Анализ спроса в разных районах"""
        try:
            if not orders:
                return {}
                
            # Фильтруем заказы по временному окну
            if time_window:
                orders = [
                    order for order in orders
                    if time_window[0] <= datetime.fromtimestamp(order['timestamp']) <= time_window[1]
                ]
            
            if not orders:
                return {}
            
            # Группируем точки по районам
            points = []
            for order in orders:
                points.append({
                    'lat': order['pickup_lat'],
                    'lon': order['pickup_lon'],
                    'timestamp': order['timestamp']
                })
            
            # Находим границы области
            coverage = self.calculate_area_coverage(points)
            if not coverage:
                return {}
            
            bbox = coverage['bbox']
            
            # Разбиваем область на зоны
            zones_lat = 5
            zones_lon = 5
            
            lat_step = (bbox[2] - bbox[0]) / zones_lat
            lon_step = (bbox[3] - bbox[1]) / zones_lon
            
            # Считаем количество заказов в каждой зоне
            zone_stats = {}
            for i in range(zones_lat):
                for j in range(zones_lon):
                    zone_key = f"zone_{i}_{j}"
                    zone_bbox = (
                        bbox[0] + i * lat_step,
                        bbox[1] + j * lon_step,
                        bbox[0] + (i + 1) * lat_step,
                        bbox[1] + (j + 1) * lon_step
                    )
                    
                    # Считаем заказы в зоне
                    zone_orders = [
                        order for order in orders
                        if (zone_bbox[0] <= order['pickup_lat'] <= zone_bbox[2] and
                            zone_bbox[1] <= order['pickup_lon'] <= zone_bbox[3])
                    ]
                    
                    if zone_orders:
                        # Рассчитываем статистику по зоне
                        timestamps = [order['timestamp'] for order in zone_orders]
                        zone_stats[zone_key] = {
                            'order_count': len(zone_orders),
                            'bbox': zone_bbox,
                            'center': {
                                'lat': (zone_bbox[0] + zone_bbox[2]) / 2,
                                'lon': (zone_bbox[1] + zone_bbox[3]) / 2
                            },
                            'peak_hour': max(
                                [datetime.fromtimestamp(ts).hour for ts in timestamps],
                                key=lambda x: timestamps.count(datetime.fromtimestamp(x).hour)
                            )
                        }
            
            return {
                'total_orders': len(orders),
                'zones': zone_stats,
                'time_range': {
                    'start': datetime.fromtimestamp(min(order['timestamp'] for order in orders)).isoformat(),
                    'end': datetime.fromtimestamp(max(order['timestamp'] for order in orders)).isoformat()
                },
                'coverage': coverage
            }
        except Exception as e:
            logger.error(f"Error analyzing area demand: {str(e)}")
            return {}
