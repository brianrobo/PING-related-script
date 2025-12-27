# ============================================================
# SpeedTestSKT Ping Log Extractor (GUI)
#
# Version: 1.1.3  (2025-12-27)
# Versioning: MAJOR.MINOR.PATCH (SemVer)
#
# Release Notes (v1.1.3):
# - (Fix) 시간 뒤 PID/TID/레벨/프로세스명 등 토큰이 끼는 logcat 형태를 안정적으로 매칭
#   * time 이후부터 "SpeedTestSKT:" 직전까지를 non-greedy로 스킵 (가장 강건)
# - (Keep) SpeedTestSKT: 이후 메시지는 원문(raw_msg) 그대로 유지
# - (Keep) UI 출력(display)에서만 Ping-request/response를 Ping-Request/Ping-Response로 표준화
# ============================================================

import re
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from pathlib import Path
import csv

# ------------------------------------------------------------
# Regex definitions (robust for logcat tokens after time)
# ------------------------------------------------------------

# date:
#   - MM-DD  (12-27)
#   - YYYY-MM-DD (2025-12-27)
# time:
#   - HH:MM:SS
#   - HH:MM:SS.mmm / HH:MM:SS,mmm
#   - fractional 3~6 digits
#
# Critical: after time, skip ANYTHING until "SpeedTestSKT:" appears.
PREFIX_RE = re.compile(
    r"(?P<date>(?:\d{4}-\d{2}-\d{2})|(?:\d{2}-\d{2}))\s+"
    r"(?P<time>\d{2}:\d{2}:\d{2}(?:[.,]\d{3,6})?)"
    r".*?\b(?P<msg>SpeedTestSKT:.*)$"
)

# Filter only Ping-related messages
PING_MSG_FILTER = re.compile(
    r"SpeedTestSKT:\s*TestData\s*Ping-(?:"
    r"[Rr]equest\d+|"
    r"[Rr]esponse\d+=\d+(?:\.\d+)?|"
    r"AvgResult.*)"
)

# Detailed parse (for CSV columns)
REQ_RE  = re.compile(r"Ping-[Rr]equest(\d+)")
RESP_RE = re.compile(r"Ping-[Rr]esponse(\d+)=([\d.]+)")
AVG_RE  = re.compile(r"Ping-AvgResult\s*=?\s*([\d.]+)?")

# For display normalization only
REQ_NORM_RE  = re.compile(r"Ping-[Rr]equest")
RESP_NORM_RE = re.compile(r"Ping-[Rr]esponse")

# ------------------------------------------------------------
# Core extraction logic
# ------------------------------------------------------------
def extract_ping_logs(log_path: Path):
    rows = []

    with log_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.rstrip("\n")

            m = PREFIX_RE.search(line)
            if not m:
                continue

            date = m.group("date")
            time = m.group("time")
            raw_msg = m.group("msg")  # SpeedTestSKT: ... 원문

            if not PING_MSG_FILTER.search(raw_msg):
                continue

            typ = "Unknown"
            seq = ""
            val = ""

            display_msg = raw_msg

            m2 = REQ_RE.search(raw_msg)
            if m2:
                typ = "Ping-Request"
                seq = m2.group(1)
                display_msg = REQ_NORM_RE.sub("Ping-Request", raw_msg)
            else:
                m2 = RESP_RE.search(raw_msg)
                if m2:
                    typ = "Ping-Response"
                    seq = m2.group(1)
                    val = m2.group(2)
                    display_msg = RESP_NORM_RE.sub("Ping-Response", raw_msg)
                else:
                    m2 = AVG_RE.search(raw_msg)
                    if m2:
                        typ = "Ping-AvgResult"
                        val = m2.group(1) or ""

            rows.append({
                "date": date,
                "time": time,
                "type": typ,
                "seq": seq,
                "value": val,
                "line": line_no,
                "raw_msg": raw_msg,                 # 원문 유지
                "display": f"{date} {time} {display_msg}",  # 표준화 반영 출력
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

    if len(results) == 0:
        output.insert(
            tk.END,
            "\n[Hint] 0건이면, SpeedTestSKT 라인이 실제로 포함되어 있는지(대소문자 포함)와\n"
            "date/time 포맷이 다른지 확인이 필요합니다.\n"
        )

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
