# ============================================================
# SpeedTestSKT Ping Log Extractor
#
# - Extracts:
#   SpeedTestSKT: TestData Ping-request##
#   SpeedTestSKT: TestData Ping-response##=##
#   SpeedTestSKT: TestData Ping-AvgResult
#
# UI: Tkinter
# ============================================================

import re
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from pathlib import Path
import csv

# -------------------------------
# Regex patterns
# -------------------------------
PATTERNS = {
    "request": re.compile(r"SpeedTestSKT:\s*TestData\s*Ping-request(\d+)"),
    "response": re.compile(r"SpeedTestSKT:\s*TestData\s*Ping-response(\d+)=([\d.]+)"),
    "avg": re.compile(r"SpeedTestSKT:\s*TestData\s*Ping-AvgResult\s*=?\s*([\d.]+)?"),
}

# -------------------------------
# Core extraction logic
# -------------------------------
def extract_ping_logs(log_path: Path):
    results = []

    with log_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()

            m = PATTERNS["request"].search(line)
            if m:
                results.append({
                    "type": "Ping-request",
                    "seq": m.group(1),
                    "value": "",
                    "line": line_no,
                    "raw": line
                })
                continue

            m = PATTERNS["response"].search(line)
            if m:
                results.append({
                    "type": "Ping-response",
                    "seq": m.group(1),
                    "value": m.group(2),
                    "line": line_no,
                    "raw": line
                })
                continue

            m = PATTERNS["avg"].search(line)
            if m:
                results.append({
                    "type": "Ping-AvgResult",
                    "seq": "",
                    "value": m.group(1) or "",
                    "line": line_no,
                    "raw": line
                })

    return results

# -------------------------------
# UI callbacks
# -------------------------------
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
        output.insert(
            tk.END,
            f"[{r['type']}] line={r['line']} "
            f"seq={r['seq']} value={r['value']}\n"
        )

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
            fieldnames=["type", "seq", "value", "line", "raw"]
        )
        writer.writeheader()
        writer.writerows(results)

    messagebox.showinfo("Saved", f"CSV saved:\n{save_path}")

# -------------------------------
# UI setup
# -------------------------------
root = tk.Tk()
root.title("SpeedTestSKT Ping Log Extractor")
root.geometry("900x600")

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
