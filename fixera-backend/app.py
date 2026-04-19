from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
import os
import subprocess
import re
import json
import sqlite3
import pickle
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from collections import Counter

app = Flask(__name__, static_folder='../fixera-frontend', static_url_path='')
CORS(app)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(os.path.dirname(__file__), '..', 'SelfData.csv')
DB_PATH = os.path.join(BASE_DIR, 'complaints.db')
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'model.pkl')
ML_VECTORIZER_PATH = os.path.join(os.path.dirname(__file__), 'ml_vectorizer.pkl')


def get_db():
    """Get a database connection (per-request)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create complaints table if it doesn't exist."""
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            category TEXT,
            priority TEXT,
            sentiment TEXT,
            confidence REAL,
            reason TEXT,
            action TEXT,
            status TEXT DEFAULT 'Pending',
            estimated_time TEXT,
            timestamp TEXT,
            updated_at TEXT,
            sla_deadline TEXT
        )
    ''')
    # Add columns if upgrading from old schema
    try:
        conn.execute('ALTER TABLE complaints ADD COLUMN updated_at TEXT')
    except Exception:
        pass
    try:
        conn.execute('ALTER TABLE complaints ADD COLUMN sla_deadline TEXT')
    except Exception:
        pass
    try:
        conn.execute('ALTER TABLE complaints ADD COLUMN customer_name TEXT')
    except Exception:
        pass
    try:
        conn.execute('ALTER TABLE complaints ADD COLUMN order_id TEXT')
    except Exception:
        pass
    # Add resolved_at column for lifecycle tracking
    try:
        conn.execute('ALTER TABLE complaints ADD COLUMN resolved_at TEXT')
    except Exception:
        pass
    conn.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            total_complaints INTEGER DEFAULT 0,
            high_count INTEGER DEFAULT 0,
            medium_count INTEGER DEFAULT 0,
            low_count INTEGER DEFAULT 0,
            categories_json TEXT DEFAULT '{}',
            sentiments_json TEXT DEFAULT '{}'
        )
    ''')
    # Activity logs for status change tracking
    conn.execute('''
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id INTEGER NOT NULL,
            old_status TEXT,
            new_status TEXT,
            changed_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    try:
        conn.execute('ALTER TABLE reports ADD COLUMN categories_json TEXT DEFAULT \'{}\'')
    except Exception:
        pass
    try:
        conn.execute('ALTER TABLE reports ADD COLUMN sentiments_json TEXT DEFAULT \'{}\'')  
    except Exception:
        pass
    # Add is_hidden column for soft delete
    try:
        conn.execute('ALTER TABLE complaints ADD COLUMN is_hidden INTEGER DEFAULT 0')
    except Exception:
        pass
    conn.commit()
    conn.close()
    # Create reports folder
    reports_dir = os.path.join(BASE_DIR, 'reports')
    os.makedirs(reports_dir, exist_ok=True)
    print('[Fixera] Database initialized.')


init_db()

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

# ---- ML Model Loading ----
ml_model = None
ml_vectorizer = None

def load_ml_model():
    """Load the trained ML model and its TF-IDF vectorizer."""
    global ml_model, ml_vectorizer
    try:
        with open(MODEL_PATH, 'rb') as f:
            ml_model = pickle.load(f)
        with open(ML_VECTORIZER_PATH, 'rb') as f:
            ml_vectorizer = pickle.load(f)
        print('[Fixera] ML model loaded successfully.')
    except FileNotFoundError:
        print('[Fixera] Warning: ML model files not found. Run train_model.py first.')
    except Exception as e:
        print(f'[Fixera] Warning: Could not load ML model — {e}')

load_ml_model()

def ml_preprocess(text):
    """Preprocess text identically to training pipeline."""
    text = str(text).lower()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\d+', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def ml_predict_category(text):
    """Predict category using trained ML model. Returns (category, confidence) or None."""
    if ml_model is None or ml_vectorizer is None:
        return None
    try:
        processed = ml_preprocess(text)
        X = ml_vectorizer.transform([processed])
        probas = ml_model.predict_proba(X)[0]
        pred_idx = np.argmax(probas)
        category = ml_model.classes_[pred_idx]
        confidence = float(probas[pred_idx])
        return {'category': category, 'confidence': confidence}
    except Exception as e:
        print(f'[Fixera] ML prediction error: {e}')
        return None

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


def find_similar_past_actions(text, top_n=5, threshold=0.15):
    """Find the most common action from similar past complaints stored in the DB."""
    try:
        conn = get_db()
        rows = conn.execute('SELECT text, action FROM complaints').fetchall()
        conn.close()

        if len(rows) < 2:
            return None

        past_texts = [r['text'].lower().strip() for r in rows if r['action']]
        past_actions = [r['action'] for r in rows if r['action']]

        # Build a temporary TF-IDF over past complaints
        vec = TfidfVectorizer(max_features=2000, stop_words='english')
        past_matrix = vec.fit_transform(past_texts)
        query_vec = vec.transform([text.lower().strip()])

        scores = cosine_similarity(query_vec, past_matrix).flatten()
        top_indices = scores.argsort()[-top_n:][::-1]

        # Actions to ignore (generic/non-actionable)
        ignore_actions = {'No immediate action required', 'No action required',
                          'Resolve within standard process', 'Forward to support team'}

        matched_actions = []
        for idx in top_indices:
            if scores[idx] >= threshold:
                act = past_actions[idx]
                # Strip all priority prefixes and suffixes to get clean core action
                core = act if act else ''
                core = re.sub(r'(URGENT:\s*)+', '', core)
                core = re.sub(r'(ESCALATE:\s*)+', '', core)
                core = core.split(' — ')[0].strip()
                core = re.sub(r'(\s*Immediate action required\.)+', '', core)
                core = re.sub(r'(\s*Ensure timely resolution\.)+', '', core)
                core = re.sub(r'(\s*Monitor situation and improve service\.)+', '', core)
                core = core.strip()
                if core and core not in ignore_actions:
                    matched_actions.append(core)

        if not matched_actions:
            return None

        action_counter = Counter(matched_actions)
        best_action, count = action_counter.most_common(1)[0]
        return {'action': best_action, 'count': count, 'total': len(matched_actions)}

    except Exception as e:
        print(f'[Fixera] Past action lookup error: {e}')
        return None

@app.route('/')
def index():
    """Serve the frontend HTML page."""
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/predict', methods=['POST'])
def predict():
    """Accept a complaint and return a hybrid (rule + dataset) analysis result."""
    data = request.get_json()
    skip_save = data.get('skip_save', False) if data else False

    if not data or 'text' not in data:
        return jsonify({'error': 'Missing "text" field in request body'}), 400

    complaint_text = data['text'].strip()
    customer_name = data.get('customer_name', '').strip() or None
    order_id = data.get('order_id', '').strip() or None

    if not complaint_text:
        return jsonify({'error': 'Complaint text cannot be empty'}), 400

    text_lower = complaint_text.lower()

    # ---- General negation handling (must run BEFORE synonym normalization) ----
    # Positive words that flip to negative when preceded by negation
    _pos_to_neg = {
        'good': 'bad', 'great': 'bad', 'excellent': 'bad', 'amazing': 'bad',
        'nice': 'bad', 'wonderful': 'bad', 'fantastic': 'bad', 'perfect': 'bad',
        'useful': 'useless', 'helpful': 'useless',
        'satisfied': 'unhappy', 'happy': 'unhappy',
        'working': 'broken', 'functioning': 'broken', 'usable': 'broken',
        'responding': 'broken', 'operational': 'broken',
        'acceptable': 'terrible', 'recommended': 'bad',
        'received': 'missing', 'delivered': 'missing',
    }
    # Negative words that flip to positive when preceded by negation
    _neg_to_pos = {
        'bad': 'good', 'terrible': 'okay', 'worst': 'okay', 'horrible': 'okay',
    }
    _negation_words = {'not', 'no', 'never', "n't", 'nt'}

    # Tokenize, apply negation window (next 3 words after negation)
    words = text_lower.split()
    i = 0
    while i < len(words):
        word_clean = words[i].strip('.,!?;:')

        # Check if this is a negation word or ends with n't
        is_neg = word_clean in _negation_words or word_clean.endswith("n't")

        if is_neg:
            # Look ahead up to 3 words for a word to flip
            for j in range(i + 1, min(i + 4, len(words))):
                target = words[j].strip('.,!?;:')
                if target in _pos_to_neg:
                    words[j] = _pos_to_neg[target]
                    words[i] = ''  # Remove the negation word
                    break
                elif target in _neg_to_pos:
                    words[j] = _neg_to_pos[target]
                    words[i] = ''  # Remove the negation word
                    break
        i += 1

    text_lower = ' '.join(w for w in words if w).strip()

    # Sentence-level negation: if negation + complaint keyword both present, inject 'bad'
    _complaint_kw = {'working', 'functioning', 'usable', 'responding', 'operational'}
    has_negation = any(n in text_lower.split() for n in _negation_words)
    has_complaint_kw = any(k in text_lower for k in _complaint_kw)
    if has_negation and has_complaint_kw and 'bad' not in text_lower:
        text_lower = 'bad ' + text_lower


    # ---- Synonym normalization (helps ML + rule matching) ----
    _synonyms = [
        ('stopped functioning', 'broken'),
        ('stopped working', 'broken'),
        ('malfunction', 'broken'),
        ("isn't working", 'broken'),
        ("doesn't work", 'broken'),
        ("does not work", 'broken'),
        ("did not work", 'broken'),
        ('failed', 'broken'),
        ('faulty', 'defective'),
        ('arrived late', 'late delivery'),
        ('delayed', 'late delivery'),
        ('took too long', 'late delivery'),
        ('no response', 'bad service'),
        ('ignored', 'bad service'),
        ('never received', 'missing delivery'),
        ('torn', 'damaged'),
        ('crushed', 'damaged'),
        ('ripped', 'damaged'),
        ('cracked', 'broken'),
    ]
    for old, new in _synonyms:
        text_lower = text_lower.replace(old, new)

    # =========================================================
    # NON-COMPLAINT DETECTION LAYER
    # Filters gibberish, random text, and irrelevant input
    # =========================================================
    is_invalid = False
    invalid_reason = ''

    # Check 1: Too short
    if len(complaint_text) < 5:
        is_invalid = True
        invalid_reason = 'Input too short to be a valid complaint'

    # Check 2: No meaningful words (no vowels = likely gibberish)
    if not is_invalid:
        vowel_count = sum(1 for c in text_lower if c in 'aeiou')
        alpha_count = sum(1 for c in text_lower if c.isalpha())
        if alpha_count < 3 or (alpha_count > 0 and vowel_count / alpha_count < 0.1):
            is_invalid = True
            invalid_reason = 'Input appears to be random characters or gibberish'

    # Check 3: ML confidence too low + no similarity match
    # But skip if text contains recognized complaint/sentiment words (from negation resolution)
    _known_complaint_words = {'bad', 'broken', 'unhappy', 'useless', 'terrible', 'damaged',
                              'defective', 'missing', 'worst', 'horrible', 'angry', 'leak',
                              'late', 'delay', 'unsafe', 'danger'}
    has_known_words = any(w in text_lower.split() for w in _known_complaint_words)

    if not is_invalid and not has_known_words:
        _ml_check = ml_predict_category(text_lower)
        _sim_check = find_similar_complaints(text_lower)
        _ds_check = dataset_consensus(_sim_check) if _sim_check else None

        ml_conf = _ml_check['confidence'] if _ml_check else 0
        sim_score = _ds_check['avg_score'] if _ds_check else 0

        if ml_conf < 0.50 and sim_score < 0.40:
            is_invalid = True
            invalid_reason = f'Low ML confidence ({ml_conf:.0%}) and weak similarity ({sim_score:.0%})'

    if is_invalid:
        now = datetime.now().isoformat()
        result = {
            'category': 'Non-Complaint',
            'priority': 'None',
            'sentiment': 'Neutral',
            'confidence': 0.0,
            'reason': f'Input not recognized as a valid complaint. {invalid_reason}. Post-processed for consistency using rule validation layer',
            'action': 'No action required',
            'status': 'Ignored',
            'estimated_time': 'N/A',
        }

        # Save to DB as ignored (skip when called from report generator)
        if not skip_save:
            try:
                conn = get_db()
                cur = conn.execute(
                    '''INSERT INTO complaints
                       (text, category, priority, sentiment, confidence, reason, action, status, estimated_time, timestamp, updated_at, sla_deadline, customer_name, order_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (complaint_text, 'Non-Complaint', 'None', 'Neutral', 0.0,
                     result['reason'], 'No action required', 'Ignored', 'N/A',
                     now, now, None, customer_name, order_id)
                )
                result['complaint_id'] = cur.lastrowid
                conn.commit()
                conn.close()
            except Exception as e:
                print(f'[Fixera] DB write error: {e}')

        return jsonify(result)

    # =========================================================
    # END NON-COMPLAINT DETECTION
    # =========================================================

    category_rules = {
        'Trade':     ['charge', 'charged', 'price', 'billing', 'bill', 'invoice', 'amount',
                      'overcharged', 'extra cost', 'wrong price', 'overcharge', 'refund',
                      'payment', 'money', 'cost', 'fee', 'discount', 'coupon', 'promo'],
        'Product':   ['broken', 'damaged', 'defective', 'not working', 'malfunction', 'faulty',
                      'battery', 'screen', 'cracked', 'overheating', 'draining', 'dead',
                      'stopped working', 'poor quality', 'does not work', 'not functioning',
                      'charger', 'charging', 'power', 'freeze', 'crash', 'glitch', 'error'],
        'Delivery':  ['late', 'delay', 'delivery', 'shipping', 'not received', 'lost',
                      'wrong address', 'tracking', 'courier', 'dispatched', 'transit',
                      'not delivered', 'missing delivery', 'shipment'],
        'Packaging': ['box damaged', 'packaging', 'leak', 'torn package', 'wrapper',
                      'seal broken', 'crushed box', 'open package', 'packing'],
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


    negative_words = ['bad', 'worst', 'angry', 'terrible', 'not happy', 'unhappy', 'horrible','damaged']
    positive_words = ['good', 'great', 'thank', 'happy']

    rule_sentiment = 'Neutral'

    for word in negative_words:
     
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

    urgent_words = ['broken', 'urgent', 'immediately']
    has_urgent = any(w in text_lower for w in urgent_words)

    if rule_sentiment == 'Negative' and has_urgent:
        rule_priority = 'High'
    elif rule_sentiment == 'Negative':
        rule_priority = 'Medium'
    else:
        rule_priority = 'Low'

    matches = find_similar_complaints(text_lower)
    ds = dataset_consensus(matches) if matches else None

    # --- ML Model Prediction (primary classifier) ---
    ml_result = ml_predict_category(text_lower)

    reason_parts = []

    # Hybrid category: rules (keyword match) > ML (high confidence) > dataset > Other
    if rule_category != 'Other':
        category = rule_category
        reason_parts.append(f'Detected keywords: {", ".join(detected_keywords)}')
    elif ml_result and ml_result['confidence'] >= 0.6:
        category = ml_result['category']
        reason_parts.append(f'ML model prediction ({ml_result["confidence"]:.0%} confidence)')
    elif ds:
        category = ds['category']
    elif ml_result:
        # Low-confidence ML is still better than "Other"
        category = ml_result['category']
        reason_parts.append(f'ML model prediction (low confidence: {ml_result["confidence"]:.0%})')
    else:
        category = 'Other'


    if rule_sentiment != 'Neutral':

        sentiment = rule_sentiment
    elif ds:

        sentiment = ds['sentiment']
    else:
        sentiment = 'Neutral'



    if sentiment == 'Negative' and has_urgent:
        priority = 'High'
    elif sentiment == 'Negative':
        priority = 'Medium'
    elif ds:

        priority = ds['priority']
    else:
        priority = 'Low'

    risk_words = ['broken', 'leak', 'defective', 'danger', 'health', 'unsafe']
    risk_hits = [w for w in risk_words if w in text_lower]
    risk_level = 'High' if risk_hits else 'Normal'


    if risk_level == 'High':
        priority = 'High'


    insight_parts = []

    if risk_level == 'High':
        insight_parts.append('⚠ Potential safety or critical issue detected')

    if ds and ds['avg_score'] >= 0.3:
        insight_parts.append('Similar complaints observed in past data')


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

    # If ML model was primary, use its confidence as dominant signal
    if ml_result and ml_result['confidence'] >= 0.6:
        confidence = max(confidence, ml_result['confidence'])


    if risk_level == 'High' and confidence < 0.9:
        confidence = min(confidence + 0.1, 0.95)


    if detected_keywords:
        unique_keywords = list(dict.fromkeys(detected_keywords))
        reason_parts.append('Detected keywords: ' + ', '.join(unique_keywords))

    if ds:
        reason_parts.append(
            f'Matched with similar past complaints (similarity: {ds["avg_score"]:.0%})'
        )

    for insight in insight_parts:
        reason_parts.append(insight)

    # --- Recommendation (context-aware variation pool + hash selection) ---
    _recommendation_pool = {
        'Product_broken': [
            'Initiate product replacement after defect validation.',
            'Proceed with replacement after confirming product failure.',
            'Arrange immediate replacement for defective item.',
            'Start replacement workflow after inspection.',
            'Trigger replacement protocol due to malfunction.',
            'Process replacement request for faulty product.',
            'Approve replacement after defect confirmation.',
            'Escalate for replacement due to product breakdown.',
            'Begin corrective replacement process immediately.',
            'Validate issue and proceed with replacement.',
            'Coordinate return and issue replacement unit.',
            'Fast-track replacement for confirmed product defect.',
            'Issue refund or replacement per product warranty.',
            'Authorize expedited replacement for broken product.',
            'Schedule pickup and dispatch replacement item.',
            'Confirm defect report and arrange product swap.',
            'Log product failure and initiate replacement cycle.',
            'Dispatch technician or send replacement based on assessment.',
            'File product defect report and process return.',
            'Expedite replacement shipment for damaged goods.',
            'Verify product malfunction details and arrange swap.',
            'Contact customer to confirm defect and ship replacement.',
            'Route to fulfillment team for priority replacement.',
            'Initiate RMA process for defective product.',
            'Open warranty claim and arrange product exchange.',
            'Process expedited return for product malfunction.',
            'Send replacement unit with upgraded shipping priority.',
            'Escalate to product team and dispatch replacement.',
            'Approve no-questions-asked replacement for defect.',
            'Begin return-and-replace workflow for broken item.',
        ],
        'Product_quality': [
            'Conduct detailed quality inspection and take corrective action.',
            'Initiate quality review and provide replacement if required.',
            'Perform product quality analysis and resolve issue.',
            'Escalate to quality control team for investigation.',
            'Log quality concern and schedule product review.',
            'Route to QA team for product inspection.',
            'Investigate product quality deviation and respond.',
            'Open quality investigation case for this product.',
            'Assess product quality against standards and act.',
            'Initiate quality assurance review and follow up.',
            'Flag product for quality audit and notify team.',
            'Submit product sample for quality testing.',
            'Cross-reference quality complaint with batch records.',
            'Arrange product testing and offer interim solution.',
            'Trigger quality hold on product batch for review.',
            'Coordinate with manufacturing on quality concern.',
            'Document quality issue and initiate corrective plan.',
            'Review product specifications and address deviation.',
            'Schedule quality callback with customer for details.',
            'Raise quality ticket and assign to inspection team.',
            'Run quality diagnostics and provide findings.',
            'Compare product against quality benchmarks.',
            'Initiate root cause analysis for quality issue.',
            'Offer replacement pending quality investigation.',
            'Alert quality department and track resolution.',
            'Investigate batch-level quality and report findings.',
            'Conduct product recall assessment if pattern detected.',
            'Run compliance check on product quality standards.',
            'Assign quality specialist to investigate complaint.',
            'Evaluate product against incoming inspection criteria.',
        ],
        'Packaging_damage': [
            'Replace item and improve packaging durability.',
            'Initiate replacement due to packaging damage.',
            'Investigate packaging failure and reinforce protection.',
            'Escalate packaging issue to logistics team.',
            'Arrange reshipment with enhanced packaging.',
            'Log packaging defect and send replacement.',
            'Review packaging materials and reship product.',
            'Coordinate with warehouse to fix packaging issue.',
            'Reship with reinforced protective packaging.',
            'File packaging damage report and replace item.',
            'Upgrade packaging standards for this product type.',
            'Issue replacement and flag packaging for review.',
            'Audit packaging process for this shipment route.',
            'Send replacement with double-layer packaging.',
            'Investigate handling damage during transit.',
            'Notify logistics partner about packaging failure.',
            'Replace damaged item and update packaging specs.',
            'Schedule packaging quality review with supplier.',
            'Fast-track replacement for packaging-damaged goods.',
            'Implement corrective packaging measures immediately.',
            'Request images of damage and dispatch replacement.',
            'Coordinate with carrier regarding handling issues.',
            'Reship item with fragile handling instructions.',
            'Escalate to packaging engineering team.',
            'Apply damage prevention protocol for future shipments.',
            'Review transit route for packaging risk factors.',
            'Issue credit and reship with improved packaging.',
            'Update packaging guidelines based on damage report.',
            'Conduct packaging stress test for this product.',
            'Arrange express replacement for packaging failure.',
        ],
        'Packaging_general': [
            'Review packaging standards and address concern.',
            'Investigate packaging issue and improve process.',
            'Assess packaging complaint and take action.',
            'Route packaging feedback to operations team.',
            'Log packaging concern for process improvement.',
            'Coordinate packaging review with quality team.',
            'Address packaging issue and offer resolution.',
            'Evaluate packaging complaint and adjust standards.',
            'Forward packaging feedback to warehouse team.',
            'Implement packaging improvement based on feedback.',
            'Review packaging specifications for adequacy.',
            'Assess packaging issue and arrange resolution.',
            'Document packaging concern for trend analysis.',
            'Escalate packaging feedback to operations lead.',
            'Review packaging workflow and make corrections.',
            'Coordinate with fulfillment on packaging concern.',
            'Optimize packaging process for this product line.',
            'Address customer packaging concern promptly.',
            'Review packaging materials for this order type.',
            'Log packaging issue and track improvement progress.',
            'Assign packaging review to warehouse supervisor.',
            'Investigate packaging process gap and resolve.',
            'Update packaging checklist based on complaint.',
            'Verify packaging compliance for this shipment.',
            'Initiate packaging audit for quality assurance.',
            'Review packaging handling procedures.',
            'Coordinate packaging fix with supply chain team.',
            'Monitor packaging quality for recurring issues.',
            'Apply corrective packaging measures for product.',
            'Schedule packaging process improvement review.',
        ],
        'Delivery_delay': [
            'Investigate delivery delay and optimize logistics.',
            'Coordinate with shipping partner to resolve delay.',
            'Escalate delay issue and improve delivery timeline.',
            'Analyze shipment tracking for delay cause.',
            'Expedite shipment and notify customer of update.',
            'Contact carrier for delivery status clarification.',
            'Reroute package for faster delivery completion.',
            'Issue delivery priority upgrade for delayed order.',
            'Investigate logistics bottleneck causing delay.',
            'Coordinate express delivery to resolve delay.',
            'Provide tracking update and expedite shipment.',
            'Escalate to shipping partner for immediate action.',
            'Analyze delivery network for delay pattern.',
            'Offer compensation and expedite remaining delivery.',
            'Contact last-mile delivery partner for resolution.',
            'Track package location and push for delivery.',
            'Arrange alternative delivery route if needed.',
            'Issue shipping credit due to delivery delay.',
            'Open investigation with courier service.',
            'Provide proactive delivery status update.',
            'Escalate to logistics manager for priority routing.',
            'Coordinate with dispatch for same-day resolution.',
            'Review carrier performance for this route.',
            'Arrange priority redelivery for delayed package.',
            'File delay claim with shipping provider.',
            'Offer delivery guarantee and compensation.',
            'Push shipment through priority delivery channel.',
            'Alert warehouse to expedite pending shipment.',
            'Notify customer with revised delivery estimate.',
            'Initiate carrier performance review for delays.',
        ],
        'Delivery_general': [
            'Investigate delivery issue and take corrective action.',
            'Coordinate with logistics to resolve delivery concern.',
            'Escalate delivery complaint to shipping department.',
            'Review delivery process and address the issue.',
            'Follow up on delivery status and resolve concern.',
            'Contact delivery partner to investigate issue.',
            'Initiate delivery investigation and update customer.',
            'Log delivery concern and coordinate resolution.',
            'Review shipment details and address complaint.',
            'Assign delivery issue to logistics coordinator.',
            'Investigate delivery exception and respond.',
            'Track delivery progress and provide update.',
            'Coordinate with fulfillment on delivery issue.',
            'Escalate delivery concern for priority handling.',
            'Review delivery workflow for improvement.',
            'Contact carrier about delivery discrepancy.',
            'Investigate delivery complaint and offer solution.',
            'Open delivery case and assign to operations.',
            'Follow up with customer on delivery resolution.',
            'File delivery incident report for analysis.',
            'Coordinate delivery correction with warehouse.',
            'Review delivery SLA compliance for this order.',
            'Initiate delivery recovery process.',
            'Provide delivery support and track outcome.',
            'Assess delivery failure and prevent recurrence.',
            'Submit delivery exception to logistics team.',
            'Arrange corrective delivery action immediately.',
            'Monitor delivery performance for this region.',
            'Coordinate re-delivery or alternative solution.',
            'Escalate delivery issue to regional manager.',
        ],
        'Trade_general': [
            'Connect with trade support specialist for resolution.',
            'Route to trade compliance team for review.',
            'Investigate trade concern and provide guidance.',
            'Escalate to trade operations for handling.',
            'Assign trade issue to specialized support agent.',
            'Review trade dispute and initiate resolution.',
            'Coordinate with trade department for action.',
            'Log trade complaint and route to specialist.',
            'Investigate trade issue and respond to customer.',
            'Open trade case with dedicated support team.',
            'Escalate trade matter to compliance officer.',
            'Review trade terms and address customer concern.',
            'Assign trade specialist for detailed investigation.',
            'Coordinate with trade partners for resolution.',
            'Initiate trade dispute resolution process.',
            'Review transaction records for trade issue.',
            'Provide trade support and track case progress.',
            'Forward trade concern to relevant department.',
            'Investigate pricing or trade discrepancy.',
            'Coordinate trade issue resolution with vendor.',
            'Open trade investigation and update customer.',
            'Review trade agreement terms for this case.',
            'Assign case to trade resolution specialist.',
            'Escalate trade complaint to management.',
            'Investigate trade-related concern thoroughly.',
            'Provide trade guidance and follow up.',
            'Route trade issue for priority resolution.',
            'Document trade complaint for review.',
            'Coordinate trade support across departments.',
            'Initiate formal trade dispute review process.',
        ],
        'Other': [
            'Forward to support team for further investigation.',
            'Route complaint to appropriate department.',
            'Log concern and assign to support specialist.',
            'Investigate issue and provide customer resolution.',
            'Escalate to relevant team for handling.',
            'Assign to customer support for follow-up.',
            'Review complaint details and take action.',
            'Open support case and coordinate resolution.',
            'Forward to operations team for investigation.',
            'Initiate investigation and track resolution.',
            'Route to appropriate department for action.',
            'Log complaint and escalate for resolution.',
            'Assign support agent for detailed follow-up.',
            'Coordinate cross-team response for this issue.',
            'Open case for investigation and resolution.',
            'Review and route to correct resolution team.',
            'Initiate customer resolution workflow.',
            'Forward to team lead for priority assessment.',
            'Document concern and assign for action.',
            'Coordinate support response for this complaint.',
            'Begin investigation and provide status update.',
            'Route to specialized team based on issue type.',
            'Log issue and initiate standard resolution.',
            'Forward for review and corrective action.',
            'Assign to available support representative.',
            'Open investigation ticket and track progress.',
            'Escalate to supervisor for case review.',
            'Coordinate immediate response for this issue.',
            'Route complaint for priority processing.',
            'Initiate standard resolution protocol.',
        ],
    }

    # Determine context key from category + text
    text_l = text_lower
    if category == 'Product' and any(w in text_l for w in ('broken', 'not working', 'defective', 'malfunction', 'damaged', 'faulty', 'stopped')):
        ctx_key = 'Product_broken'
    elif category == 'Product':
        ctx_key = 'Product_quality'
    elif category == 'Packaging' and any(w in text_l for w in ('damage', 'torn', 'crushed', 'broken', 'crack', 'leak')):
        ctx_key = 'Packaging_damage'
    elif category == 'Packaging':
        ctx_key = 'Packaging_general'
    elif category == 'Delivery' and any(w in text_l for w in ('delay', 'late', 'slow', 'waiting', 'not arrived', 'not received')):
        ctx_key = 'Delivery_delay'
    elif category == 'Delivery':
        ctx_key = 'Delivery_general'
    elif category == 'Trade':
        ctx_key = 'Trade_general'
    else:
        ctx_key = 'Other'

    pool = _recommendation_pool[ctx_key]

    # Hash-based deterministic selection (same input → same output)
    idx = hash(complaint_text) % len(pool)
    rule_action = pool[idx]

    # Try adaptive recommendation from past complaints
    past = find_similar_past_actions(text_lower)
    if past and past['count'] >= 2:
        action = past['action']
        reason_parts.append(f'Recommendation derived from {past["total"]} similar past complaint resolutions')
    elif past:
        action = past['action']
        reason_parts.append('Recommendation informed by past complaint history')
    else:
        action = rule_action

    # Strip any existing priority prefixes/suffixes before re-appending
    action = action.replace('URGENT: ', '').replace('URGENT:', '')
    action = action.replace(' Immediate action required.', '').replace('Immediate action required.', '')
    action = action.replace(' Ensure timely resolution.', '').replace('Ensure timely resolution.', '')
    action = action.replace(' Monitor situation and improve service.', '').replace('Monitor situation and improve service.', '')
    action = action.strip()

    # Priority layer
    if risk_level == 'High':
        action = 'URGENT: ' + action + ' Immediate action required.'
    elif priority == 'Medium':
        action = action + ' Ensure timely resolution.'
    elif priority == 'Low':
        action = action + ' Monitor situation and improve service.'

    # --- Assemble final reason ---
    if not reason_parts:
        reason = 'No specific keywords detected. Standard issue'
    else:
        reason = '. '.join(reason_parts)

    # =========================================================
    # POST-PROCESSING VALIDATION LAYER
    # Ensures logical consistency between all output fields
    # =========================================================

    # Step 1: Fix sentiment based on text keywords
    neg_indicators = ['broken', 'defective', 'damaged', 'stopped', 'not working',
                      'unusable', 'late', 'delay', 'worst', 'terrible', 'horrible',
                      'unsafe', 'hazard', 'danger', 'exploded', 'leak', 'angry', 'unhappy',
                      'useless', 'bad', 'missing']
    pos_indicators = ['great', 'good', 'excellent', 'happy', 'satisfied', 'okay']

    has_neg = any(w in text_lower for w in neg_indicators)
    has_pos = any(w in text_lower for w in pos_indicators)

    if has_neg:
        sentiment = 'Negative'
    elif has_pos:
        sentiment = 'Positive'
    else:
        # Keep existing sentiment if no strong signal
        pass

    # Step 2: Fix category via strong keyword correction
    if any(w in text_lower for w in ['product', 'broken', 'defective', 'stopped', 'not working']):
        category = 'Product'
    elif any(w in text_lower for w in ['packaging', 'box', 'seal', 'leak', 'package']):
        category = 'Packaging'
    elif any(w in text_lower for w in ['delivery', 'late', 'delay', 'shipment', 'shipping']):
        category = 'Delivery'
    # else: keep ML/existing category

    # Step 3: Fix priority logic
    critical_words = ['danger', 'unsafe', 'exploded', 'health', 'leak', 'hazard']
    has_critical = any(w in text_lower for w in critical_words)

    if has_critical:
        priority = 'High'
    elif sentiment == 'Negative':
        priority = 'Medium' if priority == 'Low' else priority  # at least Medium
    elif sentiment == 'Positive':
        priority = 'Low'

    # Step 4: Fix action consistency (preserve data-driven actions)
    if priority == 'High' and not action.startswith('URGENT:'):
        action = 'URGENT: ' + action + ' Immediate action required.'
    elif priority == 'Low' and action.startswith('URGENT:'):
        # Remove URGENT prefix for low-priority
        action = action.replace('URGENT: ', '').replace(' Immediate action required.', '').strip()

    reason += '. Post-processed for consistency using rule validation layer'

    # =========================================================
    # END VALIDATION LAYER
    # =========================================================

    if risk_level == 'High' or priority == 'High':
        estimated_time = '12 hours'
    else:
        time_map = {'High': '24 hours', 'Medium': '48 hours', 'Low': '72 hours'}
        estimated_time = time_map.get(priority, '48 hours')


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

    # SLA deadline calculation
    now = datetime.now()
    sla_map = {'High': 12, 'Medium': 48, 'Low': 72}
    sla_hours = sla_map.get(priority, 48)
    sla_deadline = (now + timedelta(hours=sla_hours)).isoformat()
    now_str = now.isoformat()

    # Save to database (skip when called from report generator)
    if not skip_save:
        try:
            conn = get_db()

            # --- Repeat order_id escalation ---
            if order_id and order_id != 'N/A':
                count = conn.execute(
                    'SELECT COUNT(*) FROM complaints WHERE order_id = ?', (order_id,)
                ).fetchone()[0]
                if count >= 1:  # This will be the 2nd+ occurrence
                    priority = 'High'
                    result['priority'] = 'High'
                    reason_parts_extra = 'Repeat complaint detected for same order ID.'
                    result['reason'] = result.get('reason', '') + ' ' + reason_parts_extra

            cur = conn.execute(
                '''INSERT INTO complaints
                   (text, category, priority, sentiment, confidence, reason, action, status, estimated_time, timestamp, updated_at, sla_deadline, customer_name, order_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (complaint_text, category, priority, sentiment, confidence,
                 result.get('reason', reason), action, 'Pending', estimated_time,
                 now_str, now_str, sla_deadline, customer_name, order_id)
            )
            result['complaint_id'] = cur.lastrowid
            result['sla_deadline'] = sla_deadline
            conn.commit()
            conn.close()
        except Exception as e:
            print(f'[Fixera] DB write error: {e}')

    return jsonify(result)


@app.route('/complaints', methods=['GET'])
def get_complaints():
    """Return all stored complaints, newest first, with overdue flag."""
    # Check if request asks for hidden filter (History uses show_hidden=0)
    show_hidden = request.args.get('show_hidden', '1')  # default: show all
    conn = get_db()
    if show_hidden == '0':
        rows = conn.execute(
            'SELECT id, text, category, priority, sentiment, confidence, reason, action, status, estimated_time, timestamp, updated_at, sla_deadline, customer_name, order_id '
            'FROM complaints WHERE is_hidden = 0 ORDER BY id DESC'
        ).fetchall()
    else:
        rows = conn.execute(
            'SELECT id, text, category, priority, sentiment, confidence, reason, action, status, estimated_time, timestamp, updated_at, sla_deadline, customer_name, order_id '
            'FROM complaints ORDER BY id DESC'
        ).fetchall()
    conn.close()

    now = datetime.now()
    sla_rules = {'High': 24, 'Medium': 48, 'Low': 72}
    complaints = []
    for r in rows:
        item = {
            'id': r['id'],
            'text': r['text'],
            'category': r['category'],
            'priority': r['priority'],
            'sentiment': r['sentiment'],
            'confidence': r['confidence'],
            'reason': r['reason'],
            'action': r['action'],
            'status': r['status'],
            'estimated_time': r['estimated_time'],
            'timestamp': r['timestamp'],
            'updated_at': r['updated_at'],
            'sla_deadline': r['sla_deadline'],
            'customer_name': r['customer_name'] or 'N/A',
            'order_id': r['order_id'] or 'N/A',
            'overdue': False,
            'resolved_at': None,
            'sla_breached': False,
            'time_info': '',
        }

        # Get resolved_at if exists
        try:
            item['resolved_at'] = r['resolved_at']
        except Exception:
            pass

        # Compute timeline info and SLA breach dynamically
        created = None
        try:
            created = datetime.fromisoformat(r['timestamp']) if r['timestamp'] else None
        except Exception:
            pass

        if created:
            sla_hours = sla_rules.get(r['priority'], 72)
            if item['resolved_at']:
                try:
                    resolved_dt = datetime.fromisoformat(item['resolved_at'])
                    diff_hrs = round((resolved_dt - created).total_seconds() / 3600, 1)
                    item['time_info'] = f'Resolved in {diff_hrs}h'
                    item['sla_breached'] = diff_hrs > sla_hours
                except Exception:
                    pass
            elif r['status'] not in ('Resolved', 'Closed', 'Ignored'):
                diff_hrs = round((now - created).total_seconds() / 3600, 1)
                item['time_info'] = f'Pending {diff_hrs}h'
                item['sla_breached'] = diff_hrs > sla_hours

        # Legacy overdue check
        if r['sla_deadline'] and r['status'] not in ('Resolved', 'Closed'):
            try:
                deadline = datetime.fromisoformat(r['sla_deadline'])
                if now > deadline:
                    item['overdue'] = True
            except Exception:
                pass

        complaints.append(item)

    return jsonify(complaints)


# Status transition rules: only forward movement allowed
STATUS_TRANSITIONS = {
    'Pending':     ['In Progress'],
    'New':         ['In Progress'],
    'In Progress': ['Resolved'],
    'Resolved':    ['Closed'],
    'Closed':      [],
    'Ignored':     [],
}


@app.route('/hide_complaint', methods=['POST'])
def hide_complaint():
    """Soft-delete a complaint (hide from History only, keep in analytics)."""
    data = request.get_json()
    if not data or 'id' not in data:
        return jsonify({'error': 'Missing complaint id'}), 400

    complaint_id = data['id']
    try:
        conn = get_db()
        conn.execute('UPDATE complaints SET is_hidden = 1 WHERE id = ?', (complaint_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'id': complaint_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/update_status', methods=['POST'])
def update_status():
    """Update the status of a complaint with lifecycle validation and activity logging."""
    data = request.get_json()

    if not data or 'id' not in data or 'status' not in data:
        return jsonify({'error': 'Missing "id" or "status" field'}), 400

    new_status = data['status']
    valid_statuses = ['Pending', 'New', 'In Progress', 'Resolved', 'Closed', 'Ignored']
    if new_status not in valid_statuses:
        return jsonify({'error': f'Invalid status. Must be one of: {valid_statuses}'}), 400

    try:
        conn = get_db()
        row = conn.execute('SELECT id, status, priority, timestamp, order_id FROM complaints WHERE id = ?', (data['id'],)).fetchone()

        if not row:
            conn.close()
            return jsonify({'error': 'Complaint not found'}), 404

        old_status = row['status']

        # Validate transition
        allowed = STATUS_TRANSITIONS.get(old_status, [])
        if new_status not in allowed:
            conn.close()
            return jsonify({
                'error': f'Invalid status transition: {old_status} → {new_status}. Allowed: {allowed}'
            }), 400

        now_str = datetime.now().isoformat()
        warning = None

        # Update complaint
        if new_status == 'Resolved':
            conn.execute(
                'UPDATE complaints SET status = ?, updated_at = ?, resolved_at = ? WHERE id = ?',
                (new_status, now_str, now_str, data['id'])
            )
        elif new_status == 'Closed':
            # Auto-hide from History when closed
            conn.execute(
                'UPDATE complaints SET status = ?, updated_at = ?, is_hidden = 1 WHERE id = ?',
                (new_status, now_str, data['id'])
            )

            # CASCADE: Close ALL complaints with same order_id
            order_id = row['order_id'] if 'order_id' in row.keys() else None
            if order_id and order_id != 'N/A':
                siblings = conn.execute(
                    'SELECT id, status FROM complaints WHERE order_id = ? AND id != ? AND status != ?',
                    (order_id, data['id'], 'Closed')
                ).fetchall()
                for sib in siblings:
                    conn.execute(
                        'UPDATE complaints SET status = ?, updated_at = ?, is_hidden = 1 WHERE id = ?',
                        ('Closed', now_str, sib['id'])
                    )
                    conn.execute(
                        'INSERT INTO activity_logs (complaint_id, old_status, new_status, changed_at) VALUES (?, ?, ?, ?)',
                        (sib['id'], sib['status'], 'Closed', now_str)
                    )
                if siblings:
                    warning = f'Auto-closed {len(siblings)} related complaint(s) with order ID {order_id}'
        else:
            conn.execute(
                'UPDATE complaints SET status = ?, updated_at = ? WHERE id = ?',
                (new_status, now_str, data['id'])
            )

        # Activity log
        conn.execute(
            'INSERT INTO activity_logs (complaint_id, old_status, new_status, changed_at) VALUES (?, ?, ?, ?)',
            (data['id'], old_status, new_status, now_str)
        )

        # Safety check: High priority closed within 10 minutes
        if new_status == 'Closed' and row['priority'] == 'High' and row['timestamp']:
            try:
                created = datetime.fromisoformat(row['timestamp'])
                diff_min = (datetime.now() - created).total_seconds() / 60
                if diff_min < 10:
                    w = 'This complaint is being closed unusually quickly'
                    warning = (warning + '. ' + w) if warning else w
            except Exception:
                pass

        conn.commit()
        conn.close()

        resp = {'success': True, 'id': data['id'], 'status': new_status, 'old_status': old_status}
        if warning:
            resp['warning'] = warning
        return jsonify(resp)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/activity_logs/<int:complaint_id>', methods=['GET'])
def get_activity_logs(complaint_id):
    """Return activity logs for a specific complaint."""
    try:
        conn = get_db()
        rows = conn.execute(
            'SELECT id, complaint_id, old_status, new_status, changed_at FROM activity_logs WHERE complaint_id = ? ORDER BY id DESC',
            (complaint_id,)
        ).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/stats', methods=['GET'])
def get_stats():
    """Return aggregated complaint statistics with lifecycle insights."""
    conn = get_db()

    total = conn.execute('SELECT COUNT(*) FROM complaints').fetchone()[0]

    cat_rows = conn.execute(
        'SELECT category, COUNT(*) as cnt FROM complaints GROUP BY category'
    ).fetchall()
    by_category = {r['category']: r['cnt'] for r in cat_rows}

    pri_rows = conn.execute(
        'SELECT priority, COUNT(*) as cnt FROM complaints GROUP BY priority'
    ).fetchall()
    by_priority = {r['priority']: r['cnt'] for r in pri_rows}

    sent_rows = conn.execute(
        'SELECT sentiment, COUNT(*) as cnt FROM complaints GROUP BY sentiment'
    ).fetchall()
    by_sentiment = {r['sentiment']: r['cnt'] for r in sent_rows}

    # Lifecycle stats
    pending = conn.execute(
        "SELECT COUNT(*) FROM complaints WHERE status = 'Pending'"
    ).fetchone()[0]

    overdue = 0
    now_str = datetime.now().isoformat()
    sla_rows = conn.execute(
        "SELECT sla_deadline FROM complaints WHERE status != 'Resolved' AND sla_deadline IS NOT NULL"
    ).fetchall()
    for r in sla_rows:
        try:
            if datetime.fromisoformat(r['sla_deadline']) < datetime.now():
                overdue += 1
        except Exception:
            pass

    # Also include report history totals
    try:
        rpt_rows = conn.execute(
            'SELECT COALESCE(SUM(total_complaints),0) as t, COALESCE(SUM(high_count),0) as h, '
            'COALESCE(SUM(medium_count),0) as m, COALESCE(SUM(low_count),0) as l FROM reports'
        ).fetchone()
        report_total = rpt_rows['t']
        report_high = rpt_rows['h']
        report_medium = rpt_rows['m']
        report_low = rpt_rows['l']
    except Exception:
        report_total = report_high = report_medium = report_low = 0

    # Aggregate categories from reports
    report_categories = {}
    try:
        cat_json_rows = conn.execute('SELECT categories_json FROM reports WHERE categories_json IS NOT NULL').fetchall()
        for row in cat_json_rows:
            try:
                cats = json.loads(row['categories_json'])
                for k, v in cats.items():
                    report_categories[k] = report_categories.get(k, 0) + v
            except Exception:
                pass
    except Exception:
        pass

    # Aggregate sentiments from reports
    report_sentiments = {}
    try:
        sent_json_rows = conn.execute('SELECT sentiments_json FROM reports WHERE sentiments_json IS NOT NULL').fetchall()
        for row in sent_json_rows:
            try:
                sents = json.loads(row['sentiments_json'])
                for k, v in sents.items():
                    report_sentiments[k] = report_sentiments.get(k, 0) + v
            except Exception:
                pass
    except Exception:
        pass

    conn.close()

    # Combined stats: complaints + reports
    combined_total = total + report_total
    combined_high = by_priority.get('High', 0) + report_high
    combined_medium = by_priority.get('Medium', 0) + report_medium
    combined_low = by_priority.get('Low', 0) + report_low

    # Merge categories from complaints + reports
    combined_categories = dict(by_category)
    for k, v in report_categories.items():
        combined_categories[k] = combined_categories.get(k, 0) + v

    # Merge sentiments from complaints + reports
    combined_sentiments = dict(by_sentiment)
    for k, v in report_sentiments.items():
        combined_sentiments[k] = combined_sentiments.get(k, 0) + v

    return jsonify({
        'total': combined_total,
        'by_category': combined_categories,
        'by_priority': {
            'High': combined_high,
            'Medium': combined_medium,
            'Low': combined_low,
        },
        'by_sentiment': combined_sentiments,
        'pending': pending,
        'overdue': overdue,
        'from_reports': report_total,
        'from_history': total,
    })


@app.route('/use-email-data', methods=['GET'])
def use_email_data():
    """Fetch fresh emails via fetch_emails.py, then check CSV row count."""
    csv_path = os.path.join(BASE_DIR, 'complaints.csv')
    fetch_script = os.path.join(BASE_DIR, 'fetch_emails.py')

    try:
        # Step 1: Run fetch_emails.py to pull new emails from Gmail
        env = os.environ.copy()
        env['EMAIL'] = 'fixera.system@gmail.com'
        env['PASSWORD'] = 'ujgh rhcm mloy amta'
        result = subprocess.run(
            ['/usr/local/bin/python3', fetch_script],
            capture_output=True, text=True, timeout=30, env=env, cwd=BASE_DIR
        )
        if result.returncode != 0:
            err_detail = result.stderr.strip() or result.stdout.strip() or 'Unknown error'
            return jsonify({
                'error': f'Failed to fetch emails: {err_detail}'
            }), 500

        # Step 2: Check if CSV exists and has data
        if not os.path.exists(csv_path):
            return jsonify({'error': 'No complaints.csv generated. Check Gmail credentials.'}), 400

        with open(csv_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()

        if not content:
            return jsonify({'error': 'complaints.csv is empty. No new emails found.'}), 400

        lines = [l for l in content.split('\n') if l.strip()]
        first_line = lines[0].lower() if lines else ''
        has_header = 'email' in first_line or 'subject' in first_line or 'description' in first_line
        data_rows = len(lines) - 1 if has_header else len(lines)

        if data_rows <= 0:
            return jsonify({'error': 'No complaint data in CSV. No new emails.'}), 400

        return jsonify({'success': True, 'rows': data_rows})
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Email fetch timed out. Try again.'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/generate_report', methods=['POST'])
def generate_report():
    """Generate a PDF report from uploaded CSV or complaints.csv."""
    import csv as csv_mod
    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

    csv_path = os.path.join(BASE_DIR, 'complaints.csv')
    rows = []
    has_file = 'file' in request.files and request.files['file'].filename
    use_email = request.form.get('use_email_data') == 'true'

    # Strict validation: must have file OR explicit email flag
    if not has_file and not use_email:
        return jsonify({'error': 'No input provided. Please upload a CSV file or use email data.'}), 400

    # Read data from the correct source
    if has_file:
        uploaded = request.files['file']
        try:
            content = uploaded.read().decode('utf-8', errors='ignore')
            reader = csv_mod.DictReader(content.splitlines())
            rows = list(reader)
        except Exception as e:
            return jsonify({'error': f'CSV parse error: {str(e)}'}), 400
    elif use_email:
        if not os.path.exists(csv_path):
            return jsonify({'error': 'No complaints.csv found. Fetch emails first.'}), 404
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            if not content:
                return jsonify({'error': 'complaints.csv is empty.'}), 400
            lines = content.split('\n')
            first_line = lines[0].lower() if lines else ''
            has_header = 'email' in first_line or 'subject' in first_line or 'description' in first_line
            if has_header:
                reader = csv_mod.DictReader(lines)
            else:
                # No header — assign known columns
                reader = csv_mod.DictReader(lines, fieldnames=['email', 'subject', 'description', 'fetched_at'])
            rows = list(reader)
        except Exception as e:
            return jsonify({'error': f'CSV read error: {str(e)}'}), 500

    if not rows:
        return jsonify({'error': 'CSV file is empty — no data to generate report.'}), 400

    # Analyze each complaint
    results = []
    categories = {}
    priorities = {}
    sentiments = {}
    high_risk = 0

    for row in rows:
        text = row.get('description') or row.get('Complaint') or row.get('complaint') or row.get('text') or row.get('subject', '')
        raw_name = row.get('customer_name') or row.get('name') or ''
        raw_email = row.get('email', '')
        raw_oid = row.get('order_id') or row.get('order', '')
        if not text or len(text.strip()) < 3:
            continue

        # --- Auto-extract Order ID from text if not already provided ---
        if not raw_oid or raw_oid == 'N/A':
            full_text = f"{row.get('subject', '')} {text}"
            # Match patterns: ORD-123, ORD123, Order #456, order id: 789, #ORD-001, etc.
            oid_match = re.search(
                r'(?:order\s*(?:id|no|number|#)?[\s:]*[#]?\s*)'
                r'([A-Za-z]*\d[\w-]*)'
                r'|'
                r'(ORD[\s-]?\d[\w-]*)'
                r'|'
                r'#(\d{3,})',
                full_text, re.IGNORECASE
            )
            if oid_match:
                raw_oid = (oid_match.group(1) or oid_match.group(2) or oid_match.group(3)).strip()

        # --- Auto-extract customer name from email if not provided ---
        if not raw_name:
            if raw_email and '@' in raw_email:
                # megh2850@gmail.com → Megh
                local = raw_email.split('@')[0]
                # Remove trailing digits
                clean = re.sub(r'[\d._]+$', '', local).replace('.', ' ').replace('_', ' ').strip()
                raw_name = clean.title() if clean else raw_email
            else:
                raw_name = 'Unknown'

        name = raw_name[:30]
        oid = raw_oid[:20] if raw_oid else 'N/A'

        try:
            with app.test_client() as client:
                resp = client.post('/predict', json={'text': text.strip(), 'skip_save': True})
                if resp.status_code == 200:
                    data = resp.get_json()
                    cat = data.get('category', 'Other')
                    pri = data.get('priority', 'Low')
                    sen = data.get('sentiment', 'Neutral')
                    act = data.get('action', '—')

                    categories[cat] = categories.get(cat, 0) + 1
                    priorities[pri] = priorities.get(pri, 0) + 1
                    sentiments[sen] = sentiments.get(sen, 0) + 1
                    if pri == 'High':
                        high_risk += 1

                    results.append({
                        'name': name[:30],
                        'order_id': oid[:20] if oid else 'N/A',
                        'text': text[:80],
                        'category': cat,
                        'priority': pri,
                        'action': act[:80],
                    })
        except Exception:
            continue

    if not results:
        return jsonify({'error': 'No valid complaints found in the CSV.'}), 400

    # ---- Boost priority for repeated order IDs ----
    oid_counts = {}
    for r in results:
        oid = r.get('order_id', 'N/A')
        if oid and oid != 'N/A':
            oid_counts[oid] = oid_counts.get(oid, 0) + 1

    # Upgrade to High if order_id appears more than once
    for r in results:
        oid = r.get('order_id', 'N/A')
        if oid in oid_counts and oid_counts[oid] > 1:
            if r['priority'] != 'High':
                # Adjust counters
                priorities[r['priority']] = priorities.get(r['priority'], 1) - 1
                r['priority'] = 'High'
                priorities['High'] = priorities.get('High', 0) + 1
                high_risk += 1

    # ---- Generate PDF ----
    timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'Fixera_Report_{timestamp_str}.pdf'
    reports_dir = os.path.join(BASE_DIR, 'reports')
    os.makedirs(reports_dir, exist_ok=True)
    report_path = os.path.join(reports_dir, filename)

    doc = SimpleDocTemplate(report_path, pagesize=A4,
                            topMargin=40, bottomMargin=40,
                            leftMargin=42, rightMargin=42)
    styles = getSampleStyleSheet()
    story = []

    # --- Custom styles ---
    DARK = colors.HexColor('#1e293b')
    BLUE = colors.HexColor('#2563eb')
    GRAY_BG = colors.HexColor('#f8fafc')
    LIGHT_BG = colors.HexColor('#f1f5f9')

    # Sort: most repeated order_id first, then High > Medium > Low
    _priority_order = {'High': 1, 'Medium': 2, 'Low': 3}
    results.sort(key=lambda x: (
        -oid_counts.get(x.get('order_id', ''), 0),  # most repeated first
        _priority_order.get(x.get('priority', ''), 4)  # then by priority
    ))
    BORDER = colors.HexColor('#e2e8f0')
    WHITE = colors.white

    s_title = ParagraphStyle('RptTitle', parent=styles['Title'],
        fontSize=24, leading=30, alignment=1, spaceAfter=4,
        textColor=DARK, fontName='Helvetica-Bold')
    s_subtitle = ParagraphStyle('RptSub', parent=styles['Normal'],
        fontSize=10, alignment=1, textColor=colors.HexColor('#64748b'),
        spaceAfter=4)
    s_heading = ParagraphStyle('RptH2', parent=styles['Heading2'],
        fontSize=13, leading=18, textColor=BLUE, spaceBefore=18,
        spaceAfter=8, fontName='Helvetica-Bold')
    s_body = ParagraphStyle('RptBody', parent=styles['Normal'],
        fontSize=9.5, leading=13, textColor=DARK)
    s_bullet = ParagraphStyle('RptBullet', parent=styles['Normal'],
        fontSize=10, leading=15, textColor=DARK, leftIndent=12,
        spaceBefore=3, spaceAfter=3)
    s_cell = ParagraphStyle('RptCell', parent=styles['Normal'],
        fontSize=8, leading=11, textColor=DARK)
    s_cell_head = ParagraphStyle('RptCellH', parent=styles['Normal'],
        fontSize=8.5, leading=11, textColor=WHITE, fontName='Helvetica-Bold')

    pw = A4[0] - 84  # page width minus margins

    # ===================== HEADER =====================
    story.append(Paragraph('Fixera Complaint Analysis Report', s_title))
    story.append(Paragraph(
        f'Generated on {datetime.now().strftime("%B %d, %Y at %H:%M")}',
        s_subtitle))

    # Horizontal rule
    from reportlab.platypus import HRFlowable
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width='100%', thickness=1, color=BORDER, spaceAfter=14))

    # ===================== 1. SUMMARY =====================
    story.append(Paragraph('1. Summary', s_heading))

    summary_header = [
        Paragraph('<b>Metric</b>', s_cell_head),
        Paragraph('<b>Count</b>', s_cell_head),
    ]
    summary_rows = [
        ['Total Complaints', str(len(results))],
        ['High Priority', str(priorities.get('High', 0))],
        ['Medium Priority', str(priorities.get('Medium', 0))],
        ['Low Priority', str(priorities.get('Low', 0))],
        ['High Risk', str(high_risk)],
    ]
    for cat_name, cnt in categories.items():
        summary_rows.append([f'Category: {cat_name}', str(cnt)])

    summary_data = [summary_header]
    for row in summary_rows:
        summary_data.append([
            Paragraph(row[0], s_cell),
            Paragraph(row[1], s_cell),
        ])

    summary_table = Table(summary_data, colWidths=[pw * 0.6, pw * 0.4])
    summary_table.setStyle(TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        # Data rows
        ('BACKGROUND', (0, 1), (-1, -1), GRAY_BG),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, GRAY_BG]),
        # Padding & borders
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        # Round top corners effect via line
        ('LINEABOVE', (0, 0), (-1, 0), 1.5, BLUE),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 20))

    # ===================== 2. COMPLAINT DETAILS =====================
    story.append(Paragraph('2. Complaint Details', s_heading))

    # Build header row with styled Paragraphs
    detail_header = [
        Paragraph('<b>Customer</b>', s_cell_head),
        Paragraph('<b>Order ID</b>', s_cell_head),
        Paragraph('<b>Complaint</b>', s_cell_head),
        Paragraph('<b>Category</b>', s_cell_head),
        Paragraph('<b>Priority</b>', s_cell_head),
        Paragraph('<b>Recommendation</b>', s_cell_head),
    ]

    # Build data rows with Paragraph wrapping for long text
    detail_data = [detail_header]
    for r in results:
        complaint_text = r['text'][:80]
        if len(r['text']) > 80:
            complaint_text += '...'
        action_text = r['action'][:80]
        if len(r['action']) > 80:
            action_text += '...'

        detail_data.append([
            Paragraph(r['name'], s_cell),
            Paragraph(r.get('order_id', 'N/A'), s_cell),
            Paragraph(complaint_text, s_cell),
            Paragraph(r['category'], s_cell),
            Paragraph(f"<b>{r['priority']}</b>", s_cell),
            Paragraph(action_text, s_cell),
        ])

    col_w = [pw*0.13, pw*0.14, pw*0.22, pw*0.10, pw*0.09, pw*0.32]
    detail_table = Table(detail_data, colWidths=col_w, repeatRows=1)
    detail_table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('LINEABOVE', (0, 0), (-1, 0), 1.5, BLUE),
        # Data rows
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, LIGHT_BG]),
        # Padding
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        # Borders
        ('GRID', (0, 0), (-1, -1), 0.4, BORDER),
        ('LINEBELOW', (0, 0), (-1, 0), 1, BLUE),
        # Alignment
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(detail_table)
    story.append(Spacer(1, 24))

    # ===================== 3. KEY INSIGHTS =====================
    story.append(Paragraph('3. Key Insights', s_heading))
    story.append(Spacer(1, 4))

    if categories:
        top_cat = max(categories, key=categories.get)
        story.append(Paragraph(
            f'<bullet>&bull;</bullet> Most common issue: <b>{top_cat}</b> ({categories[top_cat]} complaints)',
            s_bullet))
    story.append(Paragraph(
        f'<bullet>&bull;</bullet> High-risk complaints requiring immediate action: <b>{high_risk}</b>',
        s_bullet))
    neg_count = sentiments.get('Negative', 0)
    pos_count = sentiments.get('Positive', 0)
    story.append(Paragraph(
        f'<bullet>&bull;</bullet> Sentiment breakdown: <b>{neg_count}</b> negative, '
        f'<b>{pos_count}</b> positive out of {len(results)} total',
        s_bullet))
    if high_risk > 0:
        story.append(Paragraph(
            f'<bullet>&bull;</bullet> <font color="#dc2626">⚠ {high_risk} complaint(s) flagged as high priority '
            f'— recommend immediate escalation</font>',
            s_bullet))

    story.append(Spacer(1, 20))

    # Footer rule
    story.append(HRFlowable(width='100%', thickness=0.5, color=BORDER, spaceBefore=10))
    story.append(Paragraph(
        f'<font size="8" color="#94a3b8">Report generated by Fixera AI • {datetime.now().strftime("%Y-%m-%d %H:%M")}</font>',
        ParagraphStyle('Footer', parent=styles['Normal'], alignment=1, spaceBefore=6)))

    # Build PDF
    doc.build(story)

    # Save to database
    try:
        conn = get_db()
        conn.execute(
            'INSERT INTO reports (filename, created_at, total_complaints, high_count, medium_count, low_count, categories_json, sentiments_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (filename, datetime.now().isoformat(), len(results),
             priorities.get('High', 0), priorities.get('Medium', 0), priorities.get('Low', 0),
             json.dumps(categories), json.dumps(sentiments))
        )
        conn.commit()
        report_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        conn.close()
    except Exception as e:
        print(f'[Fixera] Report DB save error: {e}')
        report_id = None

    return jsonify({
        'success': True,
        'total': len(results),
        'high': priorities.get('High', 0),
        'medium': priorities.get('Medium', 0),
        'low': priorities.get('Low', 0),
        'report_id': report_id,
        'filename': filename,
        'file': f'/download_report/{report_id}' if report_id else '/download_report/latest',
        'message': f'Report generated with {len(results)} complaints.',
    })


@app.route('/download_report/<report_id>', methods=['GET'])
def download_report(report_id):
    """Download a specific report by ID or 'latest'."""
    reports_dir = os.path.join(BASE_DIR, 'reports')

    if report_id == 'latest':
        # Find most recent file in reports/
        files = sorted([f for f in os.listdir(reports_dir) if f.endswith('.pdf')], reverse=True)
        if not files:
            return jsonify({'error': 'No reports found.'}), 404
        filepath = os.path.join(reports_dir, files[0])
        return send_file(filepath, as_attachment=True, download_name=files[0])

    try:
        conn = get_db()
        row = conn.execute('SELECT filename FROM reports WHERE id = ?', (int(report_id),)).fetchone()
        conn.close()
        if not row:
            return jsonify({'error': 'Report not found.'}), 404
        filepath = os.path.join(reports_dir, row['filename'])
        if not os.path.exists(filepath):
            return jsonify({'error': 'Report file missing.'}), 404
        return send_file(filepath, as_attachment=True, download_name=row['filename'])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/report_history', methods=['GET'])
def report_history():
    """Return list of previously generated reports."""
    try:
        conn = get_db()
        rows = conn.execute(
            'SELECT id, filename, created_at, total_complaints, high_count, medium_count, low_count FROM reports ORDER BY id DESC LIMIT 50'
        ).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=False, host='0.0.0.0', port=port)
