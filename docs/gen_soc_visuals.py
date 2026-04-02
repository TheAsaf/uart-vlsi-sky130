#!/usr/bin/env python3
"""Generate SoC-level visual assets for the README.

Produces:
  images/soc_architecture.png     — redesigned SoC block diagram
  images/cpu_fetch_waveform.png   — GTKWave-style CPU instruction fetch
  images/uart_write_waveform.png  — GTKWave-style CPU → bus → UART write
  images/interrupt_flow.png       — GTKWave-style IRQ assert → ISR → clear
"""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import matplotlib.patheffects as pe
import numpy as np

IMG_DIR = os.path.join(os.path.dirname(__file__), "images")
os.makedirs(IMG_DIR, exist_ok=True)

# ─── Architecture colour palette ────────────────────────────────────────────
CPU_EC,  CPU_FC  = "#1E40AF", "#EFF6FF"
BUS_EC,  BUS_FC  = "#5B21B6", "#F5F3FF"
SRAM_EC, SRAM_FC = "#065F46", "#ECFDF5"
TX_EC,   TX_FC   = "#1D4ED8", "#DBEAFE"
RX_EC,   RX_FC   = "#9F1239", "#FFF1F2"
FIFO_EC, FIFO_FC = "#92400E", "#FEF3C7"
REG_EC,  REG_FC  = "#4338CA", "#EEF2FF"
IRQ_C             = "#7C3AED"
UART_EC, UART_FC = "#B45309", "#FFFDF0"
TXT_DARK = "#111827"
TXT_GRAY = "#6B7280"

# ─── GTKWave colour palette ──────────────────────────────────────────────────
GTK_BG    = "#0D1117"
GTK_GRID  = "#161B22"
GTK_CLK   = "#58A6FF"   # blue
GTK_BIT   = "#3FB950"   # green
GTK_BUS   = "#E3B341"   # amber
GTK_IRQ   = "#F85149"   # red
GTK_RX    = "#BC8CFF"   # purple
GTK_TX    = "#58A6FF"   # blue
GTK_NAMES = "#8B949E"   # dim white for signal names
GTK_ANNO  = "#F0883E"   # orange for annotation arrows/text
GTK_WHITE = "#E6EDF3"   # bright white for important text


# ─────────────────────────────────────────────────────────────────────────────
# 1.  SoC Architecture Diagram
# ─────────────────────────────────────────────────────────────────────────────

def gen_soc_architecture():
    fig = plt.figure(figsize=(17, 9.5))
    fig.patch.set_facecolor("#FFFFFF")
    ax = fig.add_axes([0.01, 0.02, 0.97, 0.88])
    ax.set_xlim(0, 17)
    ax.set_ylim(0, 9.5)
    ax.axis("off")

    # ── Helper: draw a rounded block ────────────────────────────────────
    def block(x, y, w, h, title, sub="", ec="#000", fc="#fff",
              tfs=14, sfs=10, lw=2.2, ls="-"):
        rect = FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0,rounding_size=0.22",
            linewidth=lw, edgecolor=ec, facecolor=fc,
            linestyle=ls, zorder=2,
        )
        ax.add_patch(rect)
        ty = y + h / 2 + (0.22 if sub else 0)
        ax.text(x + w / 2, ty, title,
                ha="center", va="center", fontsize=tfs,
                fontweight="bold", color=ec, zorder=3)
        if sub:
            ax.text(x + w / 2, y + h / 2 - 0.24, sub,
                    ha="center", va="center", fontsize=sfs,
                    color=ec, alpha=0.80, zorder=3)

    # ── Helper: annotate arrow ────────────────────────────────────────────
    def arr(x1, y1, x2, y2, c, lbl="", bidir=False, lw=2.0, fs=9.5):
        sty = "<|-|>" if bidir else "-|>"
        ax.annotate(
            "", xy=(x2, y2), xytext=(x1, y1),
            arrowprops=dict(arrowstyle=sty, color=c, lw=lw,
                            mutation_scale=16),
            zorder=5,
        )
        if lbl:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            ax.text(mx, my + 0.24, lbl, ha="center", fontsize=fs,
                    color=c, fontweight="bold", zorder=6,
                    bbox=dict(boxstyle="round,pad=0.18", fc="white",
                              ec="none", alpha=0.96))

    # ──────────────────────────────────────────────────────────────────────
    # Block definitions  (x, y, w, h)
    # ──────────────────────────────────────────────────────────────────────
    # PicoRV32
    CX, CY, CW, CH = 0.3, 1.2, 2.9, 7.8
    # soc_bus
    BX, BY, BW, BH = 4.7, 5.4, 3.6, 2.6
    # soc_sram
    SX, SY, SW, SH = 9.6, 5.4, 4.8, 3.1
    # uart_top container
    UX, UY, UW, UH = 4.2, 0.2, 12.3, 4.9
    # uart_top internals
    REX, REY, REW, REH = 5.0, 2.4, 2.4, 2.2   # reg interface
    RXX, RXY, RXW, RXH = 5.0, 0.55, 2.4, 1.45  # uart_rx
    FIX, FIY, FIW, FIH = 8.3, 2.6, 2.4, 2.0   # sync_fifo
    TWX, TWY, TWW, TWH = 11.5, 2.6, 3.3, 2.0  # uart_tx

    # ──────────────────────────────────────────────────────────────────────
    # Draw blocks
    # ──────────────────────────────────────────────────────────────────────

    # PicoRV32 CPU
    block(CX, CY, CW, CH, "PicoRV32", "RV32I CPU",
          ec=CPU_EC, fc=CPU_FC, tfs=16, sfs=12)
    params = [
        "ENABLE_IRQ = 1",
        "ENABLE_IRQ_QREGS = 0",
        "BARREL_SHIFTER = 1",
        "no MUL / DIV",
        "STACKADDR = 0x400",
        "PROGADDR_IRQ = 0x10",
    ]
    for i, p in enumerate(params):
        ax.text(CX + CW / 2, CY + CH - 2.1 - i * 0.44,
                p, ha="center", fontsize=9, color=CPU_EC,
                fontstyle="italic", zorder=3)

    # soc_bus
    block(BX, BY, BW, BH, "soc_bus", "address decoder",
          ec=BUS_EC, fc=BUS_FC, tfs=14, sfs=10)
    for i, line in enumerate([
        "SRAM: addr[31:10] == 0",
        "UART: addr[31:4] == 0x2000000",
    ]):
        ax.text(BX + BW / 2, BY + 0.85 - i * 0.40,
                line, ha="center", fontsize=8.5, color=BUS_EC, zorder=3)

    # soc_sram
    block(SX, SY, SW, SH, "soc_sram", "256 × 32-bit  ·  1 KB",
          ec=SRAM_EC, fc=SRAM_FC, tfs=14, sfs=10)
    for i, line in enumerate([
        "0x0000 – 0x03FF",
        "combinational read",
        "sync byte-lane write",
    ]):
        ax.text(SX + SW / 2, SY + 1.85 - i * 0.48,
                line, ha="center", fontsize=9, color=SRAM_EC, zorder=3)

    # uart_top container (dashed border)
    rect_ut = FancyBboxPatch(
        (UX, UY), UW, UH,
        boxstyle="round,pad=0,rounding_size=0.30",
        linewidth=2.4, edgecolor=UART_EC, facecolor=UART_FC,
        linestyle="--", zorder=1,
    )
    ax.add_patch(rect_ut)
    ax.text(UX + UW / 2, UY + UH - 0.30, "uart_top",
            ha="center", fontsize=15, fontweight="bold",
            color=UART_EC, zorder=3)

    # reg interface
    block(REX, REY, REW, REH, "reg interface", "4 registers",
          ec=REG_EC, fc=REG_FC, tfs=12, sfs=9)
    for i, r in enumerate(["TX_DATA [W]", "RX_DATA [R]", "STATUS [R/W1C]", "CTRL [RW]"]):
        ax.text(REX + REW / 2, REY + 1.72 - i * 0.38,
                r, ha="center", fontsize=7.5, color=REG_EC, zorder=3)

    # uart_rx
    block(RXX, RXY, RXW, RXH, "uart_rx", "2-FF sync",
          ec=RX_EC, fc=RX_FC, tfs=12, sfs=9)
    ax.text(RXX + RXW / 2, RXY + 0.32,
            "mid-bit sample", ha="center", fontsize=8, color=RX_EC, zorder=3)

    # sync_fifo
    block(FIX, FIY, FIW, FIH, "sync_fifo", "8-deep TX",
          ec=FIFO_EC, fc=FIFO_FC, tfs=12, sfs=9)
    ax.text(FIX + FIW / 2, FIY + 0.36,
            "fall-through read", ha="center", fontsize=8, color=FIFO_EC, zorder=3)

    # uart_tx
    block(TWX, TWY, TWW, TWH, "uart_tx", "8N1 / 8E1 / 8O1",
          ec=TX_EC, fc=TX_FC, tfs=12, sfs=9)
    ax.text(TWX + TWW / 2, TWY + 0.36,
            "baud counter  16-bit", ha="center", fontsize=8, color=TX_EC, zorder=3)

    # ──────────────────────────────────────────────────────────────────────
    # Arrows
    # ──────────────────────────────────────────────────────────────────────

    # 1. CPU ↔ soc_bus  (horizontal, both at y=6.7)
    BBUS_Y = BY + BH / 2  # 6.7
    arr(CX + CW, BBUS_Y, BX, BBUS_Y,
        CPU_EC, "32-bit mem bus", bidir=True, lw=2.4, fs=10)

    # 2. soc_bus ↔ soc_sram  (horizontal)
    arr(BX + BW, BBUS_Y, SX, SY + SH / 2,
        SRAM_EC, "SRAM select", bidir=True, lw=2.2, fs=9.5)

    # 3. soc_bus → uart_top  (vertical down, from bus bottom-center)
    BUS_CX = BX + BW / 2   # 6.5
    arr(BUS_CX, BY, BUS_CX, UY + UH,
        BUS_EC, "UART select", bidir=False, lw=2.2, fs=9.5)

    # 4. uart_rx → reg interface  (vertical up — directly stacked)
    REG_CX = REX + REW / 2   # 6.2
    arr(REG_CX, RXY + RXH, REG_CX, REY,
        RX_EC, "rx_data\nrx_valid", lw=2.0, fs=8.5)

    # 5. reg → sync_fifo  (horizontal)
    TX_ROW = FIY + FIH / 2   # 3.6
    arr(REX + REW, TX_ROW, FIX, TX_ROW,
        FIFO_EC, "", lw=2.0)

    # 6. sync_fifo → uart_tx  (horizontal)
    arr(FIX + FIW, TX_ROW, TWX, TX_ROW,
        TX_EC, "", lw=2.0)

    # 7. uart_tx → TX pin  (horizontal right)
    ax.annotate("", xy=(16.5, TX_ROW), xytext=(TWX + TWW, TX_ROW),
                arrowprops=dict(arrowstyle="-|>", color=TX_EC, lw=2.4,
                                mutation_scale=18), zorder=5)
    ax.text(16.55, TX_ROW, "TX", ha="left", va="center",
            fontsize=14, fontweight="bold", color=TX_EC, zorder=6)

    # 8. RX → uart_rx   L-shaped: horizontal along bottom then up
    RX_BOTTOM = 0.85  # run below internal blocks
    RXB_CX = RXX + RXW  # right edge of uart_rx = 7.4
    # horizontal segment from right edge → uart_rx right
    ax.plot([16.5, RXB_CX], [RX_BOTTOM, RX_BOTTOM],
            color=RX_EC, lw=2.2, zorder=4, solid_capstyle="round")
    # vertical segment up into uart_rx
    ax.annotate("", xy=(RXB_CX, RXY + RXH / 2),
                xytext=(RXB_CX, RX_BOTTOM),
                arrowprops=dict(arrowstyle="-|>", color=RX_EC, lw=2.2,
                                mutation_scale=16), zorder=5)
    ax.text(16.55, RX_BOTTOM, "RX", ha="left", va="center",
            fontsize=14, fontweight="bold", color=RX_EC, zorder=6)

    # 9. IRQ: uart_top left → CPU right  (horizontal at y=2.5)
    IRQ_Y = 2.55
    ax.annotate("", xy=(CX + CW, IRQ_Y), xytext=(UX, IRQ_Y),
                arrowprops=dict(arrowstyle="-|>", color=IRQ_C, lw=2.2,
                                mutation_scale=15), zorder=5)
    ax.text((CX + CW + UX) / 2, IRQ_Y + 0.22,
            "irq[0]", ha="center", fontsize=10.5, fontweight="bold",
            color=IRQ_C, zorder=6,
            bbox=dict(boxstyle="round,pad=0.22", fc="white",
                      ec=IRQ_C, alpha=0.97, lw=1.5))

    # ──────────────────────────────────────────────────────────────────────
    # Signal labels on arrows (bus width annotations)
    # ──────────────────────────────────────────────────────────────────────
    ax.text((CX + CW + BX) / 2, BBUS_Y - 0.36,
            "mem_valid / mem_ready / mem_addr[31:0]\nmem_wdata[31:0] / mem_wstrb[3:0] / mem_rdata[31:0]",
            ha="center", fontsize=7.8, color=CPU_EC, zorder=6,
            bbox=dict(boxstyle="round,pad=0.18", fc="white", ec="none", alpha=0.9))

    # ──────────────────────────────────────────────────────────────────────
    # Title + subtitle
    # ──────────────────────────────────────────────────────────────────────
    ax.text(8.5, 9.3, "rv32_soc — System Architecture",
            ha="center", fontsize=20, fontweight="bold", color=TXT_DARK)
    ax.text(8.5, 8.87,
            "PicoRV32 RV32I  ·  1 KB SRAM  ·  UART IP (8N1 / parity / 8-deep FIFO)  ·  sky130  ·  50 MHz",
            ha="center", fontsize=11, color=TXT_GRAY)

    # Legend
    patches = [
        mpatches.Patch(fc=CPU_FC, ec=CPU_EC, label="CPU Core", lw=2),
        mpatches.Patch(fc=BUS_FC, ec=BUS_EC, label="Bus Decoder", lw=2),
        mpatches.Patch(fc=SRAM_FC, ec=SRAM_EC, label="SRAM", lw=2),
        mpatches.Patch(fc=UART_FC, ec=UART_EC, label="UART Peripheral", lw=2),
        mpatches.Patch(fc="white", ec=IRQ_C, label="IRQ path", lw=2),
    ]
    ax.legend(handles=patches, loc="lower left",
              fontsize=9.5, framealpha=0.97, edgecolor="#E5E7EB",
              bbox_to_anchor=(0.01, 0.01))

    out = os.path.join(IMG_DIR, "soc_architecture.png")
    plt.savefig(out, dpi=160, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    plt.close()
    print(f"  Saved: {out}")


# ─────────────────────────────────────────────────────────────────────────────
# GTKWave-style waveform helpers
# ─────────────────────────────────────────────────────────────────────────────

def _setup_gtk_ax(ax, t_start, t_end, last=False):
    ax.set_facecolor(GTK_BG)
    ax.set_xlim(t_start, t_end)
    ax.set_ylim(-0.22, 1.50)
    for sp in ax.spines.values():
        sp.set_color(GTK_GRID)
        sp.set_linewidth(0.6)
    ax.tick_params(left=False, right=False, bottom=False,
                   labelleft=False, labelbottom=False)
    # horizontal separator line at top
    ax.axhline(1.5, color=GTK_GRID, lw=0.6)
    if last:
        ax.tick_params(bottom=True, labelbottom=True,
                       colors=GTK_NAMES, labelsize=8.5)
        ax.set_xlabel("Time (ns)", fontsize=9.5, color=GTK_NAMES, labelpad=4)
        ax.xaxis.set_tick_params(color=GTK_NAMES)
        for lbl in ax.get_xticklabels():
            lbl.set_color(GTK_NAMES)


def _sig_name(ax, name, color):
    """Write signal name on the left of a row."""
    ax.text(-0.01, 0.50, name, transform=ax.transAxes,
            ha="right", va="center", fontsize=10.5, color=color,
            fontweight="bold")


def draw_clk(ax, t_start, t_end, period=10, color=GTK_CLK, name="clk"):
    n = int((t_end - t_start) / (period / 2)) + 4
    ts, vs = [t_start], [0]
    for i in range(n):
        t = t_start + i * period / 2
        if t > t_end:
            break
        ts.append(t)
        vs.append(i % 2)
    ts.append(t_end)
    vs.append(vs[-1])
    ax.fill_between(ts, 0, vs, step="post", alpha=0.06, color=color)
    ax.step(ts, vs, where="post", color=color, lw=1.1)
    _sig_name(ax, name, color)


def draw_bit(ax, events, t_start, t_end, color=GTK_BIT, name=""):
    """Single-bit signal from [(t, v)] — v must be 0 or 1 (int)."""
    ts = [t_start]
    init = events[0][1] if events and events[0][0] <= t_start else 0
    vs = [init]
    for t, v in events:
        if t < t_start or t > t_end:
            continue
        ts.append(t)
        vs.append(v)
    ts.append(t_end)
    vs.append(vs[-1])
    ts, vs = np.array(ts, float), np.array(vs, float)
    ax.fill_between(ts, 0, vs, step="post", alpha=0.12, color=color)
    ax.step(ts, vs, where="post", color=color, lw=1.6)
    _sig_name(ax, name, color)


def draw_bus(ax, segments, t_start, t_end, color=GTK_BUS, name="",
             font_size=8.0):
    """
    Bus signal.  segments = [(t_start_seg, t_end_seg, label_str), ...]
    Draws filled 'bus' rectangles between y=0 and y=1 with labels.
    """
    # Grey X region before first segment
    if segments and segments[0][0] > t_start:
        _bus_seg(ax, t_start, segments[0][0], "X", "#2D2D4E", font_size)

    for (t1, t2, lbl) in segments:
        t1c = max(t1, t_start)
        t2c = min(t2, t_end)
        if t2c <= t1c:
            continue
        _bus_seg(ax, t1c, t2c, lbl, color, font_size)

    # Trailing X
    if segments and segments[-1][1] < t_end:
        _bus_seg(ax, segments[-1][1], t_end, "X", "#2D2D4E", font_size)

    _sig_name(ax, name, color)


def _bus_seg(ax, t1, t2, label, color, fsize):
    W = t2 - t1
    NOTCH = min(W * 0.06, 4)
    is_x = (label == "X")
    fc_a = 0.0 if is_x else 0.18
    lc = "#3A3A5A" if is_x else color
    xs = [t1, t1 + NOTCH, t2 - NOTCH, t2, t2 - NOTCH, t1 + NOTCH, t1]
    ys = [0.5, 1.0, 1.0, 0.5, 0.0, 0.0, 0.5]
    if not is_x:
        ax.fill(xs, ys, color=color, alpha=fc_a, zorder=2)
    ax.plot([t1 + NOTCH, t2 - NOTCH], [1.0, 1.0], color=lc, lw=1.3, zorder=3)
    ax.plot([t1 + NOTCH, t2 - NOTCH], [0.0, 0.0], color=lc, lw=1.3, zorder=3)
    ax.plot([t1, t1 + NOTCH, t2 - NOTCH, t2],
            [0.5, 1.0, 1.0, 0.5], color=lc, lw=1.3, zorder=3)
    ax.plot([t1, t1 + NOTCH, t2 - NOTCH, t2],
            [0.5, 0.0, 0.0, 0.5], color=lc, lw=1.3, zorder=3)
    if not is_x and W > 12:
        ax.text((t1 + t2) / 2, 0.50, label, ha="center", va="center",
                fontsize=fsize, color=GTK_WHITE, fontweight="bold", zorder=4)


def vmark(ax, t, color, label="", side="top", fs=8):
    """Vertical marker line + optional label."""
    ax.axvline(t, color=color, lw=1.2, linestyle="--", alpha=0.65, zorder=1)
    if label:
        y = 1.35 if side == "top" else -0.15
        va = "bottom" if side == "top" else "top"
        ax.text(t, y, label, ha="center", va=va, fontsize=fs,
                color=color, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.15", fc=GTK_BG,
                          ec=color, alpha=0.92, lw=0.8))


def anno(ax, t, y, label, color=GTK_ANNO, fs=8, ya=1.30, side="top"):
    """Arrow annotation pointing to a waveform event."""
    ytext = ya if side == "top" else -0.12
    ax.annotate(
        label,
        xy=(t, y), xytext=(t, ytext),
        fontsize=fs, color=color, ha="center", fontweight="bold",
        arrowprops=dict(arrowstyle="-|>", color=color, lw=1.0,
                        mutation_scale=9),
        bbox=dict(boxstyle="round,pad=0.18", fc=GTK_BG,
                  ec=color, alpha=0.95, lw=0.8),
    )


def gtk_figure(n_rows, title, height_ratios=None):
    if height_ratios is None:
        height_ratios = [1.0] * n_rows
    row_h = 1.35
    total_h = sum(height_ratios) * row_h + 0.6
    fig, axes = plt.subplots(
        n_rows, 1,
        figsize=(15, total_h),
        sharex=True,
        gridspec_kw={"hspace": 0.0, "height_ratios": height_ratios},
    )
    fig.patch.set_facecolor(GTK_BG)
    if n_rows == 1:
        axes = [axes]
    fig.suptitle(title, fontsize=13, color=GTK_WHITE, fontweight="bold",
                 y=0.995, x=0.55)
    return fig, axes


# ─────────────────────────────────────────────────────────────────────────────
# 2.  CPU Instruction Fetch Waveform
# ─────────────────────────────────────────────────────────────────────────────

def gen_cpu_fetch_waveform():
    T0, T1 = 210, 560   # ns

    # Actual data from SoC VCD
    FETCHES = [
        (270, 280, "0x0000_0000", "0x01C0_006F",  "JAL x0, _start"),
        (330, 340, "0x0000_001C", "0x2000_00B7",  "LUI x1, 0x20000"),
        (390, 400, "0x0000_0020", "0x0550_0593",  "ADDI a1, 0x55"),
        (450, 460, "0x0000_0024", "0x00B0_A023",  "SW a1, 0(x1)"),
        (510, 520, "0x0000_0028", "0x0560_0593",  "ADDI a1, 0x56"),
    ]

    # Build mem_valid / mem_ready bit events (1-cycle pulses)
    valid_events = []
    for t_rise, t_fall, *_ in FETCHES:
        valid_events += [(t_rise, 1), (t_fall, 0)]

    # Build mem_addr bus segments
    addr_segs = []
    for i, (t_rise, t_fall, addr, _, _) in enumerate(FETCHES):
        t2 = FETCHES[i + 1][0] if i + 1 < len(FETCHES) else T1
        addr_segs.append((t_rise, t2, addr))

    # Build mem_rdata bus segments
    rdata_segs = []
    for i, (t_rise, t_fall, _, rdata, mnemonic) in enumerate(FETCHES):
        t2 = FETCHES[i + 1][0] if i + 1 < len(FETCHES) else T1
        rdata_segs.append((t_rise + 10, t2, rdata))  # SRAM responds 1 cycle later

    fig, axes = gtk_figure(5, "CPU Instruction Fetch — PicoRV32 reads firmware from SRAM",
                           height_ratios=[0.65, 1.0, 1.0, 1.1, 1.1])

    for i, ax in enumerate(axes):
        _setup_gtk_ax(ax, T0, T1, last=(i == len(axes) - 1))

    # clk
    draw_clk(axes[0], T0, T1, period=10, name="clk")

    # mem_valid
    draw_bit(axes[1], valid_events, T0, T1, color=GTK_BIT, name="mem_valid")
    # pulse annotations
    for t_rise, t_fall, addr, _, mnem in FETCHES:
        anno(axes[1], (t_rise + t_fall) / 2, 1.0,
             "fetch", GTK_BIT, fs=7.5, ya=1.32)

    # mem_ready (same timing — SRAM is combinational)
    draw_bit(axes[2], valid_events, T0, T1, color=GTK_BIT, name="mem_ready")
    axes[2].text((T0 + T1) / 2, -0.12,
                 "mem_ready == mem_valid (zero wait states — combinational SRAM)",
                 ha="center", fontsize=7.5, color="#444466", style="italic")

    # mem_addr
    draw_bus(axes[3], addr_segs, T0, T1, color=GTK_BUS, name="mem_addr",
             font_size=8)
    for t_rise, _, addr, _, _ in FETCHES:
        vmark(axes[3], t_rise, GTK_BUS)

    # mem_rdata
    draw_bus(axes[4], rdata_segs, T0, T1, color="#79C0FF", name="mem_rdata",
             font_size=7.5)
    # Mnemonic labels above each rdata segment
    for i, (t_rise, t_fall, addr, rdata, mnem) in enumerate(FETCHES):
        t2 = FETCHES[i + 1][0] if i + 1 < len(FETCHES) else T1
        axes[4].text((t_rise + 10 + t2) / 2, 1.38,
                     mnem, ha="center", fontsize=7.5, color="#79C0FF",
                     fontweight="bold",
                     bbox=dict(boxstyle="round,pad=0.12", fc=GTK_BG,
                               ec="none", alpha=0.9))

    out = os.path.join(IMG_DIR, "cpu_fetch_waveform.png")
    plt.savefig(out, dpi=180, bbox_inches="tight",
                facecolor=GTK_BG, edgecolor="none")
    plt.close()
    print(f"  Saved: {out}")


# ─────────────────────────────────────────────────────────────────────────────
# 3.  UART Write Transaction Waveform
# ─────────────────────────────────────────────────────────────────────────────

def gen_uart_write_waveform():
    T0, T1 = 440, 960   # ns

    # From VCD:
    WRITES = [
        (550, 560, "0x2000_0000", "0x55  ('U')", "TX_DATA"),
        (710, 720, "0x2000_0000", "0x56  ('V')", "TX_DATA"),
        (870, 880, "0x2000_000C", "0x04",        "CTRL (irq_en)"),
    ]

    # mem_wstrb: 0=read, 1=write
    wstrb_events = []
    for t_s, t_e, *_ in WRITES:
        wstrb_events += [(t_s, 1), (t_e, 0)]

    # mem_valid
    valid_events = [(t, 1 if i % 2 == 0 else 0)
                    for i, (t, *_) in enumerate(
                        [(e, ) for w in WRITES for e in [w[0], w[1]]])]
    valid_events2 = []
    for t_s, t_e, *_ in WRITES:
        valid_events2 += [(t_s, 1), (t_e, 0)]

    # mem_addr bus segments
    addr_segs = [(t_s, t_e + 5, addr) for t_s, t_e, addr, *_ in WRITES]

    # mem_wdata bus segments
    wdata_segs = [(t_s, t_e + 5, wdata) for t_s, t_e, _, wdata, *_ in WRITES]

    # uart_tx: starts ~570ns (2 clocks after first write), 8N1 for 0x55
    BIT = 160  # ns per uart bit (CLKS_PER_BIT=16, CLK=10ns)
    TX_START = 570
    bits_U = [(0x55 >> i) & 1 for i in range(8)]
    tx_events = [(0, 1), (TX_START, 0)]  # start bit
    t_cur = TX_START + BIT
    for b in bits_U:
        tx_events.append((t_cur, b))
        t_cur += BIT
    tx_events.append((t_cur, 1))  # stop bit

    fig, axes = gtk_figure(5, "UART Write Transaction — CPU → soc_bus → uart_top",
                           height_ratios=[0.65, 0.9, 0.9, 1.1, 1.1])
    for i, ax in enumerate(axes):
        _setup_gtk_ax(ax, T0, T1, last=(i == len(axes) - 1))

    draw_clk(axes[0], T0, T1, period=10, name="clk")

    draw_bit(axes[1], valid_events2, T0, T1, color=GTK_BIT, name="mem_valid")
    for t_s, t_e, _, wdata, reg in WRITES:
        anno(axes[1], (t_s + t_e) / 2, 1.0, "SW", GTK_BIT, fs=8, ya=1.30)

    draw_bit(axes[2], wstrb_events, T0, T1, color=GTK_BIT, name="mem_wstrb")
    axes[2].text((T0 + T1) / 2, -0.14,
                 "wstrb = 0xF  →  full 32-bit word store  (UART only uses wdata[7:0])",
                 ha="center", fontsize=7.5, color="#444466", style="italic")

    draw_bus(axes[3], addr_segs, T0, T1, color=GTK_BUS, name="mem_addr",
             font_size=8.5)

    draw_bus(axes[4], wdata_segs, T0, T1, color="#79C0FF", name="mem_wdata",
             font_size=9)

    # Vertical markers at each write
    for t_s, t_e, addr, wdata, reg in WRITES:
        for ax in axes:
            ax.axvline(t_s, color="#FFD700", lw=1.0, ls="--", alpha=0.5, zorder=1)

    # uart_tx note — starts after first write
    axes[4].annotate(
        "uart_tx serialiser begins\n(FIFO → baud counter → bits)",
        xy=(TX_START, 0.5), xytext=(TX_START + 60, 1.35),
        fontsize=7.5, color=GTK_TX, fontweight="bold", ha="center",
        arrowprops=dict(arrowstyle="-|>", color=GTK_TX, lw=1.0,
                        mutation_scale=9),
        bbox=dict(boxstyle="round,pad=0.18", fc=GTK_BG, ec=GTK_TX,
                  alpha=0.95, lw=0.8),
    )

    out = os.path.join(IMG_DIR, "uart_write_waveform.png")
    plt.savefig(out, dpi=180, bbox_inches="tight",
                facecolor=GTK_BG, edgecolor="none")
    plt.close()
    print(f"  Saved: {out}")


# ─────────────────────────────────────────────────────────────────────────────
# 4.  Interrupt Flow Waveform
# ─────────────────────────────────────────────────────────────────────────────

def gen_interrupt_flow():
    T0, T1 = 7_900, 11_200  # ns

    BIT = 160   # ns per uart bit
    # RX 8N1 frame for 0xA5 ends at t=9990ns
    T_RX_START = 9_990 - 10 * BIT  # = 8390 ns
    T_RX_END   = 9_990
    bits_A5 = [(0xA5 >> i) & 1 for i in range(8)]

    # uart_rx signal
    rx_events = [(T0, 1), (T_RX_START, 0)]  # start bit
    t = T_RX_START + BIT
    for b in bits_A5:
        rx_events.append((t, b))
        t += BIT
    rx_events.append((t, 1))  # stop bit

    # irq_out (from VCD: HIGH at 10010, LOW at 10270)
    T_IRQ_HI = 10_010
    T_IRQ_LO = 10_270
    irq_events = [(T0, 0), (T_IRQ_HI, 1), (T_IRQ_LO, 0)]

    # mem_addr bus segments (from VCD)
    IDLE_ADDR = "0x0000_003C"   # main() spin loop
    ISR_ENTRY  = "0x0000_0010"  # ISR entry — _irq_entry
    ISR_C1     = "0x0000_0014"  # save context
    ISR_C2     = "0x0000_0018"  # ...
    RX_READ    = "0x2000_0004"  # UART RX_DATA read

    T_ISR_FETCH   = 10_090
    T_ISR_C1      = 10_150
    T_ISR_C2      = 10_210
    T_ISR_RX_READ = 10_250
    T_MAIN_RESUME = 10_350

    addr_segs = [
        (T0,           T_IRQ_HI,      IDLE_ADDR),
        (T_ISR_FETCH,  T_ISR_C1,      ISR_ENTRY),
        (T_ISR_C1,     T_ISR_C2,      ISR_C1),
        (T_ISR_C2,     T_ISR_RX_READ, ISR_C2),
        (T_ISR_RX_READ,T_MAIN_RESUME, RX_READ),
        (T_MAIN_RESUME,T1,            IDLE_ADDR),
    ]

    fig, axes = gtk_figure(
        4,
        "Interrupt Flow — RX Byte → IRQ Assertion → ISR Reads RX_DATA → IRQ Clear",
        height_ratios=[0.65, 1.2, 0.9, 1.2],
    )
    for i, ax in enumerate(axes):
        _setup_gtk_ax(ax, T0, T1, last=(i == len(axes) - 1))

    draw_clk(axes[0], T0, T1, period=10, name="clk")

    # uart_rx
    draw_bit(axes[1], rx_events, T0, T1, color=GTK_RX, name="uart_rx")
    # Frame annotations
    axes[1].text((T_RX_START + BIT / 2), 1.38, "START",
                 ha="center", fontsize=7.5, color="#16A34A", fontweight="bold")
    axes[1].text((T_RX_START + 4.5 * BIT), 1.38, "0xA5  (8 data bits  LSB-first)",
                 ha="center", fontsize=8, color=GTK_RX, fontweight="bold")
    axes[1].text((T_RX_END + BIT / 2), 1.38, "STOP",
                 ha="center", fontsize=7.5, color="#16A34A", fontweight="bold")
    axes[1].text((T0 + T_RX_START) / 2, 0.50, "IDLE",
                 ha="center", fontsize=9, color="#3A3A6A", style="italic")

    # irq_out
    draw_bit(axes[2], irq_events, T0, T1, color=GTK_IRQ, name="irq_out")
    anno(axes[2], T_IRQ_HI, 1.0, "ASSERT\n(rx_ready=1)",
         GTK_IRQ, fs=8, ya=1.35)
    anno(axes[2], T_IRQ_LO, 1.0, "CLEAR\n(RX_DATA read)",
         "#3FB950", fs=8, ya=1.35)
    axes[2].text((T_IRQ_HI + T_IRQ_LO) / 2, 0.50,
                 f"HIGH for {T_IRQ_LO - T_IRQ_HI} ns ({(T_IRQ_LO-T_IRQ_HI)//10} clocks)",
                 ha="center", fontsize=7.5, color=GTK_IRQ, fontweight="bold")

    # mem_addr
    draw_bus(axes[3], addr_segs, T0, T1, color=GTK_BUS, name="mem_addr",
             font_size=7.8)

    # Annotations on mem_addr
    anno(axes[3], T_ISR_FETCH, 0.8,
         "CPU jumps to\n0x10 (ISR)", GTK_ANNO, fs=7.5, ya=1.37)
    anno(axes[3], T_ISR_RX_READ, 0.8,
         "ISR reads\nRX_DATA", "#79C0FF", fs=7.5, ya=1.37)
    anno(axes[3], T_MAIN_RESUME, 0.8,
         "retirq\nresumes main()", "#3FB950", fs=7.5, ya=1.37)

    # Shared vertical markers
    for ax in axes:
        vmark(ax, T_IRQ_HI, GTK_IRQ)
        vmark(ax, T_ISR_FETCH, GTK_ANNO)
        vmark(ax, T_ISR_RX_READ, "#79C0FF")
        vmark(ax, T_IRQ_LO, "#3FB950")
        vmark(ax, T_MAIN_RESUME, "#3FB950")

    # Gap label (CPU taking interrupt — between irq assert and ISR fetch)
    axes[3].annotate(
        "CPU takes interrupt\n(saves PC → x3, PC → 0x10)",
        xy=((T_IRQ_HI + T_ISR_FETCH) / 2, 0.50),
        fontsize=7.5, color="#9CA3AF", ha="center", style="italic",
        xycoords="data",
        bbox=dict(boxstyle="round,pad=0.18", fc=GTK_BG,
                  ec="#444466", alpha=0.92, lw=0.6),
    )

    out = os.path.join(IMG_DIR, "interrupt_flow.png")
    plt.savefig(out, dpi=180, bbox_inches="tight",
                facecolor=GTK_BG, edgecolor="none")
    plt.close()
    print(f"  Saved: {out}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Generating SoC visual assets...")
    gen_soc_architecture()
    gen_cpu_fetch_waveform()
    gen_uart_write_waveform()
    gen_interrupt_flow()
    print("Done.")
