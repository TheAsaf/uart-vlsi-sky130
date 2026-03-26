#!/usr/bin/env python3
"""Generate precise UART waveform diagrams from simulation VCD data.

Produces two images:
  1. uart_8n1_waveform.png  — A single 8N1 byte (0xA5) with exact bit
     boundaries, start/data/stop annotations, and rx_valid confirmation.
  2. uart_fifo_burst.png    — FIFO burst of 4 bytes (0x11–0x44) showing
     near-zero idle between frames.

The waveforms are plotted directly from VCD transitions (no interpolation)
so every edge is pixel-accurate.
"""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np


# ---------------------------------------------------------------------------
# Precise VCD parser — full hierarchical signal names
# ---------------------------------------------------------------------------

def parse_vcd(path):
    """Return {full_hierarchical_name: [(time_ps, value_str), ...]}."""
    var_map = {}       # vcd_id → full name
    data = {}          # full name → [(time, val)]
    scope_stack = []
    in_defs = True
    current_time = 0

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if in_defs:
                if line.startswith("$scope"):
                    parts = line.split()
                    if len(parts) >= 3:
                        scope_stack.append(parts[2])
                elif line.startswith("$upscope"):
                    if scope_stack:
                        scope_stack.pop()
                elif line.startswith("$var"):
                    parts = line.split()
                    if len(parts) >= 5:
                        vcd_id = parts[3]
                        name = parts[4]
                        full = ".".join(scope_stack + [name])
                        var_map[vcd_id] = full
                        data[full] = []
                elif line.startswith("$enddefinitions"):
                    in_defs = False
                continue
            if line.startswith("#"):
                current_time = int(line[1:])
            elif len(line) >= 2 and line[0] in "01xXzZ":
                vid = line[1:]
                if vid in var_map:
                    data[var_map[vid]].append((current_time, line[0]))
            elif line.startswith("b"):
                parts = line.split()
                if len(parts) == 2 and parts[1] in var_map:
                    data[var_map[parts[1]]].append((current_time, parts[0][1:]))
    return data


def get_signal(data, suffix):
    """Find a signal by suffix match (e.g. 'u_tx.tx')."""
    for name in data:
        if name.endswith(suffix):
            return data[name]
    return []


# ---------------------------------------------------------------------------
# Build step-plot arrays directly from transitions (no sampling)
# ---------------------------------------------------------------------------

def transitions_to_step(events, t_start, t_end):
    """Convert [(time, val)] to (times, values) for plt.step().

    Returns arrays where every VCD edge maps to an exact point.
    Values: '1'→1.0, '0'→0.0, 'x'/'X'→0.5.
    """
    def to_num(v):
        if v == '1': return 1.0
        if v == '0': return 0.0
        return 0.5  # x / z

    # Find last value before the window
    init_val = 0.5
    for t, v in events:
        if t <= t_start:
            init_val = to_num(v)
        else:
            break

    ts = [t_start]
    vs = [init_val]

    for t, v in events:
        if t < t_start:
            continue
        if t > t_end:
            break
        ts.append(t)
        vs.append(to_num(v))

    ts.append(t_end)
    vs.append(vs[-1])

    return np.array(ts, dtype=float), np.array(vs, dtype=float)


# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------

COLORS = {
    "tx":       "#2563EB",
    "rx":       "#7C3AED",
    "busy":     "#EA580C",
    "valid":    "#059669",
    "done":     "#DC2626",
}


def style_axis(ax):
    ax.set_facecolor("#FAFBFC")
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(left=False, labelleft=True, bottom=True,
                   colors="#6B7280", labelsize=7)
    ax.grid(axis="y", color="#F3F4F6", linewidth=0.5)


def plot_signal(ax, times_ps, values, color, label, t_scale=1e6):
    """Plot a single digital waveform with fill."""
    t = times_ps / t_scale  # ps → µs
    ax.fill_between(t, 0, values, step="pre", alpha=0.12, color=color)
    ax.step(t, values, where="pre", linewidth=1.4, color=color)
    ax.set_ylim(-0.18, 1.55)
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["0", "1"], fontsize=7, color="#6B7280")
    ax.set_ylabel(label, fontsize=9, fontweight="bold", color="#374151",
                  rotation=0, labelpad=62, va="center")


# ---------------------------------------------------------------------------
# Figure 1: Single 8N1 byte (0xA5)
# ---------------------------------------------------------------------------

def plot_single_byte(data, out_path):
    BIT = 160_000  # ps per UART bit (16 clocks × 10 ns)

    # Exact start-bit time from VCD: first 1→0 on TX after idle
    tx_events = get_signal(data, "u_tx.tx")
    start_t = None
    for i, (t, v) in enumerate(tx_events):
        if v == '0' and i > 0 and tx_events[i-1][1] == '1' and t > 100_000:
            start_t = t
            break
    if start_t is None:
        print("ERROR: could not find first TX start bit")
        return

    # 0xA5 = 10100101, LSB-first: D0=1 D1=0 D2=1 D3=0 D4=0 D5=1 D6=0 D7=1
    data_bits = [1, 0, 1, 0, 0, 1, 0, 1]

    # Window: 1 bit before start → 1.5 bits after stop
    t0 = start_t - int(1.2 * BIT)
    t1 = start_t + int(11.5 * BIT)

    fig, axes = plt.subplots(4, 1, figsize=(13, 5.5), sharex=True,
                              gridspec_kw={"hspace": 0.08,
                                           "height_ratios": [1.3, 1.0, 0.7, 0.7]})
    fig.patch.set_facecolor("white")

    signals = [
        ("u_tx.tx",       "TX Line",       COLORS["tx"]),
        ("loopback",      "RX (loopback)", COLORS["rx"]),
        ("u_tx.tx_busy",  "tx_busy",       COLORS["busy"]),
        ("u_rx.rx_valid", "rx_valid",      COLORS["valid"]),
    ]

    for ax, (sig_suffix, label, color) in zip(axes, signals):
        events = get_signal(data, sig_suffix)
        ts, vs = transitions_to_step(events, t0, t1)
        plot_signal(ax, ts, vs, color, label)
        style_axis(ax)

    ax_tx = axes[0]

    # --- Bit-boundary vertical lines ---
    for i in range(11):
        t_line = (start_t + i * BIT) / 1e6
        for ax in axes:
            ax.axvline(t_line, color="#E5E7EB", linewidth=0.6, linestyle="--", zorder=0)
    # End of stop bit
    t_stop_end = (start_t + 10 * BIT) / 1e6
    for ax in axes:
        ax.axvline(t_stop_end, color="#E5E7EB", linewidth=0.6, linestyle="--", zorder=0)

    # --- Shaded regions ---
    # Start bit
    ax_tx.axvspan(start_t / 1e6, (start_t + BIT) / 1e6,
                  alpha=0.08, color="#16A34A", zorder=0)
    # Data bits
    ax_tx.axvspan((start_t + BIT) / 1e6, (start_t + 9 * BIT) / 1e6,
                  alpha=0.06, color="#2563EB", zorder=0)
    # Stop bit
    ax_tx.axvspan((start_t + 9 * BIT) / 1e6, (start_t + 10 * BIT) / 1e6,
                  alpha=0.08, color="#16A34A", zorder=0)

    # --- Bit labels ---
    # Start
    t_mid = (start_t + BIT / 2) / 1e6
    ax_tx.text(t_mid, 1.38, "START", ha="center", va="bottom", fontsize=7,
               fontweight="bold", color="#16A34A")

    # Data bits
    for i, b in enumerate(data_bits):
        t_mid = (start_t + (1 + i) * BIT + BIT / 2) / 1e6
        ax_tx.text(t_mid, 1.38, f"D{i}={b}", ha="center", va="bottom",
                   fontsize=6.5, fontweight="bold", color="#1E40AF")

    # Stop
    t_mid = (start_t + 9 * BIT + BIT / 2) / 1e6
    ax_tx.text(t_mid, 1.38, "STOP", ha="center", va="bottom", fontsize=7,
               fontweight="bold", color="#16A34A")

    # Byte value badge
    t_center = (start_t + 5 * BIT) / 1e6
    ax_tx.annotate("0xA5", xy=(t_center, 1.52), fontsize=10, ha="center",
                   fontweight="bold", color="#1E3A5F",
                   bbox=dict(boxstyle="round,pad=0.3", facecolor="#DBEAFE",
                             edgecolor="#93C5FD", linewidth=1.2))

    # --- Idle labels ---
    t_idle_l = (t0 + start_t) / 2 / 1e6
    ax_tx.text(t_idle_l, 0.5, "IDLE", ha="center", va="center",
               fontsize=8, color="#9CA3AF", fontstyle="italic")
    t_idle_r = (start_t + 10.7 * BIT) / 1e6
    ax_tx.text(t_idle_r, 0.5, "IDLE", ha="center", va="center",
               fontsize=8, color="#9CA3AF", fontstyle="italic")

    axes[-1].set_xlabel("Time (µs)", fontsize=9, color="#6B7280")
    fig.suptitle("UART 8N1 Transmission — Single Byte (0xA5)",
                 fontsize=13, fontweight="bold", color="#111827", y=0.97)

    plt.savefig(out_path, dpi=200, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    plt.close()
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# Figure 2: FIFO burst (4 bytes back-to-back)
# ---------------------------------------------------------------------------

def plot_fifo_burst(data, out_path):
    BIT = 160_000  # ps per UART bit

    # Identify burst frames from tx_busy: the 4 consecutive frames where
    # FIFO stays non-empty (test 4). FIFO empty signal shows it stays
    # non-empty from ~15.885 us to ~20.735 us.
    busy_events = get_signal(data, "u_tx.tx_busy")

    # Find rising edges of tx_busy (frame starts)
    frame_starts = []
    for i, (t, v) in enumerate(busy_events):
        if v == '1' and i > 0 and busy_events[i-1][1] == '0':
            frame_starts.append(t)

    # Find falling edges (frame ends)
    frame_ends = []
    for i, (t, v) in enumerate(busy_events):
        if v == '0' and i > 0 and busy_events[i-1][1] == '1':
            frame_ends.append(t)

    # The FIFO burst (test 4) has uniquely tight inter-frame gaps: the FIFO
    # feeds the TX with only ~2 clock cycles (~20,000 ps) between frames,
    # whereas testbench-driven sends have ~60,000+ ps gaps.  Find 4
    # consecutive frames whose 3 inter-frame gaps are all < 30,000 ps.
    burst_start_idx = None
    for i in range(len(frame_starts) - 3):
        gaps = []
        for j in range(3):
            gap = frame_starts[i + j + 1] - frame_ends[i + j]
            gaps.append(gap)
        if all(g < 30_000 for g in gaps):  # < 3 clocks = FIFO-driven
            burst_start_idx = i
            break

    if burst_start_idx is None:
        print("ERROR: could not identify FIFO burst frames")
        return

    burst_frames = []
    for j in range(4):
        idx = burst_start_idx + j
        burst_frames.append((frame_starts[idx], frame_ends[idx]))

    byte_values = [0x11, 0x22, 0x33, 0x44]

    # Window
    t0 = burst_frames[0][0] - int(2 * BIT)
    t1 = burst_frames[3][1] + int(2 * BIT)

    fig, axes = plt.subplots(3, 1, figsize=(15, 4.5), sharex=True,
                              gridspec_kw={"hspace": 0.08,
                                           "height_ratios": [1.4, 0.7, 0.7]})
    fig.patch.set_facecolor("white")

    sigs = [
        ("u_tx.tx",       "TX Line",  COLORS["tx"]),
        ("u_tx.tx_busy",  "tx_busy",  COLORS["busy"]),
        ("u_rx.rx_valid", "rx_valid", COLORS["valid"]),
    ]

    for ax, (sig_suffix, label, color) in zip(axes, sigs):
        events = get_signal(data, sig_suffix)
        ts, vs = transitions_to_step(events, t0, t1)
        plot_signal(ax, ts, vs, color, label)
        style_axis(ax)

    ax_tx = axes[0]

    # --- Per-frame shading and labels ---
    frame_colors = ["#DBEAFE", "#FEF3C7", "#D1FAE5", "#FCE7F3"]
    frame_edge   = ["#93C5FD", "#FCD34D", "#6EE7B7", "#F9A8D4"]
    frame_text   = ["#1E40AF", "#92400E", "#065F46", "#9D174D"]

    for i, ((fs, fe), bval) in enumerate(zip(burst_frames, byte_values)):
        # Shade the frame region on TX axis
        ax_tx.axvspan(fs / 1e6, fe / 1e6, alpha=0.12,
                      color=frame_edge[i], zorder=0)

        # Byte value badge
        t_mid = (fs + fe) / 2 / 1e6
        ax_tx.annotate(f"0x{bval:02X}", xy=(t_mid, 1.38), fontsize=10,
                       ha="center", fontweight="bold", color=frame_text[i],
                       bbox=dict(boxstyle="round,pad=0.3",
                                 facecolor=frame_colors[i],
                                 edgecolor=frame_edge[i], linewidth=1.2))

        # Start/stop bit boundary lines
        for ax in axes:
            ax.axvline(fs / 1e6, color="#D1D5DB", linewidth=0.5,
                       linestyle=":", zorder=0)
            ax.axvline(fe / 1e6, color="#D1D5DB", linewidth=0.5,
                       linestyle=":", zorder=0)

    # --- Annotate gaps between frames ---
    for i in range(3):
        gap_start = burst_frames[i][1]
        gap_end   = burst_frames[i+1][0]
        gap_clks  = (gap_end - gap_start) / 10_000  # 10ns per clock
        t_mid = (gap_start + gap_end) / 2 / 1e6
        axes[1].annotate(f"{int(gap_clks)}T", xy=(t_mid, 0.5),
                         fontsize=6, ha="center", va="center",
                         color="#6B7280", fontstyle="italic",
                         bbox=dict(boxstyle="round,pad=0.15",
                                   facecolor="white", edgecolor="#D1D5DB",
                                   linewidth=0.5))

    # --- Idle labels ---
    t_idle_l = (t0 + burst_frames[0][0]) / 2 / 1e6
    ax_tx.text(t_idle_l, 0.5, "IDLE", ha="center", va="center",
               fontsize=8, color="#9CA3AF", fontstyle="italic")
    t_idle_r = (burst_frames[3][1] + t1) / 2 / 1e6
    ax_tx.text(t_idle_r, 0.5, "IDLE", ha="center", va="center",
               fontsize=8, color="#9CA3AF", fontstyle="italic")

    axes[-1].set_xlabel("Time (µs)", fontsize=9, color="#6B7280")
    fig.suptitle("UART FIFO Burst — 4 Bytes Back-to-Back (0x11, 0x22, 0x33, 0x44)",
                 fontsize=13, fontweight="bold", color="#111827", y=0.98)

    plt.savefig(out_path, dpi=200, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    plt.close()
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    vcd_path = os.path.join(os.path.dirname(__file__), "..", "tb", "uart_top_tb.vcd")
    img_dir  = os.path.join(os.path.dirname(__file__), "images")
    os.makedirs(img_dir, exist_ok=True)

    print("Parsing VCD...")
    data = parse_vcd(vcd_path)

    print("Generating waveforms...")
    plot_single_byte(data, os.path.join(img_dir, "uart_8n1_waveform.png"))
    plot_fifo_burst(data,  os.path.join(img_dir, "uart_fifo_burst.png"))
    print("Done.")
