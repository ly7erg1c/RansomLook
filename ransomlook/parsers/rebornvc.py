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
                with open(html_doc, 'r', encoding='utf-8') as file:
                    soup = BeautifulSoup(file, 'html.parser')

                cards = soup.select('.card')
                for card in cards:
                    company = card.select_one('.company-header')
                    details = card.select_one('.victim-details')

                    if company:
                        title = company.get_text(strip=True)
                        description = details.get_text(strip=True) if details else ''

                        if title:
                            list_div.append({
                                'title': title,
                                'description': description,
                                'slug': filename
                            })
        except Exception as e:
            print(f"{group_name} - parsing fail with error: {e} in file: {filename}")

    print(list_div)
    return list_div

