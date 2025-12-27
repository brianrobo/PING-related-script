# ============================================================
# SpeedTestSKT Ping Log Extractor & Comparator (GUI, No matplotlib)
#
# Version: 1.3.1  (2025-12-27)
# Versioning: MAJOR.MINOR.PATCH (SemVer)
#
# Release Notes (v1.3.1):
# - (Fix) matplotlib 미설치 환경 지원: 외부 라이브러리 없이 Tkinter Canvas로 그래프(막대) 직접 표시
# - (Feature) Log A / Log B AvgResult summary 비교 및 Delta(%) 계산/표시
# - (Keep) 메인 출력창에서 Ping-AvgResult 출력 후 빈 줄(개행) 추가
# - (Keep) logcat 형태(시간 뒤 PID/TID/토큰 가변, 공백/탭 가변) 안정 추출:
#     * 날짜/시간과 SpeedTestSKT 태그를 독립적으로 탐색
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


# ------------------------------------------------------------
# Simple Canvas Bar Chart (No external libs)
# ------------------------------------------------------------
def draw_bar_chart(a_mean, b_mean, delta_pct):
    chart.delete("all")

    w = int(chart.winfo_width() or 900)
    h = int(chart.winfo_height() or 220)

    pad = 20
    base_y = h - 40
    top_y = 20

    # axes
    chart.create_line(pad, base_y, w - pad, base_y)  # x axis
    chart.create_line(pad, base_y, pad, top_y)       # y axis

    if a_mean is None or b_mean is None:
        chart.create_text(w // 2, h // 2, text="Load both Log A and Log B to compare")
        return

    max_val = max(a_mean, b_mean)
    if max_val <= 0:
        max_val = 1.0

    # bar settings
    bar_w = 120
    gap = 120
    x_a = pad + 120
    x_b = x_a + bar_w + gap

    def bar_height(v):
        usable = base_y - top_y - 10
        return (v / max_val) * usable

    ha = bar_height(a_mean)
    hb = bar_height(b_mean)

    # Bars (default canvas color)
    chart.create_rectangle(x_a, base_y - ha, x_a + bar_w, base_y, outline="")
    chart.create_rectangle(x_b, base_y - hb, x_b + bar_w, base_y, outline="")

    # Labels
    chart.create_text(x_a + bar_w/2, base_y + 15, text="A")
    chart.create_text(x_b + bar_w/2, base_y + 15, text="B")

    chart.create_text(x_a + bar_w/2, base_y - ha - 12, text=f"{a_mean:.4f}")
    chart.create_text(x_b + bar_w/2, base_y - hb - 12, text=f"{b_mean:.4f}")

    if delta_pct is not None:
        chart.create_text(w // 2, 12, text=f"Delta: {delta_pct:+.2f}% (B vs A)")

    # y ticks (simple)
    for i in range(1, 5):
        y = base_y - (i/4) * (base_y - top_y - 10)
        chart.create_line(pad - 5, y, pad + 5, y)
        tick_val = (i/4) * max_val
        chart.create_text(pad + 35, y, text=f"{tick_val:.2f}")


def update_compare_view():
    a = comp_state.get("A_mean")
    b = comp_state.get("B_mean")

    a_txt = f"{a:.6f}" if a is not None else "N/A"
    b_txt = f"{b:.6f}" if b is not None else "N/A"

    label_a_mean.config(text=f"A Mean: {a_txt}   (n={comp_state.get('A_count', 0)})")
    label_b_mean.config(text=f"B Mean: {b_txt}   (n={comp_state.get('B_count', 0)})")

    if a is not None and b is not None and a != 0:
        delta_pct = ((b - a) / a) * 100.0
        label_delta.config(text=f"Delta: {delta_pct:+.2f}%   (B vs A)")
        draw_bar_chart(a, b, delta_pct)
    elif a is not None and b is not None and a == 0:
        label_delta.config(text="Delta: N/A (A mean is 0)")
        draw_bar_chart(a, b, None)
    else:
        label_delta.config(text="Delta: N/A (load both A and B)")
        draw_bar_chart(None, None, None)


# ------------------------------------------------------------
# UI callbacks (Main Extractor)
# ------------------------------------------------------------
def open_main_log():
    file_path = filedialog.askopenfilename(
        title="Select log file",
        filetypes=[("Log files", "*.txt *.log"), ("All files", "*.*")]
    )
    if not file_path:
        return
    main_log_file.set(file_path)
    parse_main_log()


def parse_main_log():
    main_output.delete("1.0", tk.END)

    path = Path(main_log_file.get())
    if not path.exists():
        messagebox.showerror("Error", "Invalid log file path")
        return

    main_results.clear()
    main_results.extend(extract_ping_logs(path))

    for r in main_results:
        main_output.insert(tk.END, r["display"] + "\n")
        if r["type"] == "Ping-AvgResult":
            main_output.insert(tk.END, "\n")  # blank line after AvgResult

    main_output.insert(tk.END, f"\n--- Total {len(main_results)} entries ---\n")


def save_main_csv():
    if not main_results:
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
        writer.writerows(main_results)

    messagebox.showinfo("Saved", f"CSV saved:\n{save_path}")


# ------------------------------------------------------------
# UI callbacks (Compare Summaries)
# ------------------------------------------------------------
def open_log_a():
    file_path = filedialog.askopenfilename(
        title="Select Log A",
        filetypes=[("Log files", "*.txt *.log"), ("All files", "*.*")]
    )
    if not file_path:
        return
    log_a_path.set(file_path)
    load_and_summarize("A")


def open_log_b():
    file_path = filedialog.askopenfilename(
        title="Select Log B",
        filetypes=[("Log files", "*.txt *.log"), ("All files", "*.*")]
    )
    if not file_path:
        return
    log_b_path.set(file_path)
    load_and_summarize("B")


def load_and_summarize(which):
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

    if which == "A":
        comp_state["A_rows"] = rows
        comp_state["A_mean"] = mean_val
        comp_state["A_count"] = len(values)
    else:
        comp_state["B_rows"] = rows
        comp_state["B_mean"] = mean_val
        comp_state["B_count"] = len(values)

    for r in avg_rows:
        out.insert(tk.END, r["display"] + "\n")

    out.insert(tk.END, f"\n--- AvgResult Count (numeric): {len(values)} ---\n")
    out.insert(tk.END, f"Mean AvgResult: {mean_val:.6f}\n" if mean_val is not None else "Mean AvgResult: N/A\n")

    update_compare_view()


# ------------------------------------------------------------
# UI setup
# ------------------------------------------------------------
root = tk.Tk()
root.title("SpeedTestSKT Ping Log Extractor & Comparator (No matplotlib)")
root.geometry("1100x880")

# State
main_log_file = tk.StringVar()
main_results = []

log_a_path = tk.StringVar()
log_b_path = tk.StringVar()
comp_state = {
    "A_rows": None, "B_rows": None,
    "A_mean": None, "B_mean": None,
    "A_count": 0, "B_count": 0,
}

# ---------------- Main Extractor Section ----------------
frame_main = tk.LabelFrame(root, text="1) Extract (Single Log)")
frame_main.pack(fill="x", padx=10, pady=8)

row1 = tk.Frame(frame_main)
row1.pack(fill="x", padx=8, pady=6)

tk.Entry(row1, textvariable=main_log_file).pack(side="left", fill="x", expand=True)
tk.Button(row1, text="Browse", command=open_main_log).pack(side="left", padx=6)
tk.Button(row1, text="Save CSV", command=save_main_csv).pack(side="left")

tk.Label(frame_main, text="Extracted Logs").pack(anchor="w", padx=8)
main_output = scrolledtext.ScrolledText(frame_main, font=("Consolas", 10), height=14)
main_output.pack(fill="both", expand=False, padx=8, pady=(0, 8))

# ---------------- Compare Section ----------------
frame_comp = tk.LabelFrame(root, text="2) Compare Summaries (Log A vs Log B)")
frame_comp.pack(fill="both", expand=True, padx=10, pady=8)

ctrl = tk.Frame(frame_comp)
ctrl.pack(fill="x", padx=8, pady=6)

tk.Entry(ctrl, textvariable=log_a_path).pack(side="left", fill="x", expand=True)
tk.Button(ctrl, text="Browse A", command=open_log_a).pack(side="left", padx=6)

tk.Entry(ctrl, textvariable=log_b_path).pack(side="left", fill="x", expand=True)
tk.Button(ctrl, text="Browse B", command=open_log_b).pack(side="left", padx=6)

pane = tk.Frame(frame_comp)
pane.pack(fill="both", expand=True, padx=8, pady=6)

left = tk.Frame(pane)
left.pack(side="left", fill="both", expand=True, padx=(0, 6))

right = tk.Frame(pane)
right.pack(side="left", fill="both", expand=True, padx=(6, 0))

tk.Label(left, text="Summary A (Ping-AvgResult Only)").pack(anchor="w")
summary_a = scrolledtext.ScrolledText(left, font=("Consolas", 10), height=10)
summary_a.pack(fill="both", expand=True)

tk.Label(right, text="Summary B (Ping-AvgResult Only)").pack(anchor="w")
summary_b = scrolledtext.ScrolledText(right, font=("Consolas", 10), height=10)
summary_b.pack(fill="both", expand=True)

metrics = tk.Frame(frame_comp)
metrics.pack(fill="x", padx=8, pady=6)

label_a_mean = tk.Label(metrics, text="A Mean: N/A   (n=0)")
label_a_mean.pack(anchor="w")

label_b_mean = tk.Label(metrics, text="B Mean: N/A   (n=0)")
label_b_mean.pack(anchor="w")

label_delta = tk.Label(metrics, text="Delta: N/A (load both A and B)")
label_delta.pack(anchor="w", pady=(0, 6))

# Canvas chart
chart = tk.Canvas(frame_comp, height=220)
chart.pack(fill="x", padx=8, pady=(0, 10))

# redraw on resize
def _on_chart_resize(_evt):
    update_compare_view()

chart.bind("<Configure>", _on_chart_resize)

# initial chart
draw_bar_chart(None, None, None)

root.mainloop()
