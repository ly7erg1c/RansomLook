import os
from bs4 import BeautifulSoup
from typing import Dict, List


def extract_text_from_block(block: BeautifulSoup, label: str) -> str:
    """Extracts the value corresponding to a label in the same block."""
    labels = block.find_all('div', class_='main_block_ul')
    for div in labels:
        items = div.find_all('div', class_='main_block_li')
        if len(items) == 2 and label.lower() in items[0].text.strip().lower():
            return items[1].text.strip()
    return ''


def main() -> List[Dict[str, str]]:
    list_div: List[Dict[str, str]] = []
    group_name = __name__.split('.')[-1]

    for filename in os.listdir('source'):
        if not filename.startswith(group_name + '-'):
            continue

        html_doc = 'source/' + filename
        try:
            with open(html_doc, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'html.parser')

                victims = soup.find_all('div', class_='main_block')

                for victim in victims:
                    try:
                        title_div = victim.find('div', class_='main_block_title')
                        if not title_div:
                            continue
                        title = title_div.text.strip()

                        notes_div = victim.find('div', class_='notes-content')
                        paragraphs = notes_div.find_all('p') if notes_div else []
                        description = '\n'.join(p.text.strip() for p in paragraphs if p.text.strip())

                        if title:
                            list_div.append({
                                'title': title,
                                'description': description,
                                'slug': filename
                            })
                    except Exception as e:
                        print(f"Error parsing victim block in {filename}: {e}")
        except Exception as e:
            print(f"Error reading {filename}: {e}")

    print(list_div)
    return list_div

