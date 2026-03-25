#!/usr/bin/env python3
"""Generate UART waveform diagrams from simulation VCD data.

Produces two images:
  1. uart_8n1_waveform.png  — A single 8N1 byte transfer (0xA5) showing
     start bit, 8 data bits, stop bit, and RX valid pulse.
  2. uart_fifo_burst.png    — FIFO burst of 4 bytes showing back-to-back
     transmission without idle gaps.
"""

import struct
import re
import sys
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np


# ---------------------------------------------------------------------------
# Minimal VCD parser — extracts named signals as (time, value) pairs.
# ---------------------------------------------------------------------------

def parse_vcd(path, signals_of_interest):
    """Return {signal_name: [(time, value), ...]} from a VCD file."""
    var_map = {}   # vcd_id -> signal_name
    data = {s: [] for s in signals_of_interest}

    with open(path) as f:
        in_defs = True
        scope_stack = []
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
                    # $var wire 1 ! clk $end
                    if len(parts) >= 5:
                        vcd_id = parts[3]
                        name = parts[4]
                        full = ".".join(scope_stack + [name])
                        for s in signals_of_interest:
                            if name == s or full.endswith(s):
                                var_map[vcd_id] = s
                elif line.startswith("$enddefinitions"):
                    in_defs = False
                continue

            # Value changes
            if line.startswith("#"):
                current_time = int(line[1:])
            elif len(line) >= 2 and line[0] in "01xXzZ":
                val = line[0]
                vid = line[1:]
                if vid in var_map:
                    data[var_map[vid]].append((current_time, val))
            elif line.startswith("b"):
                parts = line.split()
                if len(parts) == 2 and parts[1] in var_map:
                    data[var_map[parts[1]]].append((current_time, parts[0][1:]))

    return data


def signal_to_digital(events, t_start, t_end, resolution=1000):
    """Convert event list to arrays suitable for step plotting."""
    times = np.linspace(t_start, t_end, resolution)
    values = np.full(resolution, np.nan)

    if not events:
        return times, values

    # Build a sorted list of transitions
    evts = [(t, v) for t, v in events if t_start <= t <= t_end]
    # Also include the last event before t_start
    pre = [(t, v) for t, v in events if t < t_start]
    if pre:
        evts.insert(0, pre[-1])
    evts.sort()

    for i, t in enumerate(times):
        # Find last event at or before t
        val = None
        for et, ev in evts:
            if et <= t:
                val = ev
            else:
                break
        if val is not None:
            if val in ("0", "1"):
                values[i] = int(val)
            else:
                values[i] = 0.5  # unknown / X

    return times, values


# ---------------------------------------------------------------------------
# Plotting helpers
# ---------------------------------------------------------------------------

COLORS = {
    "tx":       "#2563EB",  # blue
    "rx":       "#DC2626",  # red (unused here, rx=tx in loopback)
    "start":    "#16A34A",  # green
    "data":     "#2563EB",
    "valid":    "#9333EA",  # purple
    "done":     "#EA580C",  # orange
    "clk":      "#6B7280",  # grey
}

def add_bit_annotations(ax, y_base, t_start, bit_period, bits, label_prefix=""):
    """Add bit value labels above each bit cell."""
    for i, bit in enumerate(bits):
        t_center = t_start + (i + 0.5) * bit_period
        ax.text(t_center, y_base, str(bit),
                ha="center", va="bottom", fontsize=7,
                fontfamily="monospace", color="#374151", fontweight="bold")


def style_axis(ax, title=""):
    ax.set_facecolor("#FAFAFA")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#D1D5DB")
    ax.spines["bottom"].set_color("#D1D5DB")
    ax.tick_params(colors="#6B7280", labelsize=7)
    if title:
        ax.set_title(title, fontsize=9, fontweight="bold", color="#111827", loc="left", pad=8)


# ---------------------------------------------------------------------------
# Figure 1: Single 8N1 byte (0xA5) waveform
# ---------------------------------------------------------------------------

def plot_single_byte(vcd_path, out_path):
    CLK_PERIOD = 10_000  # 10 ns in ps
    CLKS_PER_BIT = 16
    BIT_PERIOD = CLK_PERIOD * CLKS_PER_BIT  # 160,000 ps

    sigs = parse_vcd(vcd_path, ["clk", "uart_tx", "uart_rx", "tx_busy", "rx_valid",
                                 "tx_start", "irq", "rx_ready"])

    # Find the first tx going low (start bit) — that's the first byte
    tx_events = sigs.get("uart_tx", [])
    first_start = None
    for t, v in tx_events:
        if v == "0" and t > 200_000:  # skip reset period
            first_start = t
            break

    if first_start is None:
        print("Could not find first TX start bit in VCD")
        return

    # Window: a bit before start to after stop bit
    margin = BIT_PERIOD * 1.5
    t_start = first_start - margin
    t_end = first_start + BIT_PERIOD * 11 + margin  # start + 8 data + stop + margin
    res = 3000

    fig, axes = plt.subplots(4, 1, figsize=(12, 5.5), sharex=True,
                              gridspec_kw={"hspace": 0.05, "height_ratios": [1, 1, 0.6, 0.6]})
    fig.patch.set_facecolor("white")

    labels = [
        ("uart_tx", "TX Line", COLORS["tx"]),
        ("uart_rx", "RX (loopback)", "#DC2626"),
        ("tx_busy", "tx_busy", COLORS["done"]),
        ("rx_valid", "rx_valid", COLORS["valid"]),
    ]

    for ax, (sig_name, label, color) in zip(axes, labels):
        times, values = signal_to_digital(sigs.get(sig_name, []), t_start, t_end, res)
        times_us = times / 1e6  # ps to µs
        ax.fill_between(times_us, 0, values, alpha=0.15, color=color, step="pre")
        ax.step(times_us, values, where="pre", linewidth=1.2, color=color)
        ax.set_ylim(-0.15, 1.4)
        ax.set_ylabel(label, fontsize=8, color="#374151", fontweight="bold", rotation=0,
                       labelpad=60, va="center")
        ax.set_yticks([0, 1])
        ax.set_yticklabels(["0", "1"], fontsize=7)
        style_axis(ax)

    # Annotate bit fields on the TX line
    ax0 = axes[0]
    data_byte = 0xA5  # 10100101
    bits = [(data_byte >> i) & 1 for i in range(8)]  # LSB first

    # Start bit
    t_s = first_start / 1e6
    bp = BIT_PERIOD / 1e6
    ax0.annotate("START", xy=(t_s + bp/2, -0.08), fontsize=6, ha="center",
                 color="#16A34A", fontweight="bold")

    # Data bits
    for i, b in enumerate(bits):
        t_center = (first_start + (1 + i) * BIT_PERIOD + BIT_PERIOD/2) / 1e6
        ax0.annotate(f"D{i}={b}", xy=(t_center, 1.25), fontsize=5.5, ha="center",
                     color="#1E40AF", fontweight="bold")

    # Stop bit
    t_stop = (first_start + 9 * BIT_PERIOD + BIT_PERIOD/2) / 1e6
    ax0.annotate("STOP", xy=(t_stop, -0.08), fontsize=6, ha="center",
                 color="#16A34A", fontweight="bold")

    # Byte value annotation
    ax0.annotate(f"0xA5", xy=(t_s + 5*bp, 1.35), fontsize=9, ha="center",
                 color="#1E3A5F", fontweight="bold",
                 bbox=dict(boxstyle="round,pad=0.3", facecolor="#DBEAFE", edgecolor="#93C5FD"))

    # Add vertical dashed lines for bit boundaries
    for i in range(11):
        t_line = (first_start + i * BIT_PERIOD) / 1e6
        for ax in axes:
            ax.axvline(t_line, color="#E5E7EB", linewidth=0.5, linestyle="--", zorder=0)

    axes[-1].set_xlabel("Time (µs)", fontsize=8, color="#6B7280")

    fig.suptitle("UART 8N1 Transmission — Single Byte (0xA5)",
                 fontsize=11, fontweight="bold", color="#111827", y=0.97)

    plt.savefig(out_path, dpi=180, bbox_inches="tight", facecolor="white", edgecolor="none")
    plt.close()
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# Figure 2: FIFO burst — 4 bytes back-to-back
# ---------------------------------------------------------------------------

def plot_fifo_burst(vcd_path, out_path):
    CLK_PERIOD = 10_000
    CLKS_PER_BIT = 16
    BIT_PERIOD = CLK_PERIOD * CLKS_PER_BIT
    FRAME_BITS = 10  # start + 8 data + stop

    sigs = parse_vcd(vcd_path, ["uart_tx", "rx_valid", "tx_busy"])

    tx_events = sigs.get("uart_tx", [])

    # Find start bits (falling edges after the design settles)
    # We need to find the FIFO burst which is test 4: bytes 0x11, 0x22, 0x33, 0x44
    # These come after tests 1-3. Let's find the 4 consecutive start bits that correspond.
    falling_edges = []
    prev_v = "1"
    for t, v in tx_events:
        if prev_v == "1" and v == "0" and t > 200_000:
            falling_edges.append(t)
        prev_v = v

    # The burst bytes (test 4) are bytes 10-13 (0-indexed: after 5+2+2=9 bytes from tests 1-3)
    if len(falling_edges) < 13:
        print(f"Not enough falling edges found ({len(falling_edges)}), skipping burst plot")
        return

    burst_start = falling_edges[9]  # 10th byte = first burst byte
    burst_end = falling_edges[9] + FRAME_BITS * BIT_PERIOD * 4 + BIT_PERIOD * 3

    margin = BIT_PERIOD * 2
    t_start = burst_start - margin
    t_end = burst_end + margin
    res = 4000

    fig, axes = plt.subplots(3, 1, figsize=(14, 4), sharex=True,
                              gridspec_kw={"hspace": 0.05, "height_ratios": [1.2, 0.6, 0.6]})
    fig.patch.set_facecolor("white")

    labels = [
        ("uart_tx", "TX Line", COLORS["tx"]),
        ("tx_busy", "tx_busy", COLORS["done"]),
        ("rx_valid", "rx_valid", COLORS["valid"]),
    ]

    for ax, (sig_name, label, color) in zip(axes, labels):
        times, values = signal_to_digital(sigs.get(sig_name, []), t_start, t_end, res)
        times_us = times / 1e6
        ax.fill_between(times_us, 0, values, alpha=0.15, color=color, step="pre")
        ax.step(times_us, values, where="pre", linewidth=1.2, color=color)
        ax.set_ylim(-0.15, 1.5)
        ax.set_ylabel(label, fontsize=8, color="#374151", fontweight="bold", rotation=0,
                       labelpad=55, va="center")
        ax.set_yticks([0, 1])
        ax.set_yticklabels(["0", "1"], fontsize=7)
        style_axis(ax)

    # Annotate each byte in the burst
    burst_bytes = [0x11, 0x22, 0x33, 0x44]
    burst_colors = ["#DBEAFE", "#FEF3C7", "#D1FAE5", "#FCE7F3"]
    burst_edge_colors = ["#93C5FD", "#FCD34D", "#6EE7B7", "#F9A8D4"]

    for idx in range(4):
        if 9 + idx < len(falling_edges):
            fe = falling_edges[9 + idx]
            t_center = (fe + FRAME_BITS * BIT_PERIOD / 2) / 1e6
            axes[0].annotate(f"0x{burst_bytes[idx]:02X}", xy=(t_center, 1.3),
                            fontsize=9, ha="center", fontweight="bold", color="#1E3A5F",
                            bbox=dict(boxstyle="round,pad=0.3",
                                     facecolor=burst_colors[idx],
                                     edgecolor=burst_edge_colors[idx]))

            # Shade the frame region
            t_frame_start = fe / 1e6
            t_frame_end = (fe + FRAME_BITS * BIT_PERIOD) / 1e6
            axes[0].axvspan(t_frame_start, t_frame_end, alpha=0.08,
                           color=burst_edge_colors[idx], zorder=0)

    axes[-1].set_xlabel("Time (µs)", fontsize=8, color="#6B7280")
    fig.suptitle("UART FIFO Burst — 4 Bytes Back-to-Back (0x11, 0x22, 0x33, 0x44)",
                 fontsize=11, fontweight="bold", color="#111827", y=0.97)

    plt.savefig(out_path, dpi=180, bbox_inches="tight", facecolor="white", edgecolor="none")
    plt.close()
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    vcd = os.path.join(os.path.dirname(__file__), "..", "tb", "uart_top_tb.vcd")
    img_dir = os.path.join(os.path.dirname(__file__), "images")
    os.makedirs(img_dir, exist_ok=True)

    print("Generating waveform images from VCD...")
    plot_single_byte(vcd, os.path.join(img_dir, "uart_8n1_waveform.png"))
    plot_fifo_burst(vcd, os.path.join(img_dir, "uart_fifo_burst.png"))
    print("Done.")
