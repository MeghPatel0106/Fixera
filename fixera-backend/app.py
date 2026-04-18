from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import re
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from collections import Counter

app = Flask(__name__, static_folder='../fixera-frontend', static_url_path='')
CORS(app)

# ==============================================================
# Dataset Loading & TF-IDF Setup (runs once at startup)
# ==============================================================
DATASET_PATH = os.path.join(os.path.dirname(__file__), '..', 'TS-PS14.csv')

df = None
tfidf_vectorizer = None
tfidf_matrix = None


def load_dataset():
    """Load dataset and precompute TF-IDF matrix."""
    global df, tfidf_vectorizer, tfidf_matrix

    try:
        df = pd.read_csv(DATASET_PATH)
        df['text_clean'] = df['text'].str.lower().str.strip()

        # Convert numeric sentiment to label for dataset rows
        # sentiment column is a float: negative < 0, positive > 0
        df['sentiment_label'] = df['sentiment'].apply(
            lambda s: 'Negative' if s < -0.2 else ('Positive' if s > 0.2 else 'Neutral')
        )

        tfidf_vectorizer = TfidfVectorizer(max_features=5000, stop_words='english')
        tfidf_matrix = tfidf_vectorizer.fit_transform(df['text_clean'])

        print(f"[Fixera] Dataset loaded: {len(df)} complaints, TF-IDF ready.")
    except Exception as e:
        print(f"[Fixera] Warning: Could not load dataset — {e}")
        df = None


load_dataset()


# ==============================================================
# Dataset Similarity Lookup
# ==============================================================
def find_similar_complaints(text, top_n=5):
    """Find top-N most similar complaints from dataset using TF-IDF cosine similarity."""
    if df is None or tfidf_vectorizer is None:
        return None

    query_vec = tfidf_vectorizer.transform([text.lower().strip()])
    scores = cosine_similarity(query_vec, tfidf_matrix).flatten()

    top_indices = scores.argsort()[-top_n:][::-1]
    top_scores = scores[top_indices]

    # Only consider matches with a minimum similarity threshold
    matches = []
    for idx, score in zip(top_indices, top_scores):
        if score > 0.05:
            matches.append({
                'category': df.iloc[idx]['category'],
                'priority': df.iloc[idx]['priority'],
                'sentiment_label': df.iloc[idx]['sentiment_label'],
                'score': float(score),
            })

    return matches if matches else None


def dataset_consensus(matches):
    """Extract majority vote from similar complaints."""
    categories = [m['category'] for m in matches]
    priorities = [m['priority'] for m in matches]
    sentiments = [m['sentiment_label'] for m in matches]

    cat_counter = Counter(categories)
    pri_counter = Counter(priorities)
    sent_counter = Counter(sentiments)

    return {
        'category': cat_counter.most_common(1)[0][0],
        'priority': pri_counter.most_common(1)[0][0],
        'sentiment': sent_counter.most_common(1)[0][0],
        'avg_score': sum(m['score'] for m in matches) / len(matches),
    }


# ==============================================================
# Routes
# ==============================================================
@app.route('/')
def index():
    """Serve the frontend HTML page."""
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/predict', methods=['POST'])
def predict():
    """Accept a complaint and return a hybrid (rule + dataset) analysis result."""
    data = request.get_json()

    if not data or 'text' not in data:
        return jsonify({'error': 'Missing "text" field in request body'}), 400

    complaint_text = data['text'].strip()

    if not complaint_text:
        return jsonify({'error': 'Complaint text cannot be empty'}), 400

    text_lower = complaint_text.lower()

    # ==============================================================
    # PHASE 1: Rule-based analysis (existing logic preserved)
    # ==============================================================

    # ------ 1. Category Detection ------
    category_rules = {
        'Product':   ['broken', 'damaged', 'defective'],
        'Delivery':  ['late', 'delay', 'delivery'],
        'Packaging': ['box', 'packaging', 'leak'],
    }

    rule_category = 'Other'
    detected_keywords = []

    for cat, keywords in category_rules.items():
        for kw in keywords:
            if kw in text_lower:
                rule_category = cat
                detected_keywords.append(kw)
        if rule_category != 'Other':
            break

    # ------ 2. Sentiment Detection ------

    negative_words = ['bad', 'worst', 'angry', 'terrible', 'not happy', 'unhappy', 'horrible']
    positive_words = ['good', 'great', 'thank', 'happy']

    rule_sentiment = 'Neutral'

    for word in negative_words:
        # Use word boundary to avoid 'happy' matching inside 'unhappy'
        if re.search(r'\b' + re.escape(word) + r'\b', text_lower):
            rule_sentiment = 'Negative'
            detected_keywords.append(word)
            break

    if rule_sentiment == 'Neutral':
        for word in positive_words:
            if re.search(r'\b' + re.escape(word) + r'\b', text_lower):
                rule_sentiment = 'Positive'
                detected_keywords.append(word)
                break

    # ------ 3. Priority Logic ------
    urgent_words = ['broken', 'urgent', 'immediately']
    has_urgent = any(w in text_lower for w in urgent_words)

    if rule_sentiment == 'Negative' and has_urgent:
        rule_priority = 'High'
    elif rule_sentiment == 'Negative':
        rule_priority = 'Medium'
    else:
        rule_priority = 'Low'

    # ==============================================================
    # PHASE 2: Dataset-based similarity lookup
    # ==============================================================
    matches = find_similar_complaints(complaint_text)
    ds = dataset_consensus(matches) if matches else None

    # ==============================================================
    # PHASE 3: Hybrid merge — rules take priority, dataset fills gaps
    # ==============================================================
    reason_parts = []

    # --- Category ---
    if rule_category != 'Other':
        # Rule detected a category — use it
        category = rule_category
    elif ds:
        # Rule missed — fallback to dataset
        category = ds['category']
    else:
        category = 'Other'

    # --- Sentiment ---
    if rule_sentiment != 'Neutral':
        # Rule has a strong opinion — use it
        sentiment = rule_sentiment
    elif ds:
        # Rule was neutral — use dataset suggestion
        sentiment = ds['sentiment']
    else:
        sentiment = 'Neutral'

    # --- Priority ---
    # Recalculate priority based on final sentiment
    if sentiment == 'Negative' and has_urgent:
        priority = 'High'
    elif sentiment == 'Negative':
        priority = 'Medium'
    elif ds:
        # Use dataset priority for non-negative sentiments
        priority = ds['priority']
    else:
        priority = 'Low'

    # ==============================================================
    # PHASE 4: Escalation & Insight Layer
    # ==============================================================
    risk_words = ['broken', 'leak', 'defective', 'danger', 'health', 'unsafe']
    risk_hits = [w for w in risk_words if w in text_lower]
    risk_level = 'High' if risk_hits else 'Normal'

    # Force priority to High for safety-critical complaints
    if risk_level == 'High':
        priority = 'High'

    # Build insight message
    insight_parts = []

    if risk_level == 'High':
        insight_parts.append('⚠ Potential safety or critical issue detected')

    if ds and ds['avg_score'] >= 0.3:
        insight_parts.append('Similar complaints observed in past data')

    # ==============================================================
    # PHASE 5: Final field assembly
    # ==============================================================

    # --- Confidence (recalculate with escalation) ---
    if ds:
        rule_matches_ds = (
            (rule_category == ds['category'] or rule_category == 'Other') and
            (rule_sentiment == ds['sentiment'] or rule_sentiment == 'Neutral')
        )
        if rule_category != 'Other' and rule_category == ds['category']:
            confidence = 0.92
        elif rule_matches_ds:
            confidence = 0.85
        else:
            confidence = 0.7
    else:
        if rule_category != 'Other' and rule_sentiment != 'Neutral':
            confidence = 0.8
        elif rule_category != 'Other' or rule_sentiment != 'Neutral':
            confidence = 0.65
        else:
            confidence = 0.5

    # Boost confidence when escalation and dataset agree
    if risk_level == 'High' and confidence < 0.9:
        confidence = min(confidence + 0.1, 0.95)

    # --- Reason (enriched with insights) ---
    if detected_keywords:
        unique_keywords = list(dict.fromkeys(detected_keywords))
        reason_parts.append('Detected keywords: ' + ', '.join(unique_keywords))

    if ds:
        reason_parts.append(
            f'Matched with similar past complaints (similarity: {ds["avg_score"]:.0%})'
        )

    for insight in insight_parts:
        reason_parts.append(insight)

    if not reason_parts:
        reason = 'No specific keywords detected. Standard issue'
    else:
        reason = '. '.join(reason_parts)

    # --- Recommendation (enhanced for high-risk) ---
    action_map = {
        'Product':   'Offer replacement or refund',
        'Delivery':  'Apologize and expedite shipment',
        'Packaging': 'Check packaging process and resend item',
        'Trade':     'Connect with trade support specialist',
    }
    action = action_map.get(category, 'Forward to support team')

    if risk_level == 'High':
        action = 'ESCALATE: ' + action + ' — flag for immediate review'

    # --- Estimated Time (faster for high-risk) ---
    if risk_level == 'High':
        estimated_time = '12 hours'
    else:
        time_map = {'High': '24 hours', 'Medium': '48 hours', 'Low': '72 hours'}
        estimated_time = time_map[priority]

    # ------ Build response ------
    result = {
        'category': category,
        'priority': priority,
        'sentiment': sentiment,
        'confidence': confidence,
        'reason': reason,
        'action': action,
        'status': 'Pending',
        'estimated_time': estimated_time,
    }

    return jsonify(result)


if __name__ == '__main__':
    app.run(debug=True, port=5000)
