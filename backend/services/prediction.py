import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
import joblib
import logging
from typing import List, Dict, Optional
import json
from .osm_service import OSMService

logger = logging.getLogger(__name__)

class DemandPredictionService:
    def __init__(self):
        self.osm_service = OSMService()
        self.model_path = 'models/demand_prediction_model.joblib'
        self.scaler_path = 'models/demand_scaler.joblib'
        self.model = None
        self.scaler = None
        
    def prepare_features(self, orders: List[Dict]) -> pd.DataFrame:
        """Подготовка признаков для модели"""
        try:
            df = pd.DataFrame(orders)
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
            
            # Временные признаки
            df['hour'] = df['datetime'].dt.hour
            df['day_of_week'] = df['datetime'].dt.dayofweek
            df['month'] = df['datetime'].dt.month
            df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
            
            # Создаем почасовые агрегации
            hourly_df = df.groupby([
                df['datetime'].dt.date,
                'hour'
            ]).agg({
                'id': 'count',  # количество заказов
                'price': ['mean', 'sum'],  # статистика по ценам
                'is_weekend': 'first'
            }).reset_index()
            
            # Переименовываем колонки
            hourly_df.columns = [
                'date', 'hour', 'order_count',
                'avg_price', 'total_revenue', 'is_weekend'
            ]
            
            # Добавляем лаговые признаки
            for lag in [1, 2, 3, 24]:  # час назад, 2 часа, 3 часа, день назад
                hourly_df[f'order_count_lag_{lag}'] = hourly_df['order_count'].shift(lag)
                hourly_df[f'avg_price_lag_{lag}'] = hourly_df['avg_price'].shift(lag)
            
            # Добавляем скользящие средние
            for window in [3, 6, 24]:
                hourly_df[f'order_count_rolling_{window}h'] = (
                    hourly_df['order_count'].rolling(window=window).mean()
                )
            
            # Добавляем день недели
            hourly_df['day_of_week'] = pd.to_datetime(hourly_df['date']).dt.dayofweek
            
            # Удаляем строки с пропущенными значениями
            hourly_df = hourly_df.dropna()
            
            return hourly_df
            
        except Exception as e:
            logger.error(f"Error preparing features: {str(e)}")
            return None

    def train_model(self, orders: List[Dict]) -> bool:
        """Обучение модели прогнозирования спроса"""
        try:
            # Подготовка данных
            df = self.prepare_features(orders)
            if df is None or len(df) < 100:  # минимальное количество данных для обучения
                return False
            
            # Определяем признаки и целевую переменную
            feature_columns = [
                'hour', 'day_of_week', 'is_weekend',
                'order_count_lag_1', 'order_count_lag_2',
                'order_count_lag_3', 'order_count_lag_24',
                'avg_price_lag_1', 'avg_price_lag_24',
                'order_count_rolling_3h',
                'order_count_rolling_6h',
                'order_count_rolling_24h'
            ]
            
            X = df[feature_columns]
            y = df['order_count']
            
            # Разделяем данные на обучающую и тестовую выборки
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )
            
            # Масштабирование признаков
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            # Обучение модели
            model = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                n_jobs=-1
            )
            model.fit(X_train_scaled, y_train)
            
            # Сохранение модели и скейлера
            joblib.dump(model, self.model_path)
            joblib.dump(scaler, self.scaler_path)
            
            self.model = model
            self.scaler = scaler
            
            # Оценка качества
            train_score = model.score(X_train_scaled, y_train)
            test_score = model.score(X_test_scaled, y_test)
            
            logger.info(f"Model trained successfully. Train R2: {train_score:.3f}, Test R2: {test_score:.3f}")
            return True
            
        except Exception as e:
            logger.error(f"Error training model: {str(e)}")
            return False

    def load_model(self) -> bool:
        """Загрузка сохраненной модели"""
        try:
            self.model = joblib.load(self.model_path)
            self.scaler = joblib.load(self.scaler_path)
            return True
        except Exception as e:
            logger.error(f"Error loading model: {str(e)}")
            return False

    def predict_demand(self, current_data: Dict[str, float],
                      horizon_hours: int = 24) -> List[Dict]:
        """Прогноз спроса на следующие N часов"""
        try:
            if self.model is None and not self.load_model():
                return []
            
            results = []
            current_features = pd.DataFrame([current_data])
            
            for hour in range(horizon_hours):
                # Масштабируем признаки
                features_scaled = self.scaler.transform(current_features)
                
                # Делаем прогноз
                prediction = self.model.predict(features_scaled)[0]
                
                # Сохраняем результат
                timestamp = datetime.now() + timedelta(hours=hour)
                results.append({
                    'timestamp': timestamp.isoformat(),
                    'hour': timestamp.hour,
                    'day_of_week': timestamp.weekday(),
                    'predicted_demand': round(max(0, prediction), 2)
                })
                
                # Обновляем признаки для следующего часа
                current_features['hour'] = (current_features['hour'] + 1) % 24
                if current_features['hour'].iloc[0] == 0:
                    current_features['day_of_week'] = (
                        (current_features['day_of_week'] + 1) % 7
                    )
                    current_features['is_weekend'] = int(
                        current_features['day_of_week'].iloc[0] in [5, 6]
                    )
                
                # Обновляем лаговые признаки
                current_features['order_count_lag_1'] = prediction
                current_features['avg_price_lag_1'] = current_features['avg_price_lag_1'].iloc[0]
                
            return results
            
        except Exception as e:
            logger.error(f"Error predicting demand: {str(e)}")
            return []

    def visualize_predictions(self, predictions: List[Dict]) -> str:
        """Визуализация прогнозов"""
        try:
            if not predictions:
                return None
                
            df = pd.DataFrame(predictions)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Создаем график
            fig = go.Figure()
            
            # Добавляем линию прогноза
            fig.add_trace(go.Scatter(
                x=df['timestamp'],
                y=df['predicted_demand'],
                mode='lines+markers',
                name='Прогноз спроса',
                line=dict(color='blue'),
                hovertemplate=(
                    'Время: %{x}<br>' +
                    'Прогноз: %{y:.1f}<br>' +
                    '<extra></extra>'
                )
            ))
            
            # Настройка внешнего вида
            fig.update_layout(
                title='Прогноз спроса на такси',
                xaxis_title='Время',
                yaxis_title='Количество заказов',
                hovermode='x unified'
            )
            
            # Сохраняем график
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            chart_path = f'cache/charts/demand_prediction_{timestamp}.html'
            fig.write_html(chart_path)
            
            return chart_path
            
        except Exception as e:
            logger.error(f"Error visualizing predictions: {str(e)}")
            return None
