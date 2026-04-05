import os
import json
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()
SECRET_KEY = os.getenv("SECRET_QUANT_API_KEY", "default-secret-key-1234")

app = FastAPI(title="KOSPI Top 30 Quant API")

# 외부 접근 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def verify_api_key(api_key: str = Query(...)):
    """API Key 검증"""
    if api_key != SECRET_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return api_key

@app.get("/")
def root():
    return {
        "message": "KOSPI Top 30 Quant API Server is running.",
        "usage": "GET /api/top30_quant?api_key=YOUR_SECRET_KEY"
    }

@app.get("/api/top30_quant")
def get_top30_quant(api_key: str = Depends(verify_api_key)):
    """
    미리 생성된 kospi_top30_api.json 파일을 읽어서 반환합니다.
    데이터는 app.py 의 /run 엔드포인트를 통해 하루 1번 생성됩니다.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    export_path = os.path.join(base_dir, "kospi_top30_api.json")

    if not os.path.exists(export_path):
        raise HTTPException(status_code=404, detail="API export data not ready. Please run the collector script first.")

    with open(export_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    return data

if __name__ == "__main__":
    import uvicorn
    # 외부에서 접속 필요 시 host="0.0.0.0" 지정 가능
    uvicorn.run(app, host="127.0.0.1", port=8000)
