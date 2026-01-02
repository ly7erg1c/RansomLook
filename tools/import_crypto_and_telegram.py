#!/usr/bin/env python3
"""
Import crypto currency information (from ransomwhe.re) and Telegram data
from a remote RansomLook API into the local cache.
"""
import argparse
import json
from collections import OrderedDict, defaultdict
from typing import Any, Dict, List, Tuple

import redis
import requests

from ransomlook.default import get_socket_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import crypto and telegram data into the local cache"
    )
    parser.add_argument(
        "--api-base",
        default="https://www.ransomlook.io/api",
        help="Remote RansomLook API base (default: https://www.ransomlook.io/api)",
    )
    parser.add_argument(
        "--crypto-url",
        default="https://api.ransomwhe.re/export",
        help="Crypto export endpoint (default: https://api.ransomwhe.re/export)",
    )
    return parser.parse_args()


def fetch_crypto(crypto_url: str) -> Dict[str, List[Dict[str, Any]]]:
    resp = requests.get(crypto_url, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for account in data.get("result", []):
        grouped[account.get("family", "unknown")].append(account)
    return grouped


def store_crypto(red: redis.Redis, grouped: Dict[str, List[Dict[str, Any]]]) -> None:
    for family, accounts in grouped.items():
        red.set(family, json.dumps(accounts))


def fetch_api_groups(api_base: str) -> List[str]:
    url = f"{api_base.rstrip('/')}/groups"
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.json()


def fetch_group_detail(api_base: str, name: str) -> Tuple[Dict[str, Any], OrderedDict]:
    url = f"{api_base.rstrip('/')}/group/{name}"
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    if not data:
        return {}, OrderedDict()
    group_meta = data[0]
    posts = data[1] if len(data) > 1 else {}
    posts = OrderedDict(sorted(posts.items(), key=lambda t: t[0])) if isinstance(posts, dict) else OrderedDict()
    return group_meta, posts


def fetch_telegram_channels(api_base: str) -> List[str]:
    url = f"{api_base.rstrip('/')}/telegram/channels"
    resp = requests.get(url, timeout=60)
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    return resp.json()


def fetch_telegram_channel(api_base: str, name: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    url = f"{api_base.rstrip('/')}/telegram/channel/{name}"
    resp = requests.get(url, timeout=60)
    if resp.status_code == 404:
        return {}, {}
    resp.raise_for_status()
    data = resp.json()
    if not data:
        return {}, {}
    group_meta = data[0]
    posts = data[1]
    posts = OrderedDict(sorted(posts.items(), key=lambda t: t[0]))
    return group_meta, posts


def store_telegram(red_channels: redis.Redis, red_posts: redis.Redis, name: str, meta: Dict[str, Any], posts: Dict[str, Any]) -> None:
    red_channels.set(name, json.dumps(meta))
    if posts:
        red_posts.set(name, json.dumps(posts))


def main() -> None:
    args = parse_args()

    # Crypto
    print("Importing cryptocurrency data...")
    crypto_data = fetch_crypto(args.crypto_url)
    red_crypto = redis.Redis(unix_socket_path=get_socket_path("cache"), db=7)
    store_crypto(red_crypto, crypto_data)
    print(f"Stored crypto data for {len(crypto_data)} families.")

    # Telegram
    print("Importing telegram channels and messages...")
    channels = fetch_telegram_channels(args.api_base)
    red_channels = redis.Redis(unix_socket_path=get_socket_path("cache"), db=5)
    red_posts = redis.Redis(unix_socket_path=get_socket_path("cache"), db=6)
    imported = 0
    if channels:
        for name in channels:
            meta, posts = fetch_telegram_channel(args.api_base, name)
            if not meta and not posts:
                continue
            store_telegram(red_channels, red_posts, name, meta, posts)
            imported += 1
        print(f"Imported {imported} telegram channels (direct telegram API).")
        return

    print("Telegram API not available, falling back to group details...")
    groups = fetch_api_groups(args.api_base)
    for name in groups:
        meta, _ = fetch_group_detail(args.api_base, name)
        if not meta:
            continue
        telegram_field = meta.get("telegram", "")
        if not telegram_field:
            continue
        entry = {
            "name": name,
            "meta": meta.get("meta", ""),
            "link": telegram_field,
            "telegram": telegram_field,
        }
        store_telegram(red_channels, red_posts, name, entry, {})
        imported += 1
    print(f"Imported {imported} telegram channels from group metadata.")


if __name__ == "__main__":
    main()
