import os
import re
import json
from bs4 import BeautifulSoup
from typing import Dict, List


def extract_projects_json(html_content: str) -> List[Dict]:
    """Extracts the `projects = [...]` JSON string from inline script."""
    match = re.search(r"const projects = (\[.*?\]);", html_content, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    return []


def main() -> List[Dict[str, str]]:
    list_div: List[Dict[str, str]] = []
    group_name = __name__.split('.')[-1]

    for filename in os.listdir('source'):
        try:
            if filename.startswith(group_name + '-'):
                html_doc = 'source/' + filename
                with open(html_doc, 'r', encoding='utf-8') as file:
                    html = file.read()

                soup = BeautifulSoup(html, 'html.parser')
                script_tags = soup.find_all('script', {'type': 'text/babel'})

                for script in script_tags:
                    if 'const projects =' in script.text:
                        victims = extract_projects_json(script.text)
                        for entry in victims:
                            title = entry.get('fullname', '').strip()
                            description = entry.get('desc', '').strip()
                            post_url = entry.get('url1', '').strip()

                            if title:
                                list_div.append({
                                    'title': title,
                                    'description': description,
                                    'link': post_url,
                                    'slug': filename
                                })
                        break  # Only parse the first matching script block
        except Exception as e:
            print(f"Error parsing {filename}: {e}")
            pass

    print(list_div)
    return list_div

