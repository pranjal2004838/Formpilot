# 🎥 FormPilot Demo Video Production Guide
## Complete Instructions for Screen Recording + Voiceover

**Deadline:** March 20, 2026, 9:15am GMT+5:30  
**Video Length:** 4:00 minutes (max)  
**Hosting:** YouTube or Vimeo (unlisted OK)  
**Status:** ✅ App is running on http://localhost:8000

---

## 🚀 QUICK START (Do This Now)

### Step 1: Verify App is Running
```bash
# Open browser and go to:
http://localhost:8000

# You should see the FormPilot landing page
# If not working, restart:
cd /workspaces/Formpilot
python backend/main.py
```

### Step 2: Download OBS Studio (Free Screen Recorder)
```
https://obsproject.com/download
Download for your OS (Windows/Mac/Linux)
Install and open
```

### Step 3: Configure OBS for Recording
1. Launch OBS Studio
2. **Sources panel (left):** Click "+" → "Display Capture" → select your screen
3. **Settings** → **Output** → **Recording**:
   - Recording Path: `/home/codespace/formpilot_demo.mp4`
   - Video Codec: H.264
   - Audio Codec: AAC
4. Start recording when ready

---

## 🎬 DETAILED SCREEN RECORDING FLOW

### **PREP (5 minutes)**
- [ ] Maximize browser window (1920x1080 or higher)
- [ ] Disable system notifications (so they don't pop up during recording)
- [ ] Clear browser tabs (only FormPilot showing)
- [ ] Open FormPilot in browser: http://localhost:8000
- [ ] Have script printed or on second monitor for reference

---

## 📺 SCENE-BY-SCENE RECORDING INSTRUCTIONS

### **Scene 1: The Home Page (0:00-0:15)**
**Script:** Opening hook about government form pain  
**Action:**
1. **Load** http://localhost:8000
2. **Wait 2 seconds** for page to fully load
3. **Slowly scroll down** to show hero section, tagline, and initial features
4. **Zoom level:** 100% (not zoomed in or out)
5. **Mouse:** Move cursor slowly toward features section (don't leave dark cursor trails)

**Key visuals to capture:**
- FormPilot logo
- "Enterprise-Grade AI Agent System" tagline
- Hero image or main illustration
- Top features (Airia orchestration, deterministic compliance, HITL governance)

**Duration:** Let page settle for 5 seconds before starting narration

---

### **Scene 2: Upload & Demo Section (0:15-0:35)**
**Script:** Pain + solution intro  
**Action:**
1. **Continue scrolling down** naturally to the "Try It" or demo section
2. **Show the demo controls:**
   - Document type dropdown (should show options: Aadhaar, Passport, PAN, Driving License, etc.)
   - Application type selector (Visa, Passport, Driver License, etc.)
   - Country selector (should default to India)
   - Upload area or demo button
3. **Hover over elements** to highlight them (buttons, inputs)
4. **Do NOT click anything yet** — just show the UI

**Key visuals:**
- "Upload your identity document" heading
- Form fields for document type, app type, country
- "🚀 Run Airia Pipeline" button
- Feature cards below

**Pacing:** Show each control, give voice narration time to explain

---

### **Scene 3: Full Features Grid (0:35-0:50)**
**Script:** Introducing FormPilot concept and 5-agent architecture  
**Action:**
1. **Continue scrolling** to the "Enterprise-Grade Capabilities" section
2. **Pause on each capability card:**
   - 🤖 Airia-Orchestrated Pipeline
   - 👤 Human-in-the-Loop (HITL)
   - 💬 Slack Block Kit Notifications
   - 📁 SharePoint Archival
   - 📊 Audit Trail & Governance
3. **Don't scroll too fast** — let camera linger 2-3 seconds on each

**Key visuals:**
- All 5+ capability cards visible
- Icons and descriptions for each
- Professional layout and design

---

### **Scene 4: Pipeline Architecture (0:50-1:10)**
**Script:** Detailed agent descriptions  
**Action:**
1. **Scroll down more** to find the agent pipeline diagram/visualization
   - If visible on home page: great, capture it
   - If not: go to `/api/docs` endpoint to show OpenAPI documentation
   - Or show the dashboard at http://localhost:8000/dashboard
2. **Point out the flow:**
   - Agent 1: Document Analyzer
   - Agent 2: Rules Validator
   - Agent 3: Field Mapper
   - Agent 4: PDF Generator
   - Agent 5: Browser Submitter
   - Flow: Document → Profile → Validation → Mapping → PDF → Submission

**Alternative if no diagram:**
1. Click "API Docs" link (if visible)
2. Show the `/api/workflows/start` endpoint
3. Demonstrate the request/response schema

---

### **Scene 5: Upload Interface (1:10-1:25)**
**Script:** Starting the demo workflow  
**Action:**
1. **Scroll back to the upload section**
2. **Show the controls clearly:**
   - Document Type dropdown (click to show options)
   - Country (should be "India")
   - Application Type (e.g., "Passport Visa Application")
3. **Exit dropdowns** without selecting (just for demonstration)
4. **Hover near the upload area** as if about to upload
5. **Do NOT upload yet**

**Key visuals:**
- Form UI is clear and functional
- Dropdowns are responsive
- Upload button is visible and ready to click

---

### **Scene 6: Run Demo Pipeline (1:25-1:45 & continuing through Scene 10)**
**Script:** Agent by agent execution  
**Action:**
1. **Click "🚀 Run Airia Pipeline"** button
   - If using real document: upload first, then click
   - If using demo mode: just click the button (it will run simulated pipeline)
2. **Wait for Agent 1 to run** (Document Analyzer)
   - Should show ~25% progress
   - Progress bar animates
   - Pipeline visualization shows Agent 1 active
3. **Do NOT interrupt**
4. **Let it continue** until you see results

**Expected behavior:**
- Workflow ID is generated
- Page shows "Step 1: Document Analyzer" with progress
- Real-time updates visible
- Agent steps animate sequentially

**What to capture:**
- Loading animation
- Progress bar movement (0% → 25%)
- Agent 1 card lights up
- Status message updates

---

### **Scene 7: Compliance Validation (1:45-2:05)**
**Script:** Agent 2 running compliance checks  
**Action:**
1. **Watch pipeline automatically progress** to Agent 2
2. **Show progress bar moving** to ~40%
3. **Show validation checks** appearing (if UI displays them)
   - Age check
   - Document validity check
   - State/country consistency check
4. **Pipeline UI should show** Agent 2 active/running

**Key visuals:**
- Progress: ~40%
- Agent 2 highlighted
- Validation results starting to appear

---

### **Scene 8: Field Mapping (2:05-2:25)**
**Script:** Agent 3 matching data to form fields  
**Action:**
1. **Let pipeline auto-progress** to Agent 3
2. **Progress bar** moves to ~60%
3. **Agent 3 card** becomes active
4. **Show mapping results** if displayed (field name → extracted value matches)

**Key visuals:**
- Progress: ~60%
- Agent 3 highlighted
- Mapping confidence scores visible

---

### **Scene 9: PDF Generation (2:25-2:45)**
**Script:** Agent 4 creating submission-ready PDF  
**Action:**
1. **Let pipeline continue** to Agent 4
2. **Progress bar** moves to ~80%
3. **Show Agent 4 running**
4. **Wait for PDF generation** to complete

**Key visuals:**
- Progress: ~80%
- Agent 4 highlighted
- PDF size/metadata might be displayed

---

### **Scene 10: Final Results (2:45-3:05)**
**Script:** Showing audit trail and complete results  
**Action:**
1. **Let pipeline finish** (100% complete)
2. **Scroll through the results section** showing:
   - **Extracted Profile:** Name, DOB, Gender, Address
   - **Validation Results:** Passed/Failed checks with details
   - **Form Mapping:** Matched fields with confidence scores
   - **Generated PDF:** Download button, file size
   - **Audit Trail:** Timestamped events (Agent 1 completed, Agent 2 validated, etc.)
3. **Scroll down slowly** so each section is visible for 3-5 seconds
4. **Maybe hover over PDF** or audit trail to emphasize detail

**Key visuals:**
- All results visible in one view (or multiple scrolls)
- Audit log entries timestamped
- PDF ready for download
- 100% completion

---

### **Scene 11: Slack Integration (3:05-3:25)**
**Script:** Explaining Slack HITL approval workflow  
**Action:**

**Option A (If Slack webhook configured):**
1. **Open Slack workspace** in another tab
2. **Point to HITL notification message** from FormPilot
3. **Show Approve/Reject buttons**
4. **Click Approve** (demonstrates the workflow resumes)

**Option B (If Slack not configured):**
1. **Scroll back to Results screen**
2. **Point to the "Integration Status" section** mentioning Slack
3. **Show a screenshot or mockup** of what the Slack card looks like
   - Can point to the README.md or AIRIA_INTEGRATION.md that has screenshots
   - Or go to `/dashboard` to see the UI description
4. **Narrate** how Slack integration works based on documentation

**Key visuals:**
- Slack notification card (or mockup)
- Interactive buttons visible
- Workflow pause/resume explained

---

### **Scene 12: Dashboard & Impact Metrics (3:25-3:50)**
**Script:** Bigger picture and business impact  
**Action:**
1. **Go to** http://localhost:8000/dashboard
   - Shows the interactive pipeline visualization for judges
2. **Or scroll to Compliance Dashboard section** on home page (if exists)
3. **Show:**
   - Pipeline metrics (completion rate, average time)
   - Benchmark data (89% success rate, 90 sec/app)
   - Number of workflows run
   - Capabilities overview

**Key visuals:**
- Professional dashboard UI
- Metrics and benchmarks
- Architecture diagram clear
- Enterprise-grade appearance

---

### **Scene 13: Closing (3:50-4:00)**
**Script:** Tagline and closing impact statement  
**Action:**
1. **Scroll back to top** of home page OR show final screenshot
2. **Show FormPilot branding** clearly
3. **Maybe show API documentation link** as credibility signal

**Voiceover over:**
- "This is FormPilot Enterprise..."
- "Built for enterprise compliance..."
- "This is the future of form automation."

**Ending visual:**
- FormPilot logo
- Or clean screenshot of the app
- Static image for 3-5 seconds while voiceover concludes

---

## 🎙️ VOICEOVER PRODUCTION (ElevenLabs)

### **How to Create Professional Audio:**

1. **Go to:** https://elevenlabs.io
2. **Sign up** (free tier available)
3. **Create new project**
4. **Copy-paste Scene 1 script** from voiceover script file into text box
5. **Select voice:** "Adam" or professional male/neutral voice
6. **Generate** (will take 30 seconds)
7. **Download as MP3**
8. **Repeat for all 13 scenes**

### **Pro Settings:**
- Voice: Professional & Calm (e.g., "Adam", "Chris", or "Bella")
- Speed: 1.0x (normal)
- Stability: 0.75 (natural variation)
- Clarity: 1.0 (crystal clear)

### **Organize Audio Files:**
```
formpilot_demo_audio/
├── 01_opening_hook.mp3
├── 02_pain_point.mp3
├── 03_meet_formpilot.mp3
├── 04_agents.mp3
├── 05_demo_begins.mp3
├── 06_agent_1.mp3
├── 07_agent_2.mp3
├── 08_agent_3.mp3
├── 09_agent_4.mp3
├── 10_results.mp3
├── 11_slack.mp3
├── 12_impact.mp3
└── 13_closing.mp3
```

---

## 🎞️ VIDEO EDITING (Combine Screen + Audio)

### **Recommended Free Tools:**
1. **DaVinci Resolve** (Professional, free)
2. **CapCut** (Easy, free)
3. **OpenShot** (Simple, free)

### **Basic Steps (Using DaVinci Resolve):**

1. **Import Screen Recording:**
   - File → Import Media → select `formpilot_demo.mp4`

2. **Import Audio Tracks:**
   - Drag all 13 MP3 files into timeline
   - Arrange in order with 0.5s gaps between them
   - Adjust volume if needed

3. **Add Title Slide (0:00-0:03):**
   - Create text: "FormPilot Enterprise"
   - Subtitle: "Automating Government Forms with AI Agents"
   - Duration: 3 seconds
   - Use professional font (Helvetica, Arial, or custom)

4. **Add Ending Slide (3:57-4:00):**
   - Text: "FormPilot Enterprise\n\nTrack 2: Active Agents\nAiria Hackathon 2026"
   - Duration: 3 seconds

5. **Export:**
   - Timeline → Export → MP4
   - Codec: H.264
   - Bitrate: 5000 Kbps (good quality)
   - Resolution: 1920x1080
   - Frame rate: 30 fps
   - Output: `formpilot_demo_final.mp4`

---

## 📤 UPLOADING TO YOUTUBE

### **Step 1: Go to YouTube**
1. https://youtube.com
2. Click your avatar → "Create a video"
3. Click "Upload video"

### **Step 2: Upload File**
1. **Select file:** `formpilot_demo_final.mp4`
2. **Wait for upload** (may take 5-10 min for 4MB video at 1080p)

### **Step 3: Fill in Details**
- **Title:** FormPilot Enterprise | Track 2: Active Agents | Airia Hackathon 2026
- **Description:**
  ```
  FormPilot automates government form filing using orchestrated AI agents.
  
  PROBLEM:
  Government forms take 4-6 hours per application. Millions of people suffer through bureaucratic processes every year.
  
  SOLUTION:
  A production-grade multi-agent system that:
  • Agent 1: Extracts identity from government documents (Aadhaar, Passport, PAN)
  • Agent 2: Validates eligibility using 100+ deterministic compliance rules
  • Agent 3: Maps extracted data to form fields with semantic intelligence
  • Agent 4: Generates submission-ready PDFs
  • Agent 5: Posts directly to government portals with human approval gates
  
  IMPACT:
  • 90 seconds per application (vs 4-6 hours)
  • 23.75 hours saved per 5 applications
  • $400+ value per person per year
  • $500M+ market opportunity for government form automation
  
  KEY FEATURES:
  ✅ Deterministic compliance (no AI hallucinations)
  ✅ Human-in-the-loop governance (Slack approval gates)
  ✅ Complete audit trail (enterprise-grade accountability)
  ✅ Multi-system integration (Slack, SharePoint, browser automation)
  ✅ Production-grade code quality & error handling
  
  TECH STACK:
  - FastAPI + Python
  - Gemini 2.0 Flash Vision
  - Deterministic rule engine
  - SQLite persistent audit trail
  - Slack Block Kit
  - SharePoint integration
  - Playwright browser automation
  
  LINKS:
  GitHub: https://github.com/pranjal2004838/Formpilot
  Airia Community: [INSERT COMMUNITY LINK AFTER PUBLISHING]
  
  Track: Airia AI Agents Hackathon 2026 | Track 2: Active Agents
  ```
- **Visibility:** Unlisted (only people with link can view)
- **Click "Next"** to continue

### **Step 4: Settings**
- **Visibility:** Unlisted ✅
- **Comments:** Allowed
- **License:** Standard YouTube license
- **Click "Publish"**

### **Step 5: Copy the Video URL**
```
https://www.youtube.com/watch?v=XXXXXXXXXXXX
```
- Use this URL in your DevPost submission

---

## ✅ FINAL CHECKLIST

Before submitting to DevPost:

- [ ] **Video recorded** (4:00 min max)
- [ ] **Voiceover added** (all 13 scenes with ElevenLabs)
- [ ] **Video uploaded to YouTube (unlisted)**
- [ ] **YouTube URL copied**
- [ ] **Video plays smoothly** (test the link)
- [ ] **Audio is clear** (no background noise)
- [ ] **Screen is 1080p or higher**
- [ ] **All agent steps visible** in recording
- [ ] **Results section clearly shown**
- [ ] **DevPost description written** using provided copy
- [ ] **GitHub repo link ready**
- [ ] **Airia Community link ready** (after publishing agent)

---

## 🚨 TROUBLESHOOTING

**Video looks pixelated:**
→ Ensure you recorded at 1920x1080 or higher

**Audio out of sync with video:**
→ Re-export from your video editor

**App shows error during recording:**
→ This is normal with simulated mode (no GEMINI_API_KEY)
→ Just click through, the demo still works

**Missing screenshots/results:**
→ Make sure pipeline completes (watch for 100% progress)
→ Let workflow finish before scrolling

**Slack integration didn't show:**
→ That's OK — use Option B (show mockup or documentation)
→ Judges understand Slack is optional for hack week

---

## 💡 PRO RECORDING TIPS

1. **Use a second monitor** for your script (so you don't look at text on screen)
2. **Record during off-hours** (less system lag)
3. **Disable screen saver** before recording
4. **Use OBS at native resolution** (don't scale)
5. **Test audio levels** before full recording (click in OBS mixer)
6. **Record full pipeline run once, then edit** (don't try to get it perfect in one take)

---

**You've got this! The app is ready, the script is ready—just press record.** 🚀

Good luck with your hackathon submission!
