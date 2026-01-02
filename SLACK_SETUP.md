# RansomLook Slack Bot Setup Guide

This guide walks you through setting up the RansomLook Slack bot, which provides:
- **Automatic notifications** when new ransomware victims are detected
- **Slash commands** to query the RansomLook API directly from Slack

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Create a Slack App](#create-a-slack-app)
3. [Configure Bot Permissions](#configure-bot-permissions)
4. [Enable Socket Mode](#enable-socket-mode)
5. [Create Slash Commands](#create-slash-commands)
6. [Install the App](#install-the-app)
7. [Configure RansomLook](#configure-ransomlook)
8. [Run the Bot](#run-the-bot)
9. [Available Commands](#available-commands)
10. [Troubleshooting](#troubleshooting)

---

## Prerequisites

- A Slack workspace where you have permission to install apps
- RansomLook instance running with the API accessible
- Python 3.10+ with the RansomLook dependencies installed

---

## Create a Slack App

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps)

2. Click **"Create New App"**

3. Choose **"From scratch"**

4. Enter the following:
   - **App Name**: `RansomLook Bot` (or your preferred name)
   - **Workspace**: Select your workspace

5. Click **"Create App"**

---

## Configure Bot Permissions

### OAuth & Permissions

1. In the left sidebar, click **"OAuth & Permissions"**

2. Scroll down to **"Scopes"** section

3. Under **"Bot Token Scopes"**, click **"Add an OAuth Scope"** and add these scopes:
   
   | Scope | Description |
   |-------|-------------|
   | `chat:write` | Send messages as the bot |
   | `chat:write.public` | Send messages to channels the bot isn't a member of |
   | `commands` | Add slash commands |
   | `channels:read` | View basic information about public channels |
   | `groups:read` | View basic information about private channels |
   | `im:read` | View basic information about direct messages |
   | `mpim:read` | View basic information about group direct messages |

---

## Enable Socket Mode

Socket Mode allows your bot to receive events without exposing a public HTTP endpoint.

1. In the left sidebar, click **"Socket Mode"**

2. Toggle **"Enable Socket Mode"** to **ON**

3. You'll be prompted to create an **App-Level Token**:
   - **Token Name**: `socket-mode-token`
   - **Scopes**: Select `connections:write`
   - Click **"Generate"**

4. **⚠️ IMPORTANT**: Copy the token that starts with `xapp-`. This is your `SLACK_APP_TOKEN`.

---

## Create Slash Commands

1. In the left sidebar, click **"Slash Commands"**

2. Click **"Create New Command"** for each command below:

### Required Commands

| Command | Short Description | Usage Hint |
|---------|-------------------|------------|
| `/rlook-help` | Show all available commands | |
| `/rlook-recent` | Get recent ransomware posts | `[count]` |
| `/rlook-last` | Get posts from last X days | `[days]` |
| `/rlook-groups` | List all ransomware groups | |
| `/rlook-group` | Get info about a specific group | `<group_name>` |
| `/rlook-markets` | List all markets | |
| `/rlook-market` | Get info about a specific market | `<market_name>` |
| `/rlook-leaks` | List all data breaches | |
| `/rlook-leak` | Get details of a breach | `<leak_id>` |
| `/rlook-rf-leaks` | List Recorded Future leaks | |
| `/rlook-rf-leak` | Get RF leak details | `<leak_name>` |
| `/rlook-telegram-channels` | List Telegram channels | |
| `/rlook-telegram` | Get Telegram channel info | `<channel_name>` |
| `/rlook-stats` | Get yearly statistics | `<year>` |
| `/rlook-stats-month` | Get monthly statistics | `<year> <month>` |
| `/rlook-posts-period` | Get posts between dates | `<start_date> <end_date>` |
| `/rlook-search` | Search posts by keyword | `<keyword>` |

For each command:
1. Click **"Create New Command"**
2. Enter the **Command** (e.g., `/rlook-help`)
3. Enter the **Short Description**
4. Enter the **Usage Hint** (if applicable)
5. Leave **Request URL** empty (using Socket Mode)
6. Click **"Save"**

---

## Install the App

1. In the left sidebar, click **"Install App"**

2. Click **"Install to Workspace"**

3. Review the permissions and click **"Allow"**

4. **⚠️ IMPORTANT**: Copy the **"Bot User OAuth Token"** that starts with `xoxb-`. This is your `SLACK_BOT_TOKEN`.

---

## Get the Signing Secret

1. In the left sidebar, click **"Basic Information"**

2. Scroll down to **"App Credentials"**

3. Click **"Show"** next to **Signing Secret**

4. **⚠️ IMPORTANT**: Copy this value. This is your `SLACK_SIGNING_SECRET`.

---

## Get the Channel ID

To get the Channel ID where you want automatic notifications posted:

1. Open Slack

2. Right-click on the channel name

3. Click **"View channel details"** (or **"Open channel details"**)

4. Scroll down to find the **Channel ID** at the bottom (starts with `C`)

5. Copy this value for `SLACK_CHANNEL_ID`

**Note**: You can also get the channel ID from the URL when viewing the channel in a browser. The URL format is:
`https://app.slack.com/client/TXXXXXXXX/CXXXXXXXX` - the `CXXXXXXXX` part is your channel ID.

---

## Configure RansomLook

You have two options for configuration:

### Option 1: Config File (Recommended)

Edit your `config/generic.json` file and add or update the `slack` section:

```json
{
    "slack": {
        "enable": true,
        "bot_token": "xoxb-your-bot-token-here",
        "app_token": "xapp-your-app-token-here",
        "signing_secret": "your-signing-secret-here",
        "channel_id": "C0123456789",
        "poll_interval": 60,
        "api_base": "http://127.0.0.1:8000/api"
    }
}
```

### Option 2: Environment Variables

Set the following environment variables:

```bash
export SLACK_BOT_TOKEN="xoxb-your-bot-token-here"
export SLACK_APP_TOKEN="xapp-your-app-token-here"
export SLACK_SIGNING_SECRET="your-signing-secret-here"
export SLACK_CHANNEL_ID="C0123456789"
export RANSOMLOOK_API_BASE="http://127.0.0.1:8000/api"
export RANSOMLOOK_POLL_INTERVAL="60"
```

**Note**: Environment variables take precedence over config file settings.

---

## Run the Bot

### Using Poetry

```bash
# Make sure you're in the RansomLook directory
cd /path/to/RansomLook

# Install dependencies (if not already done)
poetry install

# Run the Slack bot
poetry run slack
```

### Running Directly

```bash
python bin/slack.py
```

### Running in Background

```bash
# Using nohup
nohup poetry run slack > slack_bot.log 2>&1 &

# Or using screen/tmux
screen -S ransomlook-slack
poetry run slack
# Press Ctrl+A, then D to detach
```

### Expected Output

When the bot starts successfully, you should see:

```
[slack_bot] Starting RansomLook Slack Bot
[slack_bot] API Base: http://127.0.0.1:8000/api
[slack_bot] Poll Interval: 60s
[slack_bot] Channel ID: C0123456789
[poller] Starting poll loop (interval: 60s, channel: C0123456789)
[slack_bot] Bot is running! Press Ctrl+C to stop.
```

---

## Available Commands

### Posts & Victims
| Command | Description | Example |
|---------|-------------|---------|
| `/rlook-recent [count]` | Get recent posts (default: 10, max: 50) | `/rlook-recent 20` |
| `/rlook-last [days]` | Get posts from last X days (default: 1) | `/rlook-last 7` |
| `/rlook-posts-period <start> <end>` | Get posts between dates | `/rlook-posts-period 2024-01-01 2024-01-31` |
| `/rlook-search <keyword>` | Search posts by keyword | `/rlook-search hospital` |

### Groups
| Command | Description | Example |
|---------|-------------|---------|
| `/rlook-groups` | List all ransomware groups | `/rlook-groups` |
| `/rlook-group <name>` | Get info about a specific group | `/rlook-group lockbit3` |

### Markets
| Command | Description | Example |
|---------|-------------|---------|
| `/rlook-markets` | List all markets | `/rlook-markets` |
| `/rlook-market <name>` | Get info about a specific market | `/rlook-market genesis` |

### Data Breaches
| Command | Description | Example |
|---------|-------------|---------|
| `/rlook-leaks` | List all data breaches | `/rlook-leaks` |
| `/rlook-leak <id>` | Get details of a specific breach | `/rlook-leak 12345` |

### Recorded Future
| Command | Description | Example |
|---------|-------------|---------|
| `/rlook-rf-leaks` | List Recorded Future leaks | `/rlook-rf-leaks` |
| `/rlook-rf-leak <name>` | Get RF leak details | `/rlook-rf-leak example` |

### Telegram
| Command | Description | Example |
|---------|-------------|---------|
| `/rlook-telegram-channels` | List Telegram channels | `/rlook-telegram-channels` |
| `/rlook-telegram <name>` | Get Telegram channel info | `/rlook-telegram lockbit` |

### Statistics
| Command | Description | Example |
|---------|-------------|---------|
| `/rlook-stats <year>` | Get posts per group for a year | `/rlook-stats 2024` |
| `/rlook-stats-month <year> <month>` | Get posts per group for a month | `/rlook-stats-month 2024 06` |

### Help
| Command | Description |
|---------|-------------|
| `/rlook-help` | Show all available commands |

---

## Integrating with Existing Notifications

The `ransomlook/slack.py` module provides functions for programmatic notifications that can be integrated into your existing notification workflows:

```python
from ransomlook.slack import slacknotify, slacknotifyleak, slacknotifyrf

# Load your Slack config
config = {
    "enable": True,
    "bot_token": "xoxb-...",
    "channel_id": "C0123456789"
}

# Notify about a new ransomware victim
slacknotify(config, "lockbit3", "Example Corp", "Data leak announced...")

# Notify about a data breach
slacknotifyleak(config, {"name": "Company XYZ", "columns": ["email", "password"]})

# Notify about a Recorded Future dump
slacknotifyrf(config, {"name": "RF Dump", "description": "New intelligence..."})
```

---

## Troubleshooting

### "SLACK_BOT_TOKEN not configured"
- Ensure you've either set the environment variable or added `bot_token` to your config file
- Make sure the token starts with `xoxb-`

### "SLACK_APP_TOKEN not configured"
- Socket Mode requires an App-Level Token
- Go to your app's **Socket Mode** settings and generate a token with `connections:write` scope
- The token should start with `xapp-`

### "channel_not_found" error
- Verify the channel ID is correct (starts with `C`)
- Make sure the bot has been invited to the channel
- Try mentioning the bot in the channel: `@RansomLook Bot`

### Slash commands not working
- Verify all slash commands are created in the Slack app settings
- Check that Socket Mode is enabled
- Ensure the bot has the `commands` scope
- Try reinstalling the app to your workspace

### Bot not receiving messages
- Check that the bot is running and connected (look for "Bot is running!" in logs)
- Verify Socket Mode is enabled and the App Token is correct
- Check for any error messages in the console output

### API connection errors
- Verify the RansomLook API is running at the configured URL
- Check that `api_base` points to the correct endpoint (include `/api`)
- Test the API manually: `curl http://127.0.0.1:8000/api/groups`

### Polling not posting new victims
- First run doesn't post (to avoid flooding on startup)
- Check that `SLACK_CHANNEL_ID` is set
- Verify there are actually new posts since the bot started
- Check the poll interval (default: 60 seconds)

---

## Security Considerations

1. **Never commit tokens to version control** - Use environment variables or a separate `.env` file

2. **Restrict channel access** - Consider using a private channel for sensitive alerts

3. **API access** - The bot has read-only access to the API by default

4. **Network security** - If the API is internal, ensure proper network segmentation

---

## Support

If you encounter issues:
1. Check the console output for error messages
2. Verify all tokens and configuration values
3. Test the API endpoints manually
4. Check Slack's [App Management](https://api.slack.com/apps) for any app issues

For bugs or feature requests, please open an issue in the RansomLook repository.
