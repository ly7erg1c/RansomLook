import json
import redis
import requests

from ransomlook.default.config import get_config, get_socket_path
from ransomlook.rocket import rocketnotifyrf
from ransomlook.slack import slacknotifyrf
from ransomlook.sharedutils import dbglog, stdlog

def main() -> None :

    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=10)
    keys = red.keys()

    rocketconfig = get_config('generic', 'rocketchat')
    slackconfig = get_config('generic', 'slack')

    rftoken = get_config('generic', 'rf')

    header = { "x-RFToken": rftoken,
           "Content-Type": "application/json" }

    query = { "names": [""],
          "limit": 10000}

    r_details = requests.post("https://api.recordedfuture.com/identity/metadata/dump/search", headers=header, json=query)
    temp = r_details.json()

    for entry in temp['dumps']:
        next_entry = False
        for key in keys:
            if entry['name'] == key.decode():
                next_entry = True
                continue
        if not next_entry:
            red.set(entry['name'], json.dumps(entry))
            
            # Send RocketChat notification if enabled
            if rocketconfig and rocketconfig.get('enable', False):
                try:
                    rocketnotifyrf(rocketconfig, entry)
                except Exception as e:
                    dbglog(f'RocketChat notification error: {e}')
            
            # Send Slack notification if enabled
            if slackconfig and slackconfig.get('enable', False):
                try:
                    if slacknotifyrf(slackconfig, entry):
                        stdlog(f'Slack notification sent for RF dump: {entry.get("name", "unknown")}')
                    else:
                        dbglog(f'Slack notification failed for RF dump: {entry.get("name", "unknown")}')
                except Exception as e:
                    dbglog(f'Slack notification error: {e}')


if __name__ == '__main__':
    main()
