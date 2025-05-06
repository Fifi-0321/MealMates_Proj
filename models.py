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

db.init_app(app)

# === MODELS ===
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Newly added fields for profile.html
    name = db.Column(db.String(100))  # Full name
    phone = db.Column(db.String(20))
    bio = db.Column(db.Text)
    profile_image = db.Column(db.String(200))  # Filename of uploaded image
    price_range = db.Column(db.String(10))  # $, $$, etc.
    payment_method = db.Column(db.String(20))  # venmo, cash, etc.
    frequent_restaurants = db.Column(db.Text)
    meal_preferences = db.Column(db.Text)  # comma-separated: "breakfast,lunch"

    # Relationships
    orders_created = db.relationship('GroupOrder', backref='creator', lazy=True)
    participations = db.relationship('OrderParticipation', backref='user', lazy=True)

    # Placeholder: Add these later if modeled separately
    # user_tags = db.relationship('UserTag', backref='user', lazy=True)
    # cuisine_preferences = db.relationship('Cuisine', secondary='user_cuisines', lazy='subquery', backref=db.backref('users', lazy=True))
    # dietary_restrictions = db.relationship('DietaryRestriction', secondary='user_restrictions', lazy='subquery', backref=db.backref('users', lazy=True))

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

class UserPreference(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.String(20), unique=True, nullable=False)
    location = db.Column(db.String(100))
    eat_time = db.Column(db.String(100))
    delivery_freq = db.Column(db.String(50))
    dietary_restrictions = db.Column(db.String(100))
    cuisine_asian = db.Column(db.Integer)
    cuisine_italian = db.Column(db.Integer)
    cuisine_mexican = db.Column(db.Integer)
    cuisine_middle_eastern = db.Column(db.Integer)
    spice_level = db.Column(db.String(20))
    budget_level = db.Column(db.String(20))
    active = db.Column(db.Boolean, default=True)

    def to_vector(self):
        return np.array([
            self.cuisine_asian or 0,
            self.cuisine_italian or 0,
            self.cuisine_mexican or 0,
            self.cuisine_middle_eastern or 0,
            int(self.spice_level or 0),
            int(self.budget_level or 0)
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

# Possible Makeup


# === INIT FUNCTION ===
def init_db():
    with app.app_context():
        db.create_all()
        print("Database tables created!")

if __name__ == '__main__':
    from models import db, app
    with app.app_context():
        db.create_all()
        print("Database created with new columns.")