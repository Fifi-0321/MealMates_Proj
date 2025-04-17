# MealMates_Proj
BALABABABA~WELCOME to out MealMates Project, and our goal is to help everyone eat well with limited budget :)
This project aims to build a platform where students can form group meal orders to cut delivery fees and reduce individual dining costs. For example, users can team up to split large portions from restaurants like Chinese takeout, allowing each person to try more dishes without overspending.

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

