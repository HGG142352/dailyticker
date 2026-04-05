"""
dart_quant.py
=============
top30.py 의 코스피 상위 30개 종목에 대해 DART openAPI 를 호출하여
퀀트 분석용 JSON 을 생성합니다.

출력: dart_quant_top30.json
사용 API:
  - company.json       : 기업 기본정보
  - fnlttSinglAcnt     : 주요 재무지표 요약 (3개년)
  - fnlttSinglAcntAll  : 핵심 재무제표 전체 (GP, CFO)
  - list.json          : 최근 공시 리스트
  - yfinance           : 발행주식수 (sharesOutstanding)
"""

import os, json, time, requests
from datetime import datetime
from dotenv import load_dotenv
import yfinance as yf
from dart_api import download_and_build_map
from top30   import get_kospi_top_30

load_dotenv()
DART_API_KEY = os.getenv("DART_API_KEY")
BASE_URL     = "https://opendart.fss.or.kr/api"
OUTPUT_FILE  = "dart_quant_top30.json"

YEARS       = ["2022", "2023", "2024"]
LATEST_YEAR = YEARS[-1]
KEYWORDS    = ["배당", "계약", "증자", "분할", "합병", "감자", "횡령", "사채"]

# ── 계정과목 후보 목록 (우선순위 순) ─────────────────────────
# 연결/별도, 손실 표현 등 복수 명칭 대응
NI_NAMES = [
    "당기순이익",
    "당기순이익(손실)",
    "지배기업소유주지분 당기순이익",
    "당기순이익(손실) (지배)",
]
GROSS_NAMES = [
    "매출총이익",
    "매출총이익(손실)",
]
CFO_NAMES = [
    "영업활동현금흐름",
    "영업활동으로인한현금흐름",
    "영업활동으로 인한 현금흐름",
    "영업에서 창출된 현금흐름",
]


# ── 공통 API 호출 ────────────────────────────────────────────
def _fetch(endpoint: str, params: dict) -> dict:
    params["crtfc_key"] = DART_API_KEY
    resp = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=20)
    return resp.json()


# ── 수치 파싱 ────────────────────────────────────────────────
def _to_int(s) -> int:
    try:
        return int(str(s).replace(",", "").replace(" ", ""))
    except:
        return 0


def _get_val(data_list: list, names, col: str = "thstrm_amount") -> int:
    """하나 이상의 계정과목명 후보로 수치 추출 (첫 번째 매칭 반환)"""
    if isinstance(names, str):
        names = [names]
    for name in names:
        for item in data_list:
            if item.get("account_nm", "") == name:
                v = _to_int(item.get(col, 0))
                if v != 0:
                    return v
    return 0


def _fmt_pct(v):
    return f"{v:+.2f}%" if v is not None else "N/A"

def _pct(curr, prev):
    if prev and prev != 0:
        return round((curr - prev) / abs(prev) * 100, 2)
    return None


# ── yfinance TTM 밸류에이션 ──────────────────────────────────
def _get_yfinance_valuation(ticker: str, close_price: float) -> dict:
    """
    yfinance 에서 TTM 기준 지표를 가져옵니다.
    - trailingEps  : TTM EPS (원)
    - trailingPE   : TTM PER
    - bookValue    : BPS (원, 주당순자산)
    - priceToBook  : PBR
    - dividendYield: 현금배당수익률 (소수)
    - sharesOutstanding: 발행주식수
    """
    try:
        info = yf.Ticker(f"{ticker}.KS").info
        shares = info.get("sharesOutstanding", 0) or 0
        # yfinance 는 달러 기준 eps/bv를 돌려주는 경우가 있어
        # 직접 계산값과 비교해 원화 값을 선택
        eps_yf  = info.get("trailingEps")
        bv_yf   = info.get("bookValue")     # per share
        per_yf  = info.get("trailingPE")
        pbr_yf  = info.get("priceToBook")
        div_yld = info.get("dividendYield")
        if div_yld is not None:
            # yfinance 한국주식은 1.27(1.27%) 처럼 줄 때도 있고, 0.0127 로 줄 때도 있음
            if div_yld < 0.2:  # 20% 미만이면 소수로 간주
                div_yld = div_yld * 100

        return {
            "발행주식수":      shares,
            "EPS_TTM":        round(eps_yf, 2)  if eps_yf  else None,
            "BPS":            round(bv_yf, 2)   if bv_yf   else None,
            "PER_TTM":        round(per_yf, 2)  if per_yf  else None,
            "PBR":            round(pbr_yf, 2)  if pbr_yf  else None,
            "현금배당수익률":  f"{round(div_yld, 2)}%" if div_yld else "N/A",
        }
    except Exception as e:
        return {"발행주식수": 0, "EPS_TTM": None, "BPS": None,
                "PER_TTM": None, "PBR": None, "현금배당수익률": "N/A"}



# ── 단일 기업 퀀트 데이터 수집 ──────────────────────────────
def build_quant_for_corp(corp_code: str, ticker: str, corp_name: str,
                          close_price: float = 0) -> dict:

    # 1. 기업 기본정보
    info = _fetch("company.json", {"corp_code": corp_code})

    # 2. 주요 재무지표 요약 (3개년)
    summary = {}
    for yr in YEARS:
        summary[yr] = _fetch("fnlttSinglAcnt.json", {
            "corp_code": corp_code, "bsns_year": yr, "reprt_code": "11011"
        }).get("list", [])
        time.sleep(0.15)

    # 3. 핵심 재무제표 전체 (GP, CFO 용) — 연결(CFS) 우선, 없으면 별도(OFS)
    all_acc = _fetch("fnlttSinglAcntAll.json", {
        "corp_code": corp_code, "bsns_year": LATEST_YEAR,
        "reprt_code": "11011", "fs_div": "CFS"
    }).get("list", [])
    if not all_acc:
        all_acc = _fetch("fnlttSinglAcntAll.json", {
            "corp_code": corp_code, "bsns_year": LATEST_YEAR,
            "reprt_code": "11011", "fs_div": "OFS"
        }).get("list", [])

    # 4. 최근 공시
    disclosures = _fetch("list.json", {
        "corp_code": corp_code, "page_count": 20
    }).get("list", [])

    # ── 수치 추출 ────────────────────────────────────────────
    acc      = summary[LATEST_YEAR]
    acc_prev = summary.get(YEARS[-2], [])

    rev    = _get_val(acc, "매출액")
    op     = _get_val(acc, "영업이익")
    ni     = _get_val(acc, NI_NAMES)
    equity = _get_val(acc, "자본총계")
    debt   = _get_val(acc, "부채총계")
    assets = _get_val(acc, "자산총계")
    curr_a = _get_val(acc, "유동자산")
    curr_l = _get_val(acc, "유동부채")
    gross  = (_get_val(all_acc, GROSS_NAMES)          # fnlttSinglAcntAll 직접 계정
              or _get_val(acc, GROSS_NAMES))           # fnlttSinglAcnt 직접 계정
    if not gross:                                      # 폴백: 매출액 - 매출원가
        cogs  = (_get_val(acc, ["매출원가"])
                 or _get_val(all_acc, ["매출원가"]))
        if cogs and rev:
            gross = rev - cogs
    cfo    = _get_val(all_acc, CFO_NAMES)

    rev_prev = _get_val(acc_prev, "매출액")
    op_prev  = _get_val(acc_prev, "영업이익")
    ni_prev  = _get_val(acc_prev, NI_NAMES)

    # ── 지표 계산 ────────────────────────────────────────────
    roe        = round(ni / equity * 100, 2)     if equity else None
    roa        = round(ni / assets * 100, 2)     if assets else None
    op_margin  = round(op / rev    * 100, 2)     if rev    else None
    gpa        = round(gross / assets, 4)        if assets else None
    debt_ratio = round(debt / equity * 100, 2)   if equity else None
    curr_ratio = round(curr_a / curr_l * 100, 2) if curr_l else None

    # ── 밸류에이션 (yfinance + DART 폴백) ──────────────────────
    yfval  = _get_yfinance_valuation(ticker, close_price)
    shares = yfval["발행주식수"]
    
    eps = yfval["EPS_TTM"]
    if eps is None and shares > 0 and ni is not None:
        eps = round(ni / shares, 2)
        
    bps = yfval["BPS"]
    if bps is None and shares > 0 and equity is not None:
        bps = round(equity / shares, 2)
        
    per = yfval["PER_TTM"]
    if per is None and eps and eps > 0 and close_price:
        per = round(close_price / eps, 2)
        
    pbr = yfval["PBR"]
    if pbr is None and bps and bps > 0 and close_price:
        pbr = round(close_price / bps, 2)
    def _get_all_acc(yr):
        acc_all = _fetch("fnlttSinglAcntAll.json", {
            "corp_code": corp_code, "bsns_year": yr,
            "reprt_code": "11011", "fs_div": "CFS"
        }).get("list", [])
        if not acc_all:
            acc_all = _fetch("fnlttSinglAcntAll.json", {
                "corp_code": corp_code, "bsns_year": yr,
                "reprt_code": "11011", "fs_div": "OFS"
            }).get("list", [])
        return acc_all
        
    # ── 3개년 추이 ──────────────────────────────────────────
    def _gross(s_acc, all_a, rv):
        g = _get_val(all_a, GROSS_NAMES) or _get_val(s_acc, GROSS_NAMES)
        if not g:
            cogs = _get_val(s_acc, ["매출원가"]) or _get_val(all_a, ["매출원가"])
            if cogs and rv:
                g = rv - cogs
        return g

    trend = {"매출액": {}, "영업이익": {}, "당기순이익": {}, "영업활동현금흐름": {}}
    for yr in YEARS:
        s = summary[yr]
        a = _get_all_acc(yr) if yr != LATEST_YEAR else all_acc
        rv = _get_val(s, "매출액")
        trend["매출액"][yr]           = rv
        trend["영업이익"][yr]         = _get_val(s, "영업이익")
        trend["당기순이익"][yr]       = _get_val(s, NI_NAMES)
        trend["영업활동현금흐름"][yr] = _get_val(a, CFO_NAMES)
        time.sleep(0.1)


    # ── 주요 공시 필터 ───────────────────────────────────────
    events = []
    for d in disclosures[:30]:
        nm = d.get("report_nm", "")
        kw = next((k for k in KEYWORDS if k in nm), None)
        if kw:
            events.append({"날짜": d.get("rcept_dt",""), "공시명": nm, "키워드": kw})
        if len(events) >= 5:
            break

    return {
        "기업_식별_정보": {
            "법인명":    info.get("corp_name", corp_name),
            "종목코드":  ticker,
            "corp_code": corp_code,
            "업종명":    info.get("induty_name", ""),
            "대표자":    info.get("ceo_nm", ""),
            "기준연도":  LATEST_YEAR,
        },
        "퀀트_핵심_지표": {
            "수익성_Quality": {
                "ROE":       f"{roe}%"       if roe       is not None else "N/A",
                "ROA":       f"{roa}%"       if roa       is not None else "N/A",
                "영업이익률": f"{op_margin}%" if op_margin is not None else "N/A",
                "GP_A":      str(gpa)        if gpa       is not None else "N/A",
            },
            "밸류에이션": {
                "현재주가":       close_price,
                "EPS_TTM":       eps if eps is not None else "N/A",
                "BPS":           bps if bps is not None else "N/A",
                "PER_TTM":       per if per is not None else "N/A",
                "PBR":           pbr if pbr is not None else "N/A",
                "현금배당수익률": yfval.get("현금배당수익률", "N/A"),
                "발행주식수":     shares,
                "기준":          "최근 결산(DART) + 현재가",
            },
            "안정성_Safety": {
                "부채비율": f"{debt_ratio}%" if debt_ratio is not None else "N/A",
                "유동비율": f"{curr_ratio}%" if curr_ratio is not None else "N/A",
                "순현금":   "Positive" if assets and debt and (assets - debt) > 0 else "Negative",
            },
            "성장성_Growth": {
                "매출성장률_전년비":     _fmt_pct(_pct(rev, rev_prev)),
                "영업이익성장률_전년비": _fmt_pct(_pct(op,  op_prev)),
                "순이익성장률_전년비":   _fmt_pct(_pct(ni,  ni_prev)),
            },
        },
        "재무제표_3개년_추이": {"단위": "원(KRW)", "연도": YEARS, **trend},
        "최근_주요_이벤트": events,
    }


# ── 메인 ────────────────────────────────────────────────────
if __name__ == "__main__":
    # 캐시된 DART 코드 맵 로드
    corp_map_obj = download_and_build_map()
    corp_map = {r["ticker"]: r for r in corp_map_obj["data"]} \
               if isinstance(corp_map_obj, dict) else \
               {r["ticker"]: r for r in corp_map_obj}

    print("=== [1단계] 코스피 상위 30 조회 ===")
    top30 = get_kospi_top_30()
    # 현재 주가 맵 (top30.py 반환값에 price 포함)
    price_map = {item["ticker"]: item.get("price", 0) for item in top30}
    print(f"  → {len(top30)}개 종목\n")

    print("=== [2단계] DART 퀀트 데이터 수집 ===")
    results = []
    for item in top30:
        ticker = item["ticker"]
        name   = item["name"]
        dart   = corp_map.get(ticker)
        if not dart:
            print(f"  ✗ {name} ({ticker}) — DART 매핑 없음")
            continue
        print(f"  처리 중: {name} ({ticker})")
        try:
            quant = build_quant_for_corp(
                dart["corp_code"], ticker, name,
                close_price=price_map.get(ticker, 0)
            )
            results.append(quant)
            time.sleep(0.3)
        except Exception as e:
            print(f"    ✗ 에러: {e}")

    output = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(results),
        "data": results,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=4)

    print(f"\n✅ 완료!  수집: {len(results)}개  저장: {OUTPUT_FILE}")