# 🎯 LeetCode Contest Automation System

**Automatically track student LeetCode contest performance with zero manual work!**

## 🌟 What This Does

A **24/7 automated system** that:
- ✅ **Monitors** LeetCode contests (Weekly & Biweekly)
- ✅ **Triggers automatically** 2 minutes after contests end
- ✅ **Fetches** contest problems from LeetCode API
- ✅ **Reads** student LeetCode IDs from your Google Sheet
- ✅ **Evaluates** each student's submissions (N/A, 0, or count of solved problems)
- ✅ **Writes** results to new columns in Google Sheets
- ✅ **Prevents duplicates** with intelligent status tracking
- ✅ **Creates backups** in JSON format

---

## ⏰ Automatic Schedule (IST)

| Task Type | Schedule | Trigger Time | Purpose |
|-----------|----------|--------------|---------|
| **Daily Stats** | Every day | **12:00 PM (noon)** | Update total problems solved & contest rating |
| **Weekly Contest** | Every Sunday | **9:34 AM** | Process contest results (4 min after 9:30 AM end) |
| **Biweekly Contest** | Alternate Saturdays | **9:34 PM** | Process contest results (4 min after 9:30 PM end) |

---

## 🚀 Quick Start (3 Steps)

### **Step 1: Install Dependencies**

```bash
pip install -r requirements.txt
```

### **Step 2: Test Locally**

```bash
# Test with latest contests
python scheduler.py --test
```

This will process the most recent contests and update your Google Sheet immediately!

### **Step 3: Deploy (Optional)**

Deploy to run 24/7 automatically. See [Deployment Guide](#-deployment-guide) below.

---

## 📋 Prerequisites

1. **Python 3.10+** installed
2. **Google Service Account** with Sheets API access
3. **Google Sheet** with student data (Column A: Name, Column B: LeetCode ID)

---

## 🔧 Setup Instructions

### **1. Create Google Service Account**

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable **Google Sheets API**:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Google Sheets API" → Enable
4. Create **Service Account**:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "Service Account"
   - Fill in details → Create
5. Download **JSON key**:
   - Click on the service account
   - Go to "Keys" tab → "Add Key" > "Create new key"
   - Choose **JSON** format
   - Save as `service.json` in project root

### **2. Share Google Sheet with Service Account**

1. Open your `service.json` file
2. Copy the `client_email` (e.g., `your-service@project.iam.gserviceaccount.com`)
3. Open your Google Sheet
4. Click **"Share"** button
5. Paste the service account email
6. Set permissions to **"Editor"**
7. Click "Send"

### **3. Configure Your Sheet**

Edit `config.json`:

```json
{
  "sheet_id": "YOUR_SHEET_ID",
  "sheet_name": "Real data Leetcode",
  "service_account_file": "./service.json",
  "contest_slug": "biweekly-contest-171",
  "contest_display_name": "Biweekly Contest 171",
  "contest_start_ts": 1765031400,
  "contest_end_ts": 1765036800,
  "contest_problems": []
}
```

**Your Google Sheet Format:**
```
Column A: NAME          | Column B: Leetcode ID
Mohamed Askar S         | Askar786
NITHIVALAVAN N         | NITHIVALAVAN
NAVINKUMAR J           | navin_7987
Salman Khan S          | Salman_codes
```

### **4. Install Dependencies**

```bash
pip install -r requirements.txt
```

---

## 🧪 Testing

### **Test Manual Processing**

```bash
# Dry run (no write to sheets)
python main.py --dry-run

# Production run (writes to sheets)
python main.py
```

### **Test Automation**

```bash
# Process latest contests immediately
python scheduler.py --test
```

**Expected Output:**
```
TEST MODE: Processing latest contests now...
Processing weekly contest...
======================================================================
PROCESSING CONTEST: Weekly Contest 478
======================================================================
Found 4 problems
Loaded 4 students from sheet
[1/4] Processing: Mohamed Askar S (Askar786)
  Result: 2
Results written successfully to Google Sheets
✅ Successfully processed weekly-contest-478
```

---

## 📊 How It Works

### **1. Contest Detection**
- Scans LeetCode for recent Weekly (465-485) and Biweekly (135-150) contests
- Fetches official metadata: start time, duration, problems

### **2. Student Evaluation**
For each student:
1. Fetches all their submissions from API
2. Filters submissions by:
   - Problem is in contest
   - Timestamp within contest window
   - Status = "Accepted"
3. Counts unique problems solved

### **3. Result Calculation**
- **"N/A"** → No submissions during contest
- **"0"** → Submitted but none accepted
- **"1-4"** → Number of problems solved

### **4. Google Sheets Update**
- Creates new column with contest name
- Writes results for all students
- Idempotent (safe to run multiple times)

---

## 🚀 Deployment Guide

### **Option 1: Railway (RECOMMENDED)**

**Why Railway?**
- ✅ Free $5/month credit (enough for this)
- ✅ Always running 24/7
- ✅ 5-minute setup

**Steps:**

1. **Copy service.json:**
   ```bash
   # Windows
   Get-Content service.json | clip
   
   # Mac/Linux
   cat service.json | pbcopy
   ```

2. **Push to GitHub:**
   ```bash
   git init
   git add .
   git commit -m "LeetCode automation"
   git remote add origin https://github.com/YOUR_USERNAME/leetcode-automation.git
   git push -u origin main
   ```

3. **Deploy to Railway:**
   - Go to [railway.app](https://railway.app)
   - Sign up with GitHub (free)
   - New Project → Deploy from GitHub repo
   - Select your repo
   - Go to **"Variables"** tab
   - Add variable:
     - Name: `SERVICE_JSON`
     - Value: Paste your service.json content
   - Railway auto-deploys!

4. **Verify:**
   - Check "Logs" tab
   - Should see: "LEETCODE CONTEST SCHEDULER STARTED"
   - "Monitoring for trigger times..."

**✅ Done! Your automation runs 24/7!**

---

### **Option 2: Render**

1. Push to GitHub
2. Go to [render.com](https://render.com)
3. New → Background Worker
4. Connect your repo
5. Start Command: `python scheduler.py`
6. Add environment variable: `SERVICE_JSON`
7. Deploy!

---

### **Option 3: Keep PC Running**

```bash
# Run continuously (PC must stay on)
python scheduler.py
```

---

## 📅 Automation Behavior

### **Every Sunday at 9:32 AM:**
```
2025-12-08 09:32:05 - 🎯 Weekly contest trigger detected!
2025-12-08 09:32:06 - PROCESSING CONTEST: Weekly Contest 479
2025-12-08 09:32:10 - Found 4 problems
2025-12-08 09:32:11 - Loaded 4 students
2025-12-08 09:32:25 - Results written to Google Sheets
2025-12-08 09:32:26 - ✅ Successfully processed!
```

**Result:** New column "Weekly Contest 479" appears in your Google Sheet!

### **Alternate Saturdays at 9:32 PM:**
Same process for Biweekly contests.

---

## 📁 Project Structure

```
leetcode-automation/
├── scheduler.py              # Main automation (runs 24/7)
├── main.py                   # Manual processing
├── config.json               # Configuration
├── requirements.txt          # Dependencies
├── contest_detector.py       # Find recent contests
├── contest_fetcher.py        # Fetch problems
├── submissions_parser.py     # Evaluate submissions
├── sheets_handler.py         # Google Sheets operations
├── railway.json              # Railway deployment config
├── Procfile                  # Render deployment config
├── service.json              # Google credentials (local only)
├── contest_status.json       # Tracks processed contests
└── results_backup/           # JSON backups
```

---

## 🛠️ Troubleshooting

### **Issue: Wrong Timezone**

Server time might differ from your local time.

**Solution:** Update `scheduler.py`:

```python
from datetime import timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

def is_weekly_trigger_time(self) -> bool:
    now = datetime.now(IST)  # Use IST
    if now.weekday() != 6:  # Sunday
        return False
    if now.hour == 9 and 32 <= now.minute <= 33:
        return True
    return False
```

### **Issue: Google Sheets Permission Denied**

**Solution:**
1. Verify `SERVICE_JSON` environment variable
2. Ensure service account has Editor access to sheet
3. Test locally: `python scheduler.py --test`

### **Issue: Not Triggering at Correct Time**

**Solution:**
1. Check Railway/Render logs at 9:32 AM/PM
2. Verify server timezone
3. Adjust trigger times if needed

---

## 💰 Cost

| Platform | Free Tier | Your Usage | Cost |
|----------|-----------|------------|------|
| **Railway** | $5 credit/month | ~$2-3/month | **FREE** ✅ |
| **Render** | Limited free | ~$0-7/month | **FREE** ✅ |
| **AWS EC2** | None | ~$10/month | **$10/month** |

**Recommendation:** Use Railway (free & reliable)

---

## 🎯 Quick Commands

```bash
# Test automation
python scheduler.py --test

# Manual processing
python main.py

# Dry run (no write)
python main.py --dry-run

# Check processed contests
cat contest_status.json

# View logs
cat scheduler.log

# Push updates (Railway auto-deploys)
git add .
git commit -m "Update"
git push
```

---

## ✅ Success Criteria

Your automation is working when:

1. ✅ Railway shows "Running" status
2. ✅ Logs show "Monitoring for trigger times..."
3. ✅ After next contest: New column in Google Sheets
4. ✅ Results are accurate (N/A, 0, or problem count)
5. ✅ `contest_status.json` updates
6. ✅ Backup JSONs in `results_backup/`

---

## 📞 Support

**Check:**
1. Railway/Render logs (real-time monitoring)
2. `scheduler.log` file (if local)
3. `contest_status.json` (processed contests)
4. Google Sheets (verify results)

**Common Issues:**
- Wrong timezone → Update to use IST
- Permission denied → Check SERVICE_JSON
- Not triggering → Verify time in logs

---

## 🎉 You're Ready!

1. ✅ Test: `python scheduler.py --test`
2. ✅ Deploy to Railway
3. ✅ Monitor logs
4. ✅ Wait for next contest (automatic!)

**Your automation will process contests automatically from now on!** 🚀

## Project Structure

```
leetcode-fraud-detector/
├── main.py                    # CLI entry point
├── contest_fetcher.py         # Fetches contest problems via GraphQL
├── submissions_parser.py      # Fetches and evaluates user submissions
├── sheets_handler.py          # Google Sheets read/write operations
├── config.json                # Configuration file
├── requirements.txt           # Python dependencies
├── service.json              # Service account credentials (DO NOT COMMIT)
├── test_run.sh               # Local testing script
├── .github/
│   └── workflows/
│       └── schedule.yml      # GitHub Actions workflow
└── README.md                 # This file
```

## Security Notes

- **NEVER commit `service.json` to version control**
- Add `service.json` to `.gitignore`
- Use GitHub Secrets for CI/CD credentials
- Rotate service account keys periodically

## Support

For issues or questions, check:
1. Logs from the script output
2. Google Sheet permissions
3. API endpoint availability
4. Configuration values in `config.json`
