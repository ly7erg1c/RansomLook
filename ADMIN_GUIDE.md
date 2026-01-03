# RansomLook Administration Guide

This comprehensive guide covers all aspects of administering and extending RansomLook, including creating scrapers, adding groups, managing users, and configuring integrations.

## Table of Contents

1. [Creating Scrapers (Parsers)](#creating-scrapers-parsers)
2. [Verifying Scrapers Work](#verifying-scrapers-work)
3. [Adding New Groups](#adding-new-groups)
4. [Adding Sites/Domains to Groups](#adding-sitesdomains-to-groups)
5. [Adding Notes](#adding-notes)
6. [Managing Users](#managing-users)
7. [Adding Telegram Groups](#adding-telegram-groups)
8. [Adding Twitter Accounts](#adding-twitter-accounts)
9. [Priority Groups](#priority-groups)
10. [Troubleshooting](#troubleshooting)

---

## Creating Scrapers (Parsers)

Scrapers in RansomLook are Python modules that parse HTML files downloaded from ransomware group websites. Each parser extracts victim information (title, description, link) from the scraped HTML.

### Parser Location

All parsers are located in `ransomlook/parsers/` directory. Each parser is a Python file named after the group (e.g., `lockbit3.py`, `qilin.py`).

### Parser Structure

A parser must:
1. Be a Python file in `ransomlook/parsers/`
2. Have a `main()` function that returns `List[Dict[str, str]]`
3. Read HTML files from the `source/` directory
4. Extract and return structured data

### Basic Parser Template

```python
import os
from bs4 import BeautifulSoup
from typing import Dict, List

def main() -> List[Dict[str, str]]:
    """
    Parse HTML files for a ransomware group.
    
    Returns:
        List of dictionaries containing:
        - title: Victim name/title
        - description: Description of the victim
        - link: URL to the victim's page
        - slug: Source filename (automatically set)
    """
    list_div = []
    
    # Iterate through all HTML files in source/ directory
    for filename in os.listdir('source'):
        try:
            # Files are named: {groupname}-{domain}.html
            # e.g., lockbit3-onion123.onion.html
            if filename.startswith(__name__.split('.')[-1] + '-'):
                html_doc = 'source/' + filename
                file = open(html_doc, 'r', encoding='utf-8')
                soup = BeautifulSoup(file, 'html.parser')
                
                # Find all victim entries (adjust selectors for your group)
                divs_name = soup.find_all('div', {"class": "victim-entry"})
                
                for div in divs_name:
                    # Extract title
                    title = div.find('h2').text.strip()
                    
                    # Extract description (if available)
                    desc_elem = div.find('p', {"class": "description"})
                    description = desc_elem.text.strip() if desc_elem else ''
                    
                    # Extract link
                    link_elem = div.find('a')
                    link = link_elem['href'] if link_elem else ''
                    
                    # Add to results
                    list_div.append({
                        "title": title,
                        "description": description,
                        "link": link,
                        "slug": filename  # Required: source filename
                    })
                
                file.close()
        except Exception as e:
            print(f"Failed during parsing of {filename}: {e}")
            pass
    
    print(list_div)  # Debug output
    return list_div
```

### Parser Naming Convention

**Critical**: The parser filename must match the group name exactly (case-sensitive). For example:
- Group name: `lockbit3` → Parser: `lockbit3.py`
- Group name: `qilin` → Parser: `qilin.py`
- Group name with spaces: `space bears` → Parser: `space bears.py`

### Example: LockBit 3 Parser

```python
import os
from bs4 import BeautifulSoup
from typing import Dict, List

def main() -> List[Dict[str, str]]:
    list_div = []
    
    for filename in os.listdir('source'):
        try:
            if filename.startswith(__name__.split('.')[-1] + '-'):
                html_doc = 'source/' + filename
                file = open(html_doc, 'r')
                soup = BeautifulSoup(file, 'html.parser')
                
                # LockBit uses post-block classes
                divs_name = soup.find_all('div', {"class": "post-block bad"})
                for div in divs_name:
                    title = div.find('div', {"class": "post-title"}).text.strip()
                    description = div.find('div', {"class": "post-block-text"}).text.strip()
                    link = div['onclick'].split("'")[1]
                    list_div.append({
                        "title": title,
                        "description": description,
                        "link": link,
                        "slug": filename
                    })
                
                # Also check for "good" posts
                divs_name = soup.find_all('div', {"class": "post-block good"})
                for div in divs_name:
                    title = div.find('div', {"class": "post-title"}).text.strip()
                    description = div.find('div', {"class": "post-block-text"}).text.strip()
                    link = div['onclick'].split("'")[1]
                    list_div.append({
                        "title": title,
                        "description": description,
                        "link": link,
                        "slug": filename
                    })
                
                file.close()
        except Exception as e:
            print(f"Failed during: {filename} - {e}")
            pass
    
    print(list_div)
    return list_div
```

### Parser Best Practices

1. **Error Handling**: Always wrap parsing logic in try/except blocks
2. **Encoding**: Use UTF-8 encoding when reading files
3. **Multiple Selectors**: Some groups have different post types (e.g., "bad" and "good" posts)
4. **Missing Fields**: Handle cases where description or link might be missing
5. **Debugging**: Use `print()` statements to debug (output goes to logs)

### Common Parsing Patterns

#### Pattern 1: Simple List
```python
divs = soup.find_all('div', {"class": "victim"})
for div in divs:
    title = div.find('h3').text.strip()
    link = div.find('a')['href']
```

#### Pattern 2: Table Rows
```python
rows = soup.find_all('tr')
for row in rows:
    cells = row.find_all('td')
    if len(cells) >= 2:
        title = cells[0].text.strip()
        link = cells[1].find('a')['href']
```

#### Pattern 3: JavaScript Links
```python
# Some sites use onclick handlers
link = div['onclick'].split("'")[1]  # Extract from onclick="openPage('url')"
```

#### Pattern 4: Relative Links
```python
# Convert relative links to absolute
if link.startswith('/'):
    base_url = 'https://example.onion'
    link = base_url + link
```

---

## Verifying Scrapers Work

### Step 1: Manual HTML Download

Before creating a parser, manually download the HTML from the ransomware site:

```bash
# Download HTML to source/ directory
cd /path/to/RansomLook
mkdir -p source
# Manually save the page HTML as: {groupname}-{domain}.html
# e.g., lockbit3-onion123.onion.html
```

### Step 2: Test Parser Locally

Create a test script to verify your parser:

```python
#!/usr/bin/env python3
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Change to source directory
os.chdir('source')

# Import and test parser
from ransomlook.parsers.yourgroup import main

results = main()
print(f"Found {len(results)} victims")
for result in results:
    print(f"  - {result['title']}")
```

### Step 3: Run Full Scrape and Parse

```bash
# Scrape the group (downloads HTML)
poetry run scrape -g yourgroup

# Parse the downloaded HTML
poetry run parse -g yourgroup

# Check if posts were added
poetry run python3 -c "
from ransomlook.default.config import get_socket_path
import redis, json
red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=2)
posts = json.loads(red.get('yourgroup'))
print(f'Found {len(posts)} posts')
"
```

### Step 4: Verify in Web Interface

1. Start RansomLook: `poetry run start`
2. Navigate to: `http://localhost:8000/group/yourgroup`
3. Verify posts appear correctly

### Step 5: Check Logs

```bash
# View parse logs
tail -f logs/parse.log

# Check for errors
grep -i error logs/parse.log
```

### Common Issues

1. **No posts found**: Check if filename matches group name exactly
2. **Parser not found**: Ensure file is in `ransomlook/parsers/` and named correctly
3. **HTML structure changed**: Re-download HTML and update selectors
4. **Encoding errors**: Add `encoding='utf-8'` to file open calls

---

## Adding New Groups

### Method 1: Web Interface (Recommended)

1. Log in to the admin interface: `http://localhost:8000/login`
2. Navigate to Admin → Add Group
3. Fill in the form:
   - **Database**: Select `Group` (0) or `Market` (3)
   - **Group name**: Must match parser filename exactly (if parser exists)
   - **URL**: Full URL to the ransomware site
   - **File server**: Check if site has file download capability
   - **Chat**: Check if site has chat functionality
   - **Admin**: Check if site has admin panel
   - **Private DLS**: Check if this is a private data leak site
   - **Browser**: Select browser for scraping (chrome/firefox/webkit)
   - **Init Script**: Optional JavaScript to run before capture
4. Click "Add"

### Method 2: Command Line

```bash
poetry run add GROUPNAME URL DATABASE-NUMBER
```

Parameters:
- `GROUPNAME`: Group name (must match parser filename if parser exists)
- `URL`: Full URL to the ransomware site (e.g., `http://example.onion`)
- `DATABASE-NUMBER`: 
  - `0` for Ransomware Groups
  - `3` for Markets

Example:
```bash
poetry run add lockbit3 http://lockbitapizxkm5ecxq7z7h6vq3q4x3q7z7h6vq3q4.onion 0
```

### Group Name Requirements

- Must be lowercase (converted automatically)
- Must match parser filename exactly (if parser exists)
- Only alphanumeric, spaces, dashes, and underscores allowed
- Examples: `lockbit3`, `qilin`, `space bears`, `ra-group`

### Adding Groups with Parsers

If you've created a parser:

1. Ensure parser filename matches group name exactly
2. Add the group using web interface or command line
3. The parser will automatically be used during parsing

### Adding Groups without Parsers

Groups can be added without parsers, but posts won't be automatically extracted. You can:
- Manually add posts via the web interface
- Create a parser later and it will be used automatically

---

## Adding Sites/Domains to Groups

Groups can have multiple sites/domains (mirrors, relays, or different URLs).

### Method 1: Web Interface

1. Log in to admin interface
2. Navigate to Admin → Edit
3. Select the group from the dropdown
4. Click "Edit this group"
5. Scroll to "Links" section
6. Click "Add Link"
7. Enter:
   - **URL**: New site URL
   - **File server**: If applicable
   - **Chat**: If applicable
   - **Admin**: If applicable
   - **Private**: If this is a private mirror
8. Click "Save changes"

### Method 2: Command Line (Advanced)

Use the `adder` function programmatically or modify the Redis database directly.

### Location Schema

Each location (site/domain) has the following structure:

```json
{
  "fqdn": "example.onion",
  "title": null,
  "timeout": null,
  "delay": null,
  "version": 3,
  "slug": "http://example.onion",
  "available": false,
  "updated": "2025-01-15 10:30:00",
  "fs": false,
  "chat": false,
  "admin": false,
  "browser": null,
  "init_script": null,
  "private": false,
  "lastscrape": "Never"
}
```

### Private Locations

Mark locations as "private" to:
- Hide them from public API responses
- Exclude them from public web interface
- Keep them for internal monitoring only

---

## Adding Notes

Notes are additional information about ransomware groups, stored separately from group metadata.

### Notes Source

Notes are automatically imported from the ThreatLabs ransomware notes repository:
- Repository: `https://github.com/threatlabz/ransomware_notes`
- Stored in Redis database 11
- Key format: `{group_name}` (lowercase)
- Value format: JSON array of note objects

### Manual Note Import

```bash
poetry run bin/notes.py
```

This command:
1. Clones the ThreatLabs repository
2. Reads note files from each group folder
3. Stores them in Redis (db=11)

### Note Structure

Each note entry:
```json
{
  "name": "filename.md",
  "content": "Note content here..."
}
```

### Adding Custom Notes

To add custom notes, you can:

1. **Modify Redis directly** (advanced):
```python
import redis
import json
from ransomlook.default.config import get_socket_path

red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=11)

# Get existing notes
existing = json.loads(red.get('groupname') or '[]')

# Add new note
existing.append({
    'name': 'custom_note.md',
    'content': 'Your note content here...'
})

# Save back
red.set('groupname', json.dumps(existing))
```

2. **Fork and contribute to ThreatLabs repository** (recommended):
   - Fork: https://github.com/threatlabz/ransomware_notes
   - Add notes in appropriate group folder
   - Submit pull request

### Viewing Notes

- Web interface: `http://localhost:8000/notes/{groupname}`
- API: `GET /api/notes/{groupname}`
- Slack bot: `/rlook-notes {groupname}`

---

## Managing Users

RansomLook supports multiple authentication methods: local users and LDAP.

### Local Users

Local users are configured in `config/generic.json` under the `users` key.

#### Adding a User

Edit `config/generic.json`:

```json
{
  "users": {
    "admin": "password123",
    "analyst": "securepassword456",
    "viewer": ["viewerpass", "64-character-sha256-token-here"]
  }
}
```

**User Format Options:**

1. **Simple password** (username: password):
```json
"admin": "password123"
```

2. **Password with custom auth token** (username: [password, token]):
```json
"analyst": ["password123", "a1b2c3d4e5f6...64-char-hex-token"]
```

The auth token is a 64-character hexadecimal string (SHA256 hash). If not provided, one is automatically generated.

#### Generating Auth Token

```python
import hashlib
from ransomlook.default.config import get_config

def get_secret_key():
    # Read from secret_key file or generate
    pass

password = "yourpassword"
secret_key = get_secret_key()
auth_token = hashlib.pbkdf2_hmac('sha256', secret_key, password.encode(), 100000).hex()
print(auth_token)  # 64-character token
```

#### User Permissions

All local users have the same permissions:
- Access to admin interface
- Add/edit/delete groups
- Add/edit/delete posts
- View logs
- Manage alerts

#### Removing a User

Simply remove the entry from `config/generic.json`:

```json
{
  "users": {
    "admin": "password123"
    // Remove other users
  }
}
```

### LDAP Authentication

Configure LDAP in `config/generic.json`:

```json
{
  "ldap": {
    "enable": true,
    "server": "ldaps://ldap.example.com",
    "root_dn": "ou=Users,dc=example,dc=com",
    "base_dn": "uid",
    "ssl": true,
    "verify": true,
    "cert": "/path/to/cert.pem"
  }
}
```

When LDAP is enabled:
- Local users are disabled
- All authentication goes through LDAP
- Users authenticate with LDAP credentials
- Permissions are the same for all authenticated users

### Multiple Users Best Practices

1. **Use strong passwords**: Minimum 12 characters, mixed case, numbers, symbols
2. **Rotate passwords regularly**: Update passwords in config file
3. **Use LDAP for enterprise**: Centralized user management
4. **Limit admin access**: Only grant access to trusted users
5. **Monitor logs**: Check `logs/` directory for authentication attempts

### User Management via API

Users can authenticate via API using:
- Basic authentication (username/password)
- Token authentication (username/token)

API endpoints require authentication for admin operations.

---

## Adding Telegram Groups

RansomLook can monitor Telegram channels for ransomware-related content. Telegram groups are stored in Redis database 5 with the structure: `{'name': name, 'meta': None, 'link': url}`.

### Method 1: Import from File (Recommended)

Create a file with Telegram URLs (one per line):

```bash
# Create telegram_groups.txt
cat > telegram_groups.txt << EOF
https://t.me/channelname
https://t.me/joinchat/INVITE_CODE
https://t.me/+INVITE_CODE
# Comments start with #
EOF
```

Import the groups:

```bash
# Import from file
poetry run tools/import_telegram_groups.py -f telegram_groups.txt

# Dry run to preview what will be imported
poetry run tools/import_telegram_groups.py -f telegram_groups.txt --dry-run
```

The script will:
- Extract channel names from URLs automatically
- Skip duplicates (same name and URL)
- Prompt before overwriting existing entries with different URLs
- Show import statistics

**URL Formats Supported:**
- Public channels: `https://t.me/channelname` → name: `channelname`
- Join chat: `https://t.me/joinchat/CODE` → name: `joinchat_CODE`
- Invite links: `https://t.me/+CODE` → name: `invite_CODE`

### Method 2: Web Interface

1. Log in to admin interface: `http://localhost:8000/login`
2. Navigate to Admin → Add Group
3. Select **Database**: `Telegram` (5)
4. Enter:
   - **Group name**: Channel identifier (e.g., `lockbit_telegram`)
   - **URL**: Telegram channel URL
5. Click "Add"

### Method 3: Command Line (Single Group)

Use the `teladder` function programmatically or via Python:

```python
from ransomlook.telegram import teladder

# Add a single Telegram group
result = teladder("channel_name", "https://t.me/channelname")
if result == 1:
    print("Successfully added")
```

### Telegram Configuration

Telegram scraping uses Playwright to scrape Telegram web interface. No API credentials are required for basic scraping, but you can configure additional settings in `config/generic.json` if needed.

### Running Telegram Scraper

```bash
# Scrape all Telegram channels
poetry run telegram
```

This will:
1. Read all channels from Redis (db=5)
2. Scrape each channel's web page using Playwright
3. Store HTML in `source/telegram/{channelname}.html`
4. Store screenshots in `source/screenshots/telegram/{channelname}.png`
5. Parse messages and store in Redis (db=6 for posts)

### Telegram Database Structure

- **Database 5**: Channel metadata
  ```json
  {
    "name": "channelname",
    "meta": "Channel Title",
    "link": "https://t.me/channelname"
  }
  ```
- **Database 6**: Channel posts/messages (timestamped)

### Viewing Telegram Data

- Web interface: `http://localhost:8000/telegrams`
- API: `GET /api/telegram/channels`
- Individual channel: `http://localhost:8000/telegram/{channelname}`
- API channel details: `GET /api/telegram/channel/{channelname}`

### Telegram Group Naming

Channel names are automatically extracted from URLs:
- Public channels use the channel name directly
- Private channels use `joinchat_` or `invite_` prefix with code
- Names are used as Redis keys (case-sensitive)
- Avoid special characters (they're sanitized automatically)

### Managing Existing Telegram Groups

**List all Telegram groups:**
```bash
poetry run python3 -c "
from ransomlook.default.config import get_socket_path
import redis, json
red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=5)
for key in red.keys():
    data = json.loads(red.get(key))
    print(f\"{key.decode()}: {data.get('link')}\")
"
```

**Remove a Telegram group:**
```bash
poetry run python3 -c "
from ransomlook.default.config import get_socket_path
import redis
red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=5)
red.delete('channelname')  # Replace with actual channel name
print('Deleted')
"
```

---

## Adding Twitter Accounts

RansomLook can monitor Twitter/X accounts for ransomware-related content.

### Twitter Configuration

Configure Twitter API credentials in `config/generic.json`:

```json
{
  "twitter": {
    "enable": true,
    "consumer_key": "YOUR_CONSUMER_KEY",
    "consumer_secret": "YOUR_CONSUMER_SECRET",
    "access_token": "YOUR_ACCESS_TOKEN",
    "access_token_secret": "YOUR_ACCESS_TOKEN_SECRET"
  }
}
```

**Getting Twitter API Credentials:**

1. Go to https://developer.twitter.com/
2. Create a developer account
3. Create a new app
4. Generate API keys and tokens
5. Copy credentials to config file

### Adding Twitter Accounts

Twitter accounts are added via the web interface:

1. Log in to admin interface
2. Navigate to Admin → Add Group
3. Select **Database**: `Twitter` (8)
4. Enter:
   - **Group name**: Twitter handle (without @) or identifier
   - **URL**: Twitter profile URL (e.g., `https://twitter.com/username`)
5. Click "Add"

### Running Twitter Scraper

```bash
# Scrape Twitter accounts
poetry run twitter
```

This will:
1. Connect to Twitter API
2. Scrape tweets from all configured accounts
3. Store tweets in Redis (db=8)
4. Parse tweets for victim information

### Twitter Database Structure

- **Database 8**: Twitter account metadata and tweets

### Viewing Twitter Data

- Web interface: `http://localhost:8000/twitters`
- Individual account: `http://localhost:8000/twitter/{accountname}`

### Twitter Rate Limits

Twitter API has rate limits:
- Monitor API usage
- Implement delays between requests if needed
- Consider using Twitter API v2 for higher limits

---

## Priority Groups

Priority groups are scanned more frequently (every 15 minutes) compared to regular groups (every 2 hours).

### Priority Groups File

Priority groups are listed in `groups.txt` (one group name per line):

```
lockbit3
qilin
medusa
```

### Adding a Priority Group

**Method 1: Edit groups.txt**
```bash
echo "newgroup" >> groups.txt
```

**Method 2: Via Slack Bot** (if configured)
```
/rlook-priority-add newgroup
```

**Method 3: Web Interface** (if implemented)
- Navigate to admin interface
- Find priority groups management section

### Removing a Priority Group

**Method 1: Edit groups.txt**
```bash
# Remove the line containing the group name
sed -i '/^groupname$/d' groups.txt
```

**Method 2: Via Slack Bot**
```
/rlook-priority-remove groupname
```

### Priority Groups Configuration

The priority groups file path is configurable:

**Environment variable:**
```bash
export PRIORITY_GROUPS_FILE="/opt/groups.txt"
```

**Config file (`config/generic.json`):**
```json
{
  "slack": {
    "priority_groups_file": "/opt/groups.txt"
  }
}
```

### Scraping Priority Groups

Priority groups are automatically scraped more frequently when using the scraper with filtering:

```bash
# Scrape only priority groups
poetry run scrape -f groups.txt
```

Or in cron:
```bash
# Every 15 minutes
*/15 * * * * cd /opt/RansomLook && poetry run scrape -f groups.txt

# Every 2 hours for all groups
0 */2 * * * cd /opt/RansomLook && poetry run scrape
```

---

## Troubleshooting

### Parser Issues

**Problem**: Parser not being used
- **Solution**: Ensure parser filename matches group name exactly (case-sensitive)

**Problem**: No posts extracted
- **Solution**: 
  1. Check HTML structure hasn't changed
  2. Verify selectors in parser
  3. Check logs for errors
  4. Manually inspect downloaded HTML in `source/` directory

**Problem**: Parser errors
- **Solution**: 
  1. Add try/except blocks around parsing logic
  2. Check for missing HTML elements
  3. Verify file encoding (use UTF-8)

### Group Issues

**Problem**: Group not appearing in web interface
- **Solution**: 
  1. Check if group is marked as "private" (only visible when logged in)
  2. Verify group was added to correct database (0 for groups, 3 for markets)
  3. Check Redis connection

**Problem**: Sites not being scraped
- **Solution**: 
  1. Verify Tor is running: `sudo systemctl status tor`
  2. Check site availability
  3. Review scrape logs
  4. Verify site URL is correct

### User Issues

**Problem**: Cannot log in
- **Solution**: 
  1. Verify username/password in `config/generic.json`
  2. Check `secret_key` file exists and is readable
  3. Clear browser cookies
  4. Check LDAP configuration if using LDAP

**Problem**: User has no permissions
- **Solution**: All authenticated users have full admin access. If issues persist, check:
  1. User is in `users` config
  2. LDAP is properly configured (if using)
  3. Session hasn't expired

### Telegram Issues

**Problem**: Telegram scraper not working
- **Solution**: 
  1. Verify API credentials are correct
  2. Check phone number is verified
  3. Ensure `telegram_groups.txt` exists and has valid URLs
  4. Check Telegram API rate limits

**Problem**: No messages scraped
- **Solution**: 
  1. Verify channel URLs are accessible
  2. Check if channels are private (may need invite)
  3. Review Telegram API logs

### Twitter Issues

**Problem**: Twitter scraper not working
- **Solution**: 
  1. Verify API credentials are correct
  2. Check Twitter API status
  3. Verify rate limits haven't been exceeded
  4. Check account URLs are valid

### General Issues

**Problem**: Redis connection errors
- **Solution**: 
  1. Verify Valkey/Redis is running
  2. Check socket path: `get_socket_path('cache')`
  3. Verify permissions on socket file

**Problem**: Scraping takes too long
- **Solution**: 
  1. Reduce number of threads in config
  2. Use priority groups for important groups only
  3. Check network connectivity
  4. Verify Tor proxy is working

---

## Additional Resources

- **Main Repository**: https://github.com/RansomLook/RansomLook
- **Official Instance**: https://www.ransomlook.io
- **ThreatLabs Notes**: https://github.com/threatlabz/ransomware_notes
- **Slack Setup**: See `SLACK_SETUP.md`

## Support

For issues and questions:
1. Check this guide first
2. Review logs in `logs/` directory
3. Check GitHub issues: https://github.com/RansomLook/RansomLook/issues
4. Review code comments and docstrings

---

*Last updated: January 2025*

