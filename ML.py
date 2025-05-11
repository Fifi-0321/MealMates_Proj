# ml.py
from models import UserPreference
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import KMeans
import numpy as np

# === Helper: Cluster assignment (run periodically) ===
def compute_user_clusters(n_clusters=8):
    all_users = UserPreference.query.filter_by(active=True).all()
    user_vecs = np.array([u.to_vector() for u in all_users])
    if len(user_vecs) < n_clusters:
        return {}  # not enough data
    kmeans = KMeans(n_clusters=n_clusters, random_state=42)
    labels = kmeans.fit_predict(user_vecs)
    return {u.school_id: label for u, label in zip(all_users, labels)}

# === Main function: cosine matching within cluster ===
def get_top_matches_by_school_id(school_id, top_k=5):
    all_users = UserPreference.query.filter_by(active=True).all()
    cluster_map = compute_user_clusters()

    target_user = next((u for u in all_users if u.school_id == school_id), None)
    if not target_user:
        return []

    target_cluster = cluster_map.get(school_id)
    if target_cluster is None:
        return []

    target_vec = target_user.to_vector().reshape(1, -1)

    cluster_users = [
        u for u in all_users 
        if u.school_id != school_id and cluster_map.get(u.school_id) == target_cluster
    ]
    if not cluster_users:
        return []

    user_vecs = np.array([u.to_vector() for u in cluster_users])
    sim_scores = cosine_similarity(target_vec, user_vecs)[0]
    top_indices = np.argsort(sim_scores)[::-1][:top_k]

    return [(cluster_users[i], sim_scores[i]) for i in top_indices if sim_scores[i] > 0]
