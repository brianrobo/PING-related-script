# ============================================================
# SpeedTestSKT Ping Comparator (Paste or File, No matplotlib)
#
# Version: 1.5.0  (2025-12-27)
# Versioning: MAJOR.MINOR.PATCH (SemVer)
#
# Release Notes (v1.5.0):
# - (Feature) Compare 그래프 모드 추가:
#     * Mean Bar: A/B 평균 막대 비교 + Delta(%)
#     * Series Line: Ping-AvgResult 개별 값들을 A/B 시계열(라인)로 그래프화
# - (Keep) Summary A/B: 파일 로드 시 dumpState 파일명([File] <name>) 자동 표기
# - (Keep) Summary A/B: 사용자가 과거 결과물 붙여넣기 후 Compare Now로 비교 가능
# - (Keep) matplotlib 없이 Tkinter Canvas로 그래프 렌더링
# ============================================================

import re
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from pathlib import Path

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
# Regex for parsing pasted summary text (permissive)
# ------------------------------------------------------------
PASTE_AVG_LINE_RE = re.compile(r"Ping-AvgResult\b.*", re.IGNORECASE)
PASTE_AVG_VALUE_RE = re.compile(r"Ping-AvgResult\b.*?(?:=|\s)(?P<val>[\d.]+)\b", re.IGNORECASE)
PASTE_FILE_HEADER_RE = re.compile(r"^\[File\]\s+(?P<name>.+?)\s*$", re.IGNORECASE)


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
    Parse Summary text and extract:
      - optional file header: [File] xxx
      - Ping-AvgResult lines and numeric values (order preserved)
    Returns:
      - source_name: str (file name if present else 'Pasted')
      - avg_lines: list[str]
      - values: list[float]  (order preserved)
      - mean: float|None
    """
    source_name = "Pasted"
    avg_lines = []
    values = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        mh = PASTE_FILE_HEADER_RE.match(line)
        if mh:
            source_name = mh.group("name").strip()
            continue

        if not PASTE_AVG_LINE_RE.search(line):
            continue

        avg_lines.append(line)

        mv = PASTE_AVG_VALUE_RE.search(line)
        if mv:
            v = _to_float(mv.group("val"))
            if v is not None:
                values.append(v)

    mean_val = (sum(values) / len(values)) if values else None
    return source_name, avg_lines, values, mean_val


# ------------------------------------------------------------
# Canvas Drawing (No external libs)
# ------------------------------------------------------------
def _canvas_dims():
    w = int(chart.winfo_width() or 900)
    h = int(chart.winfo_height() or 220)
    return w, h


def draw_mean_bar(a_mean, b_mean, delta_pct, a_name, b_name):
    chart.delete("all")
    w, h = _canvas_dims()

    pad = 20
    base_y = h - 50
    top_y = 20

    chart.create_line(pad, base_y, w - pad, base_y)
    chart.create_line(pad, base_y, pad, top_y)

    if a_mean is None or b_mean is None:
        chart.create_text(w // 2, h // 2, text="Load/Paste both A and B, then Compare Now")
        return

    max_val = max(a_mean, b_mean)
    if max_val <= 0:
        max_val = 1.0

    bar_w = 160
    gap = 140
    x_a = pad + 140
    x_b = x_a + bar_w + gap

    def bar_height(v):
        usable = base_y - top_y - 10
        return (v / max_val) * usable

    ha = bar_height(a_mean)
    hb = bar_height(b_mean)

    chart.create_rectangle(x_a, base_y - ha, x_a + bar_w, base_y, outline="")
    chart.create_rectangle(x_b, base_y - hb, x_b + bar_w, base_y, outline="")

    chart.create_text(x_a + bar_w/2, base_y + 15, text=f"A: {a_name}")
    chart.create_text(x_b + bar_w/2, base_y + 15, text=f"B: {b_name}")

    chart.create_text(x_a + bar_w/2, base_y - ha - 12, text=f"{a_mean:.4f}")
    chart.create_text(x_b + bar_w/2, base_y - hb - 12, text=f"{b_mean:.4f}")

    if delta_pct is not None:
        chart.create_text(w // 2, 12, text=f"Delta: {delta_pct:+.2f}% (B vs A)")


def draw_series_line(a_vals, b_vals, a_name, b_name):
    """
    Draw two series (A/B) as line plots on the same axes.
    - X axis: index (1..N)
    - Y axis: value
    """
    chart.delete("all")
    w, h = _canvas_dims()

    pad_l = 60
    pad_r = 20
    pad_t = 20
    pad_b = 50

    left = pad_l
    right = w - pad_r
    top = pad_t
    bottom = h - pad_b

    # axes
    chart.create_line(left, bottom, right, bottom)
    chart.create_line(left, bottom, left, top)

    if not a_vals and not b_vals:
        chart.create_text(w // 2, h // 2, text="No numeric AvgResult values found in A/B")
        return

    # combine to find scale
    all_vals = []
    if a_vals:
        all_vals += a_vals
    if b_vals:
        all_vals += b_vals

    vmin = min(all_vals)
    vmax = max(all_vals)
    if vmax == vmin:
        # expand a little to avoid division by zero and show something
        vmax = vmin + 1.0

    # x range uses the max length
    n = max(len(a_vals), len(b_vals), 2)

    def x_pos(i):  # i: 0..n-1
        return left + (i / (n - 1)) * (right - left)

    def y_pos(v):
        # higher v => higher on plot (smaller y)
        return bottom - ((v - vmin) / (vmax - vmin)) * (bottom - top)

    # grid ticks (simple)
    for k in range(5):
        y = top + (k / 4) * (bottom - top)
        chart.create_line(left - 5, y, left + 5, y)
        val = vmax - (k / 4) * (vmax - vmin)
        chart.create_text(left - 10, y, text=f"{val:.2f}", anchor="e")

    # legend text (no color reliance; use labels and different marker shapes)
    chart.create_text(left + 5, bottom + 25, text=f"A: {a_name} (o markers)", anchor="w")
    chart.create_text(left + 5, bottom + 40, text=f"B: {b_name} (□ markers)", anchor="w")

    # plot series helper
    def plot(vals, marker="circle"):
        if not vals:
            return
        pts = []
        for i, v in enumerate(vals):
            x = x_pos(i if n == len(vals) else i)  # align to start; index-based
            y = y_pos(v)
            pts.append((x, y))

        # line
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            chart.create_line(x1, y1, x2, y2)

        # markers
        for x, y in pts:
            if marker == "circle":
                r = 3
                chart.create_oval(x - r, y - r, x + r, y + r, outline="", fill="")
                # fill="" -> uses default; outline="" -> minimal; relies on theme.
                # If fill causes invisibility in some themes, set outline only:
                # chart.create_oval(..., outline="black")
            else:
                r = 3
                chart.create_rectangle(x - r, y - r, x + r, y + r, outline="")

    # NOTE: Tkinter's fill/outline behavior can vary with theme; we keep it minimal.
    # If markers are hard to see, we can set explicit outline colors later.

    plot(a_vals, marker="circle")
    plot(b_vals, marker="square")

    # header
    chart.create_text((left + right) // 2, 12, text="Ping-AvgResult Series (A/B)")

    # x ticks
    for k in range(5):
        i = int(round(k * (n - 1) / 4))
        x = x_pos(i)
        chart.create_line(x, bottom - 5, x, bottom + 5)
        chart.create_text(x, bottom + 15, text=str(i + 1))


# ------------------------------------------------------------
# Compare logic (button-triggered)
# ------------------------------------------------------------
def compare_now():
    text_a = summary_a.get("1.0", tk.END)
    text_b = summary_b.get("1.0", tk.END)

    a_name, _, a_vals, a_mean = summarize_from_text(text_a)
    b_name, _, b_vals, b_mean = summarize_from_text(text_b)

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
        label_delta.config(text="Delta: N/A (need numeric AvgResult values in both A and B)")

    # draw based on mode
    mode = chart_mode.get()
    if mode == "MEAN":
        draw_mean_bar(a_mean, b_mean, delta_pct, a_name, b_name)
    else:
        draw_series_line(a_vals, b_vals, a_name, b_name)


def on_mode_change():
    # Re-render using current content (no auto recompute needed beyond compare_now)
    compare_now()


# ------------------------------------------------------------
# File loading into Summary A/B (convenience)
# ------------------------------------------------------------
def open_log_a():
    file_path = filedialog.askopenfilename(
        title="Select Log A (dumpState file)",
        filetypes=[("Log files", "*.txt *.log"), ("All files", "*.*")]
    )
    if not file_path:
        return
    log_a_path.set(file_path)
    load_avg_into_summary("A")


def open_log_b():
    file_path = filedialog.askopenfilename(
        title="Select Log B (dumpState file)",
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

    out.insert(tk.END, f"[File] {path.name}\n\n")

    for r in avg_rows:
        out.insert(tk.END, r["display"] + "\n")

    out.insert(tk.END, f"\n--- AvgResult Count (numeric): {len(values)} ---\n")
    out.insert(tk.END, f"Mean AvgResult: {mean_val:.6f}\n" if mean_val is not None else "Mean AvgResult: N/A\n")


# ------------------------------------------------------------
# UI setup
# ------------------------------------------------------------
root = tk.Tk()
root.title("SpeedTestSKT Ping Comparator (Series Graph, No matplotlib)")
root.geometry("1120x860")

log_a_path = tk.StringVar()
log_b_path = tk.StringVar()

frame_comp = tk.LabelFrame(root, text="Compare Summaries (Paste text OR Load dumpState files)")
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

tk.Label(left, text="Summary A").pack(anchor="w")
summary_a = scrolledtext.ScrolledText(left, font=("Consolas", 10), height=18)
summary_a.pack(fill="both", expand=True)

tk.Label(right, text="Summary B").pack(anchor="w")
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

# Chart mode selection
mode_frame = tk.Frame(frame_comp)
mode_frame.pack(fill="x", padx=8, pady=(0, 6))

chart_mode = tk.StringVar(value="MEAN")
tk.Radiobutton(mode_frame, text="Mean Bar", variable=chart_mode, value="MEAN", command=on_mode_change).pack(side="left")
tk.Radiobutton(mode_frame, text="Series Line (each AvgResult)", variable=chart_mode, value="SERIES", command=on_mode_change).pack(side="left", padx=12)

chart = tk.Canvas(frame_comp, height=230)
chart.pack(fill="x", padx=8, pady=(0, 10))

def _on_chart_resize(_evt):
    # keep current mode render
    compare_now()

chart.bind("<Configure>", _on_chart_resize)

# initial placeholder
draw_mean_bar(None, None, None, "A", "B")

root.mainloop()
