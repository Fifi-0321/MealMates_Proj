from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os
from sqlalchemy import create_engine
import pandas as pd

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
app.config[connection_string] = 'sqlite:///meal_sharing.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True

db = SQLAlchemy(app)

# === MODELS ===
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

class Restaurant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200))
    cuisine_type = db.Column(db.String(50))

class GroupOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    restaurant_id = db.Column(db.Integer, db.ForeignKey('restaurant.id'), nullable=False)

class OrderParticipation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    group_order_id = db.Column(db.Integer, db.ForeignKey('group_order.id'), nullable=False)

class MenuItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey('restaurant.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    participation_id = db.Column(db.Integer, db.ForeignKey('order_participation.id'), nullable=False)
    menu_item_id = db.Column(db.Integer, db.ForeignKey('menu_item.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)

# === INIT FUNCTION ===
def init_db():
    with app.app_context():
        db.create_all()
        print("Database tables created!")

if __name__ == '__main__':
    init_db()
    print('DB pushed')
