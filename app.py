import subprocess
import json
import sys
import os
from flask import Flask, render_template, jsonify, Response
from datetime import datetime

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/run", methods=["POST"])
def run():
    log_lines = []

    def run_script(script_name, timeout=180):
        """스크립트 실행 후 (returncode, stdout, stderr) 반환"""
        path = os.path.join(BASE_DIR, script_name)
        r = subprocess.run(
            [sys.executable, "-X", "utf8", path],
            cwd=BASE_DIR, capture_output=True,
            text=True, encoding="utf-8", timeout=timeout,
        )
        return r

    try:
        # ── 1단계 : 가격 데이터 ─────────────────────────────
        r1 = run_script("top30_data_set.py")
        log_lines.append("=== top30_data_set.py ===\n" + r1.stdout)
        if r1.returncode != 0:
            return jsonify({"error": r1.stderr or "top30_data_set.py 실행 오류"}), 500

        # ── 2단계 : 퀀트 데이터 ─────────────────────────────
        r2 = run_script("dart_quant.py", timeout=300)
        log_lines.append("=== dart_quant.py ===\n" + r2.stdout)
        if r2.returncode != 0:
            return jsonify({"error": r2.stderr or "dart_quant.py 실행 오류"}), 500

        # ── 결과 반환 ────────────────────────────────────────
        logger.info("Step 2: DART quant collector finished.")

        # 3. API 서빙용 단일 JSON (kospi_top30_api.json) 생성
        logger.info("Step 3: Generating combined flat API JSON (kospi_top30_api.json)...")
        res3 = subprocess.run(
            ["python", "-X", "utf8", "generate_api_json.py"],
            cwd=BASE_DIR, capture_output=True, text=True, check=True
        )
        logger.info(res3.stdout)
        logger.info("Step 3: API JSON generation finished.")

        # 최종 반환 (클라이언트 UI용 데이터)
        with open(os.path.join(BASE_DIR, "top30_market_data.json"), "r", encoding="utf-8") as f:
            market_data = json.load(f)
        return jsonify({"status": "success", "data": market_data, "log": "\n".join(log_lines)})

    except subprocess.TimeoutExpired:
        return jsonify({"error": "실행 시간 초과"}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Public API ───────────────────────────────────────────────────────────────

@app.route("/api/data", methods=["GET"])
def api_data():
    """최신 top30_market_data.json 을 그대로 반환합니다."""
    json_path = os.path.join(BASE_DIR, "top30_market_data.json")
    if not os.path.exists(json_path):
        return jsonify({"error": "데이터 파일이 없습니다. 먼저 /run 을 호출하세요."}), 404
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    mtime = os.path.getmtime(json_path)
    updated_at = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
    resp = jsonify({"updated_at": updated_at, "count": len(data), "data": data})
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


@app.route("/api/status", methods=["GET"])
def api_status():
    """JSON 파일 존재 여부 및 마지막 갱신 시각을 반환합니다."""
    json_path = os.path.join(BASE_DIR, "top30_market_data.json")
    if not os.path.exists(json_path):
        return jsonify({"exists": False})
    mtime = os.path.getmtime(json_path)
    updated_at = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    resp = jsonify({"exists": True, "updated_at": updated_at, "count": len(data)})
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


@app.route("/api/quant", methods=["GET"])
def api_quant():
    """dart_quant_top30.json 을 ticker 키로 인덱싱해 반환합니다."""
    path = os.path.join(BASE_DIR, "dart_quant_top30.json")
    if not os.path.exists(path):
        return jsonify({"error": "dart_quant_top30.json 없음. dart_quant.py 를 먼저 실행하세요."}), 404
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    # ticker 로 빠르게 조회할 수 있도록 dict 변환
    by_ticker = {
        item["기업_식별_정보"]["종목코드"]: item
        for item in obj.get("data", [])
    }
    resp = jsonify({"generated_at": obj.get("generated_at"), "data": by_ticker})
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


if __name__ == "__main__":
    app.run(debug=True, port=5000)
