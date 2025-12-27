# ============================================================
# SpeedTestSKT Ping Log Extractor (GUI)
#
# Version: 1.2.0  (2025-12-27)
# Versioning: MAJOR.MINOR.PATCH (SemVer)
#
# Release Notes (v1.2.0):
# - (Feature) 메인 출력창에서 Ping-AvgResult 라인 출력 후 빈 줄(개행) 추가
# - (Feature) UI 하단에 Summary 출력창 추가
#     * Ping-AvgResult만 모아서 출력
#     * AvgResult들의 value 평균(Avg of AvgResult) 계산/표시
# - (Fix) logcat 형태(시간 뒤 PID/TID/토큰 가변, 공백/탭 가변) 안정 추출:
#     * 날짜/시간과 SpeedTestSKT 태그를 독립적으로 탐색(정규식 결합 실패 방지)
# - (Keep) SpeedTestSKT: 이후 메시지는 raw_msg로 원문 유지
# - (Keep) display/type에서 Ping-request/response를 Ping-Request/Ping-Response로 표준화
# ============================================================

import re
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from pathlib import Path
import csv

# ------------------------------------------------------------
# Regex (robust, decoupled)
# ------------------------------------------------------------

# date: MM-DD or YYYY-MM-DD
DATE_RE = re.compile(r"(?P<date>(?:\d{4}-\d{2}-\d{2})|(?:\d{2}-\d{2}))")

# time: HH:MM:SS or HH:MM:SS.mmm / HH:MM:SS,mmm (fraction 3~6 optional)
TIME_RE = re.compile(r"(?P<time>\d{2}:\d{2}:\d{2}(?:[.,]\d{3,6})?)")

# SpeedTestSKT tag: allow optional spaces before colon
# Examples:
#   "SpeedTestSKT: TestData ..."
#   "SpeedTestSKT : TestData ..."
SPEEDTEST_RE = re.compile(r"(?P<msg>SpeedTestSKT\s*:\s*.*)$")

# Ping message filter (case-tolerant)
PING_MSG_FILTER = re.compile(
    r"SpeedTestSKT\s*:\s*TestData\s*Ping-(?:"
    r"[Rr]equest\d+|"
    r"[Rr]esponse\d+=\d+(?:\.\d+)?|"
    r"AvgResult.*)"
)

# Detailed parse (for CSV)
REQ_RE  = re.compile(r"Ping-[Rr]equest(\d+)")
RESP_RE = re.compile(r"Ping-[Rr]esponse(\d+)=([\d.]+)")
AVG_RE  = re.compile(r"Ping-AvgResult\s*=?\s*([\d.]+)?")

# Display normalization only
REQ_NORM_RE  = re.compile(r"Ping-[Rr]equest")
RESP_NORM_RE = re.compile(r"Ping-[Rr]esponse")


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def _find_date_time(line: str):
    d = DATE_RE.search(line)
    t = TIME_RE.search(line)
    if not d or not t:
        return None, None
    return d.group("date"), t.group("time")


def _normalize_display_msg(raw_msg: str):
    msg = REQ_NORM_RE.sub("Ping-Request", raw_msg)
    msg = RESP_NORM_RE.sub("Ping-Response", msg)
    return msg


def _to_float(s: str):
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


# ------------------------------------------------------------
# Core extraction
# ------------------------------------------------------------
def extract_ping_logs(log_path: Path):
    rows = []

    with log_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.rstrip("\n")

            date, time = _find_date_time(line)
            if not date or not time:
                continue

            m = SPEEDTEST_RE.search(line)
            if not m:
                continue

            raw_msg = m.group("msg")  # "SpeedTestSKT: ..." 원문

            if not PING_MSG_FILTER.search(raw_msg):
                continue

            typ = "Unknown"
            seq = ""
            val = ""

            m2 = REQ_RE.search(raw_msg)
            if m2:
                typ = "Ping-Request"
                seq = m2.group(1)
            else:
                m2 = RESP_RE.search(raw_msg)
                if m2:
                    typ = "Ping-Response"
                    seq = m2.group(1)
                    val = m2.group(2)
                else:
                    m2 = AVG_RE.search(raw_msg)
                    if m2:
                        typ = "Ping-AvgResult"
                        val = m2.group(1) or ""

            display_msg = _normalize_display_msg(raw_msg)

            rows.append({
                "date": date,
                "time": time,
                "type": typ,
                "seq": seq,
                "value": val,
                "line": line_no,
                "raw_msg": raw_msg,
                "display": f"{date} {time} {display_msg}",
            })

    return rows


# ------------------------------------------------------------
# UI callbacks
# ------------------------------------------------------------
def open_log():
    file_path = filedialog.askopenfilename(
        title="Select log file",
        filetypes=[("Log files", "*.txt *.log"), ("All files", "*.*")]
    )
    if not file_path:
        return
    log_file.set(file_path)
    parse_log()


def parse_log():
    output.delete("1.0", tk.END)
    summary_output.delete("1.0", tk.END)

    path = Path(log_file.get())
    if not path.exists():
        messagebox.showerror("Error", "Invalid log file path")
        return

    results.clear()
    results.extend(extract_ping_logs(path))

    # ---- Main output ----
    for r in results:
        output.insert(tk.END, r["display"] + "\n")
        # 요구사항: AvgResult 다음에는 개행(빈 줄) 추가
        if r["type"] == "Ping-AvgResult":
            output.insert(tk.END, "\n")

    output.insert(tk.END, f"\n--- Total {len(results)} entries ---\n")

    # ---- Summary output: only AvgResult ----
    avg_rows = [r for r in results if r["type"] == "Ping-AvgResult"]
    values = []
    for r in avg_rows:
        v = _to_float(r.get("value", ""))
        if v is not None:
            values.append(v)
        summary_output.insert(tk.END, r["display"] + "\n")

    summary_output.insert(tk.END, f"\n--- AvgResult Count: {len(avg_rows)} ---\n")

    if values:
        mean_val = sum(values) / len(values)
        summary_output.insert(tk.END, f"Avg of AvgResult (mean): {mean_val:.3f}\n")
    else:
        summary_output.insert(tk.END, "Avg of AvgResult (mean): N/A (no numeric values)\n")


def save_csv():
    if not results:
        messagebox.showwarning("Warning", "No data to save")
        return

    save_path = filedialog.asksaveasfilename(
        title="Save CSV",
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv")]
    )
    if not save_path:
        return

    with open(save_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["date", "time", "type", "seq", "value", "line", "raw_msg", "display"]
        )
        writer.writeheader()
        writer.writerows(results)

    messagebox.showinfo("Saved", f"CSV saved:\n{save_path}")


# ------------------------------------------------------------
# UI setup
# ------------------------------------------------------------
root = tk.Tk()
root.title("SpeedTestSKT Ping Log Extractor")
root.geometry("980x720")

log_file = tk.StringVar()
results = []

top = tk.Frame(root)
top.pack(fill="x", padx=10, pady=5)

tk.Entry(top, textvariable=log_file).pack(side="left", fill="x", expand=True)
tk.Button(top, text="Browse", command=open_log).pack(side="left", padx=5)
tk.Button(top, text="Save CSV", command=save_csv).pack(side="left")

# Main output (upper)
main_label = tk.Label(root, text="Extracted Logs")
main_label.pack(anchor="w", padx=10)

output = scrolledtext.ScrolledText(root, font=("Consolas", 10), height=18)
output.pack(fill="both", expand=True, padx=10, pady=(0, 8))

# Summary output (lower)
summary_label = tk.Label(root, text="Summary (Ping-AvgResult Only)")
summary_label.pack(anchor="w", padx=10)

summary_output = scrolledtext.ScrolledText(root, font=("Consolas", 10), height=10)
summary_output.pack(fill="both", expand=False, padx=10, pady=(0, 10))

root.mainloop()
