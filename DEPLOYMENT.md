# FormPilot Deployment Guide

## 🚀 Option 1: Railway (Recommended — 5 minutes)

Railway is the fastest and most reliable for FastAPI apps. Free tier covers hackathon demos.

### Step 1: Create Railway Account
1. Go to https://railway.app
2. Sign up with GitHub
3. Authorize Railway to access your repositories

### Step 2: Create Railway Project
1. Click **"New Project"** → **"Deploy from GitHub"**
2. Select your **Formpilot** repository
3. Railway auto-detects it's a Python app

### Step 3: Configure Environment
1. In Railway dashboard, go to **Variables**
2. Add:
   ```
   GEMINI_API_KEY=your_api_key_here
   APP_HOST=0.0.0.0
   APP_PORT=8000
   ```
3. Click **Deploy**

### Step 4: Get Your URL
```
https://formpilot-production-xxxx.railway.app
```

That's it! Your app is live.

---

## 🐳 Option 2: Docker + Heroku (Alternative)

### Step 1: Create Dockerfile

Create `Dockerfile` in project root:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY backend/ .

# Expose port
EXPOSE 8000

# Run
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "$PORT"]
```

### Step 2: Create Heroku Procfile

Create `Procfile` in project root:

```
web: cd backend && uvicorn main:app --host=0.0.0.0 --port=$PORT
```

### Step 3: Deploy to Heroku

```bash
# Install Heroku CLI
brew install heroku  # macOS
# or: curl https://cli-assets.heroku.com/install.sh | sh  # Linux

# Login
heroku login

# Create app
heroku create formpilot-yourusername

# Set environment variables
heroku config:set GEMINI_API_KEY=your_key_here

# Deploy
git push heroku main

# View logs
heroku logs --tail
```

Your app will be at: `https://formpilot-yourusername.herokuapp.com`

---

## ☁️ Option 3: Docker + Google Cloud Run (Pay Per Use)

### Step 1: Create Dockerfile (same as Heroku above)

### Step 2: Build and Push to Google Container Registry

```bash
# Install gcloud CLI
# https://cloud.google.com/sdk/docs/install

# Authenticate
gcloud auth login
gcloud auth configure-docker

# Build image
docker build -t formpilot .

# Tag for GCR
docker tag formpilot gcr.io/your-project-id/formpilot

# Push to GCR
docker push gcr.io/your-project-id/formpilot

# Deploy to Cloud Run
gcloud run deploy formpilot \
  --image gcr.io/your-project-id/formpilot \
  --platform managed \
  --region us-central1 \
  --set-env-vars GEMINI_API_KEY=your_key_here \
  --allow-unauthenticated
```

Your app will be at: `https://formpilot-xxxxx-uc.a.run.app`

---

## 📦 Option 4: Docker + Render (Simple Alternative)

### Step 1: Create Dockerfile (same as above)

### Step 2: Connect to Render

1. Go to https://render.com
2. Sign up with GitHub
3. Click **"New +"** → **"Web Service"**
4. Select your Formpilot repository
5. Set:
   - **Name:** formpilot
   - **Environment:** Python 3
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `cd backend && uvicorn main:app --host=0.0.0.0 --port=$PORT`
6. Add environment variable: `GEMINI_API_KEY=your_key_here`
7. Click **Deploy**

Your app will be at: `https://formpilot-xxxx.onrender.com`

---

## 🖥️ Option 5: Traditional VPS (AWS EC2, DigitalOcean, Linode)

### Step 1: SSH into your VPS

```bash
ssh ubuntu@your-server-ip
```

### Step 2: Install Python and Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.12
sudo apt install -y python3.12 python3.12-venv python3-pip

# Install Git
sudo apt install -y git

# Create app directory
mkdir -p /opt/formpilot
cd /opt/formpilot

# Clone repository
git clone https://github.com/yourusername/Formpilot.git .
```

### Step 3: Create Virtual Environment

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 4: Create Systemd Service

Create `/etc/systemd/system/formpilot.service`:

```ini
[Unit]
Description=FormPilot API Server
After=network.target

[Service]
Type=notify
User=ubuntu
WorkingDirectory=/opt/formpilot
Environment="PATH=/opt/formpilot/venv/bin"
Environment="GEMINI_API_KEY=your_key_here"
ExecStart=/opt/formpilot/venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Step 5: Start Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable formpilot
sudo systemctl start formpilot
sudo systemctl status formpilot
```

### Step 6: Setup Nginx Reverse Proxy

Install Nginx:
```bash
sudo apt install -y nginx
```

Create `/etc/nginx/sites-available/formpilot`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable:
```bash
sudo ln -s /etc/nginx/sites-available/formpilot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### Step 7: Setup SSL with Certbot

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot certonly --nginx -d your-domain.com
sudo systemctl reload nginx
```

Your app is now live at: `https://your-domain.com`

---

## 📋 Comparison Table

| Platform | Cost | Setup Time | Difficulty | Best For |
|----------|------|-----------|-----------|----------|
| **Railway** | Free tier + pay-as-you-go | 5 min | Very easy | Hackathon demos |
| **Heroku** | Free tier (sleeping) | 10 min | Easy | Quick prototypes |
| **Cloud Run** | Pay per invocation (~$0.40/M) | 15 min | Medium | Scalable solutions |
| **Render** | Free tier (spinning down) | 10 min | Easy | Small projects |
| **VPS** | $5-20/month | 30 min | Hard | Production apps |

---

## ✅ Post-Deployment Checklist

After deploying, verify:

```bash
# Health check
curl https://your-deployed-app.com/health

# API info
curl https://your-deployed-app.com/api

# Try demo (no API key needed)
curl -X POST https://your-deployed-app.com/api/workflows/demo

# Frontend should load
open https://your-deployed-app.com
```

---

## 🔐 Security Best Practices

1. **Never commit API keys**
   ```bash
   echo ".env" >> .gitignore
   git rm --cached .env
   ```

2. **Use environment variables** for all secrets:
   - Railway: Variables tab
   - Heroku: `heroku config:set KEY=value`
   - Cloud Run: `--set-env-vars`

3. **Enable CORS only for your domain** in production:
   ```python
   from fastapi.middleware.cors import CORSMiddleware
   
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["https://your-domain.com"],  # Not "*"
       allow_credentials=True,
       allow_methods=["*"],
       allow_headers=["*"],
   )
   ```

4. **Monitor logs** for errors and performance issues.

5. **Set up alerts** for down time or high error rates.

---

## 🆘 Troubleshooting

### App keeps crashing on startup

```bash
# Check logs
heroku logs --tail
# or
journalctl -u formpilot -f
```

Look for:
- Missing Python version
- Missing dependencies in requirements.txt
- API key validation errors

### "Port already in use"

Make sure to use `$PORT` environment variable:
```bash
uvicorn main:app --host=0.0.0.0 --port=$PORT
```

### Gemini API not working

1. Verify API key is set in environment variables (not hardcoded)
2. Check Gemini API quota: https://aistudio.google.com/app/apikey
3. Ensure free tier limit not exceeded

### Cold starts are slow

This is normal for serverless/free platforms. To minimize:
- Use lightweight startup code
- Pre-warm the app with periodic health check pings

---

## 📺 Going Live for Hackathon

### For judges to test your deployed app:

1. **Share the URL:** `https://your-app.railway.app`
2. **Include API key** in video/description if running real OCR demo, OR
3. **Use the demo endpoint** that works without any API key:
   ```
   POST https://your-app.railway.app/api/workflows/demo
   ```

### Record a demo video:

```bash
# In browser
open https://your-deployed-app.com

# Screen record:
# macOS: Cmd+Shift+5
# Linux: gnome-screenshot --interactive
# Windows: Win+Shift+S

# Show:
# 1. Load the frontend (3 sec)
# 2. Upload/drag demo document (2 sec)
# 3. Click "Run Instant Demo" (2 sec)
# 4. Watch pipeline animate (5 sec)
# 5. Download PDF (2 sec) → show it opened

# Total: 14 seconds of compelling demo
```

---

**Ready to deploy? Start with Railway — it's the fastest path to a live hackathon submission.**
