# 🪙 Coin Toss Gambling Discord Bot (Azure Ready)

A modern, high-energy Coin Toss Gambling Discord bot built in Python (`discord.py`) featuring virtual casino coins, interactive flip buttons, daily bonuses, leaderboards, and persistent storage, designed for continuous 24/7 hosting on **Microsoft Azure** (Azure Container Apps, App Service, or Virtual Machines).

---

## ✨ Features

- **🪙 Coin Toss Gambling**:
  - `/cointoss <choice> <bet>` — Bet coins on **Heads (👑)** or **Tails (🦅)** using modern Discord Slash commands.
  - `!cointoss <choice> <bet>` (or `!cf`, `!flip`) — Traditional prefix command (e.g. `!cf heads 100`, `!flip t all`).
  - **Interactive Button Controls**:
    - `/coinflip` (or `!flip`) opens an interactive button menu.
    - Every coin flip result includes **`[🔁 Flip Again]`** and **`[💰 Balance]`** action buttons for fast-paced betting!
  - **Dynamic Bet Sizes**: Bet numbers (`50`, `100`, `500`), `all` (all-in), `half`, or `max`.
  - **Color-Coded Result Embeds**:
    - 🟢 **Win**: Emerald celebration embed showing profit, chosen side, coin result, and new balance.
    - 🔴 **Loss**: Crimson embed displaying amount lost and remaining balance.

- **💰 Casino Economy & Persistence**:
  - **1,000 Starting Coins**: Every new player starts with 1,000 coins automatically.
  - `/balance` & `!bal` — Check wallet balance, win/loss stats, total bets, and net profit.
  - `/daily` & `!daily` — Claim **250 free coins** every 24 hours with live cooldown timers.
  - `/leaderboard` & `!top` — See the server's top richest gamblers.
  - `/give <user> <amount>` & `!give` — Transfer coins to other players.
  - **Persistent Storage**: Balances and statistics are saved safely in `economy.json`.

- **☁️ Azure Ready & Health Probe**:
  - Internal web server on port `8080` serving a live Azure status page (`/`) and JSON health check (`/health`).
  - Keeps Azure Container Apps / App Service alive without idle timeout restarts.
  - `/azure` & `/ping` commands to inspect cloud uptime and WebSocket latency.

---

## 🚀 Quickstart (Running Locally)

### 1. Prerequisites
- Python 3.10+ (Python 3.11 is already installed on your system).
- A Discord Bot Token in `.env`.

### 2. Run the Bot
The virtual environment has already been created with dependencies installed:

```powershell
# Run using the configured virtual environment:
.\venv\Scripts\python.exe bot.py
```

You will see:
```text
Azure health check server listening on http://0.0.0.0:8080
Syncing slash commands...
Successfully synced 9 slash command(s).
Bot logged in as 8ball#0793
Connected to 1 guild(s)
```

You can open [http://localhost:8080](http://localhost:8080) in your web browser to view the local Azure health dashboard!

---

## 🎮 Command Cheatsheet

| Command | Aliases | Description | Example |
| :--- | :--- | :--- | :--- |
| `/cointoss` | `!cf`, `!flip`, `!cointoss` | Bet coins on heads or tails | `/cointoss choice:heads bet:100` |
| `/coinflip` | `!coinflip` | Interactive button coin toss | `/coinflip` |
| `/balance` | `!bal`, `!coins`, `!wallet` | View coin balance and stats | `/balance` or `!bal @user` |
| `/daily` | `!daily` | Claim 250 free daily coins | `/daily` |
| `/leaderboard` | `!lb`, `!top` | View top richest players | `/leaderboard` |
| `/give` | `!pay`, `!send` | Send coins to another player | `/give user:@friend amount:100` |
| `/ping` | `!ping` | Check WebSocket gateway latency | `/ping` |
| `/azure` | `!azure` | View Azure host info & uptime | `/azure` |
| `/help` | `!help` | Casino instructions and rules | `/help` |

---

## ☁️ Deploying to Microsoft Azure

For full step-by-step instructions (with screenshots and CLI commands), check the [Azure Deployment Guide](file:///c:/Users/annyh/discord/deploy/azure_deployment_guide.md).
