from flask import Flask, render_template, request, redirect, url_for, flash, session
from datetime import datetime
import os
from models import *
from flask import jsonify
import requests
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from ML import get_top_matches_by_school_id

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///meal_sharing.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Routes
@app.route('/')
def home():
    active_orders = GroupOrder.query.filter_by(status='open').order_by(GroupOrder.created_at.desc()).limit(10).all()

    matches = []
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        stored = UserMatch.query.filter_by(user_id=user.id).all()
        matches = [
            (UserPreference.query.filter_by(school_id=m.matched_school_id).first(), m.similarity)
            for m in stored
        ]

    play_sound = session.pop('play_login_sound', False)  # ✅ trigger sound on login
    print("Play sound flag:", play_sound)
    return render_template('home.html', active_orders=active_orders, matches=matches, play_sound=play_sound)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        school_id = request.form['school_id']

        user_exists = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()

        if user_exists:
            flash('Username or email already exists!')
            return redirect(url_for('register'))

        # Register User
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        # Create default UserPreference row with NetID
        pref = UserPreference(school_id=school_id)
        db.session.add(pref)
        db.session.commit()

        flash('Account created successfully!')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['play_login_sound'] = True
            flash('Logged in successfully!')
            return redirect(url_for('home'))
        
        flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out')
    return redirect(url_for('home'))

@app.route('/input_preference', methods=['GET', 'POST'])
def input_preference():
    if 'user_id' not in session:
        flash("Please login first.")
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    school_id = user.username  # Assuming school_id == username

    if request.method == 'POST':
        pref = UserPreference.query.filter_by(school_id=school_id).first()
        if not pref:
            pref = UserPreference(school_id=school_id)

        pref.location = request.form['location']
        pref.eat_time = request.form['eat_time']
        pref.spice_level = int(request.form.get('spice_level', 0))
        pref.budget_level = int(request.form.get('budget_level', 0))
        pref.cuisine_asian = int(request.form.get('cuisine_asian', 0))
        pref.cuisine_italian = int(request.form.get('cuisine_italian', 0))
        pref.cuisine_mexican = int(request.form.get('cuisine_mexican', 0))
        pref.cuisine_middle_eastern = int(request.form.get('cuisine_middle_eastern', 0))
        pref.active = True
        if not is_valid_address(pref.location):
            flash("Please enter a complete address including ZIP code.")
            return redirect(url_for('input_preference'))
        coords = geocode_address(pref.location)
        if coords:
            pref.latitude, pref.longitude = coords

        db.session.add(pref)

        UserMatch.query.filter_by(user_id=user.id).delete()

        # Compute new matches and saved unless the user inout anbother new in the match.html
        new_matches = get_top_matches_by_school_id(school_id)
        for match_user, score in new_matches:
            match = UserMatch(user_id=user.id, matched_school_id=match_user.school_id, similarity=score)
            db.session.add(match)

        db.session.commit()
        flash("Preferences saved and matches updated!")
        return redirect(url_for('home'))

    return render_template('match.html')


@app.route('/match_results')
def match_results():
    if 'user_id' not in session:
        flash('Please login to view matches')
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    preference = UserPreference.query.filter_by(school_id=user.username).first()  # Assuming username == school_id

    if not preference:
        flash('No preference data found for this user')
        return redirect(url_for('profile'))

    matches = get_top_matches_by_school_id(preference.school_id)

    return render_template('match_results.html', matches=matches)


from datetime import datetime, timedelta

@app.route('/create_order', methods=['GET', 'POST'])
def create_order():
    if 'user_id' not in session:
        flash('Please login to create an order')
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Get restaurant name from form
        restaurant_name = request.form.get('restaurant_id', '')
        
        # Find the restaurant by name in the database
        restaurant = Restaurant.query.filter_by(name=restaurant_name).first()
        
        # If restaurant doesn't exist, create it
        if not restaurant:
            # Check if we have coordinates from the map selection
            # This assumes you have latitude and longitude fields in your Restaurant model
            try:
                # You might need to adjust these field names based on your form
                latitude = request.form.get('latitude')
                longitude = request.form.get('longitude')
                address = request.form.get('restaurant_address', '')
                
                restaurant = Restaurant(
                    name=restaurant_name,
                    address=address
                )
                
                # Only set coordinates if they exist
                if latitude and longitude:
                    restaurant.latitude = latitude
                    restaurant.longitude = longitude
                
                db.session.add(restaurant)
                db.session.commit()
                print(f"Created new restaurant: {restaurant_name}, ID: {restaurant.id}")
            except Exception as e:
                print(f"Error creating restaurant: {e}")
                flash("Error creating restaurant")
                return render_template('create_order.html', map_file='create_order_map.html')
        
        delivery_address = request.form.get('delivery_address', '')
        
        # Use current time instead of form input
        order_time = datetime.now()
        duration_minutes = int(request.form.get('duration', 30))
        deadline = order_time + timedelta(minutes=duration_minutes)

        payment_methods = request.form.getlist('payment_methods')
        payment_methods_str = ','.join(payment_methods)
        
        # Create the order with the restaurant ID
        new_order = GroupOrder(
            creator_id=session['user_id'],
            restaurant_id=restaurant.id,  # Use the restaurant ID, not the name
            delivery_address=delivery_address,
            order_time=order_time,
            deadline=deadline,
            payment_methods=payment_methods_str
        )
        
        db.session.add(new_order)
        db.session.commit()
        
        print(f"New order created: ID={new_order.id}, Restaurant ID={new_order.restaurant_id}")

        participation = OrderParticipation(user_id=session['user_id'], group_order_id=new_order.id)
        db.session.add(participation)
        db.session.commit()

        flash('Group order created successfully!')
        return redirect(url_for('order_details', order_id=new_order.id))
    
    restaurants = Restaurant.query.all()
    df_rest = pd.DataFrame([{
    "name": r.name,
    "latitude": float(r.latitude) if r.latitude else None,
    "longitude": float(r.longitude) if r.longitude else None,
    "address": r.address,
    "rating": getattr(r, "rating", None)  # use score if that's your rating
    } for r in restaurants])

    m = folium.Map(location=[40.73, -73.99], zoom_start=12)
    cluster = MarkerCluster().add_to(m)
    for _, r in df_rest.dropna(subset=['latitude','longitude']).iterrows():
        if r.latitude and r.longitude:
            folium.Marker(
                [float(r.latitude), float(r.longitude)],
                popup=folium.Popup(f'''
                <b>{r['name']}</b><br>{r.address}<br>
                <button onclick="window.parent.setRestaurant('{r['name']}')">Select This</button>
                ''', max_width=300)
            ).add_to(cluster)

    map_path = 'static/create_order_map.html'
    m.save(map_path)

    return render_template('create_order.html', map_file='create_order_map.html')

    restaurants = Restaurant.query.all()
    return render_template('create_order.html', restaurants=restaurants)


@app.route('/find_orders')
def find_orders():
    if 'user_id' not in session:
        flash('Please login to view group orders')
        return redirect(url_for('login'))

    orders = GroupOrder.query.filter_by(status='open').order_by(GroupOrder.created_at.desc()).all()
    return render_template('find_orders.html', orders=orders)

@app.route('/preview_eta/<school_id>', methods=['POST'])
def preview_eta(school_id):
    user_pref = UserPreference.query.filter_by(school_id=school_id).first()
    if not user_pref:
        return jsonify({'error': 'User preference not found'}), 404

    from delivery import preview_eta_for_user
    eta = preview_eta_for_user(school_id, user_pref)
    return jsonify({'estimated_time_min': eta})



# @app.route('/route_with/<school_id>', methods=['POST'])
# def route_with(school_id):
#     user_pref = UserPreference.query.filter_by(school_id=school_id).first()
#     if not user_pref:
#         return jsonify({'error': 'User preference not found'}), 404

#     from delivery import compute_delivery_route_with_new_user
#     route_info = compute_delivery_route_with_new_user(school_id, user_pref)
#     return jsonify({'route': route_info})

@app.route('/route_with/<school_id>', methods=['POST'])
def route_with(school_id):
    current_user_id = session.get('user_id')
    current_user = User.query.get(current_user_id)
    user_pref = UserPreference.query.filter_by(school_id=current_user.username).first()
    if not user_pref:
        return jsonify({'error': 'User preference not found'}), 404

    from delivery import compute_delivery_route_with_new_user
    route_info = compute_delivery_route_with_new_user(school_id, user_pref)

    if isinstance(route_info, str):  # error fallback
        return jsonify({'error': route_info}), 500

    return jsonify({
        'route': route_info['seq'],         # list of (username, ETA)
        'map_url': url_for('static', filename=f'route_map_{school_id}.html'),
        'geometry': route_info['geometry']  # encoded ORS polyline
    })

    # Generate map
    import folium
    m = folium.Map(location=list(route_info['rest_coords']), zoom_start=12)
    folium.Marker([route_info['rest_coords'][0],route_info['rest_coords'][1]], popup=folium.Popup('Your Restaurant', show=True)).add_to(m)
    for i, (user, (lat, lon)) in enumerate(route_info['coords']):
        folium.Marker([lat, lon], popup=f"{user}: Stop {i+1}").add_to(m)
    #delivery route visualized
    route_points = [route_info['rest_coords']] + [loc for _, loc in route_info['coords']]
    folium.PolyLine(route_points, color='blue', weight=4, opacity=0.7).add_to(m)

    map_file = f"static/route_map_{school_id}.html"
    m.save(map_file)

    return jsonify({'route': route_info['seq'], 'map_url': url_for('static', filename=f'route_map_{school_id}.html')})




@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        flash('Please login to view your profile')
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        user.name = request.form.get('name')
        user.phone = request.form.get('phone')
        user.bio = request.form.get('bio')
        user.price_range = request.form.get('price_range')
        user.payment_method = request.form.get('payment_method')
        user.frequent_restaurants = request.form.get('frequent_restaurants')
        user.meal_preferences = ",".join(request.form.getlist('meal_preferences'))
        db.session.commit()
        flash('Profile updated successfully!')

    # Dummy placeholders — replace with real query if needed
    cuisines = []
    dietary_restrictions = []
    return render_template('profiles.html', user=user, cuisines=cuisines, dietary_restrictions=dietary_restrictions)

@app.route('/api/restaurants_by_zip/<zipcode>')
def restaurants_by_zip(zipcode):
    # Replace with a better geocoding API if available
    resp = requests.get(f'https://nominatim.openstreetmap.org/search?postalcode={zipcode}&country=USA&format=json')
    if not resp.json():
        return jsonify({'restaurants': [], 'center': {'lat': 0, 'lon': 0}})
    
    lat = float(resp.json()[0]['lat'])
    lon = float(resp.json()[0]['lon'])

    # Sample simple radius search (customize with real distance filter)
    nearby = Restaurant.query.all()
    results = []
    for r in nearby:
        results.append({
            'id': r.id,
            'name': r.name,
            'address': r.address,
            'lat': 40.72,  # TODO: store lat/lon in DB
            'lon': -73.99
        })

    return jsonify({'restaurants': results, 'center': {'lat': lat, 'lon': lon}})

@app.route('/order/<int:order_id>')
def order_details(order_id):
    order = GroupOrder.query.options(db.joinedload(GroupOrder.restaurant)).get_or_404(order_id)
    menu_items = MenuItem.query.filter_by(restaurant_id=order.restaurant_id).all()
    return render_template('order_details.html', order=order, menu_items=menu_items)

@app.route('/join_order/<int:order_id>', methods=['GET', 'POST'])
def join_order(order_id):
    if 'user_id' not in session:
        flash('Please login to join an order')
        return redirect(url_for('login'))
    
    order = GroupOrder.query.get_or_404(order_id)

    # Prevent joining if closed
    if order.status != 'open':
        flash('This order is closed')
        return redirect(url_for('order_details', order_id=order_id))

    # Prevent duplicate joins
    existing = OrderParticipation.query.filter_by(
        user_id=session['user_id'],
        group_order_id=order_id
    ).first()

    if existing:
        flash('You already joined this order')
        return redirect(url_for('order_details', order_id=order_id))

    try:
        print("Trying to join order:", order_id, "by user:", session.get('user_id'))

        participation = OrderParticipation(
            user_id=session['user_id'],
            group_order_id=order_id
        )
        db.session.add(participation)
        db.session.commit()

        flash('You joined the group order!')
        return redirect(url_for('order_details', order_id=order_id))

    except Exception as e:
        print("Join order failed:", e)
        flash('Something went wrong while joining the order.')
        return redirect(url_for('order_details', order_id=order_id))


@app.route('/add_item/<int:participation_id>', methods=['POST'])
def add_item(participation_id):
    participation = OrderParticipation.query.get_or_404(participation_id)
    
    # Security check
    if participation.user_id != session.get('user_id'):
        flash('Not authorized')
        return redirect(url_for('home'))
    
    menu_item_id = request.form['menu_item_id']
    quantity = int(request.form['quantity'])
    notes = request.form.get('notes', '')
    
    item = OrderItem(
        participation_id=participation_id,
        menu_item_id=menu_item_id,
        quantity=quantity,
        notes=notes
    )
    
    db.session.add(item)
    db.session.commit()
    
    flash('Item added to your order')
    return redirect(url_for('order_details', order_id=participation.group_order_id))

@app.route('/finalize_order/<int:order_id>', methods=['POST'])
def finalize_order(order_id):
    order = GroupOrder.query.get_or_404(order_id)
    
    # Security check
    if order.creator_id != session.get('user_id'):
        flash('Only the creator can finalize this order')
        return redirect(url_for('order_details', order_id=order_id))
    
    order.status = 'ordered'
    db.session.commit()
    
    flash('Order has been finalized!')
    return redirect(url_for('order_details', order_id=order_id))

@app.route('/debug_DB_count')
def debug_restaurant_count():
    from models import Restaurant
    count1 = Restaurant.query.count()
    return f"Total restaurants in DB: {count1}"
def debug_user_count():
    from models import UserPreference
    count2 = UserPreference.query.count()
    return f"Total users in DB: {count2}"


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # app.run(debug=True)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

# if __name__ == '__main__':
#     with app.app_context():
#         db.drop_all()     # ⛔ This will delete all data!
#         db.create_all()   # ✅ Recreates tables with updated columns
#     app.run(debug=True)
