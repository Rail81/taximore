import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import folium
from folium import plugins
import plotly.express as px
import plotly.graph_objects as go
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor
from typing import List, Dict, Tuple, Optional
import json
import logging
from .osm_service import OSMService
from .driver_location import DriverLocationService

logger = logging.getLogger(__name__)

class AnalyticsService:
    def __init__(self):
        self.osm_service = OSMService()
        self.driver_service = DriverLocationService()
        
    def generate_heatmap(self, points: List[Dict], radius: int = 15) -> str:
        """Создать тепловую карту на основе точек"""
        try:
            if not points:
                return None
                
            # Находим центр карты
            center_lat = sum(p['lat'] for p in points) / len(points)
            center_lon = sum(p['lon'] for p in points) / len(points)
            
            # Создаем базовую карту
            m = folium.Map(
                location=[center_lat, center_lon],
                zoom_start=13,
                tiles='cartodbpositron'
            )
            
            # Подготавливаем данные для тепловой карты
            heat_data = [[p['lat'], p['lon'], p.get('weight', 1.0)] for p in points]
            
            # Добавляем тепловую карту
            plugins.HeatMap(
                heat_data,
                radius=radius,
                blur=20,
                gradient={
                    0.4: 'blue',
                    0.6: 'lime',
                    0.8: 'yellow',
                    1.0: 'red'
                }
            ).add_to(m)
            
            # Сохраняем карту
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            map_path = f'cache/heatmaps/heatmap_{timestamp}.html'
            m.save(map_path)
            return map_path
            
        except Exception as e:
            logger.error(f"Error generating heatmap: {str(e)}")
            return None

    def create_demand_charts(self, orders: List[Dict]) -> Dict[str, str]:
        """Создать графики спроса"""
        try:
            if not orders:
                return {}
                
            # Преобразуем данные в DataFrame
            df = pd.DataFrame(orders)
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
            df['hour'] = df['datetime'].dt.hour
            df['day_of_week'] = df['datetime'].dt.dayofweek
            
            # График по часам
            hourly_demand = df.groupby('hour').size().reset_index(name='count')
            fig_hourly = px.line(
                hourly_demand,
                x='hour',
                y='count',
                title='Почасовой спрос',
                labels={'hour': 'Час', 'count': 'Количество заказов'}
            )
            
            # График по дням недели
            daily_demand = df.groupby('day_of_week').size().reset_index(name='count')
            days = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
            daily_demand['day_name'] = daily_demand['day_of_week'].apply(lambda x: days[x])
            fig_daily = px.bar(
                daily_demand,
                x='day_name',
                y='count',
                title='Спрос по дням недели',
                labels={'day_name': 'День', 'count': 'Количество заказов'}
            )
            
            # Сохраняем графики
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            hourly_path = f'cache/charts/hourly_demand_{timestamp}.html'
            daily_path = f'cache/charts/daily_demand_{timestamp}.html'
            
            fig_hourly.write_html(hourly_path)
            fig_daily.write_html(daily_path)
            
            return {
                'hourly_chart': hourly_path,
                'daily_chart': daily_path
            }
            
        except Exception as e:
            logger.error(f"Error creating demand charts: {str(e)}")
            return {}

    def create_driver_analytics_dashboard(self, driver_id: int) -> Dict[str, str]:
        """Создать дашборд аналитики водителя"""
        try:
            # Получаем аналитику за последнюю неделю
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            
            analytics = self.driver_service.get_driver_analytics(
                driver_id, start_date
            )
            
            if not analytics:
                return {}
            
            # График активности по часам
            history = self.driver_service.get_driver_route_history(driver_id)
            df_history = pd.DataFrame(history)
            df_history['datetime'] = pd.to_datetime(df_history['timestamp'], unit='s')
            df_history['hour'] = df_history['datetime'].dt.hour
            
            hourly_activity = df_history.groupby('hour').size().reset_index(name='count')
            fig_activity = px.bar(
                hourly_activity,
                x='hour',
                y='count',
                title='Почасовая активность',
                labels={'hour': 'Час', 'count': 'Количество обновлений локации'}
            )
            
            # График скорости
            speeds = []
            for i in range(len(history)-1):
                time_diff = history[i+1]['timestamp'] - history[i]['timestamp']
                if time_diff > 0:
                    distance = self.osm_service.calculate_distance(
                        history[i], history[i+1]
                    )
                    speed = (distance / time_diff) * 3600  # км/ч
                    speeds.append({
                        'timestamp': history[i]['timestamp'],
                        'speed': speed
                    })
            
            df_speeds = pd.DataFrame(speeds)
            df_speeds['datetime'] = pd.to_datetime(df_speeds['timestamp'], unit='s')
            fig_speed = px.line(
                df_speeds,
                x='datetime',
                y='speed',
                title='График скорости',
                labels={'datetime': 'Время', 'speed': 'Скорость (км/ч)'}
            )
            
            # Сохраняем графики
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            activity_path = f'cache/charts/driver_activity_{timestamp}.html'
            speed_path = f'cache/charts/driver_speed_{timestamp}.html'
            
            fig_activity.write_html(activity_path)
            fig_speed.write_html(speed_path)
            
            return {
                'activity_chart': activity_path,
                'speed_chart': speed_path,
                'analytics': analytics
            }
            
        except Exception as e:
            logger.error(f"Error creating driver analytics dashboard: {str(e)}")
            return {}
