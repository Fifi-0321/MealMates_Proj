# ml.py
from models import UserPreference
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

def get_top_matches_by_school_id(school_id, top_k=5):
    all_users = UserPreference.query.all()
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
