# Running the Platform on a Chromebook

This guide walks you through every step to get the Job Application Platform
running on your Chromebook. No programming experience needed.

---

## Step 1 — Enable Linux on your Chromebook

Chromebooks have a built-in Linux environment (called "Crostini") that lets
you run real applications. Here's how to turn it on:

1. Click the **clock** in the bottom-right corner of your screen
2. Click the **gear icon** (Settings)
3. Scroll down and click **"Advanced"**
4. Click **"Developers"**
5. Next to "Linux development environment", click **"Turn on"**
6. Follow the on-screen prompts — it takes about 5 minutes to set up
7. When it finishes, a **Terminal** window will open automatically

> **Note:** If you don't see "Developers" in Settings, your Chromebook might be
> on an older version. Go to Settings → About Chrome OS → Check for updates first.

---

## Step 2 — Open the Terminal

- Press the **Search key** (the circle key where Caps Lock usually is)
- Type **"Terminal"** and press Enter
- Or: look for **"Terminal"** in your app launcher (bottom shelf)

You'll see a black window with a command prompt. This is where you'll type commands.

---

## Step 3 — Download the platform

Type this command and press Enter (copy-paste works with Ctrl+Shift+V):

```bash
git clone https://github.com/Nicodagoat/Job-applicaions.git
```

Then navigate into the project folder:

```bash
cd Job-applicaions/job-automation
```

---

## Step 4 — Run the setup script

This single command installs everything automatically:

```bash
bash setup.sh
```

**What it does:**
- Installs Python and all required packages
- Downloads a web browser for automation (Chromium, ~130MB)
- Creates the database
- Checks which AI providers are available
- Creates your configuration file

This takes about **5-10 minutes** on the first run. You'll see progress messages.

At the end it will show you which AI providers are ready and what to do next.

---

## Step 5 — Set up free AI (for cover letter writing)

You need at least one AI provider. Pick the easier option for you:

### Option A — Groq (easiest, no installation)
Works entirely in the cloud. Takes 2 minutes to set up.

1. Go to **https://console.groq.com** in your Chromebook browser
2. Click "Sign Up" — use your Google account to sign in (one click)
3. Click "API Keys" in the left menu
4. Click "Create API Key" — give it any name, e.g. "job-platform"
5. **Copy the key** (starts with `gsk_`)
6. Open the config file in the Terminal:
   ```bash
   nano config/.env
   ```
7. Find the line that says `GROQ_API_KEY=` and paste your key after it:
   ```
   GROQ_API_KEY=gsk_your_key_here
   ```
8. Press **Ctrl+X**, then **Y**, then **Enter** to save

### Option B — Ollama (fully private, runs on your Chromebook)
Runs the AI entirely on your machine — nothing leaves your computer.
Best if you have a newer Chromebook with 8GB+ RAM.

1. In your Terminal, run:
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```
2. Download the AI model (this takes a few minutes, ~4GB):
   ```bash
   ollama pull llama3.1
   ```
3. That's it — Ollama starts automatically in the background

---

## Step 6 — Get more job listings (optional but recommended)

Two completely free API keys unlock significantly more job listings:

### Adzuna (UK + Europe — very comprehensive)
1. Go to **https://developer.adzuna.com/**
2. Click "Register" → fill in your name/email → verify email
3. Go to your dashboard → copy **App ID** and **App Key**
4. Add to `config/.env`:
   ```
   ADZUNA_APP_ID=your_app_id
   ADZUNA_APP_KEY=your_app_key
   ```

### Reed.co.uk (UK's largest job board)
1. Go to **https://www.reed.co.uk/developers/jobseeker**
2. Click "Register" → sign up with email
3. Your API key will be shown on the page
4. Add to `config/.env`:
   ```
   REED_API_KEY=your_key
   ```

> **Without these keys:** The platform still works! Arbeitnow and Remotive
> are completely free and will find sustainability/ESG jobs across Europe.

---

## Step 7 — Set up Telegram notifications (optional)

Get alerts on your phone when new jobs match your profile.

1. Open **Telegram** on your phone
2. Search for `@BotFather` and start a chat
3. Send the message: `/newbot`
4. Follow the prompts — give your bot any name (e.g. "My Job Bot")
5. BotFather will give you a **token** like: `1234567890:ABCdefGHI...`
6. Copy it to `config/.env`:
   ```
   TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHI...
   ```
7. Now start a chat with your new bot on Telegram (search for its name)
8. In your Terminal, run:
   ```bash
   curl "https://api.telegram.org/bot1234567890:ABCdefGHI.../getUpdates"
   ```
   Replace the token with yours.
9. Find the number after `"id":` in the output — that's your chat ID
10. Add it to `config/.env`:
    ```
    TELEGRAM_CHAT_ID=123456789
    ```
11. Test it works:
    ```bash
    source .venv/bin/activate
    python run.py notify-test
    ```

---

## Step 8 — Start the platform

Every time you want to use the platform, run:

```bash
bash start.sh
```

This will:
1. Start the backend server
2. Open the dashboard in your Chromebook's Chrome browser automatically

If the browser doesn't open automatically, open Chrome and go to:
**http://localhost:3000**

---

## Daily use — how it saves you time

### Finding jobs
1. Click **Scraper** in the sidebar
2. Click **"Live Run"** — the platform searches LinkedIn, Arbeitnow, Reed, and more
3. It automatically filters out:
   - Italian jobs
   - Roles below your match score threshold (65% default)
   - **Jobs that are already closed** (validated in real-time)
4. Wait 1-2 minutes, then click **Job Matches**

### Reviewing matches
- Jobs are scored by how well they match your profile (0-100%)
- Green "✓ Open" badge = job URL has been verified as still active
- ESG badge = sustainability-relevant role
- Click any job title to open it on the source website

### Applying in one click
1. Click **"✍ Apply"** next to any open job
2. The platform:
   - Reads the job description
   - Selects the best CV from your collection
   - Writes a tailored cover letter using your profile data
3. **Review the letter** (edit if you want)
4. Click **"✓ Approve & Create Application"**
5. The application is saved with status "Pending approval"

### Before actually submitting
When you're ready to actually send applications:
1. Go to `config/settings.yaml`
2. Change `dry_run: true` to `dry_run: false`
3. Go to **Applications** → click **"Approve"** on each one you want to send
4. The platform will attempt to auto-fill and submit the form

---

## Troubleshooting on Chromebook

### "Command not found: python3"
```bash
sudo apt-get install python3 python3-pip python3-venv
```

### "bash setup.sh: Permission denied"
```bash
chmod +x setup.sh start.sh
bash setup.sh
```

### Browser doesn't open automatically
Open Chrome and go to: `http://localhost:3000`

### Platform won't start / port already in use
```bash
# Kill any processes using port 8000 or 3000
fuser -k 8000/tcp 2>/dev/null; fuser -k 3000/tcp 2>/dev/null
bash start.sh
```

### Ollama runs out of memory (older Chromebooks)
Use Groq instead (Option A in Step 5). Groq runs in the cloud and
uses no local memory.

### The scraper finds 0 jobs
1. Check your internet connection
2. Run: `bash start.sh` and open http://localhost:8000/docs
3. Try the `/api/scraper/run` endpoint with `dry_run=true` to see logs
4. Check `logs/app.log` for error messages

### Stop the platform
Press **Ctrl+C** in the Terminal window where you ran `bash start.sh`

---

## Updating the platform

When new features are released:
```bash
git pull origin claude/job-application-platform-Kj9zi
source .venv/bin/activate
pip install -r requirements.txt
python run.py init-db
```

---

## Privacy and security

- **Your CV and documents** are stored only on your Chromebook (in `documents/`)
- **The database** (`database/jobs.db`) is local — never uploaded anywhere
- **AI requests** via Groq send only the job description and your profile text
- **Ollama** is 100% local — nothing leaves your Chromebook
- **API keys** in `config/.env` are never committed to Git
