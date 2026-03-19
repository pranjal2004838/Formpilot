# 🚂 Railway Deployment — Complete Environment Variables Guide

**Status:** Ready to deploy FormPilot to Railway  
**Deadline:** March 20, 2026  
**Estimated setup time:** 15-20 minutes

---

## 📋 ALL ENVIRONMENT VARIABLES (Required + Optional)

### **CRITICAL (Required for App to Run)**

| Variable | Value | How to Get | Priority |
|----------|-------|-----------|----------|
| **GEMINI_API_KEY** | `your_gemini_api_key` | [Get free here](https://makersuite.google.com/app/apikey) | ⭐⭐⭐ REQUIRED |
| **APP_HOST** | `0.0.0.0` | Use this exact value | ⭐⭐ Standard |
| **APP_PORT** | `$PORT` | Use this exact value (Railway auto-fills) | ⭐⭐ Standard |
| **FRONTEND_URL** | `http://localhost:3000` or `https://your-frontend.vercel.app` | Your frontend domain | ⭐ Optional (has defaults) |
| **DATABASE_URL** | `sqlite:///./formpilot.db` | Use this exact value | ⭐ Optional (has defaults) |
| **LOG_LEVEL** | `INFO` | Use this value (or DEBUG for verbose) | ⭐ Optional |

---

### **AI/ML APIs (Optional but Recommended)**

| Variable | Value | How to Get | Use Case |
|----------|-------|-----------|----------|
| **ANTHROPIC_API_KEY** | `sk-ant-...` | [Claude API](https://console.anthropic.com/keys) | Backup LLM (optional) |
| **AIRIA_API_KEY** | `your_airia_key` | [Airia Dashboard](https://airia.community/settings) | Airia orchestration |
| **AIRIA_PIPELINE_ID** | `pipeline_id_xxx` | After publishing pipeline to Airia | Airia orchestration |
| **AIRIA_BASE_URL** | `https://api.airia.io` | Use this exact value (default) | Airia backend |
| **FORMPILOT_API_KEY** | Generate random string | `openssl rand -hex 32` | Airia callback auth |
| **FORMPILOT_API_URL** | `https://formpilot-xxx.railway.app` | Your Railway URL (after deploy) | API endpoint |

---

### **Slack Integration (Optional)**

| Variable | Value | How to Get | Use Case |
|----------|-------|-----------|----------|
| **SLACK_WEBHOOK_URL** | `https://hooks.slack.com/...` | [Slack App Guide](#slack-setup) below | HITL notifications |
| **SLACK_CHANNEL** | `#formpilot-notifications` | Your Slack channel name | Where to notify |

---

### **SharePoint Integration (Optional)**

| Variable | Value | How to Get | Use Case |
|----------|-------|-----------|----------|
| **SHAREPOINT_TENANT_ID** | `00000000-0000-0000-0000-000000000000` | [Microsoft Entra](https://ms.portal.azure.com/#blade/Microsoft_AAD_IAM/ActiveDirectoryMenuBlade/Overview) | Document upload |
| **SHAREPOINT_CLIENT_ID** | `client_app_id` | [App Registration](#sharepoint-setup) below | SharePoint auth |
| **SHAREPOINT_CLIENT_SECRET** | `secret_value` | App Registration Secret | SharePoint auth |
| **SHAREPOINT_SITE_URL** | `https://yourorg.sharepoint.com/sites/yoursite` | Your SharePoint site | Upload location |
| **SHAREPOINT_LIBRARY** | `FormPilot Documents` | Your document library name | Storage folder |

---

### **AWS S3 Storage (Optional)**

| Variable | Value | How to Get | Use Case |
|----------|-------|-----------|----------|
| **AWS_ACCESS_KEY_ID** | `AKIA...` | [AWS Console](#aws-s3-setup) below | PDF storage |
| **AWS_SECRET_ACCESS_KEY** | `secret_key_value` | AWS Access Key | PDF storage |
| **AWS_S3_BUCKET** | `formpilot-forms` | Name of your S3 bucket | Storage bucket |

---

## 🚀 STEP-BY-STEP SETUP FOR RAILWAY

### **Step 1: Get Gemini API Key (5 minutes)**

1. Go to: **https://makersuite.google.com/app/apikey**
2. Click **"Create API Key"**
3. Copy the key (starts with `AIza...`)
4. **Save this value** — you'll paste it into Railway

**Test it works locally:**
```bash
export GEMINI_API_KEY="your_key_here"
cd backend
python -c "
import os
from google.generativeai import configure, GenerativeModel
configure(api_key=os.getenv('GEMINI_API_KEY'))
model = GenerativeModel('gemini-3-flash')
response = model.generate_content('Say OK')
print('✅ Gemini API working:', response.text)
"
```

---

### **Step 2: (Optional) Set Up Slack Notifications**

<a id="slack-setup"></a>

**Only do this if you want Slack HITL approvals**

1. Go to: **https://api.slack.com/apps**
2. Click **"Create New App"** → **"From scratch"**
3. Name: `FormPilot`
4. Select your workspace
5. Go to **"Incoming Webhooks"** → **"Add New Webhook to Workspace"**
6. Select channel: `#formpilot-notifications` (or create it)
7. Click **"Allow"**
8. Copy the webhook URL: `https://hooks.slack.com/services/T.../B.../...`
9. **Save this value** — you'll paste it into Railway as `SLACK_WEBHOOK_URL`

---

### **Step 3: (Optional) Set Up SharePoint Integration**

<a id="sharepoint-setup"></a>

**Only do this if you want automatic PDF uploads to SharePoint**

#### 3a. Register App in Microsoft Entra

1. Go to: **https://ms.portal.azure.com/#blade/Microsoft_AAD_IAM/RegisteredAppsMenuBlade**
2. Click **"+ New registration"**
3. Name: `FormPilot`
4. Select: **"Accounts in this organizational directory only"**
5. Click **"Register"**
6. **On the app page, copy:** `Application (client) ID` → Save as `SHAREPOINT_CLIENT_ID`
7. Go to **"Certificates & secrets"** → **"+ New client secret"**
8. Add secret, copy the value → Save as `SHAREPOINT_CLIENT_SECRET`
9. Go to **"API permissions"** → **"+ Add a permission"** → **"Microsoft Graph"**
10. Select **"Application permissions"**
11. Find: `Sites.ReadWrite.All`, `Files.ReadWrite.All` → Check both
12. Click **"Grant admin consent"**

#### 3b. Get Tenant ID

1. Go to: **https://ms.portal.azure.com/#blade/Microsoft_AAD_IAM/ActiveDirectoryMenuBlade**
2. Scroll to **"Tenant information"**
3. Copy **"Tenant ID"** → Save as `SHAREPOINT_TENANT_ID`

#### 3c. Get SharePoint Site URL

1. Open your SharePoint site in browser
2. Copy the URL from address bar: `https://yourorg.sharepoint.com/sites/yoursite`
3. Save as `SHAREPOINT_SITE_URL`

The library name defaults to: `FormPilot Documents` (you can create this folder in SharePoint if needed)

---

### **Step 4: (Optional) Set Up AWS S3**

<a id="aws-s3-setup"></a>

**Only do this if you want PDF storage in AWS S3**

1. Go to: **https://console.aws.amazon.com/iam/home**
2. **Create an S3 bucket:**
   - Go to S3 console
   - Click **"Create bucket"**
   - Name: `formpilot-forms-[your-username]`
   - Region: US East 1 (or closest to you)
   - Keep defaults
   - Click **"Create bucket"**

3. **Create access keys:**
   - Go to **"Users"** in IAM
   - Create new user: `formpilot-app`
   - Add **"Attach policies directly"** → search `AmazonS3FullAccess`
   - Create user
   - Go to **"Security credentials"** → **"Create access key"**
   - Select **"Application running outside AWS"**
   - Copy:
     - `AWS_ACCESS_KEY_ID`
     - `AWS_SECRET_ACCESS_KEY`

4. Save bucket name as `AWS_S3_BUCKET`: `formpilot-forms-[your-username]`

---

### **Step 5: Deploy to Railway**

#### 5a. Create Railway Account

1. Go to: **https://railway.app**
2. Click **"Start New Project"**
3. Sign up with **GitHub**
4. Authorize Railway to access GitHub

#### 5b. Create Project

1. Click **"New Project"**
2. Select **"Deploy from GitHub"**
3. Authorize Railway with GitHub
4. Select your **`Formpilot`** repository
5. Click **"Deploy"**
6. **Wait 2-3 minutes** for initial build

#### 5c. Add Environment Variables

1. **In Railway Dashboard:**
   - Go to your project
   - Click **"Variables"** tab
   - Click **"New Variable"**

2. **Add MINIMUM variables:**
   ```
   GEMINI_API_KEY = your_key_from_step_1
   APP_HOST = 0.0.0.0
   FORMPILOT_API_KEY = <generate_random_string>
   ```

3. **Add OPTIONAL variables:**
   - If you setup Slack: Add `SLACK_WEBHOOK_URL`
   - If you setup SharePoint: Add all `SHAREPOINT_*` variables
   - If you setup S3: Add all `AWS_*` variables
   - If using Airia: Add `AIRIA_API_KEY`, `AIRIA_PIPELINE_ID`

4. **Click "Deploy"** after each variable addition

#### 5d. Get Your Railway URL

1. Go to **"Settings"** in Railway project
2. Find **"Public URL"** (looks like: `https://formpilot-production-xxxx.railway.app`)
3. **Copy this URL** — you'll need it for DevPost + Airia

---

## ✅ Verification Checklist

After Railway deploys, verify everything works:

```bash
# Test the API is responding
curl https://your-railway-url.railway.app/

# Should respond with HTML (the dashboard)
# If you get 502 Bad Gateway, wait 1-2 more minutes for full deploy

# Test health endpoint
curl https://your-railway-url.railway.app/health

# Should return: {"status":"ok"}

# Test demo workflow
curl -X POST https://your-railway-url.railway.app/api/workflows/demo \
  -H "Content-Type: application/json" \
  -d '{"document_type":"passport"}'

# Should return workflow_id
```

---

## 🔧 Troubleshooting

### **"502 Bad Gateway" error**
- **Cause:** App still loading
- **Fix:** Wait 2-3 minutes, refresh page

### **"GEMINI_API_KEY not set" warning**
- **Cause:** Variable not added to Railway
- **Fix:** Add variable, redeploy (Railway → Variables → Add → Deploy)

### **"No module named 'pydantic'" error**
- **Cause:** Dependencies not installed
- **Fix:** Railway auto-installs from `requirements.txt` — check file is in repo root

### **Workflow returns 500 error**
- **Cause:** Missing optional API keys (Slack, SharePoint)
- **Fix:** This is OK — app runs in simulated mode. Only add these if you need them.

### **"Cannot connect to frontend" error**
- **Cause:** `FRONTEND_URL` mismatch
- **Fix:** Update `FRONTEND_URL` to match your actual frontend domain (if deployed to Vercel)

---

## 📝 Complete .env Template (For Local Testing)

Create a `.env` file in the `backend/` directory with:

```bash
# ============================================================
# REQUIRED
# ============================================================
GEMINI_API_KEY=AIza_YOUR_KEY_HERE
APP_HOST=0.0.0.0
APP_PORT=8000

# ============================================================
# OPTIONAL AI/ML APIs
# ============================================================
ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE
AIRIA_API_KEY=your_airia_key
AIRIA_PIPELINE_ID=pipeline_id_xxx
AIRIA_BASE_URL=https://api.airia.io
FORMPILOT_API_KEY=your_random_api_key_here
FORMPILOT_API_URL=http://localhost:8000

# ============================================================
# OPTIONAL INTEGRATIONS
# ============================================================
# Slack
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
SLACK_CHANNEL=#formpilot-notifications

# SharePoint
SHAREPOINT_TENANT_ID=00000000-0000-0000-0000-000000000000
SHAREPOINT_CLIENT_ID=your_client_id
SHAREPOINT_CLIENT_SECRET=your_client_secret
SHAREPOINT_SITE_URL=https://yourorg.sharepoint.com/sites/yoursite
SHAREPOINT_LIBRARY=FormPilot Documents

# AWS S3
AWS_ACCESS_KEY_ID=AKIA_YOUR_KEY
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_S3_BUCKET=formpilot-forms

# ============================================================
# DATABASE & LOGGING
# ============================================================
DATABASE_URL=sqlite:///./formpilot.db
LOG_LEVEL=INFO
FRONTEND_URL=http://localhost:3000
```

---

## 🎯 MINIMUM VIABLE DEPLOYMENT

**To deploy FormPilot to Railway RIGHT NOW (only 3 variables needed):**

```
GEMINI_API_KEY = <your Gemini key>
APP_HOST = 0.0.0.0
FORMPILOT_API_KEY = <any random string>
```

**That's it!** Everything else has sensible defaults and will work in demo mode.

---

## 📊 Variable Guide by Priority

### **Absolute Must-Haves (Copy-paste to Railway NOW)**
```
GEMINI_API_KEY=AIza_YOUR_KEY
APP_HOST=0.0.0.0
FORMPILOT_API_KEY=any_random_String_here123
```

### **"Nice to Have" (If you want full functionality)**
```
SLACK_WEBHOOK_URL=<if you want Slack notifications>
SHAREPOINT_*=<if you want automatic PDF uploads>
AWS_*=<if you want S3 storage>
AIRIA_*=<if integrating with Airia>
```

### **Can Safely Ignore (Uses defaults)**
```
FRONTEND_URL (defaults to localhost:3000)
DATABASE_URL (defaults to SQLite)
LOG_LEVEL (defaults to INFO)
```

---

## 🔐 SECURITY NOTE

**NEVER commit `.env` file to GitHub:**

```bash
# Make sure .gitignore includes .env
echo ".env" >> .gitignore
git add .gitignore
git commit -m "Add .env to gitignore"
git rm --cached .env  # Remove if already committed
```

---

## ✨ NEXT STEPS

1. ✅ Get Gemini API key (5 minutes)
2. ✅ Go to Railway.app and deploy (2 minutes)
3. ✅ Add 3 minimum variables (2 minutes)
4. ✅ Wait for deployment (2-3 minutes)
5. ✅ Test the URL: `https://your-railway-url.railway.app`
6. ✅ Copy URL for DevPost submission

**Total time: 15 minutes**

---

**Ready to deploy? Start with Step 1 above!** 🚀

