# ============================================================
# SpeedTestSKT Ping Log Extractor (GUI)
#
# Version: 1.1.5  (2025-12-27)
# Versioning: MAJOR.MINOR.PATCH (SemVer)
#
# Release Notes (v1.1.5):
# - (Fix) logcat 형태(시간 뒤 PID/TID/토큰 가변, 공백/탭 가변)에서 매칭 실패하던 문제 해결
#   * "날짜/시간"과 "SpeedTestSKT:"를 하나의 정규식으로 묶지 않고, 각각 독립적으로 탐색
#   * "SpeedTestSKT:" 뿐 아니라 "SpeedTestSKT :" (콜론 앞 공백)도 허용
# - (Keep) Ping-Request / Ping-Response 표기 표준화(display/type에만 적용)
# - (Keep) SpeedTestSKT: 이후 메시지는 raw_msg로 원문 유지
# - (Keep) UI: 파일 선택 / 결과 표시 / CSV 저장
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

# SpeedTestSKT tag: allow optional spaces before colon, keep "SpeedTestSKT: ..." as raw_msg
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
    """
    Finds the first plausible date and time in a line.
    Returns (date, time) or (None, None).
    """
    d = DATE_RE.search(line)
    t = TIME_RE.search(line)

    if not d or not t:
        return None, None

    # Optional sanity: ensure date appears before time (typical logcat)
    if d.start() > t.start():
        # still accept, but many logs have date first; this avoids weird matches
        pass

    return d.group("date"), t.group("time")


def _normalize_display_msg(raw_msg: str):
    """
    Keeps raw_msg as-is except standardizes Ping-Request/Ping-Response casing for display.
    """
    msg = REQ_NORM_RE.sub("Ping-Request", raw_msg)
    msg = RESP_NORM_RE.sub("Ping-Response", msg)
    return msg


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

            raw_msg = m.group("msg")  # e.g., "SpeedTestSKT: TestData Ping-Request50"
            # Normalize raw_msg to canonical spacing around ":" for consistent filtering/CSV
            # (Still "원문 유지" 요구가 있으니, 저장은 raw_msg 그대로 두고 display만 정규화)
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

    path = Path(log_file.get())
    if not path.exists():
        messagebox.showerror("Error", "Invalid log file path")
        return

    results.clear()
    results.extend(extract_ping_logs(path))

    for r in results:
        output.insert(tk.END, r["display"] + "\n")

    output.insert(tk.END, f"\n--- Total {len(results)} entries ---\n")


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
root.geometry("950x600")

log_file = tk.StringVar()
results = []

top = tk.Frame(root)
top.pack(fill="x", padx=10, pady=5)

tk.Entry(top, textvariable=log_file).pack(side="left", fill="x", expand=True)
tk.Button(top, text="Browse", command=open_log).pack(side="left", padx=5)
tk.Button(top, text="Save CSV", command=save_csv).pack(side="left")

output = scrolledtext.ScrolledText(root, font=("Consolas", 10))
output.pack(fill="both", expand=True, padx=10, pady=10)

root.mainloop()
