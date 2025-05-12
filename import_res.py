import pandas as pd
from models import engine, Restaurant, UserPreference
from app import app, db
from sqlalchemy import text

# Read restaurant data from remote MySQL
with engine.connect() as conn:
    df_res = pd.read_sql(text("SELECT name, address, latitude, longitude, score, grade FROM restaurants"), conn)
    print("Restaurants table columns:", list(df_res.columns))
    print(df_res.head())
with app.app_context():
    for _, row in df_res.iterrows():
        restaurant = Restaurant(
            name=row["name"],
            address=row["address"],
            latitude=row.get("latitude"),
            longitude=row.get("longitude"),
            score=row.get("SCORE"),
            grade=row.get("GRADE"),
            cuisine_type=None  # Optional, set if available
        )
        db.session.add(restaurant)
    db.session.commit()

print(f"Imported {len(df_res)} restaurants into local Flask DB.")
print("Restaurant table columns:", list(df_res.columns))



#read user pref
with engine.connect() as conn:
    df_pref = pd.read_sql(text("SELECT * FROM user_preferences_DB"), conn)
    print("user preference table columns:", list(df_pref.columns))
    print(df_pref.head())
with app.app_context():
    for _, row in df_pref.iterrows():
        existing = UserPreference.query.filter_by(school_id=row['School ID']).first()
        if existing:
            print(f"Skipping duplicate school_id: {row['School ID']}")
            continue  # skip this entry

        new_pref = UserPreference(
            # name = row[""]
            school_id=row["School ID"],
            location=row.get("Where do you live?", ""),
            eat_time=row.get("When do you usually eat?", ""),
            delivery_freq=row.get("How often do you order delivery?", ""),
            dietary_restrictions=row.get("Do you have any dietary restrictions?", ""),
            cuisine_asian=row.get("Cuisine_Asian", 0),
            cuisine_italian=row.get("Cuisine_Italian", 0),
            cuisine_mexican=row.get("Cuisine_Mexican", 0),
            cuisine_middle_eastern=row.get("Cuisine_MiddleEastern", 0),
            cuisine_american=row.get("Cuisine_American", 0),
            cuisine_fastcasual=row.get("Cuisine_FastCasual", 0),
            spice_level=row.get("What is your spice tolerance level?", "0"),
            budget_level=row.get("What is your meal budget per person?", "0")
        )
        db.session.add(new_pref)
    db.session.commit()

print(f"Imported {len(df_pref)} user preferences into local Flask DB.")

