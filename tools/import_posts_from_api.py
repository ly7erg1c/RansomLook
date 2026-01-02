#!/usr/bin/env python3
"""
Import posts from a remote RansomLook API that exposes /posts/period and
normalize dates for all local posts (existing and newly imported).
"""
import argparse
import json
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

import redis
import requests

from ransomlook.default import get_socket_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import posts from a remote RansomLook API and normalize dates"
    )
    parser.add_argument(
        "--base-url",
        default="https://www.ransomlook.io/api",
        help="Remote API base url (default: https://www.ransomlook.io/api)",
    )
    parser.add_argument(
        "--start-date",
        default="2020-01-01",
        help="Start date (YYYY-MM-DD) for posts/period query (default: 2020-01-01)",
    )
    parser.add_argument(
        "--end-date",
        default=datetime.now().strftime("%Y-%m-%d"),
        help="End date (YYYY-MM-DD) for posts/period query (default: today)",
    )
    return parser.parse_args()


def normalize_date(date_str: str) -> str:
    """
    Ensure the discovered field is a consistent ISO string.
    """
    patterns = [
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
    ]
    dt: Optional[datetime] = None
    for pattern in patterns:
        try:
            dt = datetime.strptime(date_str, pattern)
            break
        except Exception:
            continue
    if dt is None:
        try:
            dt = datetime.fromisoformat(date_str)
        except Exception:
            return date_str
    if dt.microsecond:
        return dt.isoformat(sep=" ", timespec="microseconds")
    return dt.isoformat(sep=" ", timespec="seconds")


def fetch_remote_posts(base_url: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
    url = f"{base_url.rstrip('/')}/posts/period/{start_date}/{end_date}"
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.json()


def load_local_posts(red: redis.Redis) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {}
    for key in red.keys():
        posts = json.loads(red.get(key))  # type: ignore[arg-type]
        out[key.decode()] = posts
    return out


def dedupe_and_merge(
    existing: Dict[str, List[Dict[str, Any]]],
    incoming: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for group, posts in existing.items():
        for post in posts:
            post["discovered"] = normalize_date(str(post.get("discovered", "")))
            grouped[group].append(post)

    for post in incoming:
        group = post.get("group_name")
        if not group:
            continue
        new_post = {
            "post_title": post.get("post_title", ""),
            "discovered": normalize_date(str(post.get("discovered", ""))),
            "description": post.get("description") or "",
            "link": post.get("link"),
            "magnet": post.get("magnet"),
            "screen": post.get("screen"),
        }
        if not new_post["post_title"]:
            continue
        titles = {p.get("post_title") for p in grouped[group]}
        if new_post["post_title"] in titles:
            continue
        grouped[group].append(new_post)

    for group in grouped:
        grouped[group] = sorted(grouped[group], key=lambda p: p.get("discovered", ""))

    return grouped


def save_posts(red: redis.Redis, data: Dict[str, List[Dict[str, Any]]]) -> None:
    for group, posts in data.items():
        red.set(group, json.dumps(posts))


def main() -> None:
    args = parse_args()
    remote_posts = fetch_remote_posts(args.base_url, args.start_date, args.end_date)

    red = redis.Redis(unix_socket_path=get_socket_path("cache"), db=2)
    local_posts = load_local_posts(red)

    merged = dedupe_and_merge(local_posts, remote_posts)
    save_posts(red, merged)

    total_posts = sum(len(v) for v in merged.values())
    print(f"Imported {len(remote_posts)} remote posts.")
    print(f"Groups in cache: {len(merged)}; total posts stored: {total_posts}")


if __name__ == "__main__":
    main()
