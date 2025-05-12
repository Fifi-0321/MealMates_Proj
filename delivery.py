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
import folium
from openrouteservice import convert


# === CONFIG ===
ORS_API_KEY = "5b3ce3597851110001cf6248316bf8be8e294e96b69328834f56e0dc"
ORS_URL = "https://api.openrouteservice.org/v2/directions/cycling-electric"


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
        if response.status_code != 200:
            print("Nominatim error:", response.status_code, response.text)
            return None
        data = response.json()
        if data:
            lat = float(data[0]['lat'])
            lon = float(data[0]['lon'])
            return (lat, lon)
        else:
            print("No geocoding result for:", address)
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
    coords = geocode_address(user_pref.location)
    if coords:
        print("Geocoded user address to:", coords)
    else:
        print("Failed to geocode user address:", user_pref.location)
    return coords

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
            duration_sec = response.json()['routes'][0]['segments'][0]['duration']
            encoded_geom = response.json()['routes'][0]['geometry']
            return round(duration_sec / 60, 1), encoded_geom #here returns the calculated time !!!mark that the result needs to be better fine-tuned.
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
    print(f"Loaded preference for school_id={school_id}: {user_pref}")
    print("User lat/lon:", get_user_latlon(user_pref))
    print("Restaurant lat/lon:", get_res_latlon(order.restaurant))


    if not rest_coords or not user_coords:
        return "Missing lat/lon coordinates."

    eta, geometry = estimate_eta_ors(rest_coords, user_coords)
    return eta if eta else "Unable to estimate."

def compute_delivery_route_with_new_user(school_id, new_user_pref=None):
    """Simulate full delivery route with new user inserted at optimal position"""
    order = get_active_order_by_creator_school_id(school_id)
    if not order:
        return "No active order found."

    rest_coords = get_res_latlon(order.restaurant)
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
            waypoints.append(('new_user', coords))

    if not waypoints:
        return "No valid locations found."
    
    # Build the full coordinate list: start (restaurant) → waypoints (in current order)
    all_coords = [rest_coords] + [loc for _, loc in waypoints]
    all_users = ["restaurant"] + [u for u, _ in waypoints]

    # Prepare ORS request
    headers = {
        'Authorization': ORS_API_KEY,
        'Content-Type': 'application/json'
    }
    ors_coords = [[lon, lat] for lat, lon in all_coords]  # ORS uses [lng, lat]
    data = {
        "coordinates": ors_coords,
        "instructions": True
    }

    # Make the ORS request
    from openrouteservice import convert
    try:
        response = requests.post(ORS_URL, json=data, headers=headers)
        response.raise_for_status()
        result = response.json()
        geometry = result['routes'][0]['geometry']
        decoded = convert.decode_polyline(geometry)
    except Exception as e:
        print("ORS failed to fetch route geometry:", e)
        return "Routing failed."

    # Debug: show stop info
    print("Restaurant coordinates:", rest_coords)
    print("Waypoint coordinates:", waypoints)

    # Build sequence estimate using rough total times
    total_time = result['routes'][0]['segments'][0]['duration'] / 60  # seconds → minutes
    route_sequence = [(user, round((i+1) * total_time / len(waypoints), 1)) for i, (user, _) in enumerate(waypoints)]

    # Build the interactive map
    m = folium.Map(location=rest_coords, zoom_start=13)
    folium.Marker(
        rest_coords,
        popup=folium.Popup(order.restaurant.name, show=True),
        icon=folium.Icon(color='green')
    ).add_to(m)

    for i, (user, (lat, lon)) in enumerate(waypoints):
        if user != 'new_user':
            folium.Marker([lat, lon], popup=f"{user}: Stop {i+1}").add_to(m)

    # Draw the actual route path
    polyline_coords = [(pt[1], pt[0]) for pt in decoded['coordinates']]  # ORS → folium format
    folium.PolyLine(polyline_coords, color='blue', weight=4, opacity=0.8).add_to(m)

    # Save the map
    map_file = f"static/route_map_{school_id}.html"
    m.save(map_file)

    return {
        "seq": route_sequence,
        "coords": waypoints,
        "rest_coords": rest_coords,
        "geometry": geometry
    }

    # Create ORS matrix for route estimation (simple sequence)
    route_sequence = []
    coord_list = []
    current = rest_coords
    remaining = waypoints.copy()
    total_time = 0
    

    while remaining:
        estimates = [(u, loc, estimate_eta_ors(current, loc)[0]) for u, loc in remaining]
        estimates = [e for e in estimates if e[2] is not None]
        if not estimates:
            break
        next_user, next_loc, eta = min(estimates, key=lambda x: x[2])
        total_time += eta
        route_sequence.append((next_user, round(total_time, 1)))
        coord_list.append((next_user, next_loc))
        current = next_loc
        remaining = [r for r in remaining if r[0] != next_user]

    
    #debugging section
    print("Restaurant coordinates:", rest_coords)
    print("Waypoint coordinates:")
    print(len(coord_list), coord_list)
    for user, (lat, lon) in coord_list:
        print(f"{user}: ({lat}, {lon})")

    #the interactive visualized map
    m = folium.Map(location=rest_coords, zoom_start=12)
    print('The restaurant is ', rest_coords)
    folium.Marker([rest_coords[0],rest_coords[1]], popup=folium.Popup(order.restaurant.name, show=True)).add_to(m)
    for i, (user, (lat, lon)) in enumerate(coord_list):
        folium.Marker([lat, lon], popup=f"{user}: Stop {i+1}").add_to(m)

    # Draw route line
    # route_points = [rest_coords] + [loc for _, loc in coord_list]
    from openrouteservice import convert
    decoded = convert.decode_polyline(geometry)
    coords = [(point[1], point[0]) for point in decoded['coordinates']]
    folium.PolyLine(decoded, color='blue', weight=4, opacity=0.7).add_to(m)


    map_file = f"static/route_map_{school_id}.html"
    m.save(map_file)

    return {"seq": route_sequence, "coords": coord_list, "rest_coords": rest_coords, "decoded": geometry}





