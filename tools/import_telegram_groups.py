#!/usr/bin/env python3
"""
Import Telegram groups from a file into Redis.

This script reads Telegram channel URLs from a file (one per line) and adds them
to Redis database 5, which is used by RansomLook to store Telegram channel metadata.

Usage:
    poetry run tools/import_telegram_groups.py -f telegram_groups.txt
    poetry run tools/import_telegram_groups.py -f telegram_groups.txt --dry-run
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List
from urllib.parse import urlparse

import redis

from ransomlook.default.config import get_socket_path
from ransomlook.telegram import teladder


def extract_channel_name(url: str) -> str:
    """
    Extract a channel name from a Telegram URL.
    
    Examples:
        https://t.me/channelname -> channelname
        https://t.me/joinchat/CODE -> joinchat_CODE
        https://t.me/+INVITECODE -> invite_INVITECODE
    """
    # Remove trailing slash
    url = url.rstrip('/')
    
    # Extract from public channel: https://t.me/channelname
    match = re.search(r't\.me/([^/]+)$', url)
    if match:
        name = match.group(1)
        # Remove @ if present
        if name.startswith('@'):
            name = name[1:]
        return name
    
    # Extract from joinchat: https://t.me/joinchat/CODE
    match = re.search(r't\.me/joinchat/([^/]+)', url)
    if match:
        code = match.group(1)
        return f"joinchat_{code[:10]}"  # Truncate long codes
    
    # Extract from invite: https://t.me/+CODE
    match = re.search(r't\.me/\+([^/]+)', url)
    if match:
        code = match.group(1)
        return f"invite_{code[:10]}"  # Truncate long codes
    
    # Fallback: use domain or last part of URL
    parsed = urlparse(url)
    path = parsed.path.strip('/')
    if path:
        return path.replace('/', '_')[:50]  # Limit length
    
    return "unknown_channel"


def read_telegram_urls(filename: Path) -> List[str]:
    """Read Telegram URLs from a file, one per line."""
    urls = []
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                # Validate it looks like a Telegram URL
                if 't.me' in line or line.startswith('https://t.me') or line.startswith('http://t.me'):
                    urls.append(line)
                else:
                    print(f"Warning: Skipping line that doesn't look like a Telegram URL: {line}")
    except FileNotFoundError:
        print(f"Error: File not found: {filename}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {e}")
        sys.exit(1)
    
    return urls


def import_telegram_groups(filename: Path, dry_run: bool = False) -> None:
    """
    Import Telegram groups from a file.
    
    Args:
        filename: Path to file containing Telegram URLs (one per line)
        dry_run: If True, only print what would be imported without making changes
    """
    urls = read_telegram_urls(filename)
    
    if not urls:
        print("No valid Telegram URLs found in file.")
        return
    
    print(f"Found {len(urls)} Telegram URLs in {filename}")
    
    if dry_run:
        print("\n[DRY RUN] Would import the following groups:")
        print("-" * 60)
    
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=5)
    imported = 0
    skipped = 0
    errors = 0
    
    for url in urls:
        # Extract channel name
        channel_name = extract_channel_name(url)
        
        if dry_run:
            print(f"  Name: {channel_name}")
            print(f"  URL:  {url}")
            print()
            continue
        
        # Check if already exists
        if red.exists(channel_name):
            existing = json.loads(red.get(channel_name))  # type: ignore
            existing_url = existing.get('link', '')
            if existing_url == url:
                print(f"  Skipping {channel_name}: Already exists with same URL")
                skipped += 1
                continue
            else:
                print(f"  Warning: {channel_name} exists with different URL:")
                print(f"    Existing: {existing_url}")
                print(f"    New:      {url}")
                response = input(f"  Overwrite? [y/N]: ")
                if response.lower() != 'y':
                    skipped += 1
                    continue
        
        # Add to Redis
        try:
            result = teladder(channel_name, url)
            if result == 1:
                print(f"  ✓ Added: {channel_name} -> {url}")
                imported += 1
            else:
                print(f"  ✗ Failed to add: {channel_name}")
                errors += 1
        except Exception as e:
            print(f"  ✗ Error adding {channel_name}: {e}")
            errors += 1
    
    if not dry_run:
        print("\n" + "=" * 60)
        print(f"Import complete:")
        print(f"  Imported: {imported}")
        print(f"  Skipped:  {skipped}")
        print(f"  Errors:   {errors}")
        print(f"  Total:    {len(urls)}")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Import Telegram groups from a file into RansomLook',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import from file
  poetry run tools/import_telegram_groups.py -f telegram_groups.txt
  
  # Dry run to see what would be imported
  poetry run tools/import_telegram_groups.py -f telegram_groups.txt --dry-run
  
File format:
  One Telegram URL per line. Comments (lines starting with #) are ignored.
  
  https://t.me/channelname
  https://t.me/joinchat/CODE
  https://t.me/+INVITECODE
  # This is a comment
        """
    )
    
    parser.add_argument(
        '-f', '--file',
        type=Path,
        required=True,
        help='File containing Telegram URLs (one per line)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be imported without making changes'
    )
    
    args = parser.parse_args()
    
    # Validate file exists
    if not args.file.exists():
        print(f"Error: File not found: {args.file}")
        sys.exit(1)
    
    import_telegram_groups(args.file, dry_run=args.dry_run)


if __name__ == '__main__':
    main()

