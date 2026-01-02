
#!/usr/bin/env python3
import argparse
from pathlib import Path
from typing import Set

from ransomlook import ransomlook


def load_groups(args: argparse.Namespace) -> Set[str]:
    groups: Set[str] = set()
    if args.groups:
        groups.update({g.strip() for g in args.groups.split(',') if g.strip()})
    if args.file:
        for line in Path(args.file).read_text().splitlines():
            line = line.strip()
            if line:
                groups.add(line)
    return groups


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape RansomLook (optionally limited to specific groups)")
    parser.add_argument("-g", "--groups", help="Comma-separated list of groups to scrape")
    parser.add_argument("-f", "--file", help="Path to a file with one group per line")
    args = parser.parse_args()

    groups = load_groups(args)
    groups_filter = groups if groups else None

    print("Starting scraping")
    ransomlook.scraper(0, groups_filter=groups_filter)
    ransomlook.scraper(3, groups_filter=groups_filter)


if __name__ == '__main__':
    main()
