from ..models import FareRule
from .geo import is_point_in_city

async def calculate_fare(route, car_class='standard'):
    """Calculate fare for a route"""
    if not route:
        return None
    
    # Get fare rules for the car class
    fare_rule = FareRule.query.filter_by(
        car_class=car_class,
        is_active=True
    ).first()
    
    if not fare_rule:
        return None
    
    # Get route details
    distance = route['distance']  # in kilometers
    
    # Check if route is within city
    start_in_city = is_point_in_city(
        route['start_location']['lat'],
        route['start_location']['lng'],
        {
            'north': 56.5,  # Примерные координаты города
            'south': 56.0,
            'west': 92.5,
            'east': 93.0
        }
    )
    
    end_in_city = is_point_in_city(
        route['end_location']['lat'],
        route['end_location']['lng'],
        {
            'north': 56.5,
            'south': 56.0,
            'west': 92.5,
            'east': 93.0
        }
    )
    
    # Calculate fare based on location
    if start_in_city and end_in_city:
        # Both points in city
        per_km_rate = fare_rule.per_km_city
    else:
        # At least one point outside city
        per_km_rate = fare_rule.per_km_suburb
    
    # Calculate total fare
    fare = fare_rule.base_fare + (distance * per_km_rate)
    
    # Apply minimum fare if necessary
    if fare < fare_rule.minimum_fare:
        fare = fare_rule.minimum_fare
    
    return round(fare, 2)

def apply_surge_pricing(base_fare, demand_factor=1.0):
    """Apply surge pricing based on demand"""
    if demand_factor <= 1.0:
        return base_fare
    
    # Cap the surge multiplier at 3.0
    surge_multiplier = min(demand_factor, 3.0)
    return round(base_fare * surge_multiplier, 2)

def calculate_driver_earnings(fare, commission_rate=0.20):
    """Calculate driver's earnings from fare"""
    commission = fare * commission_rate
    earnings = fare - commission
    return round(earnings, 2)
