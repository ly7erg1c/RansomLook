#!/usr/bin/env python3
"""
Entry point for the RansomLook Slack bot.

This script starts the Slack bot which:
  - Polls for new ransomware victims and posts them to a configured Slack channel
  - Responds to slash commands for querying the RansomLook API

Configuration can be provided via:
  1. Environment variables (takes precedence)
  2. Config file at config/generic.json under the "slack" key

See SLACK_SETUP.md for detailed setup instructions.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.slack_bot import main

if __name__ == "__main__":
    main()
