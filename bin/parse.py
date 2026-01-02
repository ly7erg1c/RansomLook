#!/usr/bin/env python3
#!/usr/bin/env python3
import argparse
import glob
import importlib
import json
from os.path import basename, dirname, isfile, join
from typing import Any, Dict, List, Optional, Union, Set

from datetime import datetime
from datetime import timedelta

import redis

from ransomlook.default.config import get_config, get_socket_path
from ransomlook.posts import appender
from ransomlook.sharedutils import dbglog, stdlog, errlog, statsgroup, run_data_viz


def load_groups(args: argparse.Namespace) -> Set[str]:
    groups: Set[str] = set()
    if args.groups:
        groups.update({g.strip() for g in args.groups.split(',') if g.strip()})
    if args.file:
        with open(args.file, "r") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    groups.add(line)
    return groups


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse groups (optionally limited to specific parsers)")
    parser.add_argument("-g", "--groups", help="Comma-separated list of groups to parse")
    parser.add_argument("-f", "--file", help="Path to a file with one group per line")
    args = parser.parse_args()

    groups_filter = load_groups(args)

    modules = glob.glob(join(dirname('ransomlook/parsers/'), "*.py"))
    __all__ = [basename(f)[:-3] for f in modules if isfile(f) and not f.endswith('__init__.py')]
    if groups_filter:
        __all__ = [name for name in __all__ if name in groups_filter]

    for parser_name in __all__:
        module = importlib.import_module(f'ransomlook.parsers.{parser_name}')
        print('\nParser : ' + parser_name)

        try:
            for entry in module.main():
                appender(entry, parser_name)
        except Exception as e:
            print("Error with : " + parser_name)
            print(e)
            pass
    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=2)
    for key in red.keys():
        statsgroup(key)
    run_data_viz(7)
    run_data_viz(14)
    run_data_viz(30)
    run_data_viz(90)


if __name__ == '__main__':
    main()
