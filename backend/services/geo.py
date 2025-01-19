import osmnx as ox
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import folium
import math
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Initialize geocoder with longer timeout
geocoder = Nominatim(user_agent='taximore', timeout=10)

def get_coordinates(address):
    """Get coordinates from address"""
    try:
        location = geocoder.geocode(address)
        if location:
            return {
                'lat': location.latitude,
                'lon': location.longitude,
                'address': location.address
            }
        return None
    except Exception as e:
        logger.error(f"Error geocoding address: {str(e)}")
        return None

async def calculate_route(origin, destination):
    """Calculate route between two points using OSM"""
    try:
        # Convert addresses to coordinates if needed
        if isinstance(origin, str):
            origin_loc = get_coordinates(origin)
            if not origin_loc:
                return None
            origin = (origin_loc['lat'], origin_loc['lon'])
        elif isinstance(origin, dict):
            origin = (origin['lat'], origin['lon'])

        if isinstance(destination, str):
            dest_loc = get_coordinates(destination)
            if not dest_loc:
                return None
            destination = (dest_loc['lat'], dest_loc['lon'])
        elif isinstance(destination, dict):
            destination = (destination['lat'], destination['lon'])

        # Calculate the bounding box that encompasses both points
        min_lat = min(origin[0], destination[0])
        max_lat = max(origin[0], destination[0])
        min_lon = min(origin[1], destination[1])
        max_lon = max(origin[1], destination[1])

        # Add a small buffer to the bounding box
        buffer_deg = 0.02  # About 2km at most latitudes
        bbox = [
            min_lat - buffer_deg,
            min_lon - buffer_deg,
            max_lat + buffer_deg,
            max_lon + buffer_deg
        ]

        # Get the street network within the bounding box
        graph = ox.graph_from_bbox(
            bbox[0], bbox[2], bbox[1], bbox[3],
            network_type='drive',
            simplify=True
        )

        # Find the nearest nodes to origin and destination
        orig_node = ox.nearest_nodes(graph, origin[1], origin[0])
        dest_node = ox.nearest_nodes(graph, destination[1], destination[0])

        # Calculate the shortest path
        route = ox.shortest_path(graph, orig_node, dest_node, weight='length')
        
        if not route:
            return None

        # Calculate route details
        edge_lengths = ox.utils_graph.get_route_edge_attributes(graph, route, 'length')
        total_length = sum(edge_lengths) / 1000  # Convert to kilometers

        # Get route coordinates
        route_coords = [[graph.nodes[node]['y'], graph.nodes[node]['x']] for node in route]

        # Estimate duration (assuming average speed of 40 km/h in city)
        duration_minutes = (total_length / 40) * 60

        return {
            'distance': total_length,
            'duration': duration_minutes,
            'start_location': {'lat': origin[0], 'lng': origin[1]},
            'end_location': {'lat': destination[0], 'lng': destination[1]},
            'route_coordinates': route_coords,
            'start_address': geocoder.reverse((origin[0], origin[1])).address if isinstance(origin, tuple) else origin,
            'end_address': geocoder.reverse((destination[0], destination[1])).address if isinstance(destination, tuple) else destination
        }

    except Exception as e:
        logger.error(f"Error calculating route: {str(e)}")
        return None

def generate_map(route):
    """Generate map with route"""
    try:
        if not route or 'route_coordinates' not in route:
            return None

        # Create map centered at the midpoint of the route
        center_lat = (route['start_location']['lat'] + route['end_location']['lat']) / 2
        center_lng = (route['start_location']['lng'] + route['end_location']['lng']) / 2
        
        m = folium.Map(location=[center_lat, center_lng], zoom_start=13)

        # Add markers for start and end points
        folium.Marker(
            [route['start_location']['lat'], route['start_location']['lng']],
            popup='Start',
            icon=folium.Icon(color='green')
        ).add_to(m)

        folium.Marker(
            [route['end_location']['lat'], route['end_location']['lng']],
            popup='End',
            icon=folium.Icon(color='red')
        ).add_to(m)

        # Add route line
        folium.PolyLine(
            route['route_coordinates'],
            weight=3,
            color='blue',
            opacity=0.8
        ).add_to(m)

        return m

    except Exception as e:
        logger.error(f"Error generating map: {str(e)}")
        return None

def is_point_in_city(lat, lon, city_bounds):
    """Check if point is within city bounds"""
    return (city_bounds['south'] <= lat <= city_bounds['north'] and
            city_bounds['west'] <= lon <= city_bounds['east'])

def calculate_distance(point1, point2):
    """Calculate distance between two points"""
    return geodesic(
        (point1['lat'], point1['lon']),
        (point2['lat'], point2['lon'])
    ).kilometers
