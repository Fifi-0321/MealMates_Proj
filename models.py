from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os
from sqlalchemy import create_engine
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()


# === Remote MySQL DB Credentials ===
username = 'byte_pals'
password = 'LbyMKhLCmsiHJVd+zb6IxA=='
host = 'jsedocc7.scrc.nyu.edu'
database = 'byte_pals'
port = 3306

# === Connection String (MySQL via PyMySQL) ===
connection_string = f"mysql+pymysql://{username}:{password}@{host}:{port}/{database}?charset=utf8"
engine = create_engine(connection_string)


app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = connection_string
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True

# === MODELS ===
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

# === INIT FUNCTION ===
def init_db():
    with app.app_context():
        db.create_all()
        print("Database tables created!")

if __name__ == '__main__':
    init_db()
    print('DB pushed')
