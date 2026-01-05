#!/usr/bin/env python3
"""
Script to import new groups from ransomware.live into RansomLook.
Run this on your remote RansomLook instance.

Usage:
    cd /path/to/RansomLook
    poetry run python tools/import_new_groups.py
"""

import json
import redis
from pathlib import Path

# Try to import from ransomlook config, fall back to manual path
try:
    from ransomlook.default.config import get_socket_path
    REDIS_SOCKET = get_socket_path('cache')
except ImportError:
    # Fallback - adjust this path for your setup
    REDIS_SOCKET = str(Path(__file__).parent.parent / 'cache' / 'cache.sock')

# New groups to add (db=0 for ransomware groups)
# Format: (name, url, db)
# db=0: Groups, db=3: Markets
NEW_GROUPS = [
    # blacklock - Extracts from inline JavaScript projects JSON
    {
        'name': 'blacklock',
        'url': 'http://zdkexsh2e7yihw5uhg5hpsgq3dois2m5je7lzfagij2y6iw5ptl35gyd.onion',
        'db': 0,
        'note': 'Status: Currently unavailable according to ransomware.live'
    },
    # flocker - WordPress-style blog entries
    {
        'name': 'flocker',
        'url': 'http://flock4cvoeqm4c62gyohvmncx6ck2e7ugvyqgyxqtrumklhd5ptwzpqd.onion',
        'db': 0,
        'note': 'Status: Currently unavailable according to ransomware.live'
    },
    # medusalocker - Different from medusa, parses article elements
    {
        'name': 'medusalocker',
        'url': 'http://medusaxko7jxtrojdkxo66j7ck4q5tgktf7uqsqyfry4ebnxlcbkccyd.onion/',
        'db': 0,
        'note': 'Status: Currently unavailable according to ransomware.live'
    },
    # rebornvc - Parses .card divs with company/ransom info
    {
        'name': 'rebornvc',
        'url': 'http://ransomed.vc',
        'db': 0,
        'note': 'Status: Available according to ransomware.live'
    },
    # silentransomgroup - Parses .block_1 tables
    {
        'name': 'silentransomgroup',
        'url': 'https://business-data-leaks.com/',
        'db': 0,
        'note': 'Status: Currently unavailable according to ransomware.live'
    },
    # datavault - Parses .main_block divs
    # NOTE: No URL found in ransomware.live API - you'll need to add this manually
    # when the URL is known. Uncomment and update the URL when available:
    # {
    #     'name': 'datavault',
    #     'url': 'http://UNKNOWN_URL.onion',
    #     'db': 0,
    #     'note': 'URL not found in ransomware.live - add manually when known'
    # },
]


def add_group(red: redis.Redis, name: str, url: str) -> bool:
    """Add a new group to Redis."""
    key = name.encode()
    
    # Check if group already exists
    if red.exists(key):
        existing = json.loads(red.get(key))  # type: ignore
        print(f"  Group '{name}' already exists with locations: {existing.get('locations', [])}")
        
        # Check if URL already in locations
        locations = existing.get('locations', [])
        if url in locations:
            print(f"  URL already registered, skipping.")
            return False
        
        # Add new URL to existing locations
        locations.append(url)
        existing['locations'] = locations
        red.set(key, json.dumps(existing))
        print(f"  Added new URL to existing group.")
        return True
    
    # Create new group entry
    group_data = {
        'locations': [url],
        'captcha': False,
        'parser': True,
        'javascript_render': False,
        'meta': None,
        'profile': []
    }
    
    red.set(key, json.dumps(group_data))
    print(f"  Created new group '{name}'")
    return True


def main() -> None:
    print("=" * 60)
    print("RansomLook - Import New Groups")
    print("=" * 60)
    print(f"\nConnecting to Redis at: {REDIS_SOCKET}")
    
    # Track statistics
    added = 0
    skipped = 0
    failed = 0
    
    for group_info in NEW_GROUPS:
        name = group_info['name']
        url = group_info['url']
        db = group_info['db']
        note = group_info.get('note', '')
        
        print(f"\n[{name}]")
        print(f"  URL: {url}")
        print(f"  DB: {db}")
        if note:
            print(f"  Note: {note}")
        
        try:
            red = redis.Redis(unix_socket_path=REDIS_SOCKET, db=db)
            red.ping()  # Test connection
            
            if add_group(red, name, url):
                added += 1
            else:
                skipped += 1
                
        except redis.ConnectionError as e:
            print(f"  ERROR: Could not connect to Redis: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Summary: {added} added, {skipped} skipped, {failed} failed")
    print("=" * 60)
    
    print("\n⚠️  NOTES:")
    print("1. 'datavault' was NOT added - no URL found in ransomware.live")
    print("   Add it manually when the URL is known:")
    print("   poetry run add datavault <onion_url> 0")
    print("\n2. Most groups are currently marked as unavailable.")
    print("   The scraper will attempt to fetch them anyway.")
    print("\n3. To scrape a specific group:")
    print("   poetry run scrape -g <groupname>")
    print("   poetry run parse -g <groupname>")


if __name__ == '__main__':
    main()

