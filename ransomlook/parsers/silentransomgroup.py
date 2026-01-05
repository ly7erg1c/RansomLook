import os
import re
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

                blocks = soup.select('.block_1')
                for block in blocks:
                    try:
                        company_cell = block.find('td', string=re.compile("COMPANY:", re.IGNORECASE))
                        title = ''
                        if company_cell:
                            next_td = company_cell.find_next_sibling('td')
                            if next_td:
                                title = next_td.get_text(strip=True)

                        info_cell = block.find('td', string=re.compile("COMPANY INFO:", re.IGNORECASE))
                        description = ''
                        if info_cell:
                            next_td = info_cell.find_next_sibling('td')
                            if next_td:
                                description = next_td.get_text(strip=True)

                        # Skip entries with truncated names
                        if title and "..." not in title:
                            list_div.append({
                                'title': title,
                                'description': description,
                                'slug': filename
                            })
                    except Exception as inner_e:
                        print(f"{group_name} - inner block parsing error: {inner_e} in file: {filename}")

        except Exception as e:
            print(f"{group_name} - parsing fail with error: {e} in file: {filename}")

    print(list_div)
    return list_div

