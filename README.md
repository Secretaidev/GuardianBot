<h1 align="center">🌹 Rose</h1>

<p align="center">
  <b>The most powerful Telegram group management bot.</b><br>
  <i>Crafted by</i> <b>𝐒𝐄𝐂𝐑𝐄𝐓</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/telegram-bot%20api-26A5E4?style=for-the-badge&logo=telegram&logoColor=white" alt="Telegram"/>
  <img src="https://img.shields.io/badge/mongodb-atlas-47A248?style=for-the-badge&logo=mongodb&logoColor=white" alt="MongoDB"/>
</p>

<p align="center">
  <a href="https://t.me/RoseManagementBot">@RoseManagementBot</a> · <a href="https://t.me/SecretzBotz">@SecretzBotz</a>
</p>

---

## ⚡ Features — 27 Modules

| Module | Commands |
|--------|----------|
| **Admin** | promote, demote, title, adminlist, invitelink, setgtitle, setgdesc |
| **Antiflood** | setflood, setfloodmode, flood |
| **AntiRaid** | antiraid, raidtime, raidactionmode |
| **Approval** | approve, unapprove, approved |
| **Bans** | ban, tban, unban, sban, kick, kickme |
| **Blocklists** | addblocklist, rmblocklist, blocklist, setblocklistmode |
| **CAPTCHA** | captcha, captchamode, captchatime |
| **Clean Cmds** | cleancmds, cleanservice |
| **Connections** | connect, disconnect, connection |
| **Disabling** | disable, enable, disabled, disableable |
| **Federations** | newfed, joinfed, leavefed, fedban, unfedban, fedinfo |
| **Filters** | filter, stop, filters |
| **Formatting** | markdownhelp |
| **Greetings** | setwelcome, welcome, setgoodbye, goodbye, cleanwelcome |
| **Locks** | lock, unlock, locks |
| **Log Channels** | logchannel, setlog, unsetlog |
| **Misc** | id, info, ping, about |
| **Notes** | save, get, clear, notes, clearall |
| **Pin** | pin, unpin, unpinall, pinned |
| **Privacy** | privacy, deletedata |
| **Purges** | purge, del |
| **Reports** | report, reports |
| **Rules** | setrules, rules, clearrules, privaterules |
| **Topics** | newtopic, closetopic, opentopic |
| **Warnings** | warn, dwarn, unwarn, resetwarns, warns, warnlimit, warnmode |
| **Stats** | stats, broadcast |
| **Maintenance** | maintenance |

---

## 🚀 Quick Start

```bash
git clone https://github.com/Secretaidev/GuardianBot.git
cd GuardianBot
cp .env.example .env
# Edit .env with your BOT_TOKEN, MONGO_URI, LOG_CHANNEL_ID, OWNER_ID
pip install -r requirements.txt
python -m bot
```

## 🐳 Docker

```bash
docker build -t rose .
docker run -d --env-file .env --name rose rose
```

## 🚂 Railway

1. Fork → Connect to Railway → Set env vars → Deploy

## 🎯 Render

1. Fork → Background Worker on Render → `render.yaml` auto-configures

---

## 🏗 Architecture

```
bot/
├── __main__.py          # async entrypoint with auto-restart + health server
├── config.py            # env loader
├── fonts.py             # text formatting
├── logger.py            # console + Telegram channel logging
├── database/            # MongoDB collections
├── helpers/             # decorators, buttons, cache, extractors
└── modules/             # 27 feature modules
```

---

<p align="center">
  <b>Crafted by 𝐒𝐄𝐂𝐑𝐄𝐓</b><br>
  <a href="https://t.me/RoseManagementBot">@RoseManagementBot</a> · <a href="https://t.me/SecretzBotz">@SecretzBotz</a>
</p>
