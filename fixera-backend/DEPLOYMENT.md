# Fixera Email Fetcher — Deployment Guide

## 📋 Prerequisites

1. **Gmail App Password** (NOT your regular password)
   - Go to https://myaccount.google.com/apppasswords
   - Generate an App Password for "Mail"
   - Copy the 16-character password

2. **Python 3.7+** installed on server

---

## 🔐 Environment Variables

Set these before running:

```bash
# Linux/Mac
export EMAIL="your-email@gmail.com"
export PASSWORD="your-16-char-app-password"

# Windows (Command Prompt)
set EMAIL=your-email@gmail.com
set PASSWORD=your-16-char-app-password

# Windows (PowerShell)
$env:EMAIL = "your-email@gmail.com"
$env:PASSWORD = "your-16-char-app-password"
```

---

## 🐧 Linux/Mac — Cron Job Setup

### Step 1: Make script executable
```bash
chmod +x /path/to/fixera-backend/fetch_emails.py
```

### Step 2: Open crontab
```bash
crontab -e
```

### Step 3: Add this line (runs every 1 minute)
```cron
* * * * * EMAIL="your@gmail.com" PASSWORD="your-app-password" /usr/bin/python3 /path/to/fixera-backend/fetch_emails.py >> /path/to/fixera-backend/cron.log 2>&1
```

### Step 4: Verify
```bash
crontab -l
```

### To stop:
```bash
crontab -e
# Delete or comment out the line
```

---

## 🪟 Windows — Task Scheduler Setup

### Step 1: Create a batch file `run_fetch.bat`
```batch
@echo off
set EMAIL=your@gmail.com
set PASSWORD=your-app-password
python C:\path\to\fixera-backend\fetch_emails.py
```

### Step 2: Open Task Scheduler
- Press `Win + R` → type `taskschd.msc` → Enter

### Step 3: Create Task
1. Click **"Create Basic Task"**
2. Name: `Fixera Email Fetcher`
3. Trigger: **Daily** → then modify to repeat every **1 minute**
4. Action: **Start a Program**
   - Program: `C:\path\to\run_fetch.bat`
5. Click **Finish**

### Step 4: Modify Repetition
1. Right-click the task → **Properties**
2. Go to **Triggers** tab → **Edit**
3. Check **"Repeat task every"** → set to **1 minute**
4. Set **"for a duration of"** → **Indefinitely**
5. Click **OK**

---

## 🖥️ VPS Deployment (Recommended)

### Step 1: Upload files
```bash
scp -r fixera-backend/ user@your-vps:/opt/fixera/
```

### Step 2: Install Python (if needed)
```bash
sudo apt update && sudo apt install python3 -y
```

### Step 3: No pip dependencies needed
The script uses **only Python standard library** (imaplib, email, csv, os, logging).

### Step 4: Set up cron
```bash
crontab -e
```
Add:
```cron
* * * * * EMAIL="you@gmail.com" PASSWORD="app-pass" /usr/bin/python3 /opt/fixera/fixera-backend/fetch_emails.py
```

### Step 5: Verify it works
```bash
EMAIL="you@gmail.com" PASSWORD="app-pass" python3 /opt/fixera/fixera-backend/fetch_emails.py
cat /opt/fixera/fixera-backend/complaints.csv
```

---

## ☁️ Free Platform Options

| Platform | Works? | Notes |
|----------|--------|-------|
| **PythonAnywhere** | ✅ | Free tier has scheduled tasks (min 1 hour interval) |
| **Railway.app** | ✅ | Use cron worker, free tier has limits |
| **Render** | ✅ | Cron jobs available on paid tier |
| **Heroku** | ⚠️ | Scheduler add-on (10 min minimum interval) |
| **GitHub Actions** | ✅ | Free, schedule with `cron: '*/1 * * * *'` |

### GitHub Actions Example (`.github/workflows/fetch.yml`):
```yaml
name: Fetch Complaint Emails
on:
  schedule:
    - cron: '*/5 * * * *'  # Every 5 minutes (minimum for GitHub)
  workflow_dispatch:        # Manual trigger

jobs:
  fetch:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: python fixera-backend/fetch_emails.py
        env:
          EMAIL: ${{ secrets.EMAIL }}
          PASSWORD: ${{ secrets.PASSWORD }}
```

---

## 📁 Output

Emails are stored in `complaints.csv`:
```
email,subject,description,fetched_at
user@example.com,Broken product complaint,The item I received was...,2026-04-18T23:20:00
```

## 📝 Logs

Check `fetch_emails.log` for execution history:
```
2026-04-18 23:20:00 [INFO] Connecting to Gmail IMAP...
2026-04-18 23:20:01 [INFO] Login successful.
2026-04-18 23:20:01 [INFO] Found 3 new email(s). Processing...
2026-04-18 23:20:02 [INFO] Saved 3 complaint(s) to complaints.csv
```
