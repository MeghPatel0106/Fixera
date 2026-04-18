from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os

app = Flask(__name__, static_folder='../fixera-frontend', static_url_path='')
CORS(app)


@app.route('/')
def index():
    """Serve the frontend HTML page."""
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/predict', methods=['POST'])
def predict():
    """Accept a complaint and return a rule-based analysis result."""
    data = request.get_json()

    if not data or 'text' not in data:
        return jsonify({'error': 'Missing "text" field in request body'}), 400

    complaint_text = data['text'].strip()

    if not complaint_text:
        return jsonify({'error': 'Complaint text cannot be empty'}), 400

    text_lower = complaint_text.lower()

    # ------ 1. Category Detection ------
    category_rules = {
        'Product':   ['broken', 'damaged', 'defective'],
        'Delivery':  ['late', 'delay', 'delivery'],
        'Packaging': ['box', 'packaging', 'leak'],
    }

    category = 'Other'
    detected_keywords = []

    for cat, keywords in category_rules.items():
        for kw in keywords:
            if kw in text_lower:
                category = cat
                detected_keywords.append(kw)
        if category != 'Other':
            break

    # ------ 2. Sentiment Detection ------
    negative_words = ['bad', 'worst', 'angry', 'terrible', 'not happy']
    positive_words = ['good', 'great', 'thank', 'happy']

    sentiment = 'Neutral'

    for word in negative_words:
        if word in text_lower:
            sentiment = 'Negative'
            detected_keywords.append(word)
            break

    if sentiment == 'Neutral':
        for word in positive_words:
            if word in text_lower:
                sentiment = 'Positive'
                detected_keywords.append(word)
                break

    # ------ 3. Priority Logic ------
    urgent_words = ['broken', 'urgent', 'immediately']
    has_urgent = any(w in text_lower for w in urgent_words)

    if sentiment == 'Negative' and has_urgent:
        priority = 'High'
    elif sentiment == 'Negative':
        priority = 'Medium'
    else:
        priority = 'Low'

    # ------ 4. Recommendation ------
    action_map = {
        'Product':   'Offer replacement or refund',
        'Delivery':  'Apologize and expedite shipment',
        'Packaging': 'Check packaging process and resend item',
    }
    action = action_map.get(category, 'Forward to support team')

    # ------ 5. Confidence ------
    confidence_map = {'High': 0.9, 'Medium': 0.75, 'Low': 0.6}
    confidence = confidence_map[priority]

    # ------ 6. Estimated Time ------
    time_map = {'High': '24 hours', 'Medium': '48 hours', 'Low': '72 hours'}
    estimated_time = time_map[priority]

    # ------ 7. Reason ------
    if detected_keywords:
        # Remove duplicates while preserving order
        unique_keywords = list(dict.fromkeys(detected_keywords))
        reason = 'Detected keywords: ' + ', '.join(unique_keywords)
    else:
        reason = 'No specific keywords detected'

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
