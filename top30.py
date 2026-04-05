import requests
from bs4 import BeautifulSoup
import json
import re

def get_kospi_top_30():
    url = "https://finance.naver.com/sise/sise_market_sum.nhn?sosok=0&page=1"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # 시가총액 테이블 찾기
    table = soup.find('table', {'class': 'type_2'})
    rows = table.find_all('tr')
    
    stock_list = []
    
    for row in rows:
        # 종목명이 들어있는 <a> 태그 찾기
        name_tag = row.find('a', {'class': 'tltle'})
        if name_tag:
            # 티커(종목코드)는 href 속성에서 추출 (예: /item/main.naver?code=005930)
            href = name_tag.get('href')
            ticker = re.search(r'code=(\d+)', href).group(1)
            
            # 각 컬럼 데이터 추출
            cols = row.find_all('td')
            rank = cols[0].text.strip()
            name = name_tag.text.strip()
            price = cols[2].text.strip().replace(',', '')
            market_cap = cols[6].text.strip().replace(',', '')
            
            stock_list.append({
                "rank": int(rank),
                "name": name,
                "ticker": ticker,
                "price": int(price),
                "market_cap_billion_krw": int(market_cap)
            })
            
            # 30위까지만 수집
            if len(stock_list) >= 30:
                break
                
    return stock_list

if __name__ == "__main__":
    top_30 = get_kospi_top_30()
    # JSON으로 출력
    print(json.dumps(top_30, ensure_ascii=False, indent=4))