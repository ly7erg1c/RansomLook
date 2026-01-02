#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Slack notification module for RansomLook

This module provides notification functions similar to rocket.py,
allowing RansomLook to send notifications to Slack channels.
'''
from typing import Dict, Any, Optional, List
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from .sharedutils import errlog


def get_slack_client(config: Dict[str, Any]) -> Optional[WebClient]:
    """
    Create and return a Slack WebClient instance.
    
    Args:
        config: Slack configuration dictionary containing 'bot_token'
        
    Returns:
        WebClient instance or None if configuration is invalid
    """
    bot_token = config.get('bot_token', '')
    if not bot_token:
        errlog('Slack bot_token not configured')
        return None
    return WebClient(token=bot_token)


def slacknotify(config: Dict[str, Any], group: str, title: str, description: str) -> bool:
    """
    Post a new ransomware victim notification to Slack.
    
    Args:
        config: Slack configuration dictionary
        group: Ransomware group name
        title: Victim title/name
        description: Description of the post
        
    Returns:
        True if message was sent successfully, False otherwise
    """
    if not config.get('enable', False):
        return False
        
    client = get_slack_client(config)
    if not client:
        return False
        
    channel = config.get('channel_id', '')
    if not channel:
        errlog('Slack channel_id not configured')
        return False
    
    try:
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🚨 New Ransomware Victim",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Group:*\n{group}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Victim:*\n{title}"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Description:*\n{description[:500]}{'...' if len(description) > 500 else ''}"
                }
            },
            {
                "type": "divider"
            }
        ]
        
        client.chat_postMessage(
            channel=channel,
            text=f"New post from {group}: {title}",
            blocks=blocks
        )
        return True
    except SlackApiError as e:
        errlog(f'Slack API error: {e.response["error"]}')
        return False
    except Exception as e:
        errlog(f'Cannot connect to Slack: {str(e)}')
        return False


def slacknotifyleak(config: Dict[str, Any], datas: Dict[str, Any]) -> bool:
    """
    Post a data breach leak notification to Slack.
    
    Args:
        config: Slack configuration dictionary
        datas: Data breach information dictionary
        
    Returns:
        True if message was sent successfully, False otherwise
    """
    if not config.get('enable', False):
        return False
        
    client = get_slack_client(config)
    if not client:
        return False
        
    channel = config.get('channel_id', '')
    if not channel:
        errlog('Slack channel_id not configured')
        return False
    
    try:
        name = datas.get('name', 'Unknown')
        columns = str(datas.get('columns', []))
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "💾 New Data Breach Detected",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Name:*\n{name}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Columns:*\n{columns}"
                    }
                ]
            },
            {
                "type": "divider"
            }
        ]
        
        client.chat_postMessage(
            channel=channel,
            text=f"New DataBreach leak detected: {name}",
            blocks=blocks
        )
        return True
    except SlackApiError as e:
        errlog(f'Slack API error: {e.response["error"]}')
        return False
    except Exception as e:
        errlog(f'Cannot connect to Slack: {str(e)}')
        return False


def slacknotifyrf(config: Dict[str, Any], datas: Dict[str, str]) -> bool:
    """
    Post a Recorded Future dump notification to Slack.
    
    Args:
        config: Slack configuration dictionary
        datas: Recorded Future data dictionary
        
    Returns:
        True if message was sent successfully, False otherwise
    """
    if not config.get('enable', False):
        return False
        
    client = get_slack_client(config)
    if not client:
        return False
        
    channel = config.get('channel_id', '')
    if not channel:
        errlog('Slack channel_id not configured')
        return False
    
    try:
        name = datas.get('name', 'Unknown')
        description = datas.get('description', 'No description')
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🔍 New Recorded Future Dump",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Name:*\n{name}"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Description:*\n{description}"
                }
            },
            {
                "type": "divider"
            }
        ]
        
        client.chat_postMessage(
            channel=channel,
            text=f"New Recorded Future Dump: {name}",
            blocks=blocks
        )
        return True
    except SlackApiError as e:
        errlog(f'Slack API error: {e.response["error"]}')
        return False
    except Exception as e:
        errlog(f'Cannot connect to Slack: {str(e)}')
        return False


def slacknotify_batch(config: Dict[str, Any], posts: List[Dict[str, Any]]) -> bool:
    """
    Post multiple victim notifications in a single message.
    
    Args:
        config: Slack configuration dictionary
        posts: List of post dictionaries
        
    Returns:
        True if message was sent successfully, False otherwise
    """
    if not config.get('enable', False):
        return False
        
    if not posts:
        return True
        
    client = get_slack_client(config)
    if not client:
        return False
        
    channel = config.get('channel_id', '')
    if not channel:
        errlog('Slack channel_id not configured')
        return False
    
    try:
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🚨 {len(posts)} New Ransomware Victim(s)",
                    "emoji": True
                }
            }
        ]
        
        for post in posts[:10]:  # Limit to 10 posts per message due to Slack limits
            group = post.get('group_name', 'Unknown')
            title = post.get('post_title', 'Untitled')
            discovered = post.get('discovered', '')
            description = post.get('description', '')[:200]
            
            blocks.append({
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*{group}*"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"_{discovered}_"
                    }
                ]
            })
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{title}*\n{description}{'...' if len(post.get('description', '')) > 200 else ''}"
                }
            })
            blocks.append({"type": "divider"})
        
        if len(posts) > 10:
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"_...and {len(posts) - 10} more victims_"
                    }
                ]
            })
        
        client.chat_postMessage(
            channel=channel,
            text=f"{len(posts)} new ransomware victim(s) detected",
            blocks=blocks[:-1] if blocks[-1].get('type') == 'divider' else blocks
        )
        return True
    except SlackApiError as e:
        errlog(f'Slack API error: {e.response["error"]}')
        return False
    except Exception as e:
        errlog(f'Cannot connect to Slack: {str(e)}')
        return False
