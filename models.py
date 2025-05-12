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
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import requests
from geopy.distance import geodesic
import re

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

#before dealing with data
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

def is_valid_address(address):
    """Returns True if address includes a street name and a 5-digit ZIP code."""
    # Checks: at least 2 words + a 5-digit number
    has_street = bool(re.search(r'[A-Za-z]+\s+\d+|\d+\s+[A-Za-z]+', address))
    has_zip = bool(re.search(r'\b\d{5}\b', address))
    return has_street and has_zip

#the radar map
def compute_proximity_km(user1, user2):
    loc1 = geocode_address(user1.location)
    loc2 = geocode_address(user2.location)
    if loc1 and loc2:
        return geodesic(loc1, loc2).km
    return None

def distance_to_similarity_km(km, cap=5):
    return max(0, 1 - min(km / cap, 1))

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

class UserPreference(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.String(20), unique=True, nullable=False)
    location = db.Column(db.String(100))
    eat_time = db.Column(db.String(100))
    delivery_freq = db.Column(db.String(50))
    dietary_restrictions = db.Column(db.String(100))
    cuisine_asian = db.Column(db.Integer, nullable=True)
    cuisine_italian = db.Column(db.Integer, nullable=True)
    cuisine_mexican = db.Column(db.Integer, nullable=True)
    cuisine_middle_eastern = db.Column(db.Integer, nullable=True)
    cuisine_american=db.Column(db.Integer, nullable=True)
    cuisine_fastcasual=db.Column(db.Integer, nullable=True)
    spice_level = db.Column(db.String(20))
    budget_level = db.Column(db.String(20))
    active = db.Column(db.Boolean, default=True)

    def to_vector(self):
        def safe_int(val):
            try:
                return int(val)
            except:
                return 0

        return np.array([
            safe_int(self.cuisine_asian),
            safe_int(self.cuisine_italian),
            safe_int(self.cuisine_mexican),
            safe_int(self.cuisine_middle_eastern),
            safe_int(self.cuisine_american),
            safe_int(self.cuisine_fastcasual),
            safe_int(self.spice_level),
            safe_int(self.budget_level)
        ])

    @staticmethod
    def get_top_matches(school_id, top_k=5):
        all_users = UserPreference.query.filter_by(active=True).all()
        target_user = next((u for u in all_users if u.school_id == school_id), None)
        if not target_user:
            return []

        target_vec = target_user.to_vector().reshape(1, -1)
        user_vecs, user_refs = [], []

        for u in all_users:
            if u.school_id == school_id:
                continue
            user_vecs.append(u.to_vector())
            user_refs.append(u)

        if not user_vecs:
            return []

        sim_scores = cosine_similarity(target_vec, np.array(user_vecs))[0]
        top_indices = np.argsort(sim_scores)[::-1][:top_k]
        return [(user_refs[i], sim_scores[i]) for i in top_indices]

class UserMatch(db.Model): #so unless when users fill out new preference or the matched user list won't be upadted auto
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    matched_school_id = db.Column(db.String(20))
    similarity = db.Column(db.Float)



class Restaurant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200))
    cuisine_type = db.Column(db.String(50))
    latitude = db.Column(db.String(50))
    longitude = db.Column(db.String(50))
    score = db.Column(db.Integer)
    grade = db.Column(db.String(10))
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
    deadline = db.Column(db.DateTime)
    payment_methods = db.Column(db.String(100))  # comma-separated
    
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

#run the following to update db manually
# if __name__ == '__main__':
#     with app.app_context():
#         db.drop_all()
#         db.create_all()
#     app.run(debug=True)

