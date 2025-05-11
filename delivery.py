#this file is used to calculate the delivery time in any active order the work in two ways:
#anyone before joining the order, can see for now it takes how long to deliver to his/her home
#determine the optimal route.

#retrieve the active order and the current delivery route situation, GroupOrder and OrderParticipation could be
#two databases you may implement on.

#add the current user in and return the delivery time based on the newly added user address.
#Do you suggest using folium live map as before OR use zip code to calculate the delivery time & route.

#so the parametre should be the information about the user's preference, and what we will mainly deal with in the part
#involves only the geographical and time(how long can you tolerate) information.

# delivery.py
# delivery.py
import requests
from models import *
from sqlalchemy.orm import joinedload

# === CONFIG ===
ORS_API_KEY = "5b3ce3597851110001cf6248316bf8be8e294e96b69328834f56e0dc"
ORS_URL = "https://api.openrouteservice.org/v2/directions/driving-car"

# === HELPERS ==
def geocode_address(address):
    """Return (latitude, longitude) from a full address using Nominatim."""
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        'q': address,
        'format': 'json',
        'limit': 1
    }
    try:
        response = requests.get(url, params=params, headers={"User-Agent": "MealMatesBot"})
        data = response.json()
        if data:
            lat = float(data[0]['lat'])
            lon = float(data[0]['lon'])
            return (lat, lon)
    except Exception as e:
        print("Geocoding error:", e)
    return None

def get_active_order_by_creator_school_id(school_id):
    """Find the latest active GroupOrder created by the user with given school_id"""
    user = User.query.filter_by(username=school_id).first()
    if not user:
        return None
    return GroupOrder.query.filter_by(creator_id=user.id, status='open').order_by(GroupOrder.created_at.desc()).first()

def get_user_latlon(user_pref):
    """Extract (lat, lon) from UserPreference"""
    latitude, longitude = geocode_address(user_pref.location)
    try:
        return (float(latitude), float(longitude))
    except:
        return None

def get_res_latlon(user_pref):
    try:
        return (float(user_pref.latitude), float(user_pref.longitude))
    except:
        return None

# def estimate_eta_ors(start_latlon, end_latlon):
#     """Use OpenRouteService to estimate travel time in minutes"""
#     headers = {
#         'Authorization': ORS_API_KEY,
#         'Content-Type': 'application/json'
#     }
#     coords = [[start_latlon[1], start_latlon[0]], [end_latlon[1], end_latlon[0]]]  # ORS: lng, lat
#     data = {"coordinates": coords}

#     try:
#         response = requests.post(ORS_URL, json=data, headers=headers)
#         if response.status_code == 200:
#             duration_sec = response.json()['features'][0]['properties']['segments'][0]['duration']
#             return round(duration_sec / 60, 1)
#         else:
#             print("ORS error:", response.text)
#             return None
#     except Exception as e:
#         print("ORS failed:", e)
#         return None

#it's for debugging.
def estimate_eta_ors(start_latlon, end_latlon):
    headers = {
        'Authorization': ORS_API_KEY,
        'Content-Type': 'application/json'
    }
    coords = [[start_latlon[1], start_latlon[0]], [end_latlon[1], end_latlon[0]]]  # lng, lat
    data = {"coordinates": coords}

    try:
        response = requests.post(ORS_URL, json=data, headers=headers)
        print("ORS status:", response.status_code)
        print("ORS request:", data)
        print("ORS response:", response.text)

        if response.status_code == 200:
            duration_sec = response.json()['features'][0]['properties']['segments'][0]['duration']
            return round(duration_sec / 60, 1)
        else:
            return None
    except Exception as e:
        print("ORS request failed:", e)
        return None

# === MAIN FUNCTIONS ===
def preview_eta_for_user(school_id, user_pref):
    """Estimate delivery time from restaurant to user (before joining)"""
    order = get_active_order_by_creator_school_id(school_id)
    if not order:
        return "No active order found."

    rest_coords = get_res_latlon(order.restaurant)
    user_coords = get_user_latlon(user_pref)
    print("User lat/lon:", get_user_latlon(user_pref))
    print("Restaurant lat/lon:", get_res_latlon(order.restaurant))


    if not rest_coords or not user_coords:
        return "Missing lat/lon coordinates."

    eta = estimate_eta_ors(rest_coords, user_coords)
    return eta if eta else "Unable to estimate."

def get_route_eta_sequence(school_id, new_user_pref=None):
    """Simulate full delivery route with new user inserted at optimal position"""
    order = get_active_order_by_creator_school_id(school_id)
    if not order:
        return "No active order found."

    rest_coords = get_user_latlon(order.restaurant)
    if not rest_coords:
        return "Missing restaurant coordinates."

    # Get existing participant coordinates
    participants = OrderParticipation.query.options(joinedload(OrderParticipation.user)).filter_by(group_order_id=order.id).all()
    waypoints = []

    for p in participants:
        pref = UserPreference.query.filter_by(school_id=p.user.username).first()
        coords = get_user_latlon(pref)
        if coords:
            waypoints.append((p.user.username, coords))

    # Add new user
    if new_user_pref:
        coords = get_user_latlon(new_user_pref)
        if coords:
            waypoints.append(("new_user", coords))

    if not waypoints:
        return "No valid locations found."

    # Create ORS matrix for route estimation (simple sequence)
    route_sequence = []
    current = rest_coords
    remaining = waypoints.copy()
    total_time = 0

    while remaining:
        estimates = [(u, loc, estimate_eta_ors(current, loc)) for u, loc in remaining]
        estimates = [e for e in estimates if e[2] is not None]
        if not estimates:
            break
        next_user, next_loc, eta = min(estimates, key=lambda x: x[2])
        total_time += eta
        route_sequence.append((next_user, round(total_time, 1)))
        current = next_loc
        remaining = [r for r in remaining if r[0] != next_user]

    return route_sequence  # [(username, ETA), ...]





