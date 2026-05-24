<h1 align="center">
  🛡️ ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ
</h1>

<p align="center">
  <b>The most powerful Telegram group management bot.</b><br>
  <i>Crafted by</i> <b>𝐒𝐄𝐂𝐑𝐄𝐓</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/telegram-bot%20api-26A5E4?style=for-the-badge&logo=telegram&logoColor=white" alt="Telegram"/>
  <img src="https://img.shields.io/badge/mongodb-atlas-47A248?style=for-the-badge&logo=mongodb&logoColor=white" alt="MongoDB"/>
  <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="License"/>
  <img src="https://img.shields.io/badge/deploy-railway-0B0D0E?style=for-the-badge&logo=railway&logoColor=white" alt="Railway"/>
  <img src="https://img.shields.io/badge/deploy-render-46E3B7?style=for-the-badge&logo=render&logoColor=white" alt="Render"/>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/modules-20+-ff6b6b?style=flat-square" alt="Modules"/>
  <img src="https://img.shields.io/badge/commands-70+-ffd93d?style=flat-square" alt="Commands"/>
  <img src="https://img.shields.io/badge/style-small%20caps-9b59b6?style=flat-square" alt="Style"/>
</p>

---

## ⚡ What is GuardianBot?

GuardianBot is an **ultra-advanced** Telegram group management bot built for performance, power, and beauty. Every response is rendered in **Unicode small caps** for a distinctive premium look. Designed for groups of any size — from 10 members to 100,000+.

> **Zero third-party APIs.** No chatbot, no AI services, no external keys.  
> Pure group management. Raw power. Clean code.

---

## 🔥 Features

### ⚔️ Moderation
| Feature | Commands |
|---------|----------|
| **Bans** | `/ban`, `/tban`, `/unban`, `/sban`, `/kick`, `/kickme` |
| **Mutes** | `/mute`, `/tmute`, `/unmute`, `/smute` |
| **Warns** | `/warn`, `/dwarn`, `/unwarn`, `/resetwarns`, `/warns`, `/warnlimit`, `/warnmode` |
| **Reports** | `@admin`, `/report`, `/reports on\|off` |
| **Pins** | `/pin`, `/unpin`, `/unpinall`, `/pinned` |
| **Purge** | `/purge`, `/purge N`, `/del` |

### 🤖 Automation
| Feature | Commands |
|---------|----------|
| **Welcome** | `/setwelcome`, `/welcome on\|off`, `/setgoodbye`, `/cleanwelcome` |
| **Filters** | `/filter`, `/stop`, `/filters` |
| **Notes** | `/save`, `#name`, `/get`, `/clear`, `/notes`, `/clearall` |
| **Locks** | `/lock`, `/unlock`, `/locks` (20 lockable types) |
| **Blocklist** | `/addblock`, `/rmblock`, `/blocklist`, `/blockmode`, `/clearblock` |
| **Anti-Flood** | `/setflood`, `/flood`, `/setfloodmode` |

### 🌐 Advanced
| Feature | Commands |
|---------|----------|
| **Rules** | `/setrules`, `/rules`, `/clearrules`, `/privaterules` |
| **Federation** | `/newfed`, `/joinfed`, `/leavefed`, `/fedban`, `/unfedban`, `/fedinfo`, `/fedadmins` |
| **Disable** | `/disable`, `/enable`, `/disabled`, `/disableable` |

### 👑 Owner Powers
| Feature | Commands |
|---------|----------|
| **God Mode** | Owner has ALL bot powers in every chat where bot is admin |
| **Maintenance** | `/maintenance on\|off` — kill switch with broadcast to all chats & DMs |
| **Stats** | `/stats` — system vitals, DB status, uptime, memory |
| **Broadcast** | `/broadcast` — send message to all groups |

### 🎨 Design
- **Unicode Small Caps** — every response in premium ᴀ-ᴢ typography
- **Nested Button Menus** — ⚔️ Moderation → 🤖 Automation → 🌐 Advanced → 👑 Owner
- **Interactive Sub-Buttons** — drill-down help with back/close navigation
- **Emoji-Rich Responses** — every action has visual feedback
- **Log Channel** — all mod actions logged to private Telegram channel (unlimited cloud)

### ⚡ Performance
- **In-Memory TTL Cache** — admin lists, settings, blocklists cached to minimize DB hits
- **Connection Pooling** — MongoDB with 50-connection pool, retry writes
- **Async Everything** — python-telegram-bot v20+ with motor async MongoDB
- **Server Log Rotation** — 5MB rotating files, auto-cleanup of old logs
- **Rate-Limited Logging** — 18 msg/sec to Telegram channel, never hits flood limits

---

## 🚀 Quick Start

```bash
# Clone
git clone https://github.com/Secretaidev/GuardianBot.git
cd GuardianBot

# Configure
cp .env.example .env
# Edit .env with your BOT_TOKEN, MONGO_URI, LOG_CHANNEL_ID, OWNER_ID

# Install
pip install -r requirements.txt

# Run
python -m bot
```

---

## 🐳 Docker

```bash
docker build -t guardianbot .
docker run -d --env-file .env --name guardianbot guardianbot
```

---

## 🚂 Railway

1. Fork this repo
2. Connect to [Railway](https://railway.app)
3. Set environment variables
4. Deploy — auto-starts via `Procfile`

---

## 🎯 Render

1. Fork this repo
2. Create a **Background Worker** on [Render](https://render.com)
3. Connect your repo — `render.yaml` auto-configures everything
4. Set env vars → Deploy

---

## 🏗️ Architecture

```
GuardianBot/
├── bot/
│   ├── __main__.py          # async entrypoint
│   ├── config.py            # env loader with validation
│   ├── fonts.py             # Unicode small caps engine
│   ├── logger.py            # dual-sink: console + Telegram channel
│   ├── database/            # MongoDB async layer (motor)
│   │   ├── mongo.py         # connection pool, indexes
│   │   ├── users_db.py      # user tracking
│   │   ├── chats_db.py      # per-chat settings
│   │   ├── warns_db.py      # warning records
│   │   ├── notes_db.py      # saved notes
│   │   ├── filters_db.py    # auto-reply filters
│   │   ├── feds_db.py       # federation system
│   │   ├── blocklist_db.py  # word blocklist
│   │   └── antiflood_db.py  # flood tracking
│   ├── helpers/             # shared utilities
│   │   ├── buttons.py       # nested sub-menu builder
│   │   ├── cache.py         # TTL cache layer
│   │   ├── decorators.py    # @admin_required, @owner_everywhere
│   │   ├── extractors.py    # user/reason extraction
│   │   ├── permissions.py   # permission checkers
│   │   ├── time_parser.py   # duration parsing
│   │   └── autodelete.py    # server log rotation
│   └── modules/             # 20 feature modules
│       ├── start.py         # /start, /help with nested menus
│       ├── admin.py         # promote/demote/adminlist
│       ├── bans.py          # ban/kick system
│       ├── mutes.py         # mute system
│       ├── warns.py         # warning system
│       ├── welcome.py       # welcome/goodbye messages
│       ├── filters.py       # auto-reply filters
│       ├── notes.py         # saved notes
│       ├── locks.py         # content locks
│       ├── blocklist.py     # word blocklist
│       ├── antiflood.py     # flood protection
│       ├── reports.py       # @admin reports
│       ├── pins.py          # message pinning
│       ├── purge.py         # bulk delete
│       ├── rules.py         # group rules
│       ├── federation.py    # cross-group bans
│       ├── disable.py       # command disabling
│       ├── maintenance.py   # maintenance mode
│       ├── users.py         # user tracking
│       └── stats.py         # bot statistics
├── .env.example
├── Dockerfile
├── Procfile
├── railway.toml
├── render.yaml
├── requirements.txt
└── run.py
```

---

## 🔧 Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `BOT_TOKEN` | ✅ | Bot token from @BotFather |
| `MONGO_URI` | ✅ | MongoDB connection string |
| `LOG_CHANNEL_ID` | ✅ | Telegram channel ID for logs |
| `OWNER_ID` | ✅ | Your numeric Telegram user ID |
| `BOT_NAME` | ❌ | Display name (default: ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ) |
| `BOT_USERNAME` | ❌ | Bot @username |
| `WARN_LIMIT` | ❌ | Warns before auto-action (default: 3) |
| `SUDO_USERS` | ❌ | Comma-separated elevated user IDs |
| `FLOOD_LIMIT` | ❌ | Max messages per window (default: 5) |
| `LOG_LEVEL` | ❌ | DEBUG / INFO / WARNING / ERROR |

---

## 👑 Owner Features

### God Mode
The owner (defined by `OWNER_ID`) has **full powers** in every group where GuardianBot is admin. Whatever the bot can do, the owner can do — ban, mute, promote, delete, pin — regardless of the owner's admin status in that group.

### Maintenance Mode
```
/maintenance on [reason]   → Broadcasts maintenance banner to ALL groups + DMs
/maintenance off           → Broadcasts "back online" to ALL groups
/maintenance status        → Check current mode
```
During maintenance, ALL commands are blocked for everyone except the owner. Users see a styled maintenance banner.

---

## 📜 License

MIT License — see [LICENSE](LICENSE) for details.

---

<p align="center">
  <b>Crafted with ⚡ by 𝐒𝐄𝐂𝐑𝐄𝐓</b><br>
  <i>@its_me_secret</i>
</p>
