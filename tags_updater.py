import json
import os
import requests
from bs4 import BeautifulSoup
import yfinance as yf
from datetime import datetime
import FinanceDataReader as fdr

def get_sector_map():
    print("  - 섹터(Sector) 정보 수집 중 (FinanceDataReader)...")
    try:
        df = fdr.StockListing("KOSPI")
        return {str(row['Code']): str(row['Sector']) for _, row in df.iterrows() if row['Sector']}
    except Exception as e:
        print(f"    ! 섹터 수집 실패: {e}")
        return {}

def scrape_naver_themes():
    print("  - 테마(Theme) 정보 수집 중 (Naver Finance)...")
    themes = {}
    TARGET_THEMES = ["HBM", "CXL", "온디바이스 AI", "SMR", "LFP", "전고체", "우주항공", "방위산업", "화장품"]
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    for page in range(1, 8):
        url = f"https://finance.naver.com/sise/theme.naver?&page={page}"
        res = requests.get(url, headers=headers)
        res.encoding = 'euc-kr'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        for tr in soup.select('table.type_1 tr'):
            td = tr.select_one('td.col_type1 a')
            if not td: continue
            
            theme_name = td.text.strip()
            theme_link = "https://finance.naver.com" + td['href']
            
            # 관심 테마와 매칭되는지 확인
            matched_tags = []
            for kw in TARGET_THEMES:
                if kw.lower() in theme_name.lower():
                    matched_tags.append(kw)
                    
            if "방위산업" in theme_name: matched_tags.append("K-방산")
            if "화장품" in theme_name: matched_tags.append("K-뷰티")
                
            if matched_tags:
                try:
                    res_thm = requests.get(theme_link, headers=headers)
                    res_thm.encoding = 'euc-kr'
                    soup_thm = BeautifulSoup(res_thm.text, 'html.parser')
                    for stock_a in soup_thm.select('td.name a'):
                        ticker = stock_a['href'].split('code=')[-1]
                        if ticker not in themes: themes[ticker] = set()
                        themes[ticker].update(matched_tags)
                except:
                    pass
    return themes

def get_yfinance_momentum(tickers):
    print("  - 수급/모멘텀/거래량 지표 계산 중 (yfinance)...")
    momentum = {}
    for ticker in tickers:
        try:
            yf_ticker = f"{ticker}.KS"
            stock = yf.Ticker(yf_ticker)
            df = stock.history(period="1mo")
            if len(df) < 20:
                momentum[ticker] = []
                continue
            
            tags = []
            recent_vol = df['Volume'].iloc[-1]
            avg_20_vol = df['Volume'].iloc[-20:].mean()
            if recent_vol > avg_20_vol * 5:
                tags.append("거래폭발")
                
            ma5 = df['Close'].iloc[-5:].mean()
            ma20 = df['Close'].iloc[-20:].mean()
            prev_ma5 = df['Close'].iloc[-6:-1].mean()
            prev_ma20 = df['Close'].iloc[-21:-1].mean()
            
            if prev_ma5 <= prev_ma20 and ma5 > ma20:
                tags.append("골든크로스")
                
            ytd = stock.history(period="1y")
            if len(ytd) > 0:
                max52 = ytd['High'].max()
                current_high = df['High'].iloc[-1]
                if current_high >= max52 * 0.98:
                    tags.append("신고가")
            
            momentum[ticker] = tags
        except:
            momentum[ticker] = []
    return momentum

def process_dart_fundamentals(dart_data):
    fund_tags = {}
    for item in dart_data:
        ticker = item.get("기업_식별_정보", {}).get("종목코드", "")
        if not ticker: continue
        
        tags = []
        quant = item.get("퀀트_핵심_지표", {})
        stability = quant.get("안정성_Safety", {})
        val = quant.get("밸류에이션", {})
        
        # 고배당
        div = val.get("현금배당수익률", "N/A")
        if isinstance(div, str) and "%" in div:
            try:
                if float(div.replace("%", "")) >= 5.0:
                    tags.append("고배당")
                    tags.append("금투세 수혜")
            except: pass
            
        # 흑자전환
        growth = quant.get("성장성_Growth", {})
        ni_growth = growth.get("순이익성장률_전년비", "N/A")
        if ni_growth != "N/A": 
            # DART json 에 NI값 자체가 없으므로 간단하게 양수 성장이고 이전이 음수면 턴어라운드지만 판별 복잡.
            pass 
        
        trend = item.get("재무제표_3개년_추이", {}).get("당기순이익", {})
        years = sorted(trend.keys())
        if len(years) >= 2:
            prev_ni = trend[years[-2]]
            curr_ni = trend[years[-1]]
            if isinstance(prev_ni, (int, float)) and isinstance(curr_ni, (int, float)):
                if prev_ni < 0 and curr_ni > 0:
                    tags.append("흑자전환")
                    
        # 현금부자
        cr = stability.get("유동비율", "N/A")
        if isinstance(cr, str) and "%" in cr:
            try:
                if float(cr.replace("%", "")) >= 200.0:
                    tags.append("현금부자")
            except: pass
            
        fund_tags[ticker] = tags
    return fund_tags


def main():
    print("=== 태그 업데이트 시작 ===")
    
    # 1. 대상 종목 로드
    kospi_list = []
    if os.path.exists("kospi200_list.json"):
        with open("kospi200_list.json", "r", encoding="utf-8") as f:
            kospi_list = json.load(f)
    if not kospi_list:
        print("KOSPI 200 목록을 찾을 수 없습니다. 먼저 kospi200_list.json을 생성하세요.")
        return
        
    tickers = [item["ticker"] for item in kospi_list]
    
    # 2. 태그 소스 수집
    sector_map = get_sector_map()
    theme_map = scrape_naver_themes()
    
    dart_data = []
    if os.path.exists("dart_quant_kospi200.json"):
        with open("dart_quant_kospi200.json", "r", encoding="utf-8") as f:
            dart_data = json.load(f).get("data", [])
    fund_map = process_dart_fundamentals(dart_data)
    
    momentum_map = get_yfinance_momentum(tickers)
    
    # K-Value Up (Mocking known tickers roughly for demo, real implementation requires KRX subscription)
    # 삼성전자, 현대차, 기아, KB금융, 신한지주, 메리츠금융지주, 등
    value_up_tickers = {"005930", "005380", "000270", "105560", "055550", "138040", "032830", "024110", "086790"}
    
    # MSCI (Mocking top mega caps)
    msci_tickers = {"005930", "000660", "373220", "207940", "005380"}
    
    # 3. 통합
    tags_output = {}
    for item in kospi_list:
        ticker = item["ticker"]
        tags = []
        
        # Sector 
        sec = sector_map.get(ticker)
        if sec: tags.append(sec)
            
        # Policy
        if ticker in value_up_tickers: tags.append("코리아 밸류업")
        if ticker in msci_tickers: tags.append("MSCI 편입")
            
        # Themes
        if ticker in theme_map:
            tags.extend(list(theme_map[ticker]))
            
        # Fundamentals
        if ticker in fund_map:
            tags.extend(fund_map[ticker])
            
        # Momentum
        if ticker in momentum_map:
            tags.extend(momentum_map[ticker])
            
        tags_output[ticker] = {
            "name": item["name"],
            "tags": sorted(list(set(tags))) # Deduplication
        }

    with open("kospi200_tags.json", "w", encoding="utf-8") as f:
        json.dump(tags_output, f, ensure_ascii=False, indent=4)
        
    print(f"=== 태그 업데이트 완료 (총 {len(tags_output)}개 종목) ===")
    print("저장 경로: kospi200_tags.json")

if __name__ == "__main__":
    main()
