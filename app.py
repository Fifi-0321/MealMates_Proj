# app.py - Main Flask Application

from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
from models import *

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///meal_sharing.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

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

@app.route('/find_orders/<int:order_id>', methods=['GET', 'POST'])
def find_orders(order_id):
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

    return render_template('find_orders.html', order=order)

@app.route('/find_orders')
def list_orders():
    orders = GroupOrder.query.filter_by(status='open').all()
    return render_template('list_orders.html', orders=orders)


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