import yfinance as yf
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def get_target_business_day():
    """
    KST 16:00 이후 → 당일 종가 시도 (장 마감 15:30 이후 데이터 확정)
    KST 16:00 이전 → 전 영업일(D-1) 종가 사용
    주말이면 금요일로 후퇴
    """
    now_kst = datetime.now(KST)
    if now_kst.hour >= 16 and now_kst.weekday() < 5:  # 평일 16시 이후
        day = now_kst.date()  # 당일
    else:
        day = now_kst.date() - timedelta(days=1)  # D-1
    # 주말이면 금요일로
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


# 하위 호환용 alias
get_prev_business_day = get_target_business_day

# top30.py 의 함수를 직접 호출
from top30 import get_kospi_top_30


def fetch_yahoo_finance_data(stock_list):
    """야후 파이낸스 API로 영업일 D-1 하루치 OHLCV 수집"""
    all_data = []
    target = get_prev_business_day()          # 전 영업일
    end    = target + timedelta(days=1)       # yfinance end는 exclusive

    print(f"야후 파이낸스에서 {len(stock_list)}개 종목 데이터 수집 중... (기준일: {target})")

    for item in stock_list:
        ticker = item["ticker"]
        name   = item["name"]          # 한글 종목명
        yf_ticker = f"{ticker}.KS"    # 코스피: .KS

        try:
            stock = yf.Ticker(yf_ticker)
            df = stock.history(start=target, end=end)

            if df.empty:
                print(f"  ⚠ 데이터 없음: {yf_ticker} ({name})")
                continue

            for date, row in df.iterrows():
                all_data.append({
                    "date":   date.strftime("%Y-%m-%d"),
                    "ticker": ticker,
                    "name":   name,
                    "open":   round(float(row["Open"]),   2),
                    "high":   round(float(row["High"]),   2),
                    "low":    round(float(row["Low"]),    2),
                    "close":  round(float(row["Close"]),  2),
                    "volume": int(row["Volume"]),
                })
            print(f"  ✓ {name} ({yf_ticker})")

        except Exception as e:
            print(f"  ✗ 에러 ({yf_ticker}): {e}")

    return all_data


if __name__ == "__main__":
    # 1단계: top30.py 로 코스피 시가총액 상위 30개 종목 조회
    print("=== [1단계] 코스피 시가총액 상위 30 조회 (top30.py) ===")
    stock_list = get_kospi_top_30()

    if not stock_list:
        print("종목 목록을 가져오지 못했습니다.")
        exit(1)

    print(f"  → {len(stock_list)}개 종목 조회 완료\n")

    # 2단계: 야후 파이낸스로 OHLCV 수집
    print("=== [2단계] 야후 파이낸스 OHLCV 데이터 수집 ===")
    data_set = fetch_yahoo_finance_data(stock_list)

    # 3단계: JSON 저장
    output_file = "top30_market_data.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data_set, f, ensure_ascii=False, indent=4)

    print(f"\n✅ 작업 완료!")
    print(f"   수집 레코드 수 : {len(data_set)}")
    print(f"   저장 파일      : {output_file}")
    print(f"   기준 시각      : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")