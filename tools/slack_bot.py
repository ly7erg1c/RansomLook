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
import re
import subprocess
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
    # Handle empty responses
    if not resp.text or resp.text.strip() == '':
        return None
    try:
        return resp.json()
    except json.JSONDecodeError as e:
        print(f"[api] JSON decode error for {path}: {e}")
        print(f"[api] Response text: {resp.text[:200]}")
        return None


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
    """Return help text with common commands."""
    return """*RansomLook Slack Bot Commands*

*📊 Posts & Victims*
• `/rlook-recent [count]` - Get recent posts (default: 10)
• `/rlook-last [days]` - Get posts from last X days (default: 1)
• `/rlook-posts-period <start> <end>` - Get posts between dates (YYYY-MM-DD)
• `/rlook-search <keyword>` - Search posts by keyword

*👥 Groups*
• `/rlook-groups` - List all ransomware groups
• `/rlook-group <name>` - Get info about a specific group

*📝 Notes*
• `/rlook-notes-groups` - List groups that have notes
• `/rlook-notes <group>` - Get notes for a specific group

*🔧 Admin*
• `/rlook-scrape <group>` - Run scrape and parse for a group
• `/rlook-priority-groups` - List priority groups (scanned every 15 mins)
• `/rlook-priority-add <group>` - Add group to priority list
• `/rlook-priority-remove <group>` - Remove group from priority list

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


def cmd_group(args: str) -> Any:
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
    
    blocks: List[Dict[str, Any]] = []
    
    # Header
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": args,
            "emoji": True
        }
    })
    
    if isinstance(group, dict):
        # Locations
        if group.get("locations"):
            locations = group['locations']
            if locations:
                loc_strs = []
                for loc in locations:
                    if isinstance(loc, str):
                        loc_strs.append(loc)
                    elif isinstance(loc, dict):
                        loc_strs.append(loc.get('fqdn') or loc.get('slug') or loc.get('url') or str(loc))
                    else:
                        loc_strs.append(str(loc))
                if loc_strs:
                    # Split locations into chunks if too many for one field
                    locations_text = ", ".join(loc_strs)
                    blocks.append({
                        "type": "section",
                        "fields": [{
                            "type": "mrkdwn",
                            "text": f"*📍 Locations:*\n{locations_text}"
                        }]
                    })
        
        # Telegram
        if group.get("telegram"):
            blocks.append({
                "type": "section",
                "fields": [{
                    "type": "mrkdwn",
                    "text": f"*📱 Telegram:*\n{group['telegram']}"
                }]
            })
        
        # Description/Meta
        if group.get("meta"):
            meta = group['meta'] if isinstance(group['meta'], str) else str(group['meta'])
            # Remove HTML breaks if present
            meta = meta.replace('<br/>', '\n').replace('<br>', '\n')
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*ℹ️ Description:*\n{meta}"
                }
            })
        
        # Profile
        if group.get("profile"):
            profile = group['profile']
            if isinstance(profile, dict):
                profile_fields = []
                for key, value in profile.items():
                    val_str = str(value) if value else 'N/A'
                    profile_fields.append({
                        "type": "mrkdwn",
                        "text": f"*{key}:* {val_str}"
                    })
                
                # Split profile into sections (max 10 fields per section)
                for i in range(0, len(profile_fields), 10):
                    blocks.append({
                        "type": "section",
                        "fields": profile_fields[i:i+10]
                    })
    
    # Posts
    if posts:
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*📋 Posts ({len(posts)}):*"
            }
        })
        
        # Add all posts
        for post in posts:
            title = post.get('post_title', 'Untitled') if isinstance(post, dict) else str(post)
            discovered = post.get('discovered', '') if isinstance(post, dict) else ''
            description = post.get('description', '')[:500] if isinstance(post, dict) else ''
            link = post.get('link', '') if isinstance(post, dict) else ''
            
            post_text = f"*{title}*\n"
            if discovered:
                post_text += f"Discovered: {discovered}\n"
            if description:
                post_text += f"{description}"
            if len(post.get('description', '')) > 500:
                post_text += "..."
            
            post_block: Dict[str, Any] = {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": post_text
                }
            }
            
            if link:
                post_block["accessory"] = {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "View"
                    },
                    "url": link
                }
            
            blocks.append(post_block)
    
    # Slack has a 50 block limit, so if we exceed it, we need to truncate
    if len(blocks) > 50:
        blocks = blocks[:49]
        blocks.append({
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": "_Message truncated due to Slack block limit (50 blocks)_"
            }]
        })
    
    return {
        "blocks": blocks,
        "text": f"Group information for {args}"
    }


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


def cmd_notes_groups(_: str) -> str:
    """List all groups that have notes."""
    groups = api_get("notes/groups")
    if not groups:
        return "No groups with notes found."
    return f"*Groups with Notes ({len(groups)}):*\n" + ", ".join(sorted(groups))


def cmd_notes(args: str) -> str:
    """Get notes for a specific group."""
    if not args:
        return "Usage: /rlook-notes <group_name>"
    try:
        notes = api_get(f"notes/{args}")
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            return f"No notes found for group '{args}'."
        raise
    
    if not notes:
        return f"No notes found for group '{args}'"
    
    body = [f"*📝 Notes for {args} ({len(notes)}):*"]
    for note in notes:
        name = note.get('name', 'Untitled')
        content = note.get('content', '')
        # Truncate content for display but show it's truncated
        content_preview = content[:500] if len(content) > 500 else content
        body.append(f"\n*{name}*")
        body.append(f"```{content_preview}```")
        if len(content) > 500:
            body.append(f"_...({len(content) - 500} more characters)_")
    
    return "\n".join(body)


# RansomLook installation directory (configurable via env var or config)
RANSOMLOOK_DIR = os.getenv(
    "RANSOMLOOK_DIR",
    file_config.get("ransomlook_dir", "/opt/RansomLook")
)

# Priority groups file (groups scanned every 15 mins instead of 2 hours)
PRIORITY_GROUPS_FILE = os.getenv(
    "PRIORITY_GROUPS_FILE",
    file_config.get("priority_groups_file", "/opt/groups.txt")
)


def cmd_priority_groups(_: str) -> str:
    """List priority groups from /opt/groups.txt (scanned every 15 mins)."""
    try:
        # Read groups file from the configured path
        groups_file = Path(PRIORITY_GROUPS_FILE)
        
        if not groups_file.exists():
            return f"❌ Priority groups file not found: `{PRIORITY_GROUPS_FILE}`"
        
        with open(groups_file, 'r') as f:
            groups = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        if not groups:
            return f"📋 No priority groups configured in `{PRIORITY_GROUPS_FILE}`"
        
        body = [f"*⚡ Priority Groups ({len(groups)})*"]
        body.append(f"_These groups are scanned every 15 minutes (vs 2 hours for others)_")
        body.append(f"_File: `{PRIORITY_GROUPS_FILE}`_\n")
        
        for i, group in enumerate(groups, 1):
            body.append(f"{i}. `{group}`")
        
        return "\n".join(body)
        
    except PermissionError:
        return f"❌ Permission denied reading `{PRIORITY_GROUPS_FILE}`"
    except Exception as e:
        return f"❌ Error reading priority groups: {str(e)}"


def cmd_priority_add(args: str) -> str:
    """Add a group to the priority list."""
    if not args:
        return "Usage: /rlook-priority-add <group_name>\nExample: /rlook-priority-add lockbit3"
    
    group_name = args.strip()
    
    # Validate group name
    if not validate_group_name(group_name):
        return f"❌ Invalid group name: `{group_name}`. Only alphanumeric, dash, and underscore allowed."
    
    try:
        groups_file = Path(PRIORITY_GROUPS_FILE)
        
        # Read existing groups
        existing_groups = []
        if groups_file.exists():
            with open(groups_file, 'r') as f:
                existing_groups = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        # Check if already exists
        if group_name in existing_groups:
            return f"⚠️ Group `{group_name}` is already in the priority list."
        
        # Append to file
        with open(groups_file, 'a') as f:
            f.write(f"{group_name}\n")
        
        return f"✅ Added `{group_name}` to priority groups.\n_This group will now be scanned every 15 minutes._"
        
    except PermissionError:
        return f"❌ Permission denied writing to `{PRIORITY_GROUPS_FILE}`"
    except Exception as e:
        return f"❌ Error adding group: {str(e)}"


def cmd_priority_remove(args: str) -> str:
    """Remove a group from the priority list."""
    if not args:
        return "Usage: /rlook-priority-remove <group_name>\nExample: /rlook-priority-remove lockbit3"
    
    group_name = args.strip()
    
    try:
        groups_file = Path(PRIORITY_GROUPS_FILE)
        
        if not groups_file.exists():
            return f"❌ Priority groups file not found: `{PRIORITY_GROUPS_FILE}`"
        
        # Read all lines (preserving comments)
        with open(groups_file, 'r') as f:
            lines = f.readlines()
        
        # Find and remove the group
        new_lines = []
        removed = False
        for line in lines:
            stripped = line.strip()
            if stripped == group_name:
                removed = True
            else:
                new_lines.append(line)
        
        if not removed:
            return f"⚠️ Group `{group_name}` not found in priority list."
        
        # Write back
        with open(groups_file, 'w') as f:
            f.writelines(new_lines)
        
        return f"✅ Removed `{group_name}` from priority groups.\n_This group will now follow the standard 2-hour scan schedule._"
        
    except PermissionError:
        return f"❌ Permission denied writing to `{PRIORITY_GROUPS_FILE}`"
    except Exception as e:
        return f"❌ Error removing group: {str(e)}"


def run_scrape_async(group_name: str, channel_id: str, user_id: str) -> None:
    """Run scrape and parse commands asynchronously and post results to Slack."""
    try:
        print(f"[scrape] Starting scrape for group: {group_name}")
        
        # Run scrape command
        scrape_cmd = f"cd {RANSOMLOOK_DIR} && poetry run scrape -g {group_name}"
        print(f"[scrape] Running: {scrape_cmd}")
        
        scrape_result = subprocess.run(
            scrape_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )
        
        scrape_output = scrape_result.stdout + scrape_result.stderr
        scrape_success = scrape_result.returncode == 0
        
        # Run parse command
        parse_cmd = f"cd {RANSOMLOOK_DIR} && poetry run parse -g {group_name}"
        print(f"[scrape] Running: {parse_cmd}")
        
        parse_result = subprocess.run(
            parse_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        parse_output = parse_result.stdout + parse_result.stderr
        parse_success = parse_result.returncode == 0
        
        # Build result message
        if scrape_success and parse_success:
            status = "✅ Success"
            emoji = "white_check_mark"
        elif scrape_success:
            status = "⚠️ Scrape succeeded, Parse failed"
            emoji = "warning"
        else:
            status = "❌ Failed"
            emoji = "x"
        
        # Truncate outputs for Slack
        scrape_output_truncated = scrape_output[:1000] if scrape_output else "(no output)"
        parse_output_truncated = parse_output[:1000] if parse_output else "(no output)"
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🔄 Scrape Complete: {group_name}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Status:* {status}"},
                    {"type": "mrkdwn", "text": f"*Requested by:* <@{user_id}>"}
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Scrape Output:*\n```{scrape_output_truncated}```"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Parse Output:*\n```{parse_output_truncated}```"
                }
            }
        ]
        
        app.client.chat_postMessage(
            channel=channel_id,
            text=f"Scrape complete for {group_name}: {status}",
            blocks=blocks
        )
        print(f"[scrape] Completed for {group_name}: {status}")
        
    except subprocess.TimeoutExpired:
        app.client.chat_postMessage(
            channel=channel_id,
            text=f"❌ Scrape for `{group_name}` timed out after 10 minutes. <@{user_id}>"
        )
        print(f"[scrape] Timeout for {group_name}")
    except Exception as e:
        app.client.chat_postMessage(
            channel=channel_id,
            text=f"❌ Scrape for `{group_name}` failed with error: {str(e)[:500]}. <@{user_id}>"
        )
        print(f"[scrape] Error for {group_name}: {e}")


def validate_group_name(name: str) -> bool:
    """Validate group name to prevent command injection."""
    # Only allow alphanumeric, dash, underscore, space
    return bool(re.match(r'^[\w\s\-]+$', name)) and len(name) <= 100


def json_pretty(obj: Any) -> str:
    """Format object as pretty JSON in a code block."""
    return "```" + json.dumps(obj, indent=2, ensure_ascii=False)[:2900] + "```"


# ============================================================================
# REGISTER SLASH COMMANDS
# ============================================================================

# Help
app.command("/rlook-help")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_help))

# Admin
app.command("/rlook-priority-groups")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_priority_groups))
app.command("/rlook-priority-add")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_priority_add))
app.command("/rlook-priority-remove")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_priority_remove))

# Posts & Victims
app.command("/rlook-recent")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_recent))
app.command("/rlook-last")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_last))
app.command("/rlook-posts-period")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_posts_period))
app.command("/rlook-search")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_search))

# Groups
app.command("/rlook-groups")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_groups))
app.command("/rlook-group")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_group))

# Notes
app.command("/rlook-notes-groups")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_notes_groups))
app.command("/rlook-notes")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_notes))

# Scrape command - special handler that runs async
@app.command("/rlook-scrape")
def handle_scrape(ack, respond, command):
    """Handle the scrape command - runs scrape and parse for a group."""
    ack()
    
    group_name = command.get("text", "").strip()
    user_id = command.get("user_id", "unknown")
    channel_id = command.get("channel_id", SLACK_CHANNEL_ID)
    
    print(f"[slash] Received /rlook-scrape from {user_id} for group: {group_name}")
    
    if not group_name:
        respond("Usage: /rlook-scrape <group_name>\nExample: /rlook-scrape lockbit3")
        return
    
    # Validate group name to prevent command injection
    if not validate_group_name(group_name):
        respond(f"❌ Invalid group name: `{group_name}`. Only alphanumeric, dash, and underscore allowed.")
        return
    
    # Verify group exists
    try:
        groups = api_get("groups")
        if groups and group_name not in groups:
            respond(f"⚠️ Warning: Group `{group_name}` not found in known groups. Proceeding anyway...")
    except Exception:
        pass  # Don't block on API errors
    
    # Acknowledge and start async task
    respond(f"🔄 Starting scrape for `{group_name}`... This may take several minutes.\nYou'll be notified when complete.")
    
    # Run scrape in background thread
    threading.Thread(
        target=run_scrape_async,
        args=(group_name, channel_id, user_id),
        daemon=True
    ).start()


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
