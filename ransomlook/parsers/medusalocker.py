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

                articles = soup.find_all('article')
                for article in articles:
                    try:
                        # Extract the link
                        link_tag = article.find('a')
                        link = link_tag['href'] if link_tag else ''

                        # Extract the title
                        title_tag = article.find('h2', class_='entry-title')
                        title = title_tag.text.strip() if title_tag else ''

                        # Extract the content/description
                        content_div = article.find('div', class_='entry-content')
                        description = content_div.text.strip() if content_div else ''

                        if title:
                            list_div.append({
                                'title': title,
                                'description': description,
                                'link': link,
                                'slug': filename
                            })
                    except Exception:
                        pass

                file.close()
        except Exception:
            print(f"medusalocker: parsing fail for {filename}")
            pass

    print(list_div)
    return list_div

