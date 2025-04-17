# MealMates_Proj
BALABABABA~WELCOME to out MealMates Project, and our goal is to help everyone eat well with limited budget :)
This project aims to build a platform where students can form group meal orders to cut delivery fees and reduce individual dining costs. For example, users can team up to split large portions from restaurants like Chinese takeout, allowing each person to try more dishes without overspending.

# 🍽️ MealMate Backend System Overview

This document outlines the architecture of the MealMate backend, which powers group food ordering via user clustering, restaurant recommendation, and external data integration.

---

## 🗃️ Databases

### 1. `user_database`
- **Purpose**: Stores user profiles and dining preferences
- **Primary Operations**:
  - User registration and authentication
  - Profile management
  - Preference tracking

### 2. `restaurant_database`
- **Purpose**: Central repository of restaurant information
- **Data Sources**:
  - **Yelp API**: Basic info, ratings, categories
  - **WorldWide Restaurant API**: Global data with descriptions
  - **NYC Open Data**: Health inspection records and grades
- **Merging Strategy**:
  - Fuzzy matching on restaurant names and geographic coordinates

---

## 🌐 APIs

### 1. `yelp_api`
- Restaurant basic information
- Ratings (1.0–5.0)
- Categories
- Geographic coordinates

### 2. `worldwide_restaurants_api`
- Global restaurant data
- Descriptions and cuisine types
- Address information

### 3. `nyc_open_data_api`
- Restaurant inspection data
- Health grades (A, B, C, N/A)
- Violation descriptions
- Critical flag indicators

### 4. `internal_user_api`
- User registration/authentication
- Profile management
- Preference settings

---

## ⏱ Scheduled Jobs

### 1. `user_clustering_job`
- **Frequency**: Daily
- **Purpose**: Group users into dining cohorts (3–5 people)
- **Method**: Graph-theoretic clustering
- **Factors**: Preference similarity, geographic proximity

### 2. `recommendation_job`
- **Frequency**: Daily (post-clustering)
- **Purpose**: Suggest restaurants to user groups
- **Method**: Collaborative filtering
- **Factors**: Group preferences, ratings, health grades

---

## ⚙️ Workers

### 1. `notification_worker`
- Sends user alerts and group invites
- Dispatches recommendation notifications

### 2. `data_sync_worker`
- Syncs restaurant data from external APIs
- Ensures freshness and reliability

---

## 🎯 Event Handlers

### 1. `user_activity_handler`
- Tracks engagement with recommendations
- Updates preference models based on feedback

### 2. `group_event_handler`
- Handles group formation and dissolution events

---

## 🔄 Data Pipelines

### 1. `restaurant_integration_pipeline`
- **Stages**:
  - Data collection (Yelp, WorldWide, NYC)
  - Entity resolution (duplicate detection)
  - Data normalization
  - Record merging with confidence scoring

### 2. `user_preference_pipeline`
- **Stages**:
  - Explicit preference collection
  - Implicit inference from behavior
  - Preference model updates

---

## 🔌 Service Integrations

### 1. `geolocation_service`
- Distance calculations
- Travel time optimization

### 2. `review_aggregator`
- Combines multi-platform reviews
- Normalizes rating scales

### 3. `reservation_connector`
- Interfaces with restaurant booking systems
- Checks table availability

---

## 👨‍💻 Authors & Maintainers

Built by the MealMate backend engineering team. Contributions welcome!



# 🍱 MealMate Data Analytics Engine

This module powers the intelligent user-matching system behind MealMate, a group food ordering assistant. It enables personalized and scalable user clustering based on dining preferences using lightweight, interpretable machine learning.

---

## 🚀 Overview

The core idea is to **match users with similar food preferences** to facilitate optimized group orders. This is achieved by encoding user preferences as structured vectors and computing similarity between users using cosine distance.

---

## 📊 Data Format

Each user’s preference is represented as a **6×4 matrix**, where:

| Row Index | Feature Group      | Encoding                        |
|-----------|--------------------|---------------------------------|
| 0         | Eating Time        | One-hot over 6 time slots       |
| 1         | Cuisine Ranking    | Ranked (3/2/1) or zero          |
| 2         | Spice Level        | One-hot with 2 padding slots    |
| 3         | Budget Level       | One-hot with 2 padding slots    |
| 4–5       | Reserved / Padding | Zero-filled for extensibility   |

This matrix is flattened to a 24-dimensional vector for modeling.

---

## 🧠 Machine Learning Workflow

1. **Data Preparation**:
   - Load user preference matrices from `matching_matrix.json`
   - Flatten to vectors
   - Split into `train` (80%) and `test` (20%) sets

2. **Similarity Model**:
   - Use **cosine similarity** to compare users
   - Retrieve ranked list of most similar users from the training set

3. **Outputs**:
   - `all_sorted_matches.json`: maps each test user to a list of similar training users
   - `matching_model.pkl`: pre-trained matching object
   - `pca_user_embedding.png`: PCA visualization of all user vectors

---

## 📈 Evaluation & Visualization

- **Similarity Distribution**: Histogram showing cosine similarity scores for best matches
- **PCA Embedding**: 2D projection of all users using PCA, color-coded by train/test split

---

## 🧪 Future Improvements

- Integrate dealbreakers and filters (e.g., location, wait time)
- Introduce clustering (e.g., KMeans or HDBSCAN) for group segmentation
- Use online feedback to refine matching dynamically

---

## 📁 Key Files

| File                             | Description                             |
|----------------------------------|-----------------------------------------|
| `matching_matrix.json`           | Raw user preference matrices (6×4)      |
| `train_user_matrix.json`         | Training subset                         |
| `test_user_matrix.json`          | Testing subset                          |
| `all_sorted_matches.json`        | Match results for each test user        |
| `matching_model.pkl`             | Serialized matching model               |
| `pca_user_embedding.png`         | User embedding visualization            |

---

## 🛠 Requirements

- Python 3.7+
- `scikit-learn`
- `matplotlib`
- `pandas`, `numpy`

Install dependencies with:

```bash
pip install scikit-learn matplotlib pandas numpy

