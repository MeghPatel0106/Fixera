<p align="center">
  <img src="fixera-frontend/logo.png" alt="Fixera Logo" width="80" height="80">
</p>

<h1 align="center">Fixera — AI-Powered Complaint Management System</h1>

<p align="center">
  <strong>Automate. Analyze. Resolve.</strong><br>
  An intelligent complaint management platform that uses Machine Learning and NLP to classify, prioritize, and generate actionable insights from customer complaints.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Flask-2.x-000000?style=for-the-badge&logo=flask&logoColor=white" alt="Flask">
  <img src="https://img.shields.io/badge/scikit--learn-ML-F7931E?style=for-the-badge&logo=scikit-learn&logoColor=white" alt="scikit-learn">
  <img src="https://img.shields.io/badge/Chart.js-Visualization-FF6384?style=for-the-badge&logo=chartdotjs&logoColor=white" alt="Chart.js">
  <img src="https://img.shields.io/badge/SQLite-Database-003B57?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite">
  <img src="https://img.shields.io/badge/Render-Deployed-46E3B7?style=for-the-badge&logo=render&logoColor=white" alt="Render">
</p>

---

## 📌 Problem Statement

In today's fast-paced business environment, companies receive **thousands of customer complaints daily** through various channels — emails, support tickets, feedback forms, and more. The challenges include:

- **Manual processing** of complaints is slow, expensive, and error-prone
- **Delayed responses** to high-priority issues damage customer trust and brand reputation
- **No visibility** into complaint trends, category spikes, or sentiment shifts
- **Repeat complaints** for the same order go undetected, leading to escalated frustration
- **No standardized reporting** — managers lack actionable data to drive decisions

> **Businesses lose an average of $62 billion annually due to poor customer service.** — *Accenture*

---

## 💡 Our Solution

**Fixera** is an end-to-end AI-powered complaint management system that:

| Feature | Description |
|---------|-------------|
| 🤖 **Auto-Classification** | ML model categorizes complaints into Product, Delivery, Packaging, Trade, and Other |
| 🎯 **Smart Priority** | Assigns High/Medium/Low priority based on urgency, keywords, and sentiment |
| 📊 **Sentiment Analysis** | Detects Positive, Negative, or Neutral customer sentiment |
| 📧 **Email Integration** | Auto-fetches complaints from Gmail inbox via IMAP |
| 📄 **PDF Report Generation** | Creates professional PDF reports with full analysis |
| ⚡ **Smart Alerts** | Real-time dashboard alerts for priority spikes, category trends, and repeated orders |
| 🔁 **Repeat Detection** | Auto-escalates repeat complaints for the same order to High priority |
| 📈 **Visual Dashboard** | Interactive charts and analytics for real-time monitoring |

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FIXERA SYSTEM                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐     │
│   │   Gmail       │    │   CSV File   │    │   Manual     │     │
│   │   Inbox       │    │   Upload     │    │   Input      │     │
│   └──────┬───────┘    └──────┬───────┘    └──────┬───────┘     │
│          │                   │                    │              │
│          └───────────┬───────┘────────────────────┘              │
│                      ▼                                          │
│          ┌───────────────────────┐                               │
│          │    Flask Backend      │                               │
│          │    (REST API)         │                               │
│          └───────────┬──────────┘                               │
│                      │                                          │
│     ┌────────────────┼────────────────┐                         │
│     ▼                ▼                ▼                         │
│  ┌──────┐    ┌──────────────┐   ┌──────────┐                   │
│  │ ML   │    │   Rule-Based │   │ TF-IDF   │                   │
│  │Model │    │   Engine     │   │ Matching  │                   │
│  │(PKL) │    │              │   │          │                    │
│  └──┬───┘    └──────┬───────┘   └────┬─────┘                   │
│     └───────────────┼────────────────┘                          │
│                     ▼                                           │
│          ┌──────────────────┐                                   │
│          │   Hybrid Result  │                                   │
│          │   Category +     │                                   │
│          │   Priority +     │                                   │
│          │   Sentiment +    │                                   │
│          │   Action Plan    │                                   │
│          └────────┬─────────┘                                   │
│                   │                                             │
│      ┌────────────┼────────────┐                                │
│      ▼            ▼            ▼                                │
│  ┌────────┐  ┌─────────┐  ┌─────────┐                          │
│  │SQLite  │  │  PDF     │  │Dashboard│                          │
│  │Database│  │  Report  │  │  UI     │                          │
│  └────────┘  └─────────┘  └─────────┘                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Workflow

```mermaid
graph TD
    A[Customer Complaint] -->|Email / CSV / Manual| B[Data Ingestion]
    B --> C[Text Preprocessing]
    C --> D{Hybrid Analysis Engine}
    D --> E[ML Model Classification]
    D --> F[Rule-Based Keywords]
    D --> G[TF-IDF Dataset Matching]
    E --> H[Combined Result]
    F --> H
    G --> H
    H --> I[Category + Priority + Sentiment]
    I --> J[Store in SQLite DB]
    I --> K[Display on Dashboard]
    I --> L[Generate PDF Report]
    J --> M[History & Analytics]
    K --> N[Smart Alerts]
    K --> O[Charts & Graphs]
```

---

## 🛠️ Tech Stack

### Backend
| Technology | Purpose |
|-----------|---------|
| <img src="https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white" width="80"> | Core programming language |
| <img src="https://img.shields.io/badge/Flask-000000?style=flat-square&logo=flask&logoColor=white" width="70"> | Web framework & REST API |
| <img src="https://img.shields.io/badge/scikit--learn-F7931E?style=flat-square&logo=scikit-learn&logoColor=white" width="100"> | Machine Learning model |
| <img src="https://img.shields.io/badge/Pandas-150458?style=flat-square&logo=pandas&logoColor=white" width="80"> | Data processing & CSV handling |
| <img src="https://img.shields.io/badge/NumPy-013243?style=flat-square&logo=numpy&logoColor=white" width="80"> | Numerical computations |
| <img src="https://img.shields.io/badge/SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white" width="80"> | Lightweight database |
| <img src="https://img.shields.io/badge/ReportLab-red?style=flat-square" width="85"> | PDF report generation |
| <img src="https://img.shields.io/badge/Gunicorn-499848?style=flat-square&logo=gunicorn&logoColor=white" width="90"> | Production WSGI server |

### Frontend
| Technology | Purpose |
|-----------|---------|
| <img src="https://img.shields.io/badge/HTML5-E34F26?style=flat-square&logo=html5&logoColor=white" width="75"> | Page structure |
| <img src="https://img.shields.io/badge/CSS3-1572B6?style=flat-square&logo=css3&logoColor=white" width="70"> | Styling & responsive design |
| <img src="https://img.shields.io/badge/JavaScript-F7DF1E?style=flat-square&logo=javascript&logoColor=black" width="95"> | Frontend logic & interactivity |
| <img src="https://img.shields.io/badge/Chart.js-FF6384?style=flat-square&logo=chartdotjs&logoColor=white" width="80"> | Interactive data visualizations |

### Deployment
| Technology | Purpose |
|-----------|---------|
| <img src="https://img.shields.io/badge/Render-46E3B7?style=flat-square&logo=render&logoColor=white" width="80"> | Cloud hosting platform |
| <img src="https://img.shields.io/badge/GitHub-181717?style=flat-square&logo=github&logoColor=white" width="80"> | Version control & CI/CD |

---

## ✨ Key Features

### 1. 📊 Interactive Dashboard
- Real-time stat cards (Total, High, Medium, Low)
- Category distribution doughnut chart
- Priority breakdown chart
- Recent activity feed
- **Smart Alerts** — live notifications for anomalies

### 2. 🔍 Complaint Analyzer
- Manual complaint entry with Customer Name & Order ID
- AI-powered classification (category, priority, sentiment)
- Confidence score with visual progress bar
- Recommended action for each complaint
- Dataset matching with similar past complaints

### 3. 📋 Complaint History
- Full searchable table of all analyzed complaints
- Customer name, Order ID, category, priority, sentiment, timeline
- Report summaries integrated into history view

### 4. 📈 Insights & Analytics
- Customer sentiment overview (pie chart)
- Complaint growth trend (line chart)
- Critical vs Normal case breakdown
- Data-driven text insights with percentages
- Detection summary (risk, matches, escalations)

### 5. 📄 PDF Report Generator
- Upload CSV or fetch emails directly
- Professional multi-page PDF with:
  - Executive summary with priority breakdown
  - Detailed complaint table with all fields
  - Customer name & Order ID per complaint
- Repeated Order IDs auto-escalated to High priority
- Reports sorted by frequency and priority

### 6. 📧 Email Integration
- Direct Gmail IMAP integration
- Auto-extracts complaints from inbox
- Extracts Order IDs and Customer Names from email body
- One-click "Use Email Data" for report generation

### 7. 🚨 Smart Alert System
- **High Priority Spike** — alerts when >30% complaints are high priority
- **Category Spike** — detects >40% concentration in any category
- **Repeat Order Detection** — flags order IDs with 3+ complaints
- **Negative Sentiment Alert** — warns when >60% sentiment is negative
- Max 3 alerts shown, "All systems normal" when no triggers

---

## 🧠 ML Pipeline

```
Raw Text
   │
   ▼
┌─────────────────┐
│  Preprocessing   │  → Lowercase, remove special chars
└────────┬────────┘
         ▼
┌─────────────────┐
│  TF-IDF          │  → Text vectorization (trained on 5000+ complaints)
│  Vectorizer      │
└────────┬────────┘
         ▼
┌─────────────────┐
│  ML Classifier   │  → Trained scikit-learn model
│  (model.pkl)     │
└────────┬────────┘
         ▼
┌─────────────────┐
│  Rule Engine     │  → Keyword-based priority & sentiment override
└────────┬────────┘
         ▼
┌─────────────────┐
│  TF-IDF Match    │  → Cosine similarity with dataset for confidence
└────────┬────────┘
         ▼
   Final Result:
   Category | Priority | Sentiment | Confidence | Action
```

---

## 📁 Project Structure

```
Fixera/
├── fixera-backend/
│   ├── app.py                 # Main Flask application (API + logic)
│   ├── train_model.py         # ML model training script
│   ├── fetch_emails.py        # Gmail IMAP email fetcher
│   ├── model.pkl              # Trained ML model
│   ├── ml_vectorizer.pkl      # TF-IDF vectorizer
│   ├── complaints.db          # SQLite database
│   ├── complaints.csv         # Email-fetched complaints
│   ├── requirements.txt       # Python dependencies
│   └── reports/               # Generated PDF reports
│
├── fixera-frontend/
│   ├── index.html             # Single-page application
│   ├── app.js                 # Frontend logic & charts
│   ├── style.css              # Complete styling
│   └── logo.png               # Fixera logo
│
├── SelfData.csv               # Training dataset (5000+ complaints)
├── render.yaml                # Render deployment config
├── .gitignore                 # Git ignore rules
└── README.md                  # This file
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.9+
- pip (Python package manager)
- Git

### Local Setup

```bash
# 1. Clone the repository
git clone https://github.com/MeghPatel0106/Fixera.git
cd Fixera

# 2. Create virtual environment
python3 -m venv fixera-backend/venv
source fixera-backend/venv/bin/activate

# 3. Install dependencies
pip install -r fixera-backend/requirements.txt

# 4. Set environment variables (for email feature)
export EMAIL="fixera.system@gmail.com"
export PASSWORD="your-app-password"

# 5. Run the server
python3 fixera-backend/app.py

# 6. Open in browser
# http://127.0.0.1:5001
```

### Train the ML Model (Optional)

```bash
python3 fixera-backend/train_model.py
```

---

## 🌐 Deployment

Deployed on **Render** — [Live Demo](https://fixera.onrender.com)

| Config | Value |
|--------|-------|
| Platform | Render |
| Root Directory | `fixera-backend` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120` |

---

## 📸 Screenshots

| Dashboard | Analyze |
|-----------|---------|
| Real-time stats, charts & smart alerts | AI-powered complaint classification |

| Report Generator | Insights |
|-----------------|----------|
| CSV upload + email fetch → PDF report | Sentiment, trends & risk analysis |

---

## 🔮 Future Scope

| Feature | Description |
|---------|-------------|
| 🔐 **Admin Authentication** | Login/logout system with role-based access |
| 🌍 **Multi-language Support** | Analyze complaints in Hindi, Gujarati, and other languages |
| 📱 **Mobile App** | React Native or Flutter mobile companion app |
| 🔔 **Push Notifications** | Real-time alerts via email/SMS for critical complaints |
| 🗄️ **PostgreSQL Migration** | Replace SQLite with PostgreSQL for production scalability |
| 📊 **Advanced Analytics** | Predictive analytics, trend forecasting, and anomaly detection |
| 🤝 **CRM Integration** | Connect with Salesforce, Zendesk, or Freshdesk |
| 🧠 **Deep Learning** | Upgrade to BERT/Transformer models for better accuracy |
| 📧 **Multi-Channel Intake** | Support Twitter, WhatsApp, and live chat complaints |
| 📋 **SLA Tracking** | Monitor resolution times against service-level agreements |
| 🏷️ **Auto-Tagging** | Automatically tag complaints with subtopics |
| 📤 **Export Options** | Export reports to Excel, Word, and email delivery |

---

## 👥 Team

| Role | Name |
|------|------|
| Developer | **Megh Patel** |

---

## 📄 License

This project is developed for educational and demonstration purposes.

---