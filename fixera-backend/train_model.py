"""
Fixera ML Pipeline — Train a category classifier on SelfData.csv
Outputs: model.pkl, ml_vectorizer.pkl
"""

import os
import re
import pickle
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

# ---- Config ----
DATASET = os.path.join(os.path.dirname(__file__), '..', 'SelfData1.csv')
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'model.pkl')
VECTORIZER_PATH = os.path.join(os.path.dirname(__file__), 'ml_vectorizer.pkl')

# ---- Step 1: Load dataset ----
print('[1/7] Loading dataset...')
df = pd.read_csv(DATASET)
print(f'  Loaded {len(df)} rows, columns: {list(df.columns)}')

# Drop rows with missing text/category
df = df.dropna(subset=['text', 'category'])
print(f'  After dropping NAs: {len(df)} rows')
print(f'  Categories: {df["category"].value_counts().to_dict()}')

# ---- Step 2: Text preprocessing ----
print('[2/7] Preprocessing text...')

def preprocess(text):
    """Lowercase, remove punctuation/numbers/extra spaces."""
    text = str(text).lower()
    text = re.sub(r'[^\w\s]', '', text)   # remove punctuation
    text = re.sub(r'\d+', '', text)        # remove numbers
    text = re.sub(r'\s+', ' ', text).strip()
    return text

df['text_processed'] = df['text'].apply(preprocess)

# Remove empty texts after preprocessing
df = df[df['text_processed'].str.len() > 0]
print(f'  Preprocessed {len(df)} texts')

# ---- Step 3: Feature engineering ----
print('[3/7] Building TF-IDF features...')
vectorizer = TfidfVectorizer(
    max_features=5000,
    ngram_range=(1, 2),
    stop_words='english',
)

X = vectorizer.fit_transform(df['text_processed'])
y = df['category']
print(f'  Feature matrix: {X.shape}')

# ---- Step 4: Train-test split ----
print('[4/7] Splitting data (80/20)...')
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)
print(f'  Train: {X_train.shape[0]}, Test: {X_test.shape[0]}')

# ---- Step 5: Model training ----
print('[5/7] Training LogisticRegression...')
model = LogisticRegression(max_iter=1000, random_state=42)
model.fit(X_train, y_train)
print('  Training complete.')

# ---- Step 6: Model evaluation ----
print('[6/7] Evaluating...')
y_pred = model.predict(X_test)
acc = accuracy_score(y_test, y_pred)
print(f'\n  Accuracy: {acc:.4f} ({acc*100:.1f}%)\n')
print(classification_report(y_test, y_pred))

# ---- Step 7: Save model ----
print('[7/7] Saving model and vectorizer...')
with open(MODEL_PATH, 'wb') as f:
    pickle.dump(model, f)
with open(VECTORIZER_PATH, 'wb') as f:
    pickle.dump(vectorizer, f)

print(f'  ✅ Saved: {MODEL_PATH}')
print(f'  ✅ Saved: {VECTORIZER_PATH}')
print('\nDone! Model is ready for use in app.py.')
