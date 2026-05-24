<div align="center">

# 🛡️ GuardianBot

### *ᴛʜᴇ ᴡᴏʀʟᴅ'ꜱ ᴍᴏꜱᴛ ᴀᴅᴠᴀɴᴄᴇᴅ ᴛᴇʟᴇɢʀᴀᴍ ɢʀᴏᴜᴘ ᴍᴀɴᴀɢᴇᴍᴇɴᴛ ʙᴏᴛ*

<br/>

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-v20-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)](https://python-telegram-bot.org)
[![MongoDB](https://img.shields.io/badge/MongoDB-Motor%203.3-47A248?style=for-the-badge&logo=mongodb&logoColor=white)](https://mongodb.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

[![Deploy on Railway](https://img.shields.io/badge/Deploy%20on-Railway-0B0D0E?style=for-the-badge&logo=railway&logoColor=white)](https://railway.app)
[![Deploy to Render](https://img.shields.io/badge/Deploy%20to-Render-46E3B7?style=for-the-badge&logo=render&logoColor=white)](https://render.com)
[![Stars](https://img.shields.io/github/stars/yourusername/guardianbot?style=for-the-badge&color=FFD700&logo=github)](https://github.com/yourusername/guardianbot/stargazers)
[![Forks](https://img.shields.io/github/forks/yourusername/guardianbot?style=for-the-badge&color=silver&logo=github)](https://github.com/yourusername/guardianbot/network/members)

<br/>

> **GuardianBot** is a production-grade, fully async Telegram group management bot built with
> `python-telegram-bot v20`, `Motor` (async MongoDB), and modern Python 3.11 patterns.
> It protects your communities with an iron fist — and a velvet glove.

<br/>

```
  ██████╗ ██╗   ██╗ █████╗ ██████╗ ██████╗ ██╗ █████╗ ███╗   ██╗
 ██╔════╝ ██║   ██║██╔══██╗██╔══██╗██╔══██╗██║██╔══██╗████╗  ██║
 ██║  ███╗██║   ██║███████║██████╔╝██║  ██║██║███████║██╔██╗ ██║
 ██║   ██║██║   ██║██╔══██║██╔══██╗██║  ██║██║██╔══██║██║╚██╗██║
 ╚██████╔╝╚██████╔╝██║  ██║██║  ██║██████╔╝██║██║  ██║██║ ╚████║
  ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝
            ʙ ᴏ ᴛ  —  ɢ ʀ ᴏ ᴜ ᴘ  ᴍ ᴀ ɴ ᴀ ɢ ᴇ ᴍ ᴇ ɴ ᴛ  ʀ ᴇ ᴅ ᴇ ꜰ ɪ ɴ ᴇ ᴅ
```

</div>

---

## 📋 Table of Contents

- [✨ Features](#-features)
- [⚡ Commands Reference](#-commands-reference)
- [🚀 Quick Deploy](#-quick-deploy)
  - [🚂 Railway](#-deploy-on-railway)
  - [🌐 Render](#-deploy-on-render)
  - [🐋 Docker](#-deploy-with-docker)
  - [🖥️ Self-Host](#️-self-host-vps)
- [🔧 Environment Variables](#-environment-variables)
- [📖 Setup Guide](#-setup-guide)
- [🏗️ Architecture](#️-architecture)
- [🤝 Contributing](#-contributing)
- [📜 License](#-license)
- [💎 Credits](#-credits)

---

## ✨ Features

> GuardianBot ships with **16 powerful modules** covering every aspect of community management.

<div align="center">

| 🛡️ Feature | 📝 Description |
|:---:|:---|
| **🔨 Bans** | Permanently ban or unban users with optional reason logging. Supports ban by reply, username, or user ID. Full audit trail in log channel. |
| **🔇 Mutes** | Temporarily or permanently restrict users from sending messages. Timed mutes with auto-unmute. Rich reason support. |
| **⚠️ Warns** | Multi-level warning system with configurable limits. Auto-action (ban/kick/mute) on limit reached. Full warn history per user per group. |
| **👋 Welcome** | Fully customizable welcome & farewell messages. Supports HTML/Markdown, buttons, media. Per-group personalization with `{mention}`, `{first}`, `{count}` placeholders. |
| **🔍 Filters** | Keyword-triggered auto-responses. Supports text, buttons, stickers, media. Regex support. Perfect for FAQ automation. |
| **📝 Notes** | Save and retrieve text snippets, media, and buttons with `#notename` hashtag syntax. Global and per-group notes. |
| **🔒 Locks** | Lock specific message types: stickers, GIFs, links, forwards, polls, games, and more. Fine-grained control over what members can send. |
| **🌊 Anti-Flood** | Intelligent flood detection with configurable message limits and time windows. Automatically mutes or kicks flood offenders. |
| **🚫 Blocklist** | Word/phrase blacklist with automatic deletion and optional action. Supports wildcards and regex patterns. |
| **🚨 Reports** | `@admin` report system that pings all admins instantly. Full report log with message context forwarded to log channel. |
| **📌 Pins** | Pin and unpin messages with optional notification control. Preserves pin history. |
| **🗑️ Purge** | Bulk delete messages by count or range. Admin-only with confirmation. Cleans up spam in seconds. |
| **📜 Rules** | Set, display, and manage group rules. Inline button on join for new members to acknowledge rules. |
| **🌐 Federation** | Cross-group banning network. Fed-ban a user once to ban them across all groups in your federation. |
| **👑 Admin Tools** | Promote, demote, transfer ownership tools. Admin cache management. Bulk action utilities. |
| **📊 Stats** | Real-time group statistics: member count, message frequency, top users, admin list, and bot info. |

</div>

---

## ⚡ Commands Reference

### 🔨 Ban & Kick Commands

| Command | Description | Permission |
|:---|:---|:---:|
| `/ban [reason]` | Ban a user (reply or mention) | Admin |
| `/unban` | Unban a previously banned user | Admin |
| `/tban <time> [reason]` | Temporarily ban a user (e.g. `1h`, `2d`, `30m`) | Admin |
| `/kick [reason]` | Kick a user from the group | Admin |
| `/dban [reason]` | Ban a user and delete their last message | Admin |
| `/sban [reason]` | Silently ban without notification | Admin |

### 🔇 Mute Commands

| Command | Description | Permission |
|:---|:---|:---:|
| `/mute [reason]` | Permanently mute a user | Admin |
| `/unmute` | Remove mute restriction | Admin |
| `/tmute <time> [reason]` | Temporarily mute (e.g. `1h`, `30m`) | Admin |
| `/dmute [reason]` | Mute and delete triggering message | Admin |

### ⚠️ Warn Commands

| Command | Description | Permission |
|:---|:---|:---:|
| `/warn [reason]` | Issue a warning to a user | Admin |
| `/unwarn` | Remove the most recent warning | Admin |
| `/resetwarn` | Reset all warnings for a user | Admin |
| `/warns` | View all warnings for a user | Admin |
| `/warnlimit <number>` | Set warn limit (default: 3) | Admin |
| `/warnaction <ban\|kick\|mute>` | Set action when limit reached | Admin |

### 👋 Welcome Commands

| Command | Description | Permission |
|:---|:---|:---:|
| `/setwelcome <message>` | Set a custom welcome message | Admin |
| `/setfarewell <message>` | Set a custom goodbye message | Admin |
| `/resetwelcome` | Reset to default welcome | Admin |
| `/resetfarewell` | Reset to default farewell | Admin |
| `/welcome on\|off` | Toggle welcome messages | Admin |
| `/cleanwelcome on\|off` | Auto-delete previous welcome | Admin |

### 🔍 Filter Commands

| Command | Description | Permission |
|:---|:---|:---:|
| `/filter <keyword> <response>` | Add a new auto-filter | Admin |
| `/stop <keyword>` | Remove a filter | Admin |
| `/filters` | List all active filters | Member |

### 📝 Notes Commands

| Command | Description | Permission |
|:---|:---|:---:|
| `/save <notename> <content>` | Save a note | Admin |
| `/get <notename>` or `#notename` | Retrieve a note | Member |
| `/clear <notename>` | Delete a note | Admin |
| `/notes` | List all saved notes | Member |

### 🔒 Lock Commands

| Command | Description | Permission |
|:---|:---|:---:|
| `/lock <type>` | Lock a message type | Admin |
| `/unlock <type>` | Unlock a message type | Admin |
| `/locktypes` | List all lockable types | Member |
| `/locks` | View current lock status | Admin |

**Lock types:** `sticker`, `audio`, `voice`, `document`, `video`, `videonote`, `photo`, `gif`, `url`, `bots`, `forward`, `game`, `poll`, `inline`, `all`

### 🌊 Anti-Flood Commands

| Command | Description | Permission |
|:---|:---|:---:|
| `/setflood <number>` | Set flood message limit | Admin |
| `/setfloodtime <seconds>` | Set flood time window | Admin |
| `/flood` | View current flood settings | Admin |
| `/flood off` | Disable anti-flood | Admin |

### 🚫 Blocklist Commands

| Command | Description | Permission |
|:---|:---|:---:|
| `/addblacklist <word>` | Add word to blocklist | Admin |
| `/rmblacklist <word>` | Remove word from blocklist | Admin |
| `/blacklist` | View current blocklist | Admin |
| `/blacklistaction <ban\|kick\|mute\|del>` | Set blocklist action | Admin |

### 📌 Pin & Purge Commands

| Command | Description | Permission |
|:---|:---|:---:|
| `/pin` | Pin the replied-to message | Admin |
| `/unpin` | Unpin the current pinned message | Admin |
| `/unpinall` | Unpin all messages | Admin |
| `/purge` | Purge from replied message to current | Admin |
| `/purge <number>` | Delete last N messages | Admin |
| `/del` | Delete a single message | Admin |

### 📜 Rules Commands

| Command | Description | Permission |
|:---|:---|:---:|
| `/setrules <rules>` | Set group rules | Admin |
| `/rules` | Display the group rules | Member |
| `/clearrules` | Clear group rules | Admin |

### 🌐 Federation Commands

| Command | Description | Permission |
|:---|:---|:---:|
| `/newfed <name>` | Create a new federation | Owner |
| `/joinfed <fed_id>` | Join an existing federation | Admin |
| `/leavefed` | Leave the current federation | Admin |
| `/fedban [reason]` | Ban user across federation | Fed Admin |
| `/unfedban` | Unban user from federation | Fed Admin |
| `/fedbans` | List all federation bans | Fed Admin |
| `/fedinfo` | View federation information | Member |

### 👑 Admin & Utility Commands

| Command | Description | Permission |
|:---|:---|:---:|
| `/promote [title]` | Promote a user to admin | Admin |
| `/demote` | Demote an admin | Admin |
| `/title <title>` | Set admin title | Admin |
| `/admins` | List all group admins | Member |
| `/stats` | View group statistics | Member |
| `/id` | Get user/chat ID | Member |
| `/info` | Get detailed user information | Admin |
| `/report` | Report a user to admins | Member |
| `/start` | Start the bot / show help | Member |
| `/help [module]` | Show help for a module | Member |

---

## 🚀 Quick Deploy

### 🚂 Deploy on Railway

> **Railway** is the recommended deployment platform — one-click deploy, automatic HTTPS, and generous free tier.

<div align="center">

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template)

</div>

**Step-by-step:**

1. **Click** the "Deploy on Railway" button above
2. **Sign in** with your GitHub account at [railway.app](https://railway.app)
3. **Fork** this repository to your GitHub account
4. In Railway dashboard, click **"New Project"** → **"Deploy from GitHub repo"**
5. Select your forked `guardianbot` repository
6. Railway auto-detects the `Dockerfile` — confirm the build settings
7. Go to **"Variables"** tab and add all [required environment variables](#-environment-variables)
8. Click **"Deploy"** — Railway builds and launches your bot!
9. Check **"Logs"** to confirm `✅ ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ is ᴏɴʟɪɴᴇ` appears

> 💡 **Tip:** Railway automatically redeploys when you push to your main branch.

---

### 🌐 Deploy on Render

> **Render** offers a free tier with zero-downtime deploys and automatic SSL.

<div align="center">

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

</div>

**Step-by-step:**

1. **Fork** this repository to your GitHub account
2. Go to [render.com](https://render.com) and create a free account
3. Click **"New +"** → **"Web Service"**
4. Connect your GitHub and select the `guardianbot` repository
5. Render detects `render.yaml` automatically — click **"Apply"**
6. In the **"Environment"** section, fill in your secret variables:
   - `BOT_TOKEN`, `MONGO_URI`, `LOG_CHANNEL_ID`, `OWNER_ID`
7. Click **"Create Web Service"** and wait for the build to finish
8. Monitor **"Logs"** tab for the startup confirmation message

> ⚠️ **Note:** Render's free tier may spin down after 15 minutes of inactivity. Consider the `Starter` plan for 24/7 uptime.

---

### 🐋 Deploy with Docker

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/guardianbot.git
cd guardianbot

# 2. Copy and configure environment
cp .env.example .env
nano .env   # Fill in your values

# 3. Build the Docker image
docker build -t guardianbot:latest .

# 4. Run the container
docker run -d \
  --name guardianbot \
  --restart unless-stopped \
  --env-file .env \
  guardianbot:latest

# 5. View logs
docker logs -f guardianbot
```

**Using Docker Compose:**

```yaml
# docker-compose.yml
version: '3.9'

services:
  guardianbot:
    build: .
    container_name: guardianbot
    restart: unless-stopped
    env_file:
      - .env
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

```bash
docker-compose up -d
docker-compose logs -f
```

---

### 🖥️ Self-Host (VPS)

```bash
# 1. Clone repository
git clone https://github.com/yourusername/guardianbot.git
cd guardianbot

# 2. Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# OR: .venv\Scripts\activate  # Windows

# 3. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
nano .env  # Fill in your values

# 5. Run the bot
python -m bot

# 6. (Optional) Run as systemd service for auto-start
sudo nano /etc/systemd/system/guardianbot.service
```

```ini
[Unit]
Description=GuardianBot - Telegram Group Management Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/guardianbot
ExecStart=/home/ubuntu/guardianbot/.venv/bin/python -m bot
Restart=always
RestartSec=10
EnvironmentFile=/home/ubuntu/guardianbot/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable guardianbot
sudo systemctl start guardianbot
sudo systemctl status guardianbot
```

---

## 🔧 Environment Variables

| Variable | Required | Default | Description |
|:---|:---:|:---:|:---|
| `BOT_TOKEN` | ✅ Yes | — | Telegram Bot Token from [@BotFather](https://t.me/BotFather) |
| `MONGO_URI` | ✅ Yes | — | MongoDB connection string (Atlas or self-hosted) |
| `LOG_CHANNEL_ID` | ✅ Yes | — | Private channel ID for logging all actions |
| `OWNER_ID` | ✅ Yes | — | Your Telegram numeric user ID |
| `BOT_NAME` | ❌ No | `GuardianBot` | Display name shown in messages |
| `BOT_USERNAME` | ❌ No | — | Bot username without `@` |
| `SUDO_USERS` | ❌ No | — | Comma-separated super-admin user IDs |
| `WARN_LIMIT` | ❌ No | `3` | Warnings before auto-action triggers |
| `WARN_ACTION` | ❌ No | `ban` | Action on warn limit: `ban`, `kick`, or `mute` |
| `WARN_MUTE_DURATION` | ❌ No | `60` | Mute duration (minutes) if warn action is mute |
| `FLOOD_LIMIT` | ❌ No | `5` | Max messages in flood window |
| `FLOOD_TIME` | ❌ No | `5` | Flood detection window (seconds) |
| `DB_NAME` | ❌ No | `guardianbot` | MongoDB database name |
| `CACHE_TTL` | ❌ No | `300` | Settings cache TTL in seconds |
| `DELETE_COMMANDS` | ❌ No | `false` | Auto-delete command messages |
| `DELETE_DELAY` | ❌ No | `5` | Seconds before deleting commands |

---

## 📖 Setup Guide

### Step 1 — Create Your Bot via @BotFather

1. Open Telegram and search for **[@BotFather](https://t.me/BotFather)**
2. Send `/newbot` and follow the prompts
3. Choose a name: e.g. **GuardianBot**
4. Choose a username: e.g. **@MyGuardianBot** (must end in `bot`)
5. **Copy the token** — it looks like `1234567890:ABCDefGHIjklMNOpqrsTUVwxYZ`
6. Also send `/setprivacy` → select your bot → choose **Disable** (so it can read all messages)
7. Send `/setcommands` and paste the command list for better UX

```
ban - Ban a user
unban - Unban a user  
kick - Kick a user
mute - Mute a user
unmute - Unmute a user
warn - Warn a user
warns - View user warnings
pin - Pin a message
purge - Purge messages
rules - Show group rules
filters - Show active filters
notes - Show saved notes
admins - List admins
stats - Group statistics
help - Show help
```

---

### Step 2 — Set Up MongoDB Atlas (Free)

1. Go to **[cloud.mongodb.com](https://cloud.mongodb.com)** and create a free account
2. Click **"Build a Database"** → Select **"M0 FREE"** tier
3. Choose your preferred cloud provider and region → Click **"Create"**
4. **Set up Authentication:**
   - Username: `guardianbot`
   - Password: generate a secure password and save it
   - Click **"Create User"**
5. **Set up Network Access:**
   - Click **"Network Access"** → **"Add IP Address"**
   - Select **"Allow access from anywhere"** (`0.0.0.0/0`)
   - Click **"Confirm"**
6. **Get your connection string:**
   - Click **"Connect"** → **"Drivers"**
   - Select **Python** and version **3.12 or later**
   - Copy the connection string — it looks like:
     ```
     mongodb+srv://guardianbot:<password>@cluster0.xxxxx.mongodb.net/
     ```
   - Replace `<password>` with your actual password

---

### Step 3 — Create Private Log Channel

1. In Telegram, click the ✏️ compose button → **"New Channel"**
2. Name it something like `GuardianBot Logs`
3. Set it to **Private**
4. Add your bot as an **Administrator** with all permissions
5. Forward any message from the channel to **[@userinfobot](https://t.me/userinfobot)**
6. The bot will reply with the channel ID — it starts with `-100` followed by numbers
7. This is your `LOG_CHANNEL_ID`

---

### Step 4 — Get Your Telegram User ID

1. Open [@userinfobot](https://t.me/userinfobot) on Telegram
2. Send `/start`
3. The bot replies with your numeric user ID (e.g. `123456789`)
4. This is your `OWNER_ID`

---

### Step 5 — Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` with your values:

```env
BOT_TOKEN=1234567890:ABCDefGHIjklMNOpqrsTUVwxYZ
MONGO_URI=mongodb+srv://guardianbot:yourpassword@cluster0.xxxxx.mongodb.net/
LOG_CHANNEL_ID=-1001234567890
OWNER_ID=123456789
BOT_NAME=GuardianBot
WARN_LIMIT=3
```

---

### Step 6 — Add Bot to Your Group

1. Open your Telegram group
2. Click the group name → **"Add Members"**
3. Search for your bot's username
4. Add it to the group
5. **Make the bot an Administrator** with these permissions:
   - ✅ Delete messages
   - ✅ Ban users
   - ✅ Restrict members
   - ✅ Pin messages
   - ✅ Add new admins (optional, for `/promote`)
6. Send `/start` in the group — GuardianBot is live! 🎉

---

## 🏗️ Architecture

```mermaid
graph TB
    subgraph Users["👥 Telegram Users"]
        U1[Group Members]
        U2[Group Admins]
        U3[Bot Owner]
    end

    subgraph Telegram["📱 Telegram Platform"]
        TG[Telegram API<br/>api.telegram.org]
        GRP[Group Chats]
        LOG[Log Channel]
    end

    subgraph Bot["🤖 GuardianBot Server"]
        direction TB
        MAIN[bot/__main__.py<br/>Entry Point]
        APP[Application<br/>PTB v20 Async]
        subgraph Handlers["📦 Handler Modules"]
            H1[🔨 Ban/Kick/Mute]
            H2[⚠️ Warns]
            H3[👋 Welcome]
            H4[🔍 Filters]
            H5[📝 Notes]
            H6[🔒 Locks]
            H7[🌊 Anti-Flood]
            H8[🚫 Blocklist]
            H9[📌 Pin/Purge]
            H10[🌐 Federation]
        end
        CACHE[⚡ In-Memory Cache<br/>cachetools]
        CONFIG[⚙️ Config<br/>python-dotenv]
    end

    subgraph DB["🗄️ MongoDB Atlas"]
        COL1[(groups)]
        COL2[(users)]
        COL3[(warns)]
        COL4[(filters)]
        COL5[(notes)]
        COL6[(federations)]
    end

    U1 & U2 & U3 -->|Send messages & commands| GRP
    GRP <-->|Webhook / Long Polling| TG
    TG <-->|Updates| APP
    APP --> MAIN
    MAIN --> Handlers
    Handlers <-->|Async Read/Write| DB
    Handlers -->|Log actions| LOG
    Handlers <-->|Cache settings| CACHE
    CONFIG -->|Environment vars| APP

    style Bot fill:#1a1a2e,stroke:#26A5E4,color:#fff
    style DB fill:#0d3b2e,stroke:#47A248,color:#fff
    style Telegram fill:#1a2744,stroke:#26A5E4,color:#fff
    style Users fill:#2d1b33,stroke:#9B59B6,color:#fff
```

### 📁 Project Structure

```
guardianbot/
├── 📄 bot/
│   ├── __init__.py          # Package init
│   ├── __main__.py          # Entry point — builds Application
│   ├── config.py            # Configuration loader
│   ├── database/
│   │   ├── __init__.py
│   │   ├── mongodb.py       # Motor async client & collections
│   │   └── models.py        # Data models / schema helpers
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── admin.py         # Ban, kick, mute, promote, demote
│   │   ├── warns.py         # Warning system
│   │   ├── welcome.py       # Welcome / farewell messages
│   │   ├── filters.py       # Auto-filter triggers
│   │   ├── notes.py         # Notes save/retrieve
│   │   ├── locks.py         # Message type locks
│   │   ├── antiflood.py     # Flood detection & action
│   │   ├── blocklist.py     # Word/phrase blacklist
│   │   ├── pins.py          # Pin/unpin messages
│   │   ├── purge.py         # Bulk message deletion
│   │   ├── rules.py         # Group rules
│   │   ├── federation.py    # Cross-group federation bans
│   │   ├── reports.py       # @admin report system
│   │   └── stats.py         # Group & user statistics
│   └── utils/
│       ├── __init__.py
│       ├── decorators.py    # @admin_only, @owner_only etc.
│       ├── formatting.py    # Unicode small caps & message helpers
│       ├── cache.py         # Cachetools wrapper
│       └── time_parser.py   # Parse "1h30m" duration strings
├── 🐋 Dockerfile
├── 📦 requirements.txt
├── ⚙️ .env.example
├── 🚂 railway.toml
├── 🌐 render.yaml
├── 📋 Procfile
├── 🐍 runtime.txt
├── 🙈 .gitignore
├── 📜 LICENSE
└── 📖 README.md
```

---

## 🤝 Contributing

Contributions are warmly welcome! Whether it's a bug fix, new feature, or documentation improvement.

### How to Contribute

1. **Fork** the repository
   ```bash
   git clone https://github.com/yourusername/guardianbot.git
   ```

2. **Create a feature branch**
   ```bash
   git checkout -b feature/amazing-new-module
   ```

3. **Make your changes** — follow the code style:
   - Use `async/await` for all I/O operations
   - All bot messages must use Unicode small caps
   - Add type hints to all functions
   - Document new handlers in the README

4. **Test your changes**
   ```bash
   python -m pytest tests/
   ```

5. **Commit with a clear message**
   ```bash
   git commit -m "feat: add anti-raid module with captcha verification"
   ```

6. **Push and open a Pull Request**
   ```bash
   git push origin feature/amazing-new-module
   ```

### 🐛 Bug Reports

Found a bug? Please open an [issue](https://github.com/yourusername/guardianbot/issues) with:
- A clear title and description
- Steps to reproduce the bug
- Expected vs actual behavior
- Python and library versions

### 💡 Feature Requests

Have an idea? Open a [feature request issue](https://github.com/yourusername/guardianbot/issues/new) — we'd love to hear it!

### Code Style Guidelines

```python
# ✅ Good — async, typed, small-caps responses
async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ban a user from the group with optional reason."""
    chat = update.effective_chat
    user = update.effective_user
    # ... implementation
    await update.message.reply_text("✅ ᴜꜱᴇʀ ʜᴀꜱ ʙᴇᴇɴ ʙᴀɴɴᴇᴅ.")

# ❌ Bad — sync, untyped, plain text
def ban_user(update, context):
    update.message.reply_text("User has been banned.")
```

---

## 📜 License

```
MIT License — Copyright (c) 2024 GuardianBot

Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included
in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
```

See the full [LICENSE](LICENSE) file for details.

---

## 💎 Credits

<div align="center">

### Built With ❤️ Using

| Technology | Purpose |
|:---:|:---|
| [python-telegram-bot v20](https://python-telegram-bot.org) | Async Telegram Bot framework |
| [Motor](https://motor.readthedocs.io) | Async MongoDB driver |
| [MongoDB Atlas](https://cloud.mongodb.com) | Cloud database |
| [aiohttp](https://docs.aiohttp.org) | Async HTTP client |
| [cachetools](https://cachetools.readthedocs.io) | In-memory caching |
| [python-dotenv](https://pypi.org/project/python-dotenv/) | Environment management |
| [uvloop](https://github.com/MagicStack/uvloop) | Ultra-fast event loop (Linux) |
| [psutil](https://psutil.readthedocs.io) | System resource monitoring |

### Special Thanks

- The **[python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)** team for their incredible library
- **[Telegram](https://telegram.org)** for building the best messaging platform
- **[MongoDB](https://mongodb.com)** for the generous free Atlas tier
- Every open-source contributor who made this possible

</div>

---

<div align="center">

### 🌟 If GuardianBot protects your community, give it a star!

[![Star History Chart](https://img.shields.io/github/stars/yourusername/guardianbot?style=social)](https://github.com/yourusername/guardianbot)

---

*ᴍᴀᴅᴇ ᴡɪᴛʜ* ❤️ *ʙʏ ᴛʜᴇ ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ ᴛᴇᴀᴍ*

*© 2024 GuardianBot — MIT Licensed*

</div>
