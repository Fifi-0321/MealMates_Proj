# app.py - Main Flask Application

from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///meal_sharing.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    orders_created = db.relationship('GroupOrder', backref='creator', lazy=True)
    participations = db.relationship('OrderParticipation', backref='user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Restaurant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200))
    cuisine_type = db.Column(db.String(50))
    menu_items = db.relationship('MenuItem', backref='restaurant', lazy=True)
    group_orders = db.relationship('GroupOrder', backref='restaurant', lazy=True)

class MenuItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey('restaurant.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    order_items = db.relationship('OrderItem', backref='menu_item', lazy=True)

class GroupOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    restaurant_id = db.Column(db.Integer, db.ForeignKey('restaurant.id'), nullable=False)
    status = db.Column(db.String(20), default='open')  # open, ordered, completed, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    order_time = db.Column(db.DateTime)
    delivery_address = db.Column(db.String(200))
    participants = db.relationship('OrderParticipation', backref='group_order', lazy=True)
    
class OrderParticipation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    group_order_id = db.Column(db.Integer, db.ForeignKey('group_order.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship('OrderItem', backref='participation', lazy=True)
    
class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    participation_id = db.Column(db.Integer, db.ForeignKey('order_participation.id'), nullable=False)
    menu_item_id = db.Column(db.Integer, db.ForeignKey('menu_item.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    notes = db.Column(db.Text)

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

@app.route('/create_order', methods=['GET', 'POST'])
def create_order():
    if 'user_id' not in session:
        flash('Please login to create an order')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        restaurant_id = request.form['restaurant_id']
        delivery_address = request.form['delivery_address']
        order_time = datetime.strptime(request.form['order_time'], '%Y-%m-%dT%H:%M')
        
        new_order = GroupOrder(
            creator_id=session['user_id'],
            restaurant_id=restaurant_id,
            delivery_address=delivery_address,
            order_time=order_time
        )
        
        db.session.add(new_order)
        db.session.commit()
        
        # Creator also joins as participant automatically
        participation = OrderParticipation(user_id=session['user_id'], group_order_id=new_order.id)
        db.session.add(participation)
        db.session.commit()
        
        flash('Group order created successfully!')
        return redirect(url_for('order_details', order_id=new_order.id))
    
    restaurants = Restaurant.query.all()
    return render_template('create_order.html', restaurants=restaurants)

@app.route('/order/<int:order_id>')
def order_details(order_id):
    order = GroupOrder.query.get_or_404(order_id)
    menu_items = MenuItem.query.filter_by(restaurant_id=order.restaurant_id).all()
    return render_template('order_details.html', order=order, menu_items=menu_items)

@app.route('/join_order/<int:order_id>', methods=['GET', 'POST'])
def join_order(order_id):
    if 'user_id' not in session:
        flash('Please login to join an order')
        return redirect(url_for('login'))
    
    order = GroupOrder.query.get_or_404(order_id)
    
    # Check if order is still open
    if order.status != 'open':
        flash('This order is no longer open for joining')
        return redirect(url_for('order_details', order_id=order_id))
    
    # Check if user is already a participant
    existing = OrderParticipation.query.filter_by(
        user_id=session['user_id'], 
        group_order_id=order_id
    ).first()
    
    if existing:
        flash('You are already part of this order')
        return redirect(url_for('order_details', order_id=order_id))
    
    if request.method == 'POST':
        participation = OrderParticipation(
            user_id=session['user_id'],
            group_order_id=order_id
        )
        db.session.add(participation)
        db.session.commit()
        
        flash('You have joined the group order!')
        return redirect(url_for('order_details', order_id=order_id))
    
    return render_template('join_order.html', order=order)

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