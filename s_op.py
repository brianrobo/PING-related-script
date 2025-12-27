# ============================================================
# SpeedTestSKT Ping Log Extractor & Comparator (GUI)
#
# Version: 1.3.0  (2025-12-27)
# Versioning: MAJOR.MINOR.PATCH (SemVer)
#
# Release Notes (v1.3.0):
# - (Feature) Summary 비교 기능 추가:
#     * Log A / Log B를 각각 선택
#     * Ping-AvgResult만 모아서 각 Summary 창에 출력
#     * AvgResult 평균(A_mean, B_mean) 비교 -> Delta(%) 계산/표시
# - (Feature) 그래프 표시:
#     * A_mean vs B_mean 막대 그래프
#     * Delta(%) 텍스트로 함께 표시
# - (Keep) 메인 출력창에서 Ping-AvgResult 출력 후 빈 줄(개행) 추가
# - (Keep) logcat 형태(시간 뒤 PID/TID/토큰 가변, 공백/탭 가변) 안정 추출:
#     * 날짜/시간과 SpeedTestSKT 태그를 독립적으로 탐색
# - (Keep) SpeedTestSKT: 이후 메시지는 raw_msg로 원문 유지
# - (Keep) display/type에서 Ping-request/response를 Ping-Request/Ping-Response로 표준화
#
# Requirements:
# - matplotlib 설치 필요 (대부분 환경에 존재). 없으면: pip install matplotlib
# ============================================================

import re
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from pathlib import Path
import csv

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


# ------------------------------------------------------------
# Regex (robust, decoupled)
# ------------------------------------------------------------

DATE_RE = re.compile(r"(?P<date>(?:\d{4}-\d{2}-\d{2})|(?:\d{2}-\d{2}))")
TIME_RE = re.compile(r"(?P<time>\d{2}:\d{2}:\d{2}(?:[.,]\d{3,6})?)")

# allow optional spaces before colon
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

            raw_msg = m.group("msg")  # keep original SpeedTestSKT... part

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
    """Return (avg_rows, numeric_values, mean or None)."""
    avg_rows = [r for r in rows if r["type"] == "Ping-AvgResult"]
    values = []
    for r in avg_rows:
        v = _to_float(r.get("value", ""))
        if v is not None:
            values.append(v)
    mean_val = (sum(values) / len(values)) if values else None
    return avg_rows, values, mean_val


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

    # store
    if which == "A":
        comp_state["A_rows"] = rows
        comp_state["A_mean"] = mean_val
        comp_state["A_count"] = len(values)
    else:
        comp_state["B_rows"] = rows
        comp_state["B_mean"] = mean_val
        comp_state["B_count"] = len(values)

    # print AvgResult only
    for r in avg_rows:
        out.insert(tk.END, r["display"] + "\n")

    out.insert(tk.END, f"\n--- AvgResult Count (numeric): {len(values)} ---\n")
    out.insert(tk.END, f"Mean AvgResult: {mean_val:.6f}\n" if mean_val is not None else "Mean AvgResult: N/A\n")

    update_compare_view()


def update_compare_view():
    """Compute delta and refresh labels + chart if A and B are loaded."""
    a = comp_state.get("A_mean")
    b = comp_state.get("B_mean")

    # Update numeric labels even if one side missing
    a_txt = f"{a:.6f}" if a is not None else "N/A"
    b_txt = f"{b:.6f}" if b is not None else "N/A"
    label_a_mean.config(text=f"A Mean: {a_txt}   (n={comp_state.get('A_count', 0)})")
    label_b_mean.config(text=f"B Mean: {b_txt}   (n={comp_state.get('B_count', 0)})")

    # Delta
    if a is not None and b is not None:
        if a == 0:
            delta_txt = "Delta: N/A (A mean is 0)"
            delta_pct = None
        else:
            delta_pct = ((b - a) / a) * 100.0
            delta_txt = f"Delta: {delta_pct:+.2f}%   (B vs A)"
        label_delta.config(text=delta_txt)
        redraw_chart(a, b, delta_pct)
    else:
        label_delta.config(text="Delta: N/A (load both A and B)")
        redraw_chart(None, None, None)


def redraw_chart(a_mean, b_mean, delta_pct):
    ax.clear()
    ax.set_title("AvgResult Mean Comparison")

    if a_mean is None or b_mean is None:
        ax.text(0.5, 0.5, "Load both Log A and Log B", ha="center", va="center", transform=ax.transAxes)
        ax.set_xticks([])
        ax.set_yticks([])
    else:
        labels = ["A", "B"]
        vals = [a_mean, b_mean]
        ax.bar(labels, vals)  # no explicit colors (policy)
        ax.set_ylabel("Mean AvgResult")

        # annotate values
        for i, v in enumerate(vals):
            ax.text(i, v, f"{v:.4f}", ha="center", va="bottom")

        # delta text
        if delta_pct is not None:
            ax.text(0.5, 0.95, f"Delta: {delta_pct:+.2f}%", ha="center", va="top", transform=ax.transAxes)

    canvas.draw_idle()


# ------------------------------------------------------------
# UI setup
# ------------------------------------------------------------
root = tk.Tk()
root.title("SpeedTestSKT Ping Log Extractor & Comparator")
root.geometry("1100x850")

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

# Controls row
ctrl = tk.Frame(frame_comp)
ctrl.pack(fill="x", padx=8, pady=6)

# Log A selector
tk.Entry(ctrl, textvariable=log_a_path).pack(side="left", fill="x", expand=True)
tk.Button(ctrl, text="Browse A", command=open_log_a).pack(side="left", padx=6)

# Log B selector
tk.Entry(ctrl, textvariable=log_b_path).pack(side="left", fill="x", expand=True)
tk.Button(ctrl, text="Browse B", command=open_log_b).pack(side="left", padx=6)

# Summary panes
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

# Metrics + chart
metrics = tk.Frame(frame_comp)
metrics.pack(fill="x", padx=8, pady=6)

label_a_mean = tk.Label(metrics, text="A Mean: N/A   (n=0)")
label_a_mean.pack(anchor="w")

label_b_mean = tk.Label(metrics, text="B Mean: N/A   (n=0)")
label_b_mean.pack(anchor="w")

label_delta = tk.Label(metrics, text="Delta: N/A (load both A and B)")
label_delta.pack(anchor="w", pady=(0, 6))

# Chart (Matplotlib embed)
fig = Figure(figsize=(6.5, 3.0), dpi=100)
ax = fig.add_subplot(111)
canvas = FigureCanvasTkAgg(fig, master=frame_comp)
canvas_widget = canvas.get_tk_widget()
canvas_widget.pack(fill="x", padx=8, pady=(0, 10))

# Initialize chart
redraw_chart(None, None, None)

root.mainloop()
