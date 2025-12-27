# ============================================================
# SpeedTestSKT Metric Comparator (Ping / Uplink TP / Downlink TP)
# - Paste or File, No matplotlib
#
# Version: 1.6.2  (2025-12-27)
# Versioning: MAJOR.MINOR.PATCH (SemVer)
#
# Release Notes (v1.6.2):
# - (UX) Mean Bar 그래프에서 Title/Delta가 막대/값 라벨과 겹치지 않도록 레이아웃 개선
#     * Canvas 상단에 Header 영역을 분리 확보
#     * Title/Delta는 Header에만 표시
#     * Plot 영역(top_y)을 아래로 내려 겹침 방지
# ============================================================

import re
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from pathlib import Path

DATE_RE = re.compile(r"(?P<date>(?:\d{4}-\d{2}-\d{2})|(?:\d{2}-\d{2}))")
TIME_RE = re.compile(r"(?P<time>\d{2}:\d{2}:\d{2}(?:[.,]\d{3,6})?)")
SPEEDTEST_RE = re.compile(r"(?P<msg>SpeedTestSKT\s*:\s*.*)$")
FILE_HEADER_RE = re.compile(r"^\[File\]\s+(?P<name>.+?)\s*$", re.IGNORECASE)
METRIC_HEADER_RE = re.compile(r"^\[Metric\]\s+(?P<name>.+?)\s*$", re.IGNORECASE)

REQ_NORM_RE  = re.compile(r"Ping-[Rr]equest")
RESP_NORM_RE = re.compile(r"Ping-[Rr]esponse")

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

def _to_float_num(s):
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None

class MetricSpec:
    def __init__(self, key_label, avg_result_token):
        self.key_label = key_label
        self.avg_result_token = avg_result_token

        self.file_filter = re.compile(
            rf"SpeedTestSKT\s*:\s*TestData\b.*\b{re.escape(self.avg_result_token)}\b",
            re.IGNORECASE
        )

        self.file_value_re = re.compile(
            rf"\b{re.escape(self.avg_result_token)}\b\s*=\s*(?P<val>[\d,]+(?:\.\d+)?)",
            re.IGNORECASE
        )

        self.paste_line_re = re.compile(rf"\b{re.escape(self.avg_result_token)}\b.*", re.IGNORECASE)
        self.paste_value_re = re.compile(
            rf"\b{re.escape(self.avg_result_token)}\b.*?(?:=|\s)(?P<val>[\d,]+(?:\.\d+)?)\b",
            re.IGNORECASE
        )

    def extract_value_from_msg(self, raw_msg: str) -> str:
        m = self.file_value_re.search(raw_msg)
        if not m:
            return ""
        return m.group("val") or ""

METRICS = {
    "PING": MetricSpec("Ping", "Ping-AvgResult"),
    "UL":   MetricSpec("Uplink TP", "Up-AvgResult"),
    "DL":   MetricSpec("Downlink TP", "Down-AvgResult"),
}

def extract_avgresult_lines_from_file(path: Path, spec: MetricSpec):
    lines = []
    values = []

    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.rstrip("\n")

            date, time = _find_date_time(line)
            if not date or not time:
                continue

            m = SPEEDTEST_RE.search(line)
            if not m:
                continue

            raw_msg = m.group("msg")
            if not spec.file_filter.search(raw_msg):
                continue

            display_msg = _normalize_display_msg(raw_msg)
            lines.append(f"{date} {time} {display_msg}")

            v = _to_float_num(spec.extract_value_from_msg(raw_msg))
            if v is not None:
                values.append(v)

    return lines, values

def summarize_from_text(text: str, spec: MetricSpec):
    source_name = "Pasted"
    metric_name_in_text = None
    avg_lines = []
    values = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        mh = FILE_HEADER_RE.match(line)
        if mh:
            source_name = mh.group("name").strip()
            continue

        mm = METRIC_HEADER_RE.match(line)
        if mm:
            metric_name_in_text = mm.group("name").strip()
            continue

        if not spec.paste_line_re.search(line):
            continue

        avg_lines.append(line)

        mv = spec.paste_value_re.search(line)
        if mv:
            v = _to_float_num(mv.group("val"))
            if v is not None:
                values.append(v)

    mean_val = (sum(values) / len(values)) if values else None
    return source_name, metric_name_in_text, avg_lines, values, mean_val

def _canvas_dims():
    w = int(chart.winfo_width() or 900)
    h = int(chart.winfo_height() or 250)
    return w, h

def draw_mean_bar(a_mean, b_mean, delta_pct, a_name, b_name, title):
    """
    Layout:
      - Header band at top: Title and Delta
      - Plot area below: axes + bars + value labels
    """
    chart.delete("all")
    w, h = _canvas_dims()

    pad = 20
    header_h = 42          # reserved space for title/delta
    plot_top = header_h + 18
    base_y = h - 55

    # Header band (outside plot)
    chart.create_text(w // 2, 12, text=title)
    if delta_pct is not None:
        chart.create_text(w // 2, 28, text=f"Delta: {delta_pct:+.2f}% (B vs A)")

    # Axes in plot area
    chart.create_line(pad, base_y, w - pad, base_y)      # x axis
    chart.create_line(pad, base_y, pad, plot_top)        # y axis

    if a_mean is None or b_mean is None:
        chart.create_text(w // 2, (plot_top + base_y) // 2, text="Load/Paste both A and B, then Compare Now")
        return

    max_val = max(a_mean, b_mean)
    if max_val <= 0:
        max_val = 1.0

    bar_w = 160
    gap = 140
    x_a = pad + 140
    x_b = x_a + bar_w + gap

    def bar_height(v):
        usable = base_y - plot_top - 10
        return (v / max_val) * usable

    ha = bar_height(a_mean)
    hb = bar_height(b_mean)

    # Bars
    chart.create_rectangle(x_a, base_y - ha, x_a + bar_w, base_y, outline="")
    chart.create_rectangle(x_b, base_y - hb, x_b + bar_w, base_y, outline="")

    # X labels
    chart.create_text(x_a + bar_w/2, base_y + 16, text=f"A: {a_name}")
    chart.create_text(x_b + bar_w/2, base_y + 16, text=f"B: {b_name}")

    # Value labels: clamp to stay within plot area (not into header)
    def value_label_y(bar_top_y):
        y = bar_top_y - 12
        min_y = plot_top + 8
        if y < min_y:
            y = min_y
        return y

    chart.create_text(x_a + bar_w/2, value_label_y(base_y - ha), text=f"{a_mean:.4f}")
    chart.create_text(x_b + bar_w/2, value_label_y(base_y - hb), text=f"{b_mean:.4f}")

def draw_series_line(a_vals, b_vals, a_name, b_name, title):
    chart.delete("all")
    w, h = _canvas_dims()

    pad_l = 60
    pad_r = 20
    pad_t = 24
    pad_b = 55

    left = pad_l
    right = w - pad_r
    top = pad_t
    bottom = h - pad_b

    chart.create_text(w // 2, 12, text=title)
    chart.create_line(left, bottom, right, bottom)
    chart.create_line(left, bottom, left, top)

    if not a_vals and not b_vals:
        chart.create_text(w // 2, h // 2, text="No numeric values found for selected metric in A/B")
        return

    all_vals = (a_vals or []) + (b_vals or [])
    vmin = min(all_vals)
    vmax = max(all_vals)
    if vmax == vmin:
        vmax = vmin + 1.0

    n = max(len(a_vals), len(b_vals), 2)

    def x_pos(i):
        return left + (i / (n - 1)) * (right - left)

    def y_pos(v):
        return bottom - ((v - vmin) / (vmax - vmin)) * (bottom - top)

    for k in range(5):
        y = top + (k / 4) * (bottom - top)
        chart.create_line(left - 5, y, left + 5, y)
        val = vmax - (k / 4) * (vmax - vmin)
        chart.create_text(left - 10, y, text=f"{val:.2f}", anchor="e")

    chart.create_text(left + 5, bottom + 25, text=f"A: {a_name} (o)", anchor="w")
    chart.create_text(left + 5, bottom + 40, text=f"B: {b_name} (□)", anchor="w")

    def plot(vals, marker="circle"):
        if not vals:
            return
        pts = [(x_pos(i), y_pos(v)) for i, v in enumerate(vals)]
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            chart.create_line(x1, y1, x2, y2)
        for x, y in pts:
            r = 3
            if marker == "circle":
                chart.create_oval(x - r, y - r, x + r, y + r, outline="")
            else:
                chart.create_rectangle(x - r, y - r, x + r, y + r, outline="")

    plot(a_vals, marker="circle")
    plot(b_vals, marker="square")

    for k in range(5):
        i = int(round(k * (n - 1) / 4))
        x = x_pos(i)
        chart.create_line(x, bottom - 5, x, bottom + 5)
        chart.create_text(x, bottom + 15, text=str(i + 1))

def current_spec():
    return METRICS[metric_kind.get()]

def load_a_from_file():
    fp = filedialog.askopenfilename(
        title="Select dumpState for A",
        filetypes=[("Log files", "*.txt *.log"), ("All files", "*.*")]
    )
    if not fp:
        return
    path_a.set(fp)
    fill_summary_from_file("A")

def load_b_from_file():
    fp = filedialog.askopenfilename(
        title="Select dumpState for B",
        filetypes=[("Log files", "*.txt *.log"), ("All files", "*.*")]
    )
    if not fp:
        return
    path_b.set(fp)
    fill_summary_from_file("B")

def fill_summary_from_file(which):
    spec = current_spec()
    p = Path(path_a.get()) if which == "A" else Path(path_b.get())
    box = summary_a if which == "A" else summary_b

    if not p.exists():
        messagebox.showerror("Error", f"Invalid file for {which}")
        return

    lines, values = extract_avgresult_lines_from_file(p, spec)
    mean_val = (sum(values) / len(values)) if values else None

    box.delete("1.0", tk.END)
    box.insert(tk.END, f"[File] {p.name}\n")
    box.insert(tk.END, f"[Metric] {spec.key_label}\n\n")
    for ln in lines:
        box.insert(tk.END, ln + "\n")
    box.insert(tk.END, f"\n--- Count (numeric): {len(values)} ---\n")
    box.insert(tk.END, f"Mean: {mean_val:.6f}\n" if mean_val is not None else "Mean: N/A\n")

def compare_now():
    spec = current_spec()

    a_name, _, _, a_vals, a_mean = summarize_from_text(summary_a.get("1.0", tk.END), spec)
    b_name, _, _, b_vals, b_mean = summarize_from_text(summary_b.get("1.0", tk.END), spec)

    a_txt = f"{a_mean:.6f}" if a_mean is not None else "N/A"
    b_txt = f"{b_mean:.6f}" if b_mean is not None else "N/A"

    label_a_mean.config(text=f"A ({a_name}) Mean: {a_txt}   (n={len(a_vals)})")
    label_b_mean.config(text=f"B ({b_name}) Mean: {b_txt}   (n={len(b_vals)})")

    delta_pct = None
    if a_mean is not None and b_mean is not None and a_mean != 0:
        delta_pct = ((b_mean - a_mean) / a_mean) * 100.0
        label_delta.config(text=f"Delta: {delta_pct:+.2f}%   (B vs A)")
    elif a_mean is not None and b_mean is not None and a_mean == 0:
        label_delta.config(text="Delta: N/A (A mean is 0)")
    else:
        label_delta.config(text="Delta: N/A (need numeric values in both A and B)")

    title = f"{spec.key_label} AvgResult Comparison"
    if chart_mode.get() == "MEAN":
        draw_mean_bar(a_mean, b_mean, delta_pct, a_name, b_name, title)
    else:
        draw_series_line(a_vals, b_vals, a_name, b_name, title)

def on_metric_change():
    compare_now()

def on_mode_change():
    compare_now()

root = tk.Tk()
root.title("SpeedTestSKT Metric Comparator (No matplotlib)")
root.geometry("1150x900")

metric_kind = tk.StringVar(value="PING")
chart_mode = tk.StringVar(value="MEAN")

top = tk.LabelFrame(root, text="Metric Selector")
top.pack(fill="x", padx=10, pady=8)

tk.Radiobutton(top, text="Ping", variable=metric_kind, value="PING", command=on_metric_change).pack(side="left", padx=10)
tk.Radiobutton(top, text="Uplink TP", variable=metric_kind, value="UL", command=on_metric_change).pack(side="left", padx=10)
tk.Radiobutton(top, text="Downlink TP", variable=metric_kind, value="DL", command=on_metric_change).pack(side="left", padx=10)

frame = tk.LabelFrame(root, text="Compare Summaries (Paste OR Load files)")
frame.pack(fill="both", expand=True, padx=10, pady=8)

path_a = tk.StringVar()
path_b = tk.StringVar()

ctrl = tk.Frame(frame)
ctrl.pack(fill="x", padx=8, pady=6)

tk.Entry(ctrl, textvariable=path_a).pack(side="left", fill="x", expand=True)
tk.Button(ctrl, text="Load A (from file)", command=load_a_from_file).pack(side="left", padx=6)

tk.Entry(ctrl, textvariable=path_b).pack(side="left", fill="x", expand=True)
tk.Button(ctrl, text="Load B (from file)", command=load_b_from_file).pack(side="left", padx=6)

pane = tk.Frame(frame)
pane.pack(fill="both", expand=True, padx=8, pady=6)

left = tk.Frame(pane)
left.pack(side="left", fill="both", expand=True, padx=(0, 6))
right = tk.Frame(pane)
right.pack(side="left", fill="both", expand=True, padx=(6, 0))

tk.Label(left, text="Summary A").pack(anchor="w")
summary_a = scrolledtext.ScrolledText(left, font=("Consolas", 10), height=18)
summary_a.pack(fill="both", expand=True)

tk.Label(right, text="Summary B").pack(anchor="w")
summary_b = scrolledtext.ScrolledText(right, font=("Consolas", 10), height=18)
summary_b.pack(fill="both", expand=True)

actions = tk.Frame(frame)
actions.pack(fill="x", padx=8, pady=6)

tk.Button(actions, text="Compare Now", command=compare_now).pack(side="left")

label_a_mean = tk.Label(actions, text="A Mean: N/A   (n=0)")
label_a_mean.pack(side="left", padx=16)

label_b_mean = tk.Label(actions, text="B Mean: N/A   (n=0)")
label_b_mean.pack(side="left", padx=16)

label_delta = tk.Label(actions, text="Delta: N/A")
label_delta.pack(side="left", padx=16)

mode_frame = tk.Frame(frame)
mode_frame.pack(fill="x", padx=8, pady=(0, 6))

tk.Radiobutton(mode_frame, text="Mean Bar", variable=chart_mode, value="MEAN", command=on_mode_change).pack(side="left")
tk.Radiobutton(mode_frame, text="Series Line (each AvgResult)", variable=chart_mode, value="SERIES", command=on_mode_change).pack(side="left", padx=12)

chart = tk.Canvas(frame, height=250)
chart.pack(fill="x", padx=8, pady=(0, 10))

def _on_chart_resize(_evt):
    compare_now()

chart.bind("<Configure>", _on_chart_resize)

# initial
draw_mean_bar(None, None, None, "A", "B", "Metric AvgResult Comparison")

root.mainloop()
