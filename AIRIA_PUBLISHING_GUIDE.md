# 📢 Publishing FormPilot to Airia Community
## Complete Guide to Publish Your Agent (10 minutes)

**Deadline:** March 20, 2026, 9:15am GMT+5:30  
**Time to Complete:** 10 minutes  
**Outcome:** Airia Community URL for DevPost submission

---

## 🚀 QUICK START

1. **Visit:** https://app.airia.io
2. **Log in** with your Airia account (or create one)
3. **Navigate:** Pipelines → Create → Import YAML
4. **Paste:** Content from `airia_pipeline_config.yaml`
5. **Publish:** Set to PUBLIC, Click "Publish"
6. **Copy:** Community URL → Save for DevPost

---

## 📋 STEP-BY-STEP PUBLISHING INSTRUCTIONS

### **Step 1: Access Airia Platform (1 minute)**

1. Open https://app.airia.io in your browser
2. **If not logged in:**
   - Click "Sign Up" or "Log In"
   - Use email from your FormPilot Team account (or create one)
   - Complete 2FA if required
3. **Once logged in:**
   - You should see: Dashboard → Pipelines → Community

---

### **Step 2: Create New Pipeline (2 minutes)**

**Option A: From Pipelines Dashboard**
1. Click **"Pipelines"** (left sidebar)
2. Click **"Create New"** or **"+ New Pipeline"**
3. Choose **"Import YAML"** (or "Upload YAML File")
4. **Skip to Step 3**

**Option B: Direct Import**
1. Go directly to: https://app.airia.io/pipelines/import
2. **Skip to Step 3**

---

### **Step 3: Upload Pipeline Configuration (2 minutes)**

**Copy YAML Content:**
1. Open `/workspaces/Formpilot/airia_pipeline_config.yaml` in your editor
2. Select ALL content (Ctrl+A)
3. Copy (Ctrl+C)

**Paste into Airia:**
1. In Airia, paste the full YAML into the **"Pipeline YAML"** text box
2. Airia will auto-validate the YAML structure
3. If any errors appear → Red box with error details (fix in the YAML)
4. Once valid → Green checkmark ✅ appears

**What you're uploading:**
- Pipeline name: `FormPilot — Document-to-Form Pipeline`
- Version: 2.0.0
- 5-step agent orchestration workflow
- All input/output schemas
- HITL governance configuration
- Slack + SharePoint integration definitions

---

### **Step 4: Register Environment Variables (2 minutes)**

After uploading YAML, Airia will ask for **environment variables**:

**Click on each variable and set values:**

| Variable | Value | Where to Get | Optional? |
|----------|-------|-------------|-----------|
| **GEMINI_API_KEY** | `your_key_here` | https://makersuite.google.com → Get API Key | ❌ Required |
| **AIRIA_API_KEY** | `your_airia_key` | https://app.airia.io/settings/api-keys | ✅ Optional |
| **SLACK_WEBHOOK_URL** | `https://hooks.slack.com/...` | Slack Workspace → Apps → Incoming Webhooks | ✅ Optional |
| **SHAREPOINT_CLIENT_ID** | From Azure | https://portal.azure.com → App registrations | ✅ Optional |
| **SHAREPOINT_CLIENT_SECRET** | From Azure | Azure app registration | ✅ Optional |
| **LOG_LEVEL** | `INFO` | Default: `INFO` | ✅ Optional |

**Important:**
- At minimum, set **GEMINI_API_KEY** (required for agent to function)
- Leave optional variables blank if you haven't configured them yet
- You can update these later after publishing

---

### **Step 5: Configure Publishing Details (2 minutes)**

Airia will show a **"Publish Settings"** form:

**Fill in:**

| Field | Value |
|-------|-------|
| **Agent Name** | FormPilot Enterprise |
| **Display Name** | FormPilot — Document-to-Form Pipeline |
| **Description** | *See below* |
| **Category** | Document Processing & Automation |
| **Tags** | enterprise, form-filling, government, HITL, compliance, automation |
| **Author/Organization** | Your Name / FormPilot Team |
| **Version** | 2.0.0 |
| **License** | MIT (or your choice) |

**USE THIS DESCRIPTION:**

```
Enterprise-grade multi-agent pipeline that automates government form filing.

WHAT IT DOES:
✅ Extracts identity from ID documents using Gemini 3 Flash Vision (94% accuracy)
✅ Validates government eligibility with 100+ deterministic compliance rules
✅ Maps extracted data to target form fields using semantic intelligence (89% accuracy)
✅ Generates professional, submission-ready PDFs
✅ Sends Slack notifications + uploads to SharePoint via Graph API
✅ Includes human-in-the-loop approval gates for eligibility failures

PERFORMANCE:
• Reduces 30–60 min manual filing to < 3 seconds
• 89% completion rate on 100 synthetic applications
• Handles: Aadhaar, Passport, PAN, Driving License
• Supports: India, USA, UK, Canada

INTEGRATIONS:
• Slack Block Kit for real-time notifications
• Microsoft SharePoint for document archival
• Google Gemini 3 Flash for vision + reasoning
• Playwright for browser automation
• SQLite for persistent audit trails

USE CASES:
• Government visa/passport applications
• HR onboarding & compliance
• Driver license & vehicle registration
• Business license applications
• Subsidy & grant applications

Track: Airia AI Agents Hackathon 2026 | Track 2: Active Agents
```

---

### **Step 6: Set Visibility to PUBLIC (1 minute)**

**Critical Step:**

1. Look for **"Visibility"** or **"Access Level"** dropdown
2. Select **"Public"** (NOT "Private" or "Unlisted")
3. This makes your agent visible in Airia Community
4. Without PUBLIC, it won't be findable by judges/users

**Options you might see:**
- ✅ **Public** ← SELECT THIS
- ⚠️ Private (only you can see)
- ⚠️ Unlisted (only with direct link)
- ⚠️ Draft (not published yet)

---

### **Step 7: Publish the Agent (1 minute)**

1. **Review everything** one more time:
   - ✅ YAML uploaded correctly
   - ✅ Environment variables set (at least GEMINI_API_KEY)
   - ✅ Description is complete
   - ✅ Visibility is set to **PUBLIC**
   - ✅ Tags are relevant

2. **Click "Publish"** (NOT "Save Draft")

3. **Wait for confirmation:**
   - Airia will validate and process
   - Should see: ✅ "Successfully published!"
   - Takes 10-30 seconds

---

### **Step 8: Copy Your Community URL (1 minute)**

**After publishing:**

1. Airia will show your **Agent Page** URL
2. Format: `https://community.airia.io/agents/formpilot-enterprise` (or similar)
3. **Copy this URL** (use Ctrl+C or click copy button)
4. **Save it** — you'll need this for DevPost!

**Verify the link works:**
1. Paste the URL in a new browser tab
2. You should see:
   - Agent name: "FormPilot Enterprise"
   - Description you just entered
   - Tags and metadata
   - "Run Agent" or "Try It" button

---

## ✅ VERIFICATION CHECKLIST

Before moving to DevPost, verify:

- [ ] Agent published successfully (no errors)
- [ ] Visibility is **PUBLIC**
- [ ] Community URL works (accessible in new tab)
- [ ] Description displays correctly
- [ ] Tags are visible
- [ ] YAML configuration loaded
- [ ] "Run Agent" or "Try It" button appears
- [ ] Community URL copied to clipboard

---

## 🔗 YOUR COMMUNITY URL

**Pattern:** `https://community.airia.io/agents/{your-agent-slug}`

**Example:** `https://community.airia.io/agents/formpilot-enterprise`

**Paste this URL in DevPost:**
- Field: "Airia Community URL"
- This proves your agent is published & public

---

## 🚨 TROUBLESHOOTING

### **"YAML validation failed"**
→ Check `airia_pipeline_config.yaml` syntax  
→ Ensure all required fields are present  
→ Copy the FULL file (don't skip sections)

### **"Environment variables required"**
→ Set **GEMINI_API_KEY** at minimum  
→ Get it from: https://makersuite.google.com  
→ Other variables (Slack, SharePoint) are optional

### **"Visibility won't change to Public"**
→ Check if you're in Draft mode (finish publishing first)  
→ Ensure your account has publish permissions  
→ Try refreshing the page

### **"Community URL not working"**
→ Wait 1-2 minutes after publishing (propagation delay)  
→ Verify visibility is PUBLIC (not Private)  
→ Check URL format is correct  
→ Try incognito/private browser window

### **"Agent doesn't appear in Community search"**
→ Wait 5-10 minutes for index refresh  
→ Verify tags are properly set  
→ Check if agent is Public visibility  
→ Try searching by exact name: "FormPilot Enterprise"

---

## 💡 PRO TIPS

1. **Test before publishing:**
   - Click "Preview" if available (shows how it will look)
   - Verify all sections render correctly

2. **After publishing:**
   - Join Airia Community to see your agent listed
   - Share the URL with judges/stakeholders
   - Monitor for any formatting issues

3. **For DevPost:**
   - You need this Community URL to complete submission
   - Keep the URL handy when filling DevPost form
   - Test the link one more time before submitting

4. **If you need to update:**
   - You can edit after publishing
   - Changes take 1-2 minutes to propagate
   - New version will still be at same Community URL

---

## 📊 WHAT HAPPENS AFTER PUBLISHING

✅ Your agent is now:
- **Public** on Airia Community
- **Discoverable** in agent marketplace
- **Ready** to be invoked by other agents or users
- **Ranked** in community leaderboard

✅ Judges can now:
- Find your submission
- View agent details
- Test the agent
- See your implementation

✅ You can now:
- Submit to DevPost with Community URL
- Track agent usage statistics
- Update/improve based on feedback
- Build reputation in community

---

## 📝 NEXT STEP: DEVPOST SUBMISSION

Once you have your Community URL:

1. Go to: https://devpost.com/software/formpilot-enterprise
2. Fill in DevPost form
3. Paste Community URL in the Airia field
4. Submit before deadline: **March 20, 2026, 9:15am GMT+5:30**

**DevPost fields that need Community URL:**
```
🔗 FORM FIELD: AIRIA COMMUNITY URL
https://community.airia.io/agents/formpilot-enterprise
```

---

## 🎯 SUCCESS CRITERIA

✅ **Published When:**
- Agent appears on Airia Community
- URL is public & accessible
- Community link works in DevPost

✅ **Ready for Judges When:**
- Agent is published (PUBLIC visibility)
- Community URL is in DevPost submission
- All 3 links work: YouTube + GitHub + Airia Community

---

## ⏰ TIME BREAKDOWN

| Task | Duration |
|------|----------|
| Access Airia + login | 1 min |
| Create new pipeline | 2 min |
| Upload YAML config | 2 min |
| Set env variables | 2 min |
| Configure publishing | 2 min |
| Set visibility to PUBLIC | 1 min |
| Publish agent | 1 min |
| Copy community URL | 1 min |
| **TOTAL** | **~10 minutes** |

---

**Ready? Head to https://app.airia.io and publish your agent! 🚀**

Good luck! Don't forget to copy that Community URL for DevPost! 🎉
