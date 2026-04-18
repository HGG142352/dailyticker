"""API용 최종 병합 JSON을 생성하는 스크립트"""
import json
import os
from datetime import datetime

base_dir = os.path.dirname(os.path.abspath(__file__))
MARKET_PATH = os.path.join(base_dir, "kospi200_market_data.json")
QUANT_PATH  = os.path.join(base_dir, "dart_quant_kospi200.json")
TAGS_PATH   = os.path.join(base_dir, "kospi200_tags.json")
EXPORT_PATH = os.path.join(base_dir, "api_data_kospi200.json")

def generate_export_json():
    if not os.path.exists(MARKET_PATH) or not os.path.exists(QUANT_PATH):
        print("Data files missing.")
        return

    with open(MARKET_PATH, "r", encoding="utf-8") as f:
        market_data = json.load(f)
    
    with open(QUANT_PATH, "r", encoding="utf-8") as f:
        quant_obj = json.load(f)
        
    tags_dict = {}
    if os.path.exists(TAGS_PATH):
        with open(TAGS_PATH, "r", encoding="utf-8") as f:
            tags_dict = json.load(f)
            
    quant_dict = {
        item["기업_식별_정보"]["종목코드"]: item 
        for item in quant_obj.get("data", [])
    }

    result = []
    latest_update = quant_obj.get("generated_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    for m in market_data:
        ticker = m["ticker"]
        q = quant_dict.get(ticker, {})

        if not q:
            continue

        info = q.get("기업_식별_정보", {})
        kpi  = q.get("퀀트_핵심_지표", {})
        qual = kpi.get("수익성_Quality", {})
        val  = kpi.get("밸류에이션", {})
        safe = kpi.get("안정성_Safety", {})
        grow = kpi.get("성장성_Growth", {})

        flat_item = {
            "rank": m.get("rank"),
            "name": m.get("name"),
            "ticker": ticker,
            "date": m.get("date"),
            "close_price": m.get("close"),
            "volume": m.get("volume"),

            "industry": info.get("업종명"),
            "ceo": info.get("대표자"),

            "roe": qual.get("ROE"),
            "roa": qual.get("ROA"),
            "op_margin": qual.get("영업이익률"),
            "gp_a": qual.get("GP_A"),

            "eps": val.get("EPS_TTM"),
            "bps": val.get("BPS"),
            "per": val.get("PER_TTM"),
            "pbr": val.get("PBR"),
            "dividend_yield": val.get("현금배당수익률"),

            "debt_ratio": safe.get("부채비율"),
            "current_ratio": safe.get("유동비율"),
            "rev_growth": grow.get("매출성장률_전년비"),
            "op_growth": grow.get("영업이익성장률_전년비"),
            "ni_growth": grow.get("순이익성장률_전년비"),

            "latest_event": q.get("최근_주요_이벤트", [{}])[0].get("공시명", "없음") if q.get("최근_주요_이벤트") else "없음",
            
            "tags": tags_dict.get(ticker, {}).get("tags", [])
        }
        result.append(flat_item)

    export_obj = {
        "status": "success",
        "latest_update": latest_update,
        "count": len(result),
        "data": result
    }

    with open(EXPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(export_obj, f, ensure_ascii=False, indent=4)
    print(f"✅ API export file created: {EXPORT_PATH}")

if __name__ == "__main__":
    generate_export_json()
