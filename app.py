from flask import Flask, render_template, request, redirect, url_for, flash, session
from datetime import datetime
import os
from models import *
from flask import jsonify
import requests
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from geopy.distance import geodesic
import re
from sqlalchemy import text

#For delivery estimation
import openrouteservice
client = openrouteservice.Client(key="5b3ce3597851110001cf6248832279b9f6a64a398e3108c6f67ff090")
def geocode_address(address):
    try:
        result = client.pelias_search(text=address)
        coords = result['features'][0]['geometry']['coordinates']
        return {"longitude": coords[0], "latitude": coords[1]}
    except Exception as e:
        print(f"[Geocoding Error] {e}")
        return None
def estimate_delivery_time(start_coords, end_coords):
    try:
        route = client.directions(
            coordinates=[start_coords, end_coords],
            profile='driving-car',
            format='json'
        )
        seconds = route['routes'][0]['summary']['duration']
        return int(seconds / 60)
    except Exception as e:
        print(f"[Routing Error] {e}")
        return None


app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///meal_sharing.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Routes
@app.route('/')
def home():
    active_orders = GroupOrder.query.filter_by(status='open').order_by(GroupOrder.created_at.desc()).limit(10).all()
    return render_template('home.html', active_orders=active_orders)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        user_exists = User.query.filter_by(username=username).first() or User.query.filter_by(email=email).first()
        
        if user_exists:
            flash('Username or email already exists!')
            return redirect(url_for('register'))
        
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        
        db.session.add(new_user)
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
            flash('Logged in successfully!')
            return redirect(url_for('home'))
        
        flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out')
    return redirect(url_for('home'))

@app.route('/match', methods=['GET'])
def match_user():
    school_id = request.args.get('school_id')
    if not school_id:
        return jsonify({'error': 'school_id required'}), 400

    matches = UserPreference.get_top_matches(school_id, top_k=5)
    result = [
        {
            'school_id': u.school_id,
            'similarity': round(score, 3),
            'location': u.location,
            'eat_time': u.eat_time,
            'dietary_restrictions': u.dietary_restrictions
        }
        for u, score in matches
    ]
    return jsonify(result)

from datetime import datetime, timedelta

@app.route('/create_order', methods=['GET', 'POST'])
def create_order():
    if 'user_id' not in session:
        flash('Please login to create an order')
        return redirect(url_for('login'))

    if request.method == 'POST':
        restaurant_id = int(request.form['restaurant_id'])
        restaurant = Restaurant.query.get(restaurant_id)

        if not restaurant:
            flash('Selected restaurant not found.')
            return redirect(url_for('create_order'))

        restaurant_id = restaurant.id
        delivery_address = request.form['delivery_address']
        order_time = datetime.strptime(request.form['order_time'], '%Y-%m-%dT%H:%M')
        duration_minutes = int(request.form['duration'])
        deadline = order_time + timedelta(minutes=duration_minutes)

        payment_methods = request.form.getlist('payment_methods')
        payment_methods_str = ','.join(payment_methods)

        new_order = GroupOrder(
            creator_id=session['user_id'],
            restaurant_id=restaurant_id,
            delivery_address=delivery_address,
            order_time=order_time,
            deadline=deadline,
            payment_methods=payment_methods_str
        )

        db.session.add(new_order)
        db.session.commit()

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
    # print(df_rest.columns)
    # print("Columns:", df_rest.columns)
    # print("First 5 rows:\n", df_rest.head())
    # print("Null values:\n", df_rest.isnull().sum())

    m = folium.Map(location=[40.73, -73.99], zoom_start=12)
    cluster = MarkerCluster().add_to(m)
    for _, r in df_rest.dropna(subset=['latitude','longitude']).iterrows():
        if r.latitude and r.longitude:
            folium.Marker(
                [float(r.latitude), float(r.longitude)],
                popup=folium.Popup(f'''
                <b>{r.name}</b><br>{r.address}<br>
                <button onclick="window.parent.setRestaurant('{r.name}')">Select This</button>
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


@app.route('/api/restaurants_by_zip/<zipcode>', methods=['POST'])
def restaurants_by_zip(zipcode):
    data = request.get_json()
    cuisine = data.get("cuisine", "").strip().lower()

    all_restaurants = Restaurant.query.all()

    # Filter by ZIP inside address
    zip_filtered = [
        r for r in all_restaurants
        if r.address and re.search(r'\b' + re.escape(zipcode) + r'\b', r.address)
    ]

    if cuisine:
        final_results = [
            r for r in zip_filtered
            if r.cuisine_type and cuisine in r.cuisine_type.lower()
        ]
    else:
        final_results = zip_filtered

    return jsonify([
        {
            "id": r.id,
            "name": r.name,
            "address": r.address,
            "cuisine_type": r.cuisine_type
        }
        for r in final_results [:5]
    ])



@app.route('/order/<int:order_id>')
def order_details(order_id):
    order = GroupOrder.query.options(db.joinedload(GroupOrder.restaurant)).get_or_404(order_id)
    menu_items = MenuItem.query.filter_by(restaurant_id=order.restaurant_id).all()

    # Estimate delivery time
    estimated_delivery_time = None
    if order.restaurant and order.restaurant.latitude and order.restaurant.longitude:
        user_coords = geocode_address(order.delivery_address)
        if user_coords:
            estimated_delivery_time = estimate_delivery_time(
                (order.restaurant.longitude, order.restaurant.latitude),
                (user_coords["longitude"], user_coords["latitude"])
            )

    return render_template(
        'order_details.html',
        order=order,
        menu_items=menu_items,
        estimated_delivery_time=estimated_delivery_time
    )


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
    return f"Total restaurants in DB: {count2}"


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

# if __name__ == '__main__':
#     with app.app_context():
#         db.drop_all()     # ⛔ This will delete all data!
#         db.create_all()   # ✅ Recreates tables with updated columns
#     app.run(debug=True)


@app.route("/debug_raw")
def debug_raw():
    with db.engine.connect() as conn:
        result = conn.execute(text("SELECT name, Cuisine FROM restaurants LIMIT 5"))
        return [{"name": row[0], "cuisine": row[1]} for row in result]
@app.route("/which_db")
def which_db():
    return {"db_uri": app.config['SQLALCHEMY_DATABASE_URI']}
