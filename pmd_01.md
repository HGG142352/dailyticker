# 📈 KOSPI Top 30 Quant Dashboard & API (프로젝트 명세서)

## 1. 프로젝트 목적
**KOSPI 시가총액 상위 30개 종목(보통주 기준)**의 실시간 마켓 데이터(시세)와 DART(금융감독원) 공시 기반의 재무 퀀트 지표를 결합하여 사용자에게 명관하게 제공하는 것입니다. 
별도의 백엔드 서버 렌더링 유지 비용 없이, **GitHub Actions**와 **Vercel 무료 티어** 환경에서 데이터 수집, 저장, 배포가 완전 자동화된 파이프라인을 구축하는 것을 목표로 합니다.

---

## 2. 작동 방식 (Architecture & Data Flow)

Vercel 무료 배포 횟수 제약(재배포 최소화)을 극복하기 위해 **GitHub Raw URL 기반의 동적 로딩 방식**을 채택했습니다. Vercel은 최초 1회만 배포되며, 이후의 모든 데이터 갱신은 GitHub Actions가 수행합니다.

### 🔄 자동화 파이프라인 흐름
1. **스케줄링**: `GitHub Actions`가 평일 (KST 07:00, 12:00, 20:00) 마다 자동으로 파이썬 스크립트 실행.
2. **데이터 수집 (Data Pipeline)**:
    - `top30.py`: 네이버 금융에서 KOSPI 시총 상위 30개 종목 추출 (**우선주 제외, 보통주만**)
    - `top30_data_set.py`: 장 마감 이전/이후 시간에 맞추어 야후 파이낸스에서 일봉 데이터(시/고/저/종/거래량) 수집
    - `dart_quant.py`: DART API를 호출하여 배당, ROE, PBR, 순이익, 영업활동CF 등 최신 퀀트/재무 정보 추출
    - `generate_api_json.py`: 수집된 데이터를 하나로 병합하여 `kospi_top30_api.json` 생성
3. **저장 및 배포**: 생성된 JSON 파일(`.json`)들을 GitHub `main` 원격 저장소에 `push`.
4. **프론트엔드 (대시보드)**: 사용자가 `index.html` (Vercel 배포)에 접속하거나 "🔄 새로고침" 버튼 클릭 시, 브라우저가 최신 `GitHub Raw URL`에서 직접 JSON을 읽어와 화면에 실시간 차트/테이블 렌더링.
5. **외부 API 서빙 (Serverless)**: Vercel의 Serverless Function (`api/data.js`)을 통해 안전하게 토큰을 확인하고 제 3자에게 JSON 데이터를 서빙.

---

## 3. 프로젝트 구조 (Directory Layout)

```
📂 dailyticker
 ┣ 📂 .github/workflows
 ┃ ┗ 📜 update_data.yml        # GitHub Actions 자동 업데이트 스케줄 
 ┣ 📂 api
 ┃ ┗ 📜 data.js                # Vercel Serverless 엔드포인트 (API 키 인증 프록시)
 ┣ 📜 index.html               # 메인 대시보드 UI (정적 사이트)
 ┣ 📜 vercel.json              # Vercel 라우팅 및 서버리스 함수 보안/캐시 설정
 ┣ 📜 top30.py                 # (수집 로직) 시가총액 상위 30위 선별기
 ┣ 📜 top30_data_set.py        # (수집 로직) 주가/거래량 데이터 수집기
 ┣ 📜 dart_quant.py            # (수집 로직) DART 퀀트 데이터 수집기
 ┣ 📜 generate_api_json.py     # (수집 로직) 최종 API JSON 병합기
 ┣ 📜 top30_market_data.json   # (결과물) 일간 주가 조회 결과
 ┣ 📜 dart_quant_top30.json    # (결과물) 퀀트 재무 결과
 ┗ 📜 kospi_top30_api.json     # (결과물) 최종 외부 서빙용 API 데이터셋
```

---

## 4. 특장점 및 해결된 기술 이슈

- **스마트 날짜 로직**: 장 마감(KST 15:30) 기준, 16:00 이전엔 어제(D-1) 데이터를 검색하고, 16:00 이후엔 안전하게 오늘 종가를 가져오도록 구현됨.
- **우선주 필터링**: 시가총액 상위 리스트 수집 시, DART 공시 조회 에러를 유발하고 퀀트 분석에 불리한 '우선주(e.g., 삼성전자우)'를 자동으로 스킵하고 순수 보통주 30개를 채우도록 고안됨.
- **인증된 외부 API 제공**: `api/data.js`를 이용해, 외부에서 `https://[도메인]/api/data?key=[SECRET_QUANT_API_KEY]` 형식으로 요청 시, 인증된 클라이언트에게만 GitHub Raw 데이터를 중계(Proxy)하는 보안 엔드포인트 마련.
- **UTF-8 인코딩 통일화**: 로컬 OS 환경에 상관없이 GitHub 봇과 충돌 없이 `-X utf8` 인수를 통해 CLI에서 한글 이모지/특수문자가 깨지지 않도록 설계됨.
