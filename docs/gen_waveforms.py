#!/usr/bin/env python3
"""Generate precise UART waveform diagrams from simulation VCD data.

Produces two images:
  1. uart_8n1_waveform.png  — A single 8N1 byte (0xA5) with exact bit
     boundaries, start/data/stop annotations, mid-bit sampling markers,
     and a clearly visible rx_valid single-clock pulse.
  2. uart_fifo_burst.png    — FIFO burst of 4 bytes (0x11–0x44) showing
     continuous tx_busy, near-zero idle between frames, and 4 rx_valid
     pulses.

Waveforms are plotted directly from VCD transitions (no interpolation)
so every edge is pixel-accurate to the RTL simulation.
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


def find_pulse_times(events, t_start, t_end):
    """Find rising edges of single-clock pulses within a window.

    Returns list of (rise_time, fall_time) in ps.
    """
    pulses = []
    for i, (t, v) in enumerate(events):
        if t < t_start or t > t_end:
            continue
        if v == '1' and i > 0 and events[i-1][1] == '0':
            # Find the corresponding fall
            t_fall = t_end
            if i + 1 < len(events) and events[i+1][1] == '0':
                t_fall = events[i+1][0]
            pulses.append((t, t_fall))
    return pulses


# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------

COLORS = {
    "tx":       "#2563EB",
    "rx":       "#7C3AED",
    "busy":     "#EA580C",
    "valid":    "#059669",
    "sample":   "#DC2626",
}


def style_axis(ax):
    ax.set_facecolor("#FAFBFC")
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(left=False, labelleft=True, bottom=True,
                   colors="#6B7280", labelsize=7)
    ax.grid(axis="y", color="#F3F4F6", linewidth=0.5)


def plot_signal(ax, times_ps, values, color, label, lw=1.4, t_scale=1e6):
    """Plot a single digital waveform with fill."""
    t = times_ps / t_scale  # ps → µs
    ax.fill_between(t, 0, values, step="post", alpha=0.10, color=color)
    ax.step(t, values, where="post", linewidth=lw, color=color)
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
    CLK = 10_000   # ps per clock

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

    fig, axes = plt.subplots(4, 1, figsize=(14, 6.2), sharex=True,
                              gridspec_kw={"hspace": 0.06,
                                           "height_ratios": [1.4, 1.1, 0.8, 0.8]})
    fig.patch.set_facecolor("white")

    # --- TX Line ---
    tx_ts, tx_vs = transitions_to_step(tx_events, t0, t1)
    plot_signal(axes[0], tx_ts, tx_vs, COLORS["tx"], "TX Line")
    style_axis(axes[0])

    # --- RX (loopback) — same as TX but delayed through 2-FF sync ---
    rx_events = get_signal(data, "u_rx.rx_sync")
    if not rx_events:
        # Fallback: use u_tx.tx as proxy (loopback with negligible delay)
        rx_events = tx_events
    rx_ts, rx_vs = transitions_to_step(rx_events, t0, t1)
    plot_signal(axes[1], rx_ts, rx_vs, COLORS["rx"], "RX Line")
    style_axis(axes[1])

    # --- Mid-bit sampling markers on RX ---
    # The RX FSM samples data at baud_tick (every CLKS_PER_BIT clocks after
    # the half-baud start-bit confirmation). We derive sampling points from
    # bit_idx transitions.
    bit_idx_events = get_signal(data, "u_rx.bit_idx")
    # Sampling points: when bit_idx increments (each baud_tick in S_DATA)
    # Also: the start-bit confirmation is at half_baud_tick
    # Start bit mid-sample: start_t + (CLKS_PER_BIT/2 - 1) * CLK
    # In our sim, CLKS_PER_BIT=16, so half = 7 clocks = 70,000 ps after
    # the RX sync detects the falling edge. The RX sync is 2 clocks behind TX.
    rx_sync_delay = 2 * CLK  # 2 FF synchronizer delay
    rx_start_detect = start_t + rx_sync_delay  # when rx_sync goes low
    half_baud = (16 // 2) * CLK  # 8 clocks = 80,000 ps

    # Start bit mid-sample point (confirmation)
    start_mid_sample = rx_start_detect + half_baud - CLK  # half_baud_tick fires at cnt=7

    # Data bit sample points: each CLKS_PER_BIT after the start confirmation
    sample_points = [start_mid_sample]  # start bit confirmation
    for i in range(8):
        sample_points.append(start_mid_sample + (i + 1) * BIT)
    # Stop bit sample point
    sample_points.append(start_mid_sample + 9 * BIT)

    # Plot sampling markers on RX axis
    for sp in sample_points:
        if t0 <= sp <= t1:
            sp_us = sp / 1e6
            # Get RX value at this point
            rx_val = 0.5
            for t, v in rx_events:
                if t <= sp:
                    rx_val = 1.0 if v == '1' else 0.0
                else:
                    break
            axes[1].plot(sp_us, rx_val, marker='v', markersize=5,
                        color=COLORS["sample"], zorder=5, markeredgewidth=0.8,
                        markeredgecolor="white")

    # Sampling legend on RX axis
    axes[1].plot([], [], marker='v', markersize=5, color=COLORS["sample"],
                linestyle='none', label="mid-bit sample")
    axes[1].legend(loc="upper right", fontsize=6, framealpha=0.8,
                  edgecolor="#E5E7EB", handletextpad=0.3)

    # --- tx_busy ---
    busy_events = get_signal(data, "u_tx.tx_busy")
    busy_ts, busy_vs = transitions_to_step(busy_events, t0, t1)
    plot_signal(axes[2], busy_ts, busy_vs, COLORS["busy"], "tx_busy")
    style_axis(axes[2])

    # --- rx_valid (single-clock pulse) ---
    valid_events = get_signal(data, "u_rx.rx_valid")
    valid_ts, valid_vs = transitions_to_step(valid_events, t0, t1)
    plot_signal(axes[3], valid_ts, valid_vs, COLORS["valid"], "rx_valid", lw=1.6)
    style_axis(axes[3])

    # Mark the rx_valid pulse with a prominent triangle marker since
    # a 1-clock pulse (10ns) is very narrow at this time scale
    valid_pulses = find_pulse_times(valid_events, t0, t1)
    for vp_rise, vp_fall in valid_pulses:
        vp_mid = (vp_rise + vp_fall) / 2 / 1e6
        # Arrow pointing down to the pulse
        axes[3].annotate("", xy=(vp_mid, 1.0), xytext=(vp_mid, 1.35),
                        arrowprops=dict(arrowstyle="-|>", color=COLORS["valid"],
                                       lw=1.5, mutation_scale=10))
        axes[3].text(vp_mid, 1.40, "1-clk pulse", ha="center", va="bottom",
                    fontsize=6, color=COLORS["valid"], fontweight="bold")

    ax_tx = axes[0]

    # --- Bit-boundary vertical lines ---
    for i in range(11):
        t_line = (start_t + i * BIT) / 1e6
        for ax in axes:
            ax.axvline(t_line, color="#E5E7EB", linewidth=0.6, linestyle="--", zorder=0)

    # --- Shaded regions for frame structure ---
    # Start bit — green tint
    ax_tx.axvspan(start_t / 1e6, (start_t + BIT) / 1e6,
                  alpha=0.10, color="#16A34A", zorder=0)
    # Data region — blue tint
    ax_tx.axvspan((start_t + BIT) / 1e6, (start_t + 9 * BIT) / 1e6,
                  alpha=0.06, color="#2563EB", zorder=0)
    # Stop bit — green tint
    ax_tx.axvspan((start_t + 9 * BIT) / 1e6, (start_t + 10 * BIT) / 1e6,
                  alpha=0.10, color="#16A34A", zorder=0)

    # --- Bit labels ---
    t_mid = (start_t + BIT / 2) / 1e6
    ax_tx.text(t_mid, 1.38, "START", ha="center", va="bottom", fontsize=7,
               fontweight="bold", color="#16A34A")

    for i, b in enumerate(data_bits):
        t_mid = (start_t + (1 + i) * BIT + BIT / 2) / 1e6
        ax_tx.text(t_mid, 1.38, f"D{i}={b}", ha="center", va="bottom",
                   fontsize=6.5, fontweight="bold", color="#1E40AF")

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

    # --- Frame duration bracket on tx_busy ---
    busy_start = start_t / 1e6
    busy_end = (start_t + 10 * BIT) / 1e6
    axes[2].annotate("", xy=(busy_start, 1.30), xytext=(busy_end, 1.30),
                    arrowprops=dict(arrowstyle="<->", color=COLORS["busy"],
                                   lw=1.0, mutation_scale=8))
    axes[2].text((busy_start + busy_end) / 2, 1.38, "10 bit periods (160 clks)",
                ha="center", va="bottom", fontsize=6, color=COLORS["busy"],
                fontweight="bold")

    axes[-1].set_xlabel("Time (µs)", fontsize=9, color="#6B7280")
    fig.suptitle("UART 8N1 Transmission — Single Byte (0xA5)",
                 fontsize=13, fontweight="bold", color="#111827", y=0.98)

    plt.savefig(out_path, dpi=200, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    plt.close()
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# Figure 2: FIFO burst (4 bytes back-to-back)
# ---------------------------------------------------------------------------

def plot_fifo_burst(data, out_path):
    BIT = 160_000  # ps per UART bit
    CLK = 10_000   # ps per clock

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

    # The FIFO burst (test 4) has uniquely tight inter-frame gaps: ~2 clock
    # cycles (~20,000 ps) vs ~60,000+ ps for testbench-driven sends.
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

    fig, axes = plt.subplots(3, 1, figsize=(16, 5.2), sharex=True,
                              gridspec_kw={"hspace": 0.06,
                                           "height_ratios": [1.5, 0.8, 0.8]})
    fig.patch.set_facecolor("white")

    # --- TX Line ---
    tx_events = get_signal(data, "u_tx.tx")
    tx_ts, tx_vs = transitions_to_step(tx_events, t0, t1)
    plot_signal(axes[0], tx_ts, tx_vs, COLORS["tx"], "TX Line")
    style_axis(axes[0])

    # --- tx_busy ---
    busy_ts, busy_vs = transitions_to_step(busy_events, t0, t1)
    plot_signal(axes[1], busy_ts, busy_vs, COLORS["busy"], "tx_busy")
    style_axis(axes[1])

    # --- rx_valid ---
    valid_events = get_signal(data, "u_rx.rx_valid")
    valid_ts, valid_vs = transitions_to_step(valid_events, t0, t1)
    plot_signal(axes[2], valid_ts, valid_vs, COLORS["valid"], "rx_valid", lw=1.6)
    style_axis(axes[2])

    # Mark each rx_valid pulse with arrow + label
    valid_pulses = find_pulse_times(valid_events, t0, t1)
    for idx, (vp_rise, vp_fall) in enumerate(valid_pulses):
        vp_mid = (vp_rise + vp_fall) / 2 / 1e6
        axes[2].annotate("", xy=(vp_mid, 1.0), xytext=(vp_mid, 1.30),
                        arrowprops=dict(arrowstyle="-|>", color=COLORS["valid"],
                                       lw=1.2, mutation_scale=8))
        if idx < len(byte_values):
            axes[2].text(vp_mid, 1.35, f"0x{byte_values[idx]:02X}",
                        ha="center", va="bottom", fontsize=5.5,
                        color=COLORS["valid"], fontweight="bold")

    ax_tx = axes[0]

    # --- Per-frame shading and labels ---
    frame_colors = ["#DBEAFE", "#FEF3C7", "#D1FAE5", "#FCE7F3"]
    frame_edge   = ["#93C5FD", "#FCD34D", "#6EE7B7", "#F9A8D4"]
    frame_text   = ["#1E40AF", "#92400E", "#065F46", "#9D174D"]

    for i, ((fs, fe), bval) in enumerate(zip(burst_frames, byte_values)):
        # Shade the frame region on TX axis
        ax_tx.axvspan(fs / 1e6, fe / 1e6, alpha=0.12,
                      color=frame_edge[i], zorder=0)

        # Frame boundary lines on all axes
        for ax in axes:
            ax.axvline(fs / 1e6, color="#D1D5DB", linewidth=0.5,
                       linestyle=":", zorder=0)
            ax.axvline(fe / 1e6, color="#D1D5DB", linewidth=0.5,
                       linestyle=":", zorder=0)

        # Byte value badge
        t_mid = (fs + fe) / 2 / 1e6
        ax_tx.annotate(f"0x{bval:02X}", xy=(t_mid, 1.40), fontsize=10,
                       ha="center", fontweight="bold", color=frame_text[i],
                       bbox=dict(boxstyle="round,pad=0.3",
                                 facecolor=frame_colors[i],
                                 edgecolor=frame_edge[i], linewidth=1.2))

        # Within each frame, add start/data/stop structure markers
        # Start bit
        ax_tx.text((fs + BIT / 2) / 1e6, -0.12, "S", ha="center",
                   fontsize=5.5, color="#16A34A", fontweight="bold")
        # Stop bit
        ax_tx.text((fe - BIT / 2) / 1e6, -0.12, "P", ha="center",
                   fontsize=5.5, color="#16A34A", fontweight="bold")

    # --- Annotate inter-frame gaps ---
    for i in range(3):
        gap_start = burst_frames[i][1]
        gap_end   = burst_frames[i+1][0]
        gap_clks  = (gap_end - gap_start) / CLK
        t_mid = (gap_start + gap_end) / 2 / 1e6

        # Draw bracket on tx_busy axis showing the brief deassert
        axes[1].annotate(f"{int(gap_clks)}T gap", xy=(t_mid, 0.50),
                         fontsize=5.5, ha="center", va="center",
                         color="#6B7280", fontstyle="italic",
                         bbox=dict(boxstyle="round,pad=0.15",
                                   facecolor="white", edgecolor="#D1D5DB",
                                   linewidth=0.5))

    # --- Overall burst bracket on tx_busy ---
    burst_total_start = burst_frames[0][0] / 1e6
    burst_total_end = burst_frames[3][1] / 1e6
    axes[1].annotate("", xy=(burst_total_start, 1.28),
                    xytext=(burst_total_end, 1.28),
                    arrowprops=dict(arrowstyle="<->", color=COLORS["busy"],
                                   lw=1.0, mutation_scale=8))
    total_bits = (burst_frames[3][1] - burst_frames[0][0]) / BIT
    axes[1].text((burst_total_start + burst_total_end) / 2, 1.35,
                f"4 frames \u2248 {total_bits:.0f} bit periods",
                ha="center", va="bottom", fontsize=6, color=COLORS["busy"],
                fontweight="bold")

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
