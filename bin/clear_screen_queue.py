#!/usr/bin/env python3
"""
Clear the screenshot queue (toscan) from Redis.

This removes all pending screenshot jobs, allowing fresh screenshots
to be queued as new posts are discovered.
"""
import json
import redis

from ransomlook.default.config import get_socket_path


def main() -> None:
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=1)

    if 'toscan'.encode() not in red.keys():
        print("Screenshot queue is already empty.")
        return

    # Show current queue size before clearing
    toscan = json.loads(red.get('toscan'))  # type: ignore
    queue_size = len(toscan) if toscan else 0
    print(f"Current screenshot queue size: {queue_size}")

    # Delete the queue
    red.delete('toscan')
    print("Screenshot queue cleared successfully.")


if __name__ == '__main__':
    main()

