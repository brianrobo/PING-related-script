https://chatgpt.com/share/694f7350-4164-800a-a572-5b61b15b4f17


가능합니다. 지금 Tkinter로 만든 것을 “웹페이지에서 파일 업로드/텍스트 붙여넣기 → 서버에서 파싱 → 결과(추출/요약/비교/그래프)” 형태로 제공하는 방식은 표준적으로 다음 두 가지 아키텍처 중 하나로 구현합니다.

선택지 2가지

1) 서버 렌더링(간단·빠름): FastAPI/Flask + HTML 템플릿

웹페이지에서 파일 업로드/텍스트 붙여넣기

서버(Python)가 즉시 파싱해서

결과를 HTML로 렌더링해서 반환


장점: 구현 빠르고 운영 단순
단점: UI 상호작용(그래프 확대, 동적 비교 등)을 더 하려면 프론트 자바스크립트가 조금 늘어남

2) API + SPA(확장성 높음): FastAPI(백엔드) + React/Vue(프론트)

프론트는 파일 업로드/텍스트 입력 UI만 담당

백엔드 API가 파싱/비교 결과를 JSON으로 반환

프론트가 JSON을 시각화(차트/테이블/다운로드)


장점: UI/UX 확장 매우 좋음
단점: 초기 셋업이 더 큼

업무 자동화 툴을 빠르게 “내부 웹툴”로 만들 목적이면, 보통 1) FastAPI + 간단 HTML로 시작하고, 필요할 때 2)로 확장하는 흐름이 가장 효율적입니다.


---

권장 구현(당장 적용 가능한 형태)

아래는 “웹페이지 1개”로 해결하는 구조입니다.

상단: Metric selector (Ping / Uplink TP / Downlink TP)

좌측: Summary A(파일 업로드 또는 텍스트 붙여넣기)

우측: Summary B(파일 업로드 또는 텍스트 붙여넣기)

Compare 버튼 → 서버에서 파싱/평균/델타/시계열 포인트 생성

결과:

추출된 AvgResult 라인 리스트

Mean/Delta

시계열은 “값 리스트”를 테이블로 먼저 보여주고(차트는 옵션)



차트는 지금 matplotlib가 없다고 하셨으니, 웹에서는 오히려 쉬운 편입니다:

브라우저에서 Chart.js(자바스크립트)로 라인 차트/바 차트를 쉽게 그릴 수 있습니다.

서버는 값 배열만 JSON으로 내려주면 됩니다.



---

보안/운영 관점 체크포인트(중요)

사내 dumpState 로그는 민감할 수 있어서, 보통 아래 중 하나로 갑니다.

사내망 전용 서버(VPN/내부 DNS)

로컬 실행형(각자 PC에서 localhost:8000로 실행) → 외부 유출 리스크 최소


가장 안전하고 빠른 형태는 로컬 실행형 웹앱(127.0.0.1) 입니다.
사용자는 브라우저로 접속해서 쓰고, 파싱은 로컬에서만 이뤄집니다.


---

바로 쓸 수 있는 “최소 웹버전” 예시 (FastAPI)

아래 코드는:

/ : 웹 UI(HTML)

/api/compare : A/B 텍스트를 받아서 파싱 후 JSON 반환


까지 포함한 단일 파일 PoC입니다. (차트는 일단 숫자 리스트만 반환)

> 설치: pip install fastapi uvicorn
실행: python app.py 또는 uvicorn app:app --reload



# app.py
# ============================================================
# SpeedTestSKT Metric Comparator - Web PoC
# Version: 0.1.0 (2025-12-27)
# ============================================================

import re
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI()

# ---- tokens
TOKENS = {
    "PING": ("Ping", "Ping-AvgResult"),
    "UL": ("Uplink TP", "Up-AvgResult"),
    "DL": ("Downlink TP", "Downlink TP", "Down-AvgResult"),
}

# 실제 사용 토큰(정리)
METRICS = {
    "PING": ("Ping", "Ping-AvgResult"),
    "UL":   ("Uplink TP", "Up-AvgResult"),
    "DL":   ("Downlink TP", "Down-AvgResult"),
}

FILE_HEADER_RE = re.compile(r"^\[File\]\s+(?P<name>.+?)\s*$", re.IGNORECASE)

def to_float_num(s):
    s = (s or "").strip().replace(",", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None

def parse_summary(text: str, token: str):
    """
    Return: source_name, values(list), lines(list)
    """
    source = "Pasted"
    values = []
    lines = []

    line_re = re.compile(rf"\b{re.escape(token)}\b.*", re.IGNORECASE)
    val_re = re.compile(rf"\b{re.escape(token)}\b.*?(?:=|\s)(?P<val>[\d,]+(?:\.\d+)?)\b", re.IGNORECASE)

    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        mh = FILE_HEADER_RE.match(line)
        if mh:
            source = mh.group("name").strip()
            continue
        if not line_re.search(line):
            continue
        lines.append(line)
        mv = val_re.search(line)
        if mv:
            v = to_float_num(mv.group("val"))
            if v is not None:
                values.append(v)

    return source, values, lines

@app.get("/", response_class=HTMLResponse)
def index():
    return """
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>SpeedTestSKT Comparator (Web)</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 16px; }
    .row { display: flex; gap: 16px; }
    textarea { width: 100%; height: 240px; font-family: Consolas, monospace; font-size: 12px; }
    .box { flex: 1; }
    .result { white-space: pre-wrap; background: #f6f6f6; padding: 12px; border-radius: 8px; }
  </style>
</head>
<body>
  <h2>SpeedTestSKT Metric Comparator (Web PoC)</h2>

  <label>Metric:
    <select id="metric">
      <option value="PING">Ping</option>
      <option value="UL">Uplink TP</option>
      <option value="DL">Downlink TP</option>
    </select>
  </label>

  <div class="row" style="margin-top:12px;">
    <div class="box">
      <h3>Summary A</h3>
      <textarea id="a"></textarea>
    </div>
    <div class="box">
      <h3>Summary B</h3>
      <textarea id="b"></textarea>
    </div>
  </div>

  <button id="compare" style="margin-top:12px;">Compare</button>

  <h3>Result</h3>
  <div class="result" id="out">-</div>

<script>
document.getElementById("compare").addEventListener("click", async () => {
  const metric = document.getElementById("metric").value;
  const a = document.getElementById("a").value;
  const b = document.getElementById("b").value;

  const form = new FormData();
  form.append("metric", metric);
  form.append("a_text", a);
  form.append("b_text", b);

  const res = await fetch("/api/compare", { method:"POST", body: form });
  const js = await res.json();

  document.getElementById("out").textContent = JSON.stringify(js, null, 2);
});
</script>
</body>
</html>
"""

@app.post("/api/compare")
def api_compare(metric: str = Form(...), a_text: str = Form(""), b_text: str = Form("")):
    if metric not in METRICS:
        return JSONResponse({"error": "invalid metric"}, status_code=400)

    label, token = METRICS[metric]
    a_src, a_vals, a_lines = parse_summary(a_text, token)
    b_src, b_vals, b_lines = parse_summary(b_text, token)

    if not a_vals or not b_vals:
        return {
            "metric": label,
            "token": token,
            "warning": "No matching values in A or B. Check metric selector or pasted text.",
            "A": {"source": a_src, "n": len(a_vals), "mean": None, "values": a_vals, "lines": a_lines[:50]},
            "B": {"source": b_src, "n": len(b_vals), "mean": None, "values": b_vals, "lines": b_lines[:50]},
        }

    a_mean = sum(a_vals) / len(a_vals)
    b_mean = sum(b_vals) / len(b_vals)
    delta_pct = ((b_mean - a_mean) / a_mean) * 100.0 if a_mean != 0 else None

    return {
        "metric": label,
        "token": token,
        "A": {"source": a_src, "n": len(a_vals), "mean": a_mean, "values": a_vals, "lines": a_lines[:50]},
        "B": {"source": b_src, "n": len(b_vals), "mean": b_mean, "values": b_vals, "lines": b_lines[:50]},
        "delta_pct": delta_pct,
    }

이 PoC는 “웹에서 붙여넣기 → Compare → JSON 결과”까지 바로 됩니다.
여기서 다음 단계로:

파일 업로드( <input type="file"> + FastAPI UploadFile)

결과 화면을 지금 Tkinter처럼 보기 좋게 구성

Chart.js로 Mean bar/Series line을 브라우저에서 렌더링


을 붙이면, 원하시는 “특정 웹페이지에 접속해서 dumpState 올리고 결과 보는 툴”이 됩니다.


---

다음 단계 제안(업무 적용 관점)

1. 로컬 실행형 웹앱부터 (내부 로그 안전)


2. UI 요구사항이 안정되면


3. 사내 서버(내부망) 배포 + 계정/접근제어(SSO 또는 단순 인증)




---

원하시면, 지금 가지고 계신 Tkinter 기능을 기준으로 “웹 버전 v0.1.0”을 다음 요구사항까지 한 번에 올려드릴 수 있습니다.

파일 업로드(A/B 각각)

Metric selector

Compare 버튼

Mean/Delta 표시

AvgResult 라인 표 + 값 리스트 표

Chart.js로 Mean bar + Series line


필요한 것은 딱 하나입니다: 배포 형태를 (A) 로컬 실행형으로 할지, (B) 사내 서버 배포로 할지.
그 외는 제가 위 구조로 바로 코드로 옮겨드릴 수 있습니다.
