"""
dart_api.py
===========
DART openAPI 에서 전체 기업코드(corpCode.xml) 를 받아
상장 종목의 ticker(6자리) → DART corp_code(8자리) 매핑을
ticker_to_dart.json 으로 저장합니다.

- 한번만 실행하면 되는 정적 데이터 (종목코드는 거의 변하지 않음)
- 강제 갱신이 필요할 때만 --refresh 옵션으로 재실행
"""

import os, io, sys, zipfile, json
import xml.etree.ElementTree as ET
import requests
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
DART_API_KEY  = os.getenv("DART_API_KEY")
CORP_CODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"
OUTPUT_FILE   = "ticker_to_dart.json"


def download_and_build_map(force: bool = False) -> list:
    """
    ticker_to_dart.json 이 이미 있으면 그대로 읽어 반환.
    없거나 force=True 이면 DART API 를 호출해 새로 생성.
    """
    if os.path.exists(OUTPUT_FILE) and not force:
        print(f"[캐시] {OUTPUT_FILE} 가 이미 존재합니다. 갱신하려면 --refresh 옵션 사용.")
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    if not DART_API_KEY:
        raise ValueError(".env 에 DART_API_KEY 가 없습니다.")

    # ── 1. ZIP 다운로드 ──────────────────────────────────────
    print("DART 전체 기업코드 다운로드 중...")
    resp = requests.get(CORP_CODE_URL, params={"crtfc_key": DART_API_KEY}, timeout=30)
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        xml_name  = next(n for n in zf.namelist() if n.lower().endswith(".xml"))
        xml_bytes = zf.read(xml_name)

    # ── 2. XML 파싱 ──────────────────────────────────────────
    root     = ET.fromstring(xml_bytes)
    all_data = []

    for item in root.findall("list"):
        stock_code  = (item.findtext("stock_code")  or "").strip()
        corp_code   = (item.findtext("corp_code")   or "").strip()
        corp_name   = (item.findtext("corp_name")   or "").strip()
        modify_date = (item.findtext("modify_date") or "").strip()

        if not stock_code:          # 비상장(공백) 제외
            continue

        all_data.append({
            "ticker":      stock_code,   # 6자리 주식코드
            "corp_code":   corp_code,    # 8자리 DART 고유번호
            "corp_name":   corp_name,
            "modify_date": modify_date,
        })

    all_data.sort(key=lambda x: x["ticker"])

    # ── 3. JSON 저장 ─────────────────────────────────────────
    saved_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    output   = {"saved_at": saved_at, "count": len(all_data), "data": all_data}

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=4)

    print(f"  → 상장 종목 {len(all_data)}개 저장 완료 → {OUTPUT_FILE}")
    return all_data


# ── 개별 조회 헬퍼 ──────────────────────────────────────────
def get_corp_code(ticker: str) -> dict | None:
    """ticker(6자리) 로 corp_code 정보를 반환. 없으면 None."""
    if not os.path.exists(OUTPUT_FILE):
        raise FileNotFoundError(f"{OUTPUT_FILE} 없음. 먼저 dart_api.py 를 실행하세요.")
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        obj = json.load(f)
    for row in obj["data"]:
        if row["ticker"] == ticker:
            return row
    return None


if __name__ == "__main__":
    force = "--refresh" in sys.argv
    data  = download_and_build_map(force=force)
    print(f"\n✅ 완료! 총 {len(data)}개 종목 매핑")
    print(f"   저장 파일 : {OUTPUT_FILE}")
    print("\n[샘플 3개]")
    for row in data[:3]:
        print(f"  {row['ticker']} → {row['corp_code']}  ({row['corp_name']})")
