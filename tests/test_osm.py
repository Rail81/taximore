import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.geo import get_coordinates, calculate_route, generate_map
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_geocoding():
    """Test address geocoding"""
    logger.info("Testing geocoding...")
    
    # Test with specific addresses
    addresses = [
        "Москва, Красная площадь",
        "Казань, Кремлевская улица",
        "Санкт-Петербург, Невский проспект"
    ]
    
    for address in addresses:
        coords = get_coordinates(address)
        if coords:
            logger.info(f"Address: {address}")
            logger.info(f"Coordinates: lat={coords['lat']}, lon={coords['lon']}")
            logger.info(f"Full address: {coords['address']}\n")
        else:
            logger.error(f"Failed to geocode address: {address}\n")

async def test_route_calculation():
    """Test route calculation"""
    logger.info("Testing route calculation...")
    
    # Test coordinates (Москва: Красная площадь -> Парк Горького)
    origin = {
        'lat': 55.7539,
        'lon': 37.6208
    }
    destination = {
        'lat': 55.7298,
        'lon': 37.6010
    }
    
    route = await calculate_route(origin, destination)
    if route:
        logger.info("Route calculated successfully:")
        logger.info(f"Distance: {route['distance']:.2f} km")
        logger.info(f"Duration: {route['duration']:.2f} minutes")
        logger.info(f"Start address: {route['start_address']}")
        logger.info(f"End address: {route['end_address']}")
        
        # Generate and save map
        map_obj = generate_map(route)
        if map_obj:
            map_file = 'test_route_map.html'
            map_obj.save(map_file)
            logger.info(f"Map saved to {map_file}")
    else:
        logger.error("Failed to calculate route")

async def test_address_to_address():
    """Test route calculation between addresses"""
    logger.info("Testing route calculation between addresses...")
    
    origin_address = "Москва, Красная площадь"
    destination_address = "Москва, Парк Горького"
    
    route = await calculate_route(origin_address, destination_address)
    if route:
        logger.info("Route calculated successfully:")
        logger.info(f"Distance: {route['distance']:.2f} km")
        logger.info(f"Duration: {route['duration']:.2f} minutes")
        logger.info(f"Start address: {route['start_address']}")
        logger.info(f"End address: {route['end_address']}")
        
        # Generate and save map
        map_obj = generate_map(route)
        if map_obj:
            map_file = 'test_address_route_map.html'
            map_obj.save(map_file)
            logger.info(f"Map saved to {map_file}")
    else:
        logger.error("Failed to calculate route between addresses")

async def run_tests():
    """Run all tests"""
    try:
        await test_geocoding()
        await test_route_calculation()
        await test_address_to_address()
    except Exception as e:
        logger.error(f"Error during tests: {str(e)}")

if __name__ == "__main__":
    asyncio.run(run_tests())
