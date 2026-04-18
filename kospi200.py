import requests
from bs4 import BeautifulSoup
import json
import re

def get_kospi_200():
    """
    네이버 금융의 코스피 200 편입종목 페이지를 스크래핑하여 200개 종목을 리스트로 반환합니다.
    """
    stock_list = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    rank = 1
    for page in range(1, 21):
        url = f"https://finance.naver.com/sise/entryJongmok.naver?&page={page}"
        response = requests.get(url, headers=headers)
        response.encoding = 'euc-kr'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        table = soup.find('table', {'class': 'type_1'})
        if not table:
            continue
            
        rows = table.find_all('tr')
        for row in rows:
            name_tag = row.find('td', {'class': 'ctg'})
            if not name_tag:
                continue
                
            a_tag = name_tag.find('a')
            if not a_tag:
                continue
                
            name = a_tag.text.strip()
            href = a_tag.get('href')
            ticker_match = re.search(r'code=(\d+)', href)
            ticker = ticker_match.group(1) if ticker_match else ""
            
            cols = row.find_all('td')
            # cols[0] = name(ctg)
            # cols[1] = price
            # cols[2] = change
            # cols[3] = change_ratio
            # cols[4] = volume
            # cols[5] = amount
            # cols[6] = market_cap
            
            try:
                price = int(cols[1].text.strip().replace(',', ''))
                market_cap = int(cols[6].text.strip().replace(',', ''))
            except ValueError:
                price = 0
                market_cap = 0
                
            stock_list.append({
                "rank": rank,
                "name": name,
                "ticker": ticker,
                "price": price,
                "market_cap_billion_krw": market_cap
            })
            rank += 1
            
    return stock_list

if __name__ == "__main__":
    k200 = get_kospi_200()
    print(f"총 {len(k200)}개 종목 수집 완료.")
    with open("kospi200_list.json", "w", encoding="utf-8") as f:
        json.dump(k200, f, ensure_ascii=False, indent=4)
