import os
from bs4 import BeautifulSoup
from typing import Dict, List


def main() -> List[Dict[str, str]]:
    list_div: List[Dict[str, str]] = []
    group_name = __name__.split('.')[-1]

    for filename in os.listdir('source'):
        try:
            if filename.startswith(group_name + '-'):
                html_doc = 'source/' + filename
                file = open(html_doc, 'r', encoding='utf-8')
                soup = BeautifulSoup(file, 'html.parser')

                entries = soup.find_all('h2', class_='entry-title ast-blog-single-element')
                for entry in entries:
                    title = entry.text.strip()
                    link_tag = entry.find('a')
                    link = link_tag['href'] if link_tag else ''

                    # Try to get description from sibling div
                    description = ''
                    desc_div = entry.find_next_sibling('div', class_='ast-excerpt-container ast-blog-single-element')
                    if desc_div:
                        description = desc_div.text.strip()

                    if title:
                        list_div.append({
                            'title': title,
                            'description': description,
                            'link': link,
                            'slug': filename
                        })

                file.close()
        except Exception as e:
            print(f"Flocker - parsing fail with error: {e} in file: {filename}")
            pass

    print(list_div)
    return list_div

