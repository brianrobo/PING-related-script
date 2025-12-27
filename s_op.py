# ============================================================
# SpeedTestSKT Ping Log Extractor & Comparator (GUI, No matplotlib)
#
# Version: 1.4.0  (2025-12-27)
# Versioning: MAJOR.MINOR.PATCH (SemVer)
#
# Release Notes (v1.4.0):
# - (Feature) Summary A/B에 "파일 결과"뿐 아니라 "사용자 붙여넣기" 텍스트도 지원
#     * Summary 박스에 과거 결과물을 붙여넣고
#     * [Compare Now] 버튼을 누르면 A/B를 파싱하여 Mean/Delta/그래프 업데이트
# - (Keep) 파일 Browse A/B 시에도 Summary 박스에 AvgResult만 자동 채워줌
# - (Keep) matplotlib 없이 Tkinter Canvas로 막대 그래프 표시
# ============================================================

import re
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from pathlib import Path
import csv

# ------------------------------------------------------------
# Regex for log extraction (file-based)
# ------------------------------------------------------------
DATE_RE = re.compile(r"(?P<date>(?:\d{4}-\d{2}-\d{2})|(?:\d{2}-\d{2}))")
TIME_RE = re.compile(r"(?P<time>\d{2}:\d{2}:\d{2}(?:[.,]\d{3,6})?)")
SPEEDTEST_RE = re.compile(r"(?P<msg>SpeedTestSKT\s*:\s*.*)$")

PING_MSG_FILTER = re.compile(
    r"SpeedTestSKT\s*:\s*TestData\s*Ping-(?:"
    r"[Rr]equest\d+|"
    r"[Rr]esponse\d+=\d+(?:\.\d+)?|"
    r"AvgResult.*)"
)

REQ_RE  = re.compile(r"Ping-[Rr]equest(\d+)")
RESP_RE = re.compile(r"Ping-[Rr]esponse(\d+)=([\d.]+)")
AVG_RE  = re.compile(r"Ping-AvgResult\s*=?\s*([\d.]+)?")

REQ_NORM_RE  = re.compile(r"Ping-[Rr]equest")
RESP_NORM_RE = re.compile(r"Ping-[Rr]esponse")

# ------------------------------------------------------------
# Regex for parsing pasted summary text (more permissive)
# ------------------------------------------------------------
# Accept lines that contain Ping-AvgResult and an optional numeric value after '=' or whitespace.
PASTE_AVG_LINE_RE = re.compile(r"Ping-AvgResult\b.*", re.IGNORECASE)
PASTE_AVG_VALUE_RE = re.compile(r"Ping-AvgResult\b.*?(?:=|\s)(?P<val>[\d.]+)\b", re.IGNORECASE)


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


def _to_float(s):
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


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

            raw_msg = m.group("msg")
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


def summarize_avgresults(rows):
    avg_rows = [r for r in rows if r["type"] == "Ping-AvgResult"]
    values = []
    for r in avg_rows:
        v = _to_float(r.get("value", ""))
        if v is not None:
            values.append(v)
    mean_val = (sum(values) / len(values)) if values else None
    return avg_rows, values, mean_val


def summarize_from_text(text: str):
    """
    Parse pasted/edited summary text and extract Ping-AvgResult lines + numeric values.
    Returns:
      - lines: list[str] (AvgResult lines)
      - values: list[float]
      - mean: float|None
    """
    lines = []
    values = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if not PASTE_AVG_LINE_RE.search(line):
            continue

        lines.append(line)

        mv = PASTE_AVG_VALUE_RE.search(line)
        if mv:
            v = _to_float(mv.group("val"))
            if v is not None:
                values.append(v)

    mean_val = (sum(values) / len(values)) if values else None
    return lines, values, mean_val


# ------------------------------------------------------------
# Canvas bar chart (no external libs)
# ------------------------------------------------------------
def draw_bar_chart(a_mean, b_mean, delta_pct):
    chart.delete("all")

    w = int(chart.winfo_width() or 900)
    h = int(chart.winfo_height() or 220)

    pad = 20
    base_y = h - 40
    top_y = 20

    chart.create_line(pad, base_y, w - pad, base_y)
    chart.create_line(pad, base_y, pad, top_y)

    if a_mean is None or b_mean is None:
        chart.create_text(w // 2, h // 2, text="Paste/Load both Summary A and Summary B, then click 'Compare Now'")
        return

    max_val = max(a_mean, b_mean)
    if max_val <= 0:
        max_val = 1.0

    bar_w = 120
    gap = 120
    x_a = pad + 120
    x_b = x_a + bar_w + gap

    def bar_height(v):
        usable = base_y - top_y - 10
        return (v / max_val) * usable

    ha = bar_height(a_mean)
    hb = bar_height(b_mean)

    chart.create_rectangle(x_a, base_y - ha, x_a + bar_w, base_y, outline="")
    chart.create_rectangle(x_b, base_y - hb, x_b + bar_w, base_y, outline="")

    chart.create_text(x_a + bar_w/2, base_y + 15, text="A")
    chart.create_text(x_b + bar_w/2, base_y + 15, text="B")

    chart.create_text(x_a + bar_w/2, base_y - ha - 12, text=f"{a_mean:.4f}")
    chart.create_text(x_b + bar_w/2, base_y - hb - 12, text=f"{b_mean:.4f}")

    if delta_pct is not None:
        chart.create_text(w // 2, 12, text=f"Delta: {delta_pct:+.2f}% (B vs A)")


# ------------------------------------------------------------
# Compare logic (button-triggered)
# ------------------------------------------------------------
def compare_now():
    text_a = summary_a.get("1.0", tk.END)
    text_b = summary_b.get("1.0", tk.END)

    a_lines, a_vals, a_mean = summarize_from_text(text_a)
    b_lines, b_vals, b_mean = summarize_from_text(text_b)

    comp_state["A_mean"] = a_mean
    comp_state["B_mean"] = b_mean
    comp_state["A_count"] = len(a_vals)
    comp_state["B_count"] = len(b_vals)

    a_txt = f"{a_mean:.6f}" if a_mean is not None else "N/A"
    b_txt = f"{b_mean:.6f}" if b_mean is not None else "N/A"

    label_a_mean.config(text=f"A Mean: {a_txt}   (n={len(a_vals)})")
    label_b_mean.config(text=f"B Mean: {b_txt}   (n={len(b_vals)})")

    if a_mean is not None and b_mean is not None and a_mean != 0:
        delta_pct = ((b_mean - a_mean) / a_mean) * 100.0
        label_delta.config(text=f"Delta: {delta_pct:+.2f}%   (B vs A)")
        draw_bar_chart(a_mean, b_mean, delta_pct)
    elif a_mean is not None and b_mean is not None and a_mean == 0:
        label_delta.config(text="Delta: N/A (A mean is 0)")
        draw_bar_chart(a_mean, b_mean, None)
    else:
        label_delta.config(text="Delta: N/A (need numeric AvgResult values in both A and B)")
        draw_bar_chart(None, None, None)


# ------------------------------------------------------------
# File loading into Summary A/B (optional convenience)
# ------------------------------------------------------------
def open_log_a():
    file_path = filedialog.askopenfilename(
        title="Select Log A",
        filetypes=[("Log files", "*.txt *.log"), ("All files", "*.*")]
    )
    if not file_path:
        return
    log_a_path.set(file_path)
    load_avg_into_summary("A")


def open_log_b():
    file_path = filedialog.askopenfilename(
        title="Select Log B",
        filetypes=[("Log files", "*.txt *.log"), ("All files", "*.*")]
    )
    if not file_path:
        return
    log_b_path.set(file_path)
    load_avg_into_summary("B")


def load_avg_into_summary(which):
    if which == "A":
        path = Path(log_a_path.get())
        out = summary_a
    else:
        path = Path(log_b_path.get())
        out = summary_b

    out.delete("1.0", tk.END)

    if not path.exists():
        messagebox.showerror("Error", f"Invalid Log {which} path")
        return

    rows = extract_ping_logs(path)
    avg_rows, values, mean_val = summarize_avgresults(rows)

    for r in avg_rows:
        out.insert(tk.END, r["display"] + "\n")

    out.insert(tk.END, f"\n--- AvgResult Count (numeric): {len(values)} ---\n")
    out.insert(tk.END, f"Mean AvgResult: {mean_val:.6f}\n" if mean_val is not None else "Mean AvgResult: N/A\n")


# ------------------------------------------------------------
# UI setup
# ------------------------------------------------------------
root = tk.Tk()
root.title("SpeedTestSKT Ping Comparator (Paste or File, No matplotlib)")
root.geometry("1100x820")

log_a_path = tk.StringVar()
log_b_path = tk.StringVar()

comp_state = {"A_mean": None, "B_mean": None, "A_count": 0, "B_count": 0}

frame_comp = tk.LabelFrame(root, text="Compare Summaries (Paste text OR Load logs)")
frame_comp.pack(fill="both", expand=True, padx=10, pady=10)

ctrl = tk.Frame(frame_comp)
ctrl.pack(fill="x", padx=8, pady=6)

tk.Entry(ctrl, textvariable=log_a_path).pack(side="left", fill="x", expand=True)
tk.Button(ctrl, text="Load A (from file)", command=open_log_a).pack(side="left", padx=6)

tk.Entry(ctrl, textvariable=log_b_path).pack(side="left", fill="x", expand=True)
tk.Button(ctrl, text="Load B (from file)", command=open_log_b).pack(side="left", padx=6)

pane = tk.Frame(frame_comp)
pane.pack(fill="both", expand=True, padx=8, pady=6)

left = tk.Frame(pane)
left.pack(side="left", fill="both", expand=True, padx=(0, 6))

right = tk.Frame(pane)
right.pack(side="left", fill="both", expand=True, padx=(6, 0))

tk.Label(left, text="Summary A (Paste here or Load A)").pack(anchor="w")
summary_a = scrolledtext.ScrolledText(left, font=("Consolas", 10), height=18)
summary_a.pack(fill="both", expand=True)

tk.Label(right, text="Summary B (Paste here or Load B)").pack(anchor="w")
summary_b = scrolledtext.ScrolledText(right, font=("Consolas", 10), height=18)
summary_b.pack(fill="both", expand=True)

actions = tk.Frame(frame_comp)
actions.pack(fill="x", padx=8, pady=6)

tk.Button(actions, text="Compare Now", command=compare_now).pack(side="left")

label_a_mean = tk.Label(actions, text="A Mean: N/A   (n=0)")
label_a_mean.pack(side="left", padx=16)

label_b_mean = tk.Label(actions, text="B Mean: N/A   (n=0)")
label_b_mean.pack(side="left", padx=16)

label_delta = tk.Label(actions, text="Delta: N/A")
label_delta.pack(side="left", padx=16)

chart = tk.Canvas(frame_comp, height=200)
chart.pack(fill="x", padx=8, pady=(0, 10))

# initial
draw_bar_chart(None, None, None)

root.mainloop()
