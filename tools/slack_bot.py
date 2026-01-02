#!/usr/bin/env python3
"""
Slack bot for RansomLook
 - Posts newly discovered victims from /api/recent into a channel (polling).
 - Exposes slash commands that mirror the exposed API endpoints.

Env vars:
  SLACK_BOT_TOKEN           Bot token (starts with xoxb-)
  SLACK_SIGNING_SECRET      Slack signing secret
  SLACK_CHANNEL_ID          Channel ID to post automatic updates
  RANSOMLOOK_API_BASE       Base URL for the API (default: http://127.0.0.1:8000/api)
  RANSOMLOOK_POLL_INTERVAL  Poll interval in seconds (default: 60)
"""

import os
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Tuple

import requests
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

API_BASE = os.getenv("RANSOMLOOK_API_BASE", "http://127.0.0.1:8000/api")
POLL_INTERVAL = int(os.getenv("RANSOMLOOK_POLL_INTERVAL", "60"))
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID", "")

app = App(
    token=os.getenv("SLACK_BOT_TOKEN"),
    signing_secret=os.getenv("SLACK_SIGNING_SECRET"),
)


def api_get(path: str) -> Any:
    url = f"{API_BASE.rstrip('/')}/{path.lstrip('/')}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def format_post(post: Dict[str, Any]) -> str:
    title = post.get("post_title", "untitled")
    group = post.get("group_name", "unknown")
    discovered = post.get("discovered", "")
    descr = post.get("description", "")
    link = post.get("link")
    link_part = f" | link: {link}" if link else ""
    return f"*{group}* – {title} ({discovered}){link_part}\n{descr}"


def parse_iso(date_str: str) -> datetime:
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
        print("SLACK_CHANNEL_ID not set; skipping poller.")
        return

    last_seen: datetime = datetime.min
    first_run = True
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
                    blocks = []
                    for post in new_posts:
                        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": format_post(post)}})
                        blocks.append({"type": "divider"})
                    app.client.chat_postMessage(channel=SLACK_CHANNEL_ID, text="New victims", blocks=blocks[:-1] if blocks else None)
            first_run = False
        except Exception as exc:
            print(f"[poller] error: {exc}")
        time.sleep(POLL_INTERVAL)


def slash_reply(ack, respond, command, handler):
    ack()
    try:
        respond(handler(command["text"].strip()))
    except Exception as exc:
        respond(f"Error: {exc}")


def cmd_recent(args: str) -> str:
    count = int(args) if args else 10
    data = api_get(f"recent/{count}")
    lines = [format_post(p) for p in data[:count]]
    return "\n\n".join(lines) or "No posts."


def cmd_last(args: str) -> str:
    days = int(args) if args else 1
    data = api_get(f"last/{days}")
    lines = [format_post(p) for p in data]
    return "\n\n".join(lines) or f"No posts in last {days} day(s)."


def cmd_groups(_: str) -> str:
    groups = api_get("groups")
    return f"Groups ({len(groups)}): " + ", ".join(groups)


def cmd_group(args: str) -> str:
    if not args:
        return "Usage: /rlook-group <name>"
    group, posts = api_get(f"group/{args}")
    if not group:
        return f"No data for {args}"
    body = [f"*{args}*"]
    if group.get("telegram"):
        body.append(f"telegram: {group['telegram']}")
    if group.get("meta"):
        body.append(group["meta"])
    if posts:
        body.append(f"Recent posts ({len(posts)}):")
        for post in posts[:5]:
            body.append(f"- {post.get('post_title')} ({post.get('discovered')})")
    return "\n".join(body)


def cmd_markets(_: str) -> str:
    markets = api_get("markets")
    return f"Markets ({len(markets)}): " + ", ".join(markets)


def cmd_leaks(_: str) -> str:
    leaks = api_get("leaks/leaks")
    body = [f"Breaches ({len(leaks)}):"]
    body.extend([f"- {l['id']}: {l['name']}" for l in leaks])
    return "\n".join(body)


def cmd_leak(args: str) -> str:
    if not args:
        return "Usage: /rlook-leak <id>"
    leak = api_get(f"leaks/leaks/{args}")
    return json_pretty(leak)


def cmd_rf_leaks(_: str) -> str:
    leaks = api_get("rf/leaks")
    return f"RF leaks ({len(leaks)}): " + ", ".join(leaks)


def cmd_rf_leak(args: str) -> str:
    if not args:
        return "Usage: /rlook-rf-leak <name>"
    leak = api_get(f"rf/leak/{args}")
    return json_pretty(leak)


def cmd_telegram_channels(_: str) -> str:
    chans = api_get("telegram/channels")
    return f"Telegram channels ({len(chans)}): " + ", ".join(chans)


def cmd_telegram(args: str) -> str:
    if not args:
        return "Usage: /rlook-telegram <name>"
    data = api_get(f"telegram/channel/{args}")
    if not data:
        return f"No data for {args}"
    meta, posts = data
    body = [f"*{args}*"]
    if meta.get("meta"):
        body.append(meta["meta"])
    if posts:
        body.append("Posts:")
        for ts, post in list(posts.items())[:5]:
            text = post if isinstance(post, str) else post.get("message", "")
            body.append(f"- {ts}: {text[:120]}")
    return "\n".join(body)


def json_pretty(obj: Any) -> str:
    import json
    return "```" + json.dumps(obj, indent=2, ensure_ascii=False) + "```"


# Slash commands
app.command("/rlook-recent")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_recent))
app.command("/rlook-last")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_last))
app.command("/rlook-groups")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_groups))
app.command("/rlook-group")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_group))
app.command("/rlook-markets")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_markets))
app.command("/rlook-leaks")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_leaks))
app.command("/rlook-leak")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_leak))
app.command("/rlook-rf-leaks")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_rf_leaks))
app.command("/rlook-rf-leak")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_rf_leak))
app.command("/rlook-telegram-channels")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_telegram_channels))
app.command("/rlook-telegram")(lambda ack, respond, command: slash_reply(ack, respond, command, cmd_telegram))


def main() -> None:
    threading.Thread(target=poll_recent, daemon=True).start()
    handler = SocketModeHandler(app, os.getenv("SLACK_APP_TOKEN"))
    handler.start()


if __name__ == "__main__":
    main()
