# ============================================================
# SpeedTestSKT Ping Log Extractor (GUI)
#
# Version: 1.1.1  (2025-12-27)
# Versioning: MAJOR.MINOR.PATCH (SemVer)
#
# Release Notes (v1.1.1):
# - (Fix) Ping-request  → Ping-Request (대문자 R)
# - (Fix) Ping-response → Ping-Response (대문자 R)
# - (Rule) 로그 원문(SpeedTestSKT: ...)은 그대로 유지
#          UI 출력(display)과 type 필드만 표준화된 표기 사용
#
# Previous Features:
# - 날짜(MM-DD) + 시간(HH:MM:SS.mmm) 추출
# - SpeedTestSKT Ping 관련 로그만 필터링
# - Tkinter GUI (파일 선택 / 결과 표시 / CSV 저장)
#
# Output Format:
#   "<MM-DD> <HH:MM:SS.mmm> SpeedTestSKT: TestData Ping-Request..."
# ============================================================

import re
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from pathlib import Path
import csv

# ------------------------------------------------------------
# Regex definitions
# ------------------------------------------------------------

PREFIX_RE = re.compile(
    r"(?P<date>\d{2}-\d{2})\s+"
    r"(?P<time>\d{2}:\d{2}:\d{2}\.\d{3})\s+"
    r"(?P<msg>SpeedTestSKT:.*)$"
)

PING_MSG_FILTER = re.compile(
    r"SpeedTestSKT:\s*TestData\s*Ping-(?:"
    r"[Rr]equest\d+|"
    r"[Rr]esponse\d+=\d+(?:\.\d+)?|"
    r"AvgResult.*)"
)

REQ_RE  = re.compile(r"Ping-[Rr]equest(\d+)")
RESP_RE = re.compile(r"Ping-[Rr]esponse(\d+)=([\d.]+)")
AVG_RE  = re.compile(r"Ping-AvgResult\s*=?\s*([\d.]+)?")

# ------------------------------------------------------------
# Core extraction logic
# ------------------------------------------------------------
def extract_ping_logs(log_path: Path):
    rows = []

    with log_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.rstrip("\n")

            m = PREFIX_RE.search(line.strip())
            if not m:
                continue

            date = m.group("date")
            time = m.group("time")
            raw_msg = m.group("msg")  # 원문 유지

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
                display_msg = re.sub(r"Ping-[Rr]equest", "Ping-Request", raw_msg)

            else:
                m2 = RESP_RE.search(raw_msg)
                if m2:
                    typ = "Ping-Response"
                    seq = m2.group(1)
                    val = m2.group(2)
                    display_msg = re.sub(r"Ping-[Rr]esponse", "Ping-Response", raw_msg)

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
            fieldnames=[
                "date", "time", "type",
                "seq", "value", "line",
                "raw_msg", "display"
            ]
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
