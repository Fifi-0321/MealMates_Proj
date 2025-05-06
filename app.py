from flask import Flask, render_template, request, redirect, url_for, flash, session
from datetime import datetime
import os
from models import *
from flask import jsonify
import requests

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
        restaurant_id = request.form['restaurant_id']
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


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)