#!/usr/bin/env python3
"""
Slack bot for RansomLook
 - Posts newly discovered victims from /api/recent into a channel (polling).
 - Exposes slash commands that mirror the exposed API endpoints.
 - Supports both environment variables and config file configuration.

Configuration can be provided via:
  1. Environment variables (takes precedence)
  2. Config file at config/generic.json under the "slack" key

Env vars:
  SLACK_BOT_TOKEN           Bot token (starts with xoxb-)
  SLACK_APP_TOKEN           App token for Socket Mode (starts with xapp-)
  SLACK_SIGNING_SECRET      Slack signing secret
  SLACK_CHANNEL_ID          Channel ID to post automatic updates
  RANSOMLOOK_API_BASE       Base URL for the API (default: http://127.0.0.1:8000/api)
  RANSOMLOOK_POLL_INTERVAL  Poll interval in seconds (default: 60)
"""

import json
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# Try to load config from file
CONFIG_FILE = Path(__file__).parent.parent / "config" / "generic.json"


def load_config() -> Dict[str, Any]:
    """Load Slack configuration from config file."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                return config.get("slack", {})
        except Exception as e:
            print(f"[config] Warning: Could not load config file: {e}")
    return {}


# Load config from file
file_config = load_config()

# Environment variables take precedence over config file
API_BASE = os.getenv(
    "RANSOMLOOK_API_BASE",
    file_config.get("api_base", "http://127.0.0.1:8000/api")
)
POLL_INTERVAL = int(os.getenv(
    "RANSOMLOOK_POLL_INTERVAL",
    str(file_config.get("poll_interval", 60))
))
SLACK_CHANNEL_ID = os.getenv(
    "SLACK_CHANNEL_ID",
    file_config.get("channel_id", "")
)
SLACK_BOT_TOKEN = os.getenv(
    "SLACK_BOT_TOKEN",
    file_config.get("bot_token", "")
)
SLACK_SIGNING_SECRET = os.getenv(
    "SLACK_SIGNING_SECRET",
    file_config.get("signing_secret", "")
)
SLACK_APP_TOKEN = os.getenv(
    "SLACK_APP_TOKEN",
    file_config.get("app_token", "")
)

# Check if Slack is enabled via config file
SLACK_ENABLED = file_config.get("enable", True) if file_config else True

if not SLACK_ENABLED:
    print("[slack_bot] Slack is disabled in config. Set 'enable': true to enable.")
    sys.exit(0)

if not SLACK_BOT_TOKEN:
    print("[slack_bot] Error: SLACK_BOT_TOKEN not configured")
    sys.exit(1)

app = App(
    token=SLACK_BOT_TOKEN,
    signing_secret=SLACK_SIGNING_SECRET,
)


def api_get(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    """Make a GET request to the RansomLook API."""
    url = f"{API_BASE.rstrip('/')}/{path.lstrip('/')}"
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def api_post(path: str, data: Any = None) -> Any:
    """Make a POST request to the RansomLook API."""
    url = f"{API_BASE.rstrip('/')}/{path.lstrip('/')}"
    resp = requests.post(url, json=data, timeout=30)
    resp.raise_for_status()
    return resp.json()


def format_post(post: Dict[str, Any]) -> str:
    """Format a post for Slack display."""
    title = post.get("post_title", "untitled")
    group = post.get("group_name", "unknown")
    discovered = post.get("discovered", "")
    descr = post.get("description", "")[:300]
    link = post.get("link")
    link_part = f" | <{link}|link>" if link else ""
    return f"*{group}* – {title} ({discovered}){link_part}\n{descr}{'...' if len(post.get('description', '')) > 300 else ''}"


def format_post_blocks(post: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Format a post as Slack blocks for richer display."""
    title = post.get("post_title", "untitled")
    group = post.get("group_name", "unknown")
    discovered = post.get("discovered", "")
    descr = post.get("description", "")[:500]
    link = post.get("link")
    
    blocks = [
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Group:* {group}"},
                {"type": "mrkdwn", "text": f"*Discovered:* {discovered}"}
            ]
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*{title}*\n{descr}{'...' if len(post.get('description', '')) > 500 else ''}"}
        }
    ]
    
    if link:
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"<{link}|View Details>"}]
        })
    
    return blocks


def parse_iso(date_str: str) -> datetime:
    """Parse ISO date string to datetime."""
    try:
        return datetime.fromisoformat(date_str.replace("T", " "))
    except Exception:
        return datetime.min


def poll_recent():
    """
    Poll /api/recent and post any unseen items to the configured channel.
    Uses the discovered timestamp to gate new posts.
    """
    if not SLACK_CHANNEL_ID:
        print("[poller] SLACK_CHANNEL_ID not set; skipping poller.")
        return

    last_seen: datetime = datetime.min
    first_run = True
    
    print(f"[poller] Starting poll loop (interval: {POLL_INTERVAL}s, channel: {SLACK_CHANNEL_ID})")
    
    while True:
        try:
            recent: List[Dict[str, Any]] = api_get("recent/50")
            # sort newest first
            recent_sorted = sorted(recent, key=lambda x: x.get("discovered", ""), reverse=True)
            new_posts: List[Dict[str, Any]] = []
            
            for post in recent_sorted:
                ts = parse_iso(str(post.get("discovered", "")))
                if ts > last_seen:
                    new_posts.append(post)
                    
            if new_posts:
                last_seen = max(parse_iso(str(p.get("discovered", ""))) for p in new_posts)
                if not first_run:
                    # Build blocks for all new posts
                    blocks = [
                        {
                            "type": "header",
                            "text": {
                                "type": "plain_text",
                                "text": f"🚨 {len(new_posts)} New Victim(s) Detected",
                                "emoji": True
                            }
                        }
                    ]
                    
                    for post in new_posts[:10]:  # Limit due to Slack block limits
                        blocks.extend(format_post_blocks(post))
                        blocks.append({"type": "divider"})
                    
                    if len(new_posts) > 10:
                        blocks.append({
                            "type": "context",
                            "elements": [{"type": "mrkdwn", "text": f"_...and {len(new_posts) - 10} more_"}]
                        })
                    
                    app.client.chat_postMessage(
                        channel=SLACK_CHANNEL_ID,
                        text=f"{len(new_posts)} new victim(s) detected",
                        blocks=blocks[:-1] if blocks and blocks[-1].get("type") == "divider" else blocks
                    )
                    print(f"[poller] Posted {len(new_posts)} new victim(s)")
                    
            first_run = False
        except Exception as exc:
            print(f"[poller] error: {exc}")
        time.sleep(POLL_INTERVAL)


def slash_reply(ack, respond, command, handler):
    """Generic handler for slash commands."""
    cmd_name = command.get("command", "unknown")
    print(f"[slash] Received command: {cmd_name}")
    ack()
    try:
        result = handler(command["text"].strip())
        if isinstance(result, dict) and "blocks" in result:
            respond(blocks=result["blocks"], text=result.get("text", ""))
        else:
            respond(result)
        print(f"[slash] Command {cmd_name} completed successfully")
    except Exception as exc:
        print(f"[slash] Command {cmd_name} failed with error: {exc}")
        respond(f"❌ Error: {exc}")


# ============================================================================
# SLASH COMMAND HANDLERS
# ============================================================================

def cmd_help(_: str) -> str:
    """Return help text with all available commands."""
    return """*RansomLook Slack Bot Commands*

*📊 Posts & Victims*
• `/rlook-recent [count]` - Get recent posts (default: 10)
• `/rlook-last [days]` - Get posts from last X days (default: 1)
• `/rlook-posts-period <start> <end>` - Get posts between dates (YYYY-MM-DD)

*👥 Groups*
• `/rlook-groups` - List all ransomware groups
• `/rlook-group <name>` - Get info about a specific group

*🏪 Markets*
• `/rlook-markets` - List all markets
• `/rlook-market <name>` - Get info about a specific market

*💾 Data Breaches*
• `/rlook-leaks` - List all data breaches
• `/rlook-leak <id>` - Get details of a specific breach

*🔍 Recorded Future*
• `/rlook-rf-leaks` - List Recorded Future leaks
• `/rlook-rf-leak <name>` - Get RF leak details

*📱 Telegram*
• `/rlook-telegram-channels` - List Telegram channels
• `/rlook-telegram <name>` - Get Telegram channel info

*📈 Statistics*
• `/rlook-stats <year>` - Get posts per group for a year
• `/rlook-stats-month <year> <month>` - Get posts per group for a month

*ℹ️ Help*
• `/rlook-help` - Show this help message
"""


def cmd_recent(args: str) -> str:
    """Get recent posts."""
    count = int(args) if args else 10
    count = min(count, 50)  # Cap at 50
    data = api_get(f"recent/{count}")
    if not data:
        return "No recent posts found."
    lines = [format_post(p) for p in data[:count]]
    return "\n\n".join(lines) or "No posts."


def cmd_last(args: str) -> str:
    """Get posts from last X days."""
    days = int(args) if args else 1
    data = api_get(f"last/{days}")
    if not data:
        return f"No posts in last {days} day(s)."
    lines = [format_post(p) for p in data]
    return "\n\n".join(lines) or f"No posts in last {days} day(s)."


def cmd_posts_period(args: str) -> str:
    """Get posts between two dates."""
    parts = args.split()
    if len(parts) != 2:
        return "Usage: /rlook-posts-period <start_date> <end_date>\nDate format: YYYY-MM-DD"
    start_date, end_date = parts
    data = api_get(f"posts/period/{start_date}/{end_date}")
    if not data:
        return f"No posts found between {start_date} and {end_date}."
    lines = [format_post(p) for p in data[:20]]
    footer = f"\n\n_Showing {len(lines)} of {len(data)} posts_" if len(data) > 20 else ""
    return "\n\n".join(lines) + footer


def cmd_groups(_: str) -> str:
    """List all ransomware groups."""
    groups = api_get("groups")
    return f"*Ransomware Groups ({len(groups)}):*\n" + ", ".join(sorted(groups))


def cmd_group(args: str) -> str:
    """Get info about a specific group."""
    if not args:
        return "Usage: /rlook-group <name>"
    try:
        data = api_get(f"group/{args}")
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            return f"Group '{args}' not found."
        raise
        
    if not data:
        return f"No data for group '{args}'"
        
    group, posts = data if isinstance(data, (list, tuple)) and len(data) == 2 else (data, [])
    
    body = [f"*{args}*"]
    
    if isinstance(group, dict):
        if group.get("locations"):
            body.append(f"📍 *Locations:* {', '.join(group['locations'])}")
        if group.get("telegram"):
            body.append(f"📱 *Telegram:* {group['telegram']}")
        if group.get("meta"):
            body.append(f"ℹ️ *Description:* {group['meta'][:500]}")
        if group.get("profile"):
            for key, value in group['profile'].items():
                body.append(f"• *{key}:* {value}")
                
    if posts:
        body.append(f"\n*Recent posts ({len(posts)}):*")
        for post in posts[:5]:
            title = post.get('post_title', 'Untitled')
            discovered = post.get('discovered', '')
            body.append(f"• {title} ({discovered})")
        if len(posts) > 5:
            body.append(f"_...and {len(posts) - 5} more_")
            
    return "\n".join(body)


def cmd_markets(_: str) -> str:
    """List all markets."""
    markets = api_get("markets")
    return f"*Markets ({len(markets)}):*\n" + ", ".join(sorted(markets))


def cmd_market(args: str) -> str:
    """Get info about a specific market."""
    if not args:
        return "Usage: /rlook-market <name>"
    try:
        data = api_get(f"market/{args}")
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            return f"Market '{args}' not found."
        raise
        
    if not data:
        return f"No data for market '{args}'"
    return json_pretty(data)


def cmd_leaks(_: str) -> str:
    """List all data breaches."""
    leaks = api_get("leaks/leaks")
    body = [f"*Data Breaches ({len(leaks)}):*"]
    for leak in leaks[:20]:
        leak_id = leak.get('id', 'N/A')
        name = leak.get('name', 'Unknown')
        body.append(f"• `{leak_id}`: {name}")
    if len(leaks) > 20:
        body.append(f"_...and {len(leaks) - 20} more_")
    return "\n".join(body)


def cmd_leak(args: str) -> str:
    """Get details of a specific breach."""
    if not args:
        return "Usage: /rlook-leak <id>"
    try:
        leak = api_get(f"leaks/leaks/{args}")
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            return f"Leak '{args}' not found."
        raise
    return json_pretty(leak)


def cmd_rf_leaks(_: str) -> str:
    """List Recorded Future leaks."""
    leaks = api_get("rf/leaks")
    return f"*Recorded Future Leaks ({len(leaks)}):*\n" + ", ".join(leaks[:30]) + (f"\n_...and {len(leaks) - 30} more_" if len(leaks) > 30 else "")


def cmd_rf_leak(args: str) -> str:
    """Get RF leak details."""
    if not args:
        return "Usage: /rlook-rf-leak <name>"
    try:
        leak = api_get(f"rf/leak/{args}")
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            return f"RF leak '{args}' not found."
        raise
    return json_pretty(leak)


def cmd_telegram_channels(_: str) -> str:
    """List Telegram channels."""
    chans = api_get("telegram/channels")
    return f"*Telegram Channels ({len(chans)}):*\n" + ", ".join(chans)


def cmd_telegram(args: str) -> str:
    """Get Telegram channel info."""
    if not args:
        return "Usage: /rlook-telegram <name>"
    try:
        data = api_get(f"telegram/channel/{args}")
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            return f"Telegram channel '{args}' not found."
        raise
        
    if not data:
        return f"No data for '{args}'"
        
    meta, posts = data if isinstance(data, (list, tuple)) and len(data) == 2 else (data, {})
    
    body = [f"*📱 {args}*"]
    
    if isinstance(meta, dict) and meta.get("meta"):
        body.append(f"ℹ️ {meta['meta'][:500]}")
        
    if posts:
        body.append("\n*Recent Messages:*")
        items = list(posts.items())[:5] if isinstance(posts, dict) else []
        for ts, post in items:
            text = post if isinstance(post, str) else post.get("message", "")
            body.append(f"• `{ts}`: {text[:100]}{'...' if len(text) > 100 else ''}")
            
    return "\n".join(body)


def cmd_stats(args: str) -> str:
    """Get posts per group for a year."""
    if not args:
        return "Usage: /rlook-stats <year>\nExample: /rlook-stats 2024"
    try:
        data = api_get(f"graphs/bar/{args}")
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            return f"No stats found for year {args}."
        raise
        
    if not data:
        return f"No stats for year {args}"
        
    # Sort by count descending
    sorted_data = sorted(data.items() if isinstance(data, dict) else [], key=lambda x: x[1], reverse=True)
    
    body = [f"*📊 Posts per Group ({args}):*"]
    for group, count in sorted_data[:15]:
        bar = "█" * min(int(count / 10), 20)
        body.append(f"`{group[:20]:<20}` {bar} {count}")
    if len(sorted_data) > 15:
        body.append(f"_...and {len(sorted_data) - 15} more groups_")
        
    return "\n".join(body)


def cmd_stats_month(args: str) -> str:
    """Get posts per group for a specific month."""
    parts = args.split()
    if len(parts) != 2:
        return "Usage: /rlook-stats-month <year> <month>\nExample: /rlook-stats-month 2024 06"
    year, month = parts
    try:
        data = api_get(f"graphs/bar/{year}/{month}")
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            return f"No stats found for {year}-{month}."
        raise
        
    if not data:
        return f"No stats for {year}-{month}"
        
    sorted_data = sorted(data.items() if isinstance(data, dict) else [], key=lambda x: x[1], reverse=True)
    
    body = [f"*📊 Posts per Group ({year}-{month}):*"]
    for group, count in sorted_data[:15]:
        bar = "█" * min(count, 20)
        body.append(f"`{group[:20]:<20}` {bar} {count}")
    if len(sorted_data) > 15:
        body.append(f"_...and {len(sorted_data) - 15} more groups_")
        
    return "\n".join(body)


def cmd_search(args: str) -> str:
    """Search for posts by keyword (searches post titles)."""
    if not args:
        return "Usage: /rlook-search <keyword>"
    # Get recent posts and filter locally (API may not have search endpoint)
    data = api_get("recent/100")
    keyword_lower = args.lower()
    matches = [p for p in data if keyword_lower in p.get("post_title", "").lower() or keyword_lower in p.get("description", "").lower()]
    
    if not matches:
        return f"No posts found matching '{args}'"
        
    lines = [format_post(p) for p in matches[:10]]
    footer = f"\n\n_Found {len(matches)} matching posts_" if len(matches) > 10 else f"\n\n_Found {len(matches)} matching post(s)_"
    return "\n\n".join(lines) + footer


def json_pretty(obj: Any) -> str:
    """Format object as pretty JSON in a code block."""
    return "```" + json.dumps(obj, indent=2, ensure_ascii=False)[:2900] + "```"


# ============================================================================
# REGISTER SLASH COMMANDS
# ============================================================================

# Help
app.command("/rlook-help")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_help))

# Posts & Victims
app.command("/rlook-recent")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_recent))
app.command("/rlook-last")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_last))
app.command("/rlook-posts-period")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_posts_period))
app.command("/rlook-search")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_search))

# Groups
app.command("/rlook-groups")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_groups))
app.command("/rlook-group")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_group))

# Markets
app.command("/rlook-markets")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_markets))
app.command("/rlook-market")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_market))

# Leaks
app.command("/rlook-leaks")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_leaks))
app.command("/rlook-leak")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_leak))

# Recorded Future
app.command("/rlook-rf-leaks")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_rf_leaks))
app.command("/rlook-rf-leak")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_rf_leak))

# Telegram
app.command("/rlook-telegram-channels")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_telegram_channels))
app.command("/rlook-telegram")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_telegram))

# Stats
app.command("/rlook-stats")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_stats))
app.command("/rlook-stats-month")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_stats_month))


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main() -> None:
    """Start the Slack bot."""
    print(f"[slack_bot] Starting RansomLook Slack Bot")
    print(f"[slack_bot] API Base: {API_BASE}")
    print(f"[slack_bot] Poll Interval: {POLL_INTERVAL}s")
    print(f"[slack_bot] Channel ID: {SLACK_CHANNEL_ID or 'Not set (polling disabled)'}")
    
    if not SLACK_APP_TOKEN:
        print("[slack_bot] Error: SLACK_APP_TOKEN not configured (required for Socket Mode)")
        sys.exit(1)
    
    # Start the polling thread
    threading.Thread(target=poll_recent, daemon=True).start()
    
    # Start the Slack app in Socket Mode
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    print("[slack_bot] Bot is running! Press Ctrl+C to stop.")
    handler.start()


if __name__ == "__main__":
    main()
