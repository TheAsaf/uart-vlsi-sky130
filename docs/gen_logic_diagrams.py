#!/usr/bin/env python3
"""
Generate logical structure diagrams for rv32_soc GitHub documentation.

Produces:
  docs/images/soc_hierarchy.png     — module hierarchy with port connections
  docs/images/soc_block_diagram.png — blocks sized by cell count + data-flow arrows
  docs/images/fifo_internal.png     — sync_fifo internals (pointers, mem, flags)
"""

import os
import math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import matplotlib.gridspec as gridspec
import numpy as np

REPO  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMGS  = os.path.join(REPO, "docs", "images")
os.makedirs(IMGS, exist_ok=True)

# ─── shared style ────────────────────────────────────────────────────────────
BG      = "#0F172A"
PANEL   = "#1E293B"
BORDER  = "#334155"
SUBTLE  = "#475569"
TEXT    = "#E2E8F0"
MUTED   = "#94A3B8"

COL = {
    "cpu":   "#3B82F6",   # blue
    "sram":  "#10B981",   # green
    "uart":  "#F59E0B",   # amber
    "bus":   "#8B5CF6",   # violet
    "top":   "#EC4899",   # pink
    "fifo":  "#14B8A6",   # teal
    "tx":    "#FB923C",   # orange
    "rx":    "#A78BFA",   # purple
    "io":    "#64748B",   # slate
}

def _rgba(hex_color, alpha=0.25):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i+2], 16) / 255 for i in (0, 2, 4))
    return (r, g, b, alpha)

def _text(ax, x, y, s, **kw):
    defaults = dict(color=TEXT, fontsize=9, ha="center", va="center",
                    path_effects=[pe.withStroke(linewidth=1.5, foreground=BG)])
    defaults.update(kw)
    return ax.text(x, y, s, **defaults)

def _box(ax, x, y, w, h, color, label, sublabel="", zorder=3):
    r, g, b, _ = _rgba(color, 0.3)
    rect = FancyBboxPatch((x - w/2, y - h/2), w, h,
                           boxstyle="round,pad=0.015",
                           linewidth=1.5, edgecolor=color,
                           facecolor=(r, g, b, 0.35), zorder=zorder)
    ax.add_patch(rect)
    _text(ax, x, y + (h * 0.12 if sublabel else 0), label,
          fontsize=9, fontweight="bold", color="white", zorder=zorder+1)
    if sublabel:
        _text(ax, x, y - h*0.22, sublabel, fontsize=7.5, color=MUTED,
              zorder=zorder+1)

def _arrow(ax, x0, y0, x1, y1, label="", color=MUTED, lw=1.2, style="->"):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(arrowstyle=style, color=color,
                                lw=lw, connectionstyle="arc3,rad=0.0"))
    if label:
        mx, my = (x0+x1)/2, (y0+y1)/2
        _text(ax, mx, my, label, fontsize=7, color=color,
              bbox=dict(facecolor=BG, edgecolor="none", alpha=0.7, pad=1.5))


# ═══════════════════════════════════════════════════════════════════════════════
# helpers shared by hierarchy + block diagram
# ═══════════════════════════════════════════════════════════════════════════════

def _filled_box(ax, x, y, w, h, color, zo=3):
    """Filled rounded rectangle. (x,y) = bottom-left corner."""
    r, g, b = [int(color.lstrip("#")[i:i+2], 16)/255 for i in (0,2,4)]
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.02",
        linewidth=2.0, edgecolor=color,
        facecolor=(r, g, b, 0.22), zorder=zo))

def _label(ax, x, y, txt, fs=12, bold=True, color="white", zo=10):
    ax.text(x, y, txt,
            ha="center", va="center",
            fontsize=fs, fontweight="bold" if bold else "normal",
            color=color, zorder=zo,
            path_effects=[pe.withStroke(linewidth=2.5, foreground=BG)])

def _sublabel(ax, x, y, txt, fs=9.5, color=None, zo=10):
    _label(ax, x, y, txt, fs=fs, bold=False, color=color or MUTED, zo=zo)

def _hline(ax, x0, x1, y, color, lw=2.0, zo=6):
    """Horizontal line segment."""
    ax.plot([x0, x1], [y, y], color=color, lw=lw, solid_capstyle="round", zorder=zo)

def _vline(ax, x, y0, y1, color, lw=2.0, zo=6):
    """Vertical line segment."""
    ax.plot([x, x], [y0, y1], color=color, lw=lw, solid_capstyle="round", zorder=zo)

def _arrow_right(ax, x0, x1, y, color, lw=2.2, zo=7):
    ax.annotate("", xy=(x1, y), xytext=(x0, y),
                arrowprops=dict(arrowstyle="-|>", color=color, lw=lw,
                                mutation_scale=16), zorder=zo)

def _arrow_left(ax, x0, x1, y, color, lw=2.2, zo=7):
    """Arrow pointing left (tip at x0)."""
    ax.annotate("", xy=(x0, y), xytext=(x1, y),
                arrowprops=dict(arrowstyle="-|>", color=color, lw=lw,
                                mutation_scale=16), zorder=zo)

def _arrow_up(ax, x, y0, y1, color, lw=2.2, zo=7):
    ax.annotate("", xy=(x, y1), xytext=(x, y0),
                arrowprops=dict(arrowstyle="-|>", color=color, lw=lw,
                                mutation_scale=16), zorder=zo)

def _arrow_down(ax, x, y0, y1, color, lw=2.2, zo=7):
    ax.annotate("", xy=(x, y1), xytext=(x, y0),
                arrowprops=dict(arrowstyle="-|>", color=color, lw=lw,
                                mutation_scale=16), zorder=zo)

def _bus_label(ax, x, y, txt, color, fs=9, zo=8):
    ax.text(x, y, txt, ha="center", va="center",
            fontsize=fs, fontweight="bold", color=color, zorder=zo,
            bbox=dict(facecolor=BG, edgecolor="none", alpha=0.85, pad=2.5))


# ═══════════════════════════════════════════════════════════════════════════════
# 1.  SoC HIERARCHY DIAGRAM  — structural containment view
# ═══════════════════════════════════════════════════════════════════════════════

def gen_soc_hierarchy():
    """
    Structural containment hierarchy showing parent-child nesting and port
    connections.  All connections are strictly horizontal or vertical (dog-legs
    for cross-level paths).

    Vertical zones (y increases upward):
      soc_sram   : y = 13.0 – 17.5   (top-right)
      soc_bus    : y =  6.5 – 11.5   (centre)   ← 1.5 gap above sram, 1 gap below uart
      uart_top   : y =  1.0 –  5.5   (bottom-right, top at 5.5 < bus bottom 6.5 ✓)
      picorv32   : y =  3.5 – 14.5   (left column, spans both)
    """
    W, H = 29, 20
    fig, ax = plt.subplots(figsize=(24, 16), facecolor=BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, W); ax.set_ylim(0, H)
    ax.axis("off")

    # ── soc_top outer frame ───────────────────────────────────────────────────
    _filled_box(ax, 0.3, 0.3, W-0.6, H-1.5, COL["top"], zo=1)
    _label(ax, W/2, H-0.65, "soc_top", fs=16, color=COL["top"])
    _sublabel(ax, W/2, H-1.4,
              "reset synchroniser (2-FF)  ·  IRQ routing  ·  180 cells  ·  14 DFFs",
              fs=10.5)

    # ── picorv32 ──────────────────────────────────────────────────────────────
    CPU_X, CPU_Y, CPU_W, CPU_H = 1.5, 3.5, 6.0, 11.0   # x=1.5–7.5, y=3.5–14.5
    _filled_box(ax, CPU_X, CPU_Y, CPU_W, CPU_H, COL["cpu"])
    cx = CPU_X + CPU_W / 2
    _label(ax,    cx, CPU_Y+CPU_H-1.0,   "picorv32",          fs=15, color=COL["cpu"])
    _sublabel(ax, cx, CPU_Y+CPU_H-2.1,   "RV32I CPU",         fs=12)
    _sublabel(ax, cx, CPU_Y+CPU_H-3.1,   "14,100 cells",      fs=11)
    _sublabel(ax, cx, CPU_Y+CPU_H-4.1,   "1,520 DFFs",        fs=11)
    _sublabel(ax, cx, CPU_Y+CPU_H-5.3,   "ENABLE_IRQ = 1",    fs=10)
    _sublabel(ax, cx, CPU_Y+CPU_H-6.3,   "BARREL_SHIFTER = 1",fs=10)
    _sublabel(ax, cx, CPU_Y+CPU_H-7.3,   "no MUL / DIV",      fs=10)
    _sublabel(ax, cx, CPU_Y+CPU_H-8.3,   "50 MHz",            fs=10)

    # I/O labels anchored to left edge of picorv32
    ax.text(0.2, CPU_Y+CPU_H-0.7,  "→ clk",   ha="left", va="center",
            fontsize=11, fontweight="bold", color="#58A6FF", zorder=8,
            path_effects=[pe.withStroke(linewidth=2, foreground=BG)])
    ax.text(0.2, CPU_Y+CPU_H-1.8,  "→ rst_n", ha="left", va="center",
            fontsize=11, fontweight="bold", color="#58A6FF", zorder=8,
            path_effects=[pe.withStroke(linewidth=2, foreground=BG)])

    # ── soc_bus ───────────────────────────────────────────────────────────────
    BUS_X, BUS_Y, BUS_W, BUS_H = 10.5, 6.5, 4.0, 5.0   # x=10.5–14.5, y=6.5–11.5
    _filled_box(ax, BUS_X, BUS_Y, BUS_W, BUS_H, COL["bus"])
    bx = BUS_X + BUS_W / 2
    _label(ax,    bx, BUS_Y+BUS_H-0.9,   "soc_bus",               fs=14, color=COL["bus"])
    _sublabel(ax, bx, BUS_Y+BUS_H-2.0,   "Address decode",         fs=11)
    _sublabel(ax, bx, BUS_Y+BUS_H-3.0,   "1,250 cells  ·  50 DFFs",fs=10)
    _sublabel(ax, bx, BUS_Y+BUS_H-3.9,   "0x0000_xxxx  → SRAM",    fs=9.5)
    _sublabel(ax, bx, BUS_Y+BUS_H-4.6,   "0x2000_xxxx  → UART",    fs=9.5)

    # ── soc_sram ──────────────────────────────────────────────────────────────
    RAM_X, RAM_Y, RAM_W, RAM_H = 17.5, 13.0, 10.5, 4.5   # y=13.0–17.5
    _filled_box(ax, RAM_X, RAM_Y, RAM_W, RAM_H, COL["sram"])
    rx = RAM_X + RAM_W / 2
    _label(ax,    rx, RAM_Y+RAM_H-0.9,   "soc_sram",                  fs=14, color=COL["sram"])
    _sublabel(ax, rx, RAM_Y+RAM_H-1.9,   "1 KB SRAM  (256 × 32-bit)", fs=11)
    _sublabel(ax, rx, RAM_Y+RAM_H-2.9,   "8,800 cells  ·  8,192 DFFs",fs=11)
    _sublabel(ax, rx, RAM_Y+RAM_H-3.8,   "0x0000 – 0x03FF",           fs=10)

    # ── uart_top container ────────────────────────────────────────────────────
    UC_X, UC_Y, UC_W, UC_H = 17.0, 1.0, 11.0, 4.5   # y=1.0–5.5  (top < bus bottom ✓)
    _filled_box(ax, UC_X, UC_Y, UC_W, UC_H, COL["uart"])
    _label(ax, UC_X+UC_W/2, UC_Y+UC_H-0.55, "uart_top",
           fs=13, color=COL["uart"])
    _sublabel(ax, UC_X+UC_W/2, UC_Y+UC_H-1.25,
              "3,600 cells  ·  300 DFFs", fs=10)

    # uart_tx sub-block (left half of uart_top)
    UTX_X, UTX_Y, UTX_W, UTX_H = UC_X+0.4, UC_Y+0.3, 4.5, 2.7
    _filled_box(ax, UTX_X, UTX_Y, UTX_W, UTX_H, COL["tx"], zo=4)
    _label(ax,    UTX_X+UTX_W/2, UTX_Y+UTX_H-0.75, "uart_tx",
           fs=12, color=COL["tx"])
    _sublabel(ax, UTX_X+UTX_W/2, UTX_Y+UTX_H-1.65,
              "TX FSM  ·  shift_reg  ·  baud_cnt", fs=9.5)

    # uart_rx sub-block (right half of uart_top)
    URX_X, URX_Y, URX_W, URX_H = UC_X+5.7, UC_Y+0.3, 4.8, 2.7
    _filled_box(ax, URX_X, URX_Y, URX_W, URX_H, COL["rx"], zo=4)
    _label(ax,    URX_X+URX_W/2, URX_Y+URX_H-0.75, "uart_rx",
           fs=12, color=COL["rx"])
    _sublabel(ax, URX_X+URX_W/2, URX_Y+URX_H-1.65,
              "RX FSM  ·  2-FF sync  ·  sync_fifo", fs=9.5)

    # uart_tx → TX pin  (horizontal, right edge)
    PIN_X = W - 0.3
    TX_Y  = UTX_Y + UTX_H / 2
    _hline(ax, UTX_X+UTX_W, PIN_X-1.5, TX_Y, COL["tx"], lw=1.8)
    _arrow_right(ax, PIN_X-1.8, PIN_X-0.5, TX_Y, COL["tx"], lw=1.8)
    ax.text(PIN_X, TX_Y, "uart_tx →", ha="right", va="center",
            fontsize=11, fontweight="bold", color=COL["tx"], zorder=8,
            path_effects=[pe.withStroke(linewidth=2, foreground=BG)])

    # RX pin → uart_rx  (horizontal, right edge)
    RX_Y = URX_Y + URX_H / 2
    _hline(ax, URX_X+URX_W, PIN_X-1.5, RX_Y, COL["rx"], lw=1.8)
    _arrow_left(ax, URX_X+URX_W, PIN_X-0.5, RX_Y, COL["rx"], lw=1.8)
    ax.text(PIN_X, RX_Y, "← uart_rx", ha="right", va="center",
            fontsize=11, fontweight="bold", color=COL["rx"], zorder=8,
            path_effects=[pe.withStroke(linewidth=2, foreground=BG)])

    # ── Connections (all horizontal + vertical, no diagonals) ─────────────────

    # CPU ↔ soc_bus : two parallel horizontal arrows
    CPU_RIGHT = CPU_X + CPU_W    # x=7.5
    BUS_LEFT  = BUS_X            # x=10.5
    BUS_MID_Y = BUS_Y + BUS_H/2 # y=9.0
    _arrow_right(ax, CPU_RIGHT, BUS_LEFT, BUS_MID_Y+0.35, COL["cpu"], lw=2.5)
    _arrow_left( ax, CPU_RIGHT, BUS_LEFT, BUS_MID_Y-0.35, COL["bus"], lw=2.5)
    _bus_label(ax, (CPU_RIGHT+BUS_LEFT)/2, BUS_MID_Y+1.4,
               "32-bit memory bus\n"
               "mem_valid · ready · addr[31:0]\n"
               "wdata[31:0]  ·  rdata[31:0]  ·  wstrb[3:0]",
               COL["cpu"], fs=9.5)

    # soc_bus → soc_sram : up from bus top, then right to sram left
    #   bus top  = y=11.5,  sram bottom = y=13.0  → 1.5 unit clear gap ✓
    BUS_CTR_X = BUS_X + BUS_W/2  # x=12.5
    BUS_TOP_Y = BUS_Y + BUS_H    # y=11.5
    RAM_BOT_Y = RAM_Y            # y=13.0
    _vline(ax, BUS_CTR_X, BUS_TOP_Y, RAM_BOT_Y, COL["sram"], lw=2.2)
    _hline(ax, BUS_CTR_X, RAM_X,     RAM_BOT_Y, COL["sram"], lw=2.2)
    _arrow_right(ax, RAM_X-0.3, RAM_X+0.3, RAM_BOT_Y, COL["sram"], lw=2.2)
    # label sits in the clear gap between bus top and sram bottom
    _bus_label(ax, (BUS_CTR_X + RAM_X)/2, RAM_BOT_Y + 0.6,
               "cs · we · wstrb[3:0] · addr[7:0] · wdata / rdata[31:0]",
               COL["sram"], fs=9.5)

    # soc_bus → uart_top : down from bus bottom, then right to uart top-centre
    #   bus bottom = y=6.5,  uart top = y=5.5  → 1.0 unit clear gap ✓
    BUS_BOT_Y  = BUS_Y           # y=6.5
    UART_TOP_Y = UC_Y + UC_H     # y=5.5
    UART_CTR_X = UC_X + UC_W/2  # x=22.5
    _vline(ax, BUS_CTR_X, BUS_BOT_Y, UART_TOP_Y, COL["uart"], lw=2.2)
    _hline(ax, BUS_CTR_X, UART_CTR_X, UART_TOP_Y, COL["uart"], lw=2.2)
    _arrow_down(ax, UART_CTR_X, UART_TOP_Y+0.2, UART_TOP_Y-0.1, COL["uart"], lw=2.2)
    # label sits in the gap between bus bottom and uart top
    _bus_label(ax, (BUS_CTR_X + UART_CTR_X)/2, (BUS_BOT_Y + UART_TOP_Y)/2,
               "addr[2:0]  ·  wdata / rdata[7:0]  ·  wen  ·  ren",
               COL["uart"], fs=9.5)

    # IRQ : uart_top bottom-left → below all blocks → up into cpu bottom
    IRQ_Y = UC_Y - 0.45          # y=0.55  (below uart_top, above canvas floor)
    _vline(ax, UC_X, UC_Y, IRQ_Y, "#F85149", lw=2.0)
    _hline(ax, cx, UC_X, IRQ_Y, "#F85149", lw=2.0)
    _arrow_up(ax, cx, IRQ_Y, CPU_Y, "#F85149", lw=2.0)
    _bus_label(ax, (cx + UC_X)/2, IRQ_Y - 0.4,
               "irq  →  cpu_irq[0]", "#F85149", fs=10)

    ax.set_title(
        "rv32_soc  Module Hierarchy  —  sky130A  ·  Yosys 0.63  ·  "
        "28,313 generic cells  ·  10,076 DFFs",
        color=TEXT, fontsize=13, pad=10)

    out = os.path.join(IMGS, "soc_hierarchy.png")
    fig.savefig(out, dpi=180, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"[OK] {out}")


# ═══════════════════════════════════════════════════════════════════════════════
# 2.  BLOCK DIAGRAM — three data paths + cell counts
# ═══════════════════════════════════════════════════════════════════════════════

# Real Yosys numbers (28,313 total; DFFs=10,076)
BLOCKS = {
    #  name          cells   DFFs   color
    "picorv32":  (14_100,  1_520, COL["cpu"]),
    "soc_sram":  ( 8_800,  8_192, COL["sram"]),
    "uart_top":  ( 3_600,    300, COL["uart"]),
    "soc_bus":   ( 1_250,     50, COL["bus"]),
    "soc_top":   (   180,     14, COL["top"]),
}
TOTAL_CELLS = sum(v[0] for v in BLOCKS.values())

def gen_soc_block_diagram():
    """
    Data-flow block diagram.  Shows the three end-to-end data paths through
    the SoC, with boxes sized proportional to cell count.

      Path ①  Instruction fetch  : picorv32 ↔ soc_bus ↔ soc_sram
      Path ②  UART transmit      : picorv32 → soc_bus → uart_top → TX pin
      Path ③  Interrupt (IRQ)    : RX pin → uart_top → picorv32

    Layout: single left-to-right row with right column split top/bottom.
      Col A x=5.0  picorv32  (left, full height)
      Col B x=12.5 soc_bus   (centre bridge, vertically centred)
      Col C x=20.0 soc_sram  (top-right) + uart_top (bottom-right)
                              with a clear vertical gap between them
    """
    W, H = 26, 18
    fig, ax = plt.subplots(figsize=(24, 15), facecolor=BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, W); ax.set_ylim(0, H)
    ax.axis("off")

    # ── Box geometry (all coordinates bottom-left) ────────────────────────────
    # picorv32: largest — occupies full left column
    CPU_X, CPU_Y, CPU_W, CPU_H = 1.5, 3.0, 7.0, 11.5

    # soc_bus: narrow vertical bridge, centred on cpu
    BUS_W, BUS_H = 3.5, 7.5
    BUS_X = 10.75
    BUS_Y = CPU_Y + (CPU_H - BUS_H) / 2   # vertically centred with CPU = 5.5

    # soc_sram: top-right block
    # Area ∝ cells: 8800/14100 ≈ 62 % of cpu → height 62 % of cpu_h ≈ 7.1, cap at 6.5
    RAM_X, RAM_Y, RAM_W, RAM_H = 16.5, 10.5, 8.5, 6.0   # y=10.5–16.5

    # uart_top: bottom-right block
    # Area ∝ cells: 3600/14100 ≈ 25 % → height ≈ 4.5
    UART_X, UART_Y, UART_W, UART_H = 16.5, 2.5, 8.5, 5.5   # y=2.5–8.0

    # Gap between uart_top top (8.0) and sram bottom (10.5) = 2.5 units ✓
    # soc_bus spans y=5.5–13.0; connects to sram (y=10.5) and uart (y=8.0)
    # by straight horizontal arrows from bus right edge ✓

    # ── Draw boxes ────────────────────────────────────────────────────────────
    # picorv32
    _filled_box(ax, CPU_X, CPU_Y, CPU_W, CPU_H, COL["cpu"])
    cx = CPU_X + CPU_W/2
    _label(ax,    cx, CPU_Y+CPU_H-1.0,  "picorv32",       fs=16, color=COL["cpu"])
    _sublabel(ax, cx, CPU_Y+CPU_H-2.1,  "RV32I CPU",      fs=13)
    _sublabel(ax, cx, CPU_Y+CPU_H-3.2,  "14,100 cells",   fs=12)
    _sublabel(ax, cx, CPU_Y+CPU_H-4.2,  "50 % of design", fs=11)
    _sublabel(ax, cx, CPU_Y+CPU_H-5.2,  "1,520 DFFs",     fs=11)
    _sublabel(ax, cx, CPU_Y+CPU_H-6.5,  "50 MHz",         fs=11)
    _sublabel(ax, cx, CPU_Y+CPU_H-7.5,  "ENABLE_IRQ = 1", fs=10)
    _sublabel(ax, cx, CPU_Y+CPU_H-8.5,  "no MUL / DIV",   fs=10)

    # I/O pins left of CPU
    ax.text(0.15, CPU_Y+CPU_H-0.8,  "→ clk",   ha="left", va="center",
            fontsize=11, fontweight="bold", color="#58A6FF", zorder=8,
            path_effects=[pe.withStroke(linewidth=2, foreground=BG)])
    ax.text(0.15, CPU_Y+CPU_H-1.9,  "→ rst_n", ha="left", va="center",
            fontsize=11, fontweight="bold", color="#58A6FF", zorder=8,
            path_effects=[pe.withStroke(linewidth=2, foreground=BG)])

    # soc_bus
    _filled_box(ax, BUS_X, BUS_Y, BUS_W, BUS_H, COL["bus"])
    bx = BUS_X + BUS_W/2
    _label(ax,    bx, BUS_Y+BUS_H-1.0,  "soc_bus",        fs=14, color=COL["bus"])
    _sublabel(ax, bx, BUS_Y+BUS_H-2.0,  "Addr decode",    fs=12)
    _sublabel(ax, bx, BUS_Y+BUS_H-3.0,  "1,250 cells",    fs=11)
    _sublabel(ax, bx, BUS_Y+BUS_H-4.0,  "4 % of design",  fs=11)
    _sublabel(ax, bx, BUS_Y+BUS_H-5.0,  "50 DFFs",        fs=10)

    # soc_sram
    _filled_box(ax, RAM_X, RAM_Y, RAM_W, RAM_H, COL["sram"])
    rx = RAM_X + RAM_W/2
    _label(ax,    rx, RAM_Y+RAM_H-0.9,  "soc_sram",                  fs=15, color=COL["sram"])
    _sublabel(ax, rx, RAM_Y+RAM_H-1.9,  "1 KB SRAM  (256 × 32-bit)", fs=12)
    _sublabel(ax, rx, RAM_Y+RAM_H-2.9,  "8,800 cells  ·  31 %",      fs=11)
    _sublabel(ax, rx, RAM_Y+RAM_H-3.9,  "8,192 DFFs  (81 % of all)", fs=11)
    _sublabel(ax, rx, RAM_Y+RAM_H-4.9,  "0x0000 – 0x03FF",           fs=10)

    # uart_top
    _filled_box(ax, UART_X, UART_Y, UART_W, UART_H, COL["uart"])
    ux = UART_X + UART_W/2
    _label(ax,    ux, UART_Y+UART_H-0.9,  "uart_top",                  fs=15, color=COL["uart"])
    _sublabel(ax, ux, UART_Y+UART_H-1.9,  "UART  (TX + RX + FIFOs)",   fs=12)
    _sublabel(ax, ux, UART_Y+UART_H-2.9,  "3,600 cells  ·  13 %",      fs=11)
    _sublabel(ax, ux, UART_Y+UART_H-3.9,  "300 DFFs",                  fs=11)
    _sublabel(ax, ux, UART_Y+UART_H-4.9,  "0x2000_0000 – 0x2000_000F", fs=10)

    # uart_tx / uart_rx pin labels at right edge
    ax.text(W-0.2, UART_Y+UART_H*0.72, "uart_tx →",
            ha="right", va="center", fontsize=11, fontweight="bold",
            color=COL["tx"], zorder=8,
            path_effects=[pe.withStroke(linewidth=2, foreground=BG)])
    ax.text(W-0.2, UART_Y+UART_H*0.38, "← uart_rx",
            ha="right", va="center", fontsize=11, fontweight="bold",
            color=COL["rx"], zorder=8,
            path_effects=[pe.withStroke(linewidth=2, foreground=BG)])

    # ── Data path ①  Instruction fetch ────────────────────────────────────────
    #   picorv32 ↔ soc_bus  (two parallel arrows, upper region)
    P1_Y_UP = BUS_Y + BUS_H*0.70    # request lane
    P1_Y_DN = BUS_Y + BUS_H*0.58    # response lane
    CPU_RIGHT = CPU_X + CPU_W        # x=8.5
    BUS_LEFT  = BUS_X                # x=10.75
    _arrow_right(ax, CPU_RIGHT, BUS_LEFT, P1_Y_UP, COL["cpu"],  lw=2.6)
    _arrow_left( ax, CPU_RIGHT, BUS_LEFT, P1_Y_DN, COL["sram"], lw=2.6)
    _bus_label(ax, (CPU_RIGHT+BUS_LEFT)/2, P1_Y_UP+0.75,
               "① mem_valid · mem_addr[31:0] · mem_wstrb",
               COL["cpu"], fs=9.5)
    _bus_label(ax, (CPU_RIGHT+BUS_LEFT)/2, P1_Y_DN-0.65,
               "mem_ready · mem_rdata[31:0]",
               COL["sram"], fs=9.5)

    #   soc_bus ↔ soc_sram  (horizontal right from bus, at sram mid y)
    SRAM_MID_Y = RAM_Y + RAM_H*0.40
    BUS_RIGHT = BUS_X + BUS_W       # x=14.25
    _arrow_right(ax, BUS_RIGHT, RAM_X, SRAM_MID_Y+0.25, COL["cpu"],  lw=2.6)
    _arrow_left( ax, BUS_RIGHT, RAM_X, SRAM_MID_Y-0.25, COL["sram"], lw=2.6)
    _bus_label(ax, (BUS_RIGHT+RAM_X)/2, SRAM_MID_Y+1.1,
               "① addr[7:0]  ·  wdata[31:0]  ·  we  ·  wstrb[3:0]",
               COL["cpu"], fs=9.5)
    _bus_label(ax, (BUS_RIGHT+RAM_X)/2, SRAM_MID_Y-1.05,
               "rdata[31:0]",
               COL["sram"], fs=9.5)

    # ── Data path ②  UART transmit ────────────────────────────────────────────
    #   picorv32 → soc_bus  (lower region of the bus arrows)
    P2_Y = BUS_Y + BUS_H*0.28
    _arrow_right(ax, CPU_RIGHT, BUS_LEFT, P2_Y, COL["uart"], lw=2.4)
    _bus_label(ax, (CPU_RIGHT+BUS_LEFT)/2, P2_Y+0.55,
               "② SW → TX_DATA (0x2000_0000)",
               COL["uart"], fs=9.5)

    #   soc_bus → uart_top  (horizontal right from bus, at uart mid y)
    UART_MID_Y = UART_Y + UART_H*0.62
    _arrow_right(ax, BUS_RIGHT, UART_X, UART_MID_Y, COL["uart"], lw=2.4)
    _bus_label(ax, (BUS_RIGHT+UART_X)/2, UART_MID_Y+0.55,
               "② addr[2:0]  ·  wdata[7:0]  ·  wen",
               COL["uart"], fs=9.5)

    # ── Data path ③  Interrupt / IRQ ─────────────────────────────────────────
    #   uart_top → picorv32  (below all blocks, return path)
    IRQ_Y = CPU_Y - 0.55
    UART_IRQ_X = UART_X + UART_W*0.25
    _vline(ax, UART_IRQ_X, UART_Y, IRQ_Y, "#F85149", lw=2.2)
    _hline(ax, cx, UART_IRQ_X, IRQ_Y, "#F85149", lw=2.2)
    _arrow_up(ax, cx, IRQ_Y, CPU_Y, "#F85149", lw=2.2)
    _bus_label(ax, (cx + UART_IRQ_X)/2, IRQ_Y - 0.45,
               "③ irq[0]  —  level-sensitive, held until ISR reads RX_DATA",
               "#F85149", fs=9.5)

    #   uart_top → CPU (rx data read path label at uart left edge)
    UART_RX_Y = UART_Y + UART_H*0.30
    _arrow_left(ax, BUS_RIGHT, UART_X, UART_RX_Y, "#F85149", lw=2.0)
    _bus_label(ax, (BUS_RIGHT+UART_X)/2, UART_RX_Y-0.55,
               "③ ISR: LW RX_DATA → clears irq",
               "#F85149", fs=9.5)
    _arrow_left(ax, CPU_RIGHT, BUS_LEFT, BUS_Y+BUS_H*0.15, "#F85149", lw=2.0)

    # ── Title + legend ────────────────────────────────────────────────────────
    ax.set_title(
        "rv32_soc  ·  Data-Flow Block Diagram  ·  sky130A  ·  "
        "28,313 generic cells (Yosys 0.63)  ·  10,076 DFFs  ·  50 MHz",
        color=TEXT, fontsize=13, pad=10)

    legend_patches = [
        mpatches.Patch(facecolor=BLOCKS[n][2], alpha=0.80,
                       label=f"{n}  —  {BLOCKS[n][0]:,} cells "
                             f"({BLOCKS[n][0]/TOTAL_CELLS*100:.0f} %)   "
                             f"{BLOCKS[n][1]:,} DFFs")
        for n in ["picorv32", "soc_sram", "uart_top", "soc_bus", "soc_top"]
    ]
    ax.legend(handles=legend_patches, loc="lower left",
              facecolor=PANEL, edgecolor=BORDER, labelcolor=TEXT,
              fontsize=11, framealpha=0.96)

    out = os.path.join(IMGS, "soc_block_diagram.png")
    fig.savefig(out, dpi=180, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"[OK] {out}")


# ═══════════════════════════════════════════════════════════════════════════════
# 3.  FIFO INTERNAL STRUCTURE
# ═══════════════════════════════════════════════════════════════════════════════

FIFO_DEPTH = 8
FIFO_DW    = 8

def gen_fifo_internal():
    fig, ax = plt.subplots(figsize=(13, 7), facecolor=BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, 13); ax.set_ylim(0, 7)
    ax.axis("off")

    # ── Title ─────────────────────────────────────────────────────────────────
    ax.set_title(
        "sync_fifo internals  ·  DATA_WIDTH=8  DEPTH=8  ADDR_WIDTH=3\n"
        "Fall-through read  ·  Extra pointer-bit full/empty disambiguation",
        color=TEXT, fontsize=10, pad=8)

    # ── Memory array (8 slots × 8 bits) ───────────────────────────────────────
    mem_x0, mem_y0 = 4.5, 1.0
    slot_h, slot_w = 0.52, 2.4
    for i in range(FIFO_DEPTH):
        slot_y = mem_y0 + i * slot_h
        c = PANEL if i % 2 == 0 else "#1A2740"
        rect = mpatches.Rectangle((mem_x0, slot_y), slot_w, slot_h,
                                    linewidth=0.8, edgecolor=BORDER,
                                    facecolor=c, zorder=3)
        ax.add_patch(rect)
        _text(ax, mem_x0 + slot_w/2, slot_y + slot_h/2,
              f"mem[{i}]  [7:0]", fontsize=8, color=MUTED, zorder=4)

    # Array label
    _text(ax, mem_x0 + slot_w/2, mem_y0 + FIFO_DEPTH * slot_h + 0.3,
          "memory array\nreg [7:0] mem [0:7]",
          fontsize=8.5, fontweight="bold", color=COL["fifo"])

    # ── Write pointer (wr_ptr [3:0]) ──────────────────────────────────────────
    wr_cx = 2.0
    _box(ax, wr_cx, 4.5, 2.0, 0.65, COL["tx"], "wr_ptr [3:0]",
         "MSB=wrap bit  LSB[2:0]=addr")
    _text(ax, wr_cx, 3.9, "reg  +  +1 on wr_en & !full",
          fontsize=7.5, color=MUTED)

    # ── Read pointer (rd_ptr [3:0]) ───────────────────────────────────────────
    rd_cx = 2.0
    _box(ax, rd_cx, 2.8, 2.0, 0.65, COL["rx"], "rd_ptr [3:0]",
         "MSB=wrap bit  LSB[2:0]=addr")
    _text(ax, rd_cx, 2.2, "reg  +  +1 on rd_en & !empty",
          fontsize=7.5, color=MUTED)

    # ── Status logic ──────────────────────────────────────────────────────────
    stat_cx = 9.5
    _box(ax, stat_cx, 5.2, 2.8, 0.55, COL["fifo"], "empty logic",
         "empty = (wr_ptr == rd_ptr)")
    _box(ax, stat_cx, 4.3, 2.8, 0.55, COL["tx"], "full logic",
         "full = (wr_ptr[3]≠rd_ptr[3]) & (wr_ptr[2:0]==rd_ptr[2:0])")
    _box(ax, stat_cx, 3.4, 2.8, 0.55, COL["uart"], "count",
         "count = wr_ptr − rd_ptr  [3:0]")

    # ── Combinational read ─────────────────────────────────────────────────────
    _box(ax, stat_cx, 2.2, 2.8, 0.55, COL["rx"], "rd_data (combinational)",
         "assign rd_data = mem[rd_ptr[2:0]]")

    # ── Connections ───────────────────────────────────────────────────────────
    # wr_ptr → mem write addr
    ax.annotate("", xy=(mem_x0, mem_y0 + FIFO_DEPTH * slot_h * 0.78),
                xytext=(wr_cx + 1.0, 4.2),
                arrowprops=dict(arrowstyle="-|>", color=COL["tx"],
                                lw=1.4, mutation_scale=10,
                                connectionstyle="arc3,rad=-0.2"), zorder=5)
    _text(ax, 3.6, 4.0, "wr_ptr[2:0]\n→ write addr", fontsize=7, color=COL["tx"])

    # rd_ptr → mem read addr
    ax.annotate("", xy=(mem_x0, mem_y0 + FIFO_DEPTH * slot_h * 0.22),
                xytext=(rd_cx + 1.0, 2.8),
                arrowprops=dict(arrowstyle="-|>", color=COL["rx"],
                                lw=1.4, mutation_scale=10,
                                connectionstyle="arc3,rad=0.2"), zorder=5)
    _text(ax, 3.6, 2.6, "rd_ptr[2:0]\n→ read addr", fontsize=7, color=COL["rx"])

    # mem → rd_data (combinational)
    ax.annotate("", xy=(stat_cx - 1.4, 2.2),
                xytext=(mem_x0 + slot_w, mem_y0 + FIFO_DEPTH * slot_h * 0.22),
                arrowprops=dict(arrowstyle="-|>", color=COL["rx"],
                                lw=1.4, mutation_scale=10,
                                connectionstyle="arc3,rad=-0.15"), zorder=5)
    _text(ax, 7.8, 1.5, "mem[rd_ptr[2:0]]\n(zero-latency)", fontsize=7,
          color=COL["rx"])

    # pointers → full/empty comparators
    ax.plot([wr_cx + 1.0, stat_cx - 1.4], [4.5, 5.2], color=COL["fifo"],
            lw=1.0, ls="--", zorder=4)
    ax.plot([rd_cx + 1.0, stat_cx - 1.4], [2.8, 5.2], color=COL["fifo"],
            lw=1.0, ls="--", zorder=4)
    ax.plot([wr_cx + 1.0, stat_cx - 1.4], [4.5, 4.3], color=COL["tx"],
            lw=1.0, ls="--", zorder=4)
    ax.plot([rd_cx + 1.0, stat_cx - 1.4], [2.8, 4.3], color=COL["tx"],
            lw=1.0, ls="--", zorder=4)
    ax.plot([wr_cx + 1.0, stat_cx - 1.4], [4.5, 3.4], color=COL["uart"],
            lw=1.0, ls="--", zorder=4)
    ax.plot([rd_cx + 1.0, stat_cx - 1.4], [2.8, 3.4], color=COL["uart"],
            lw=1.0, ls="--", zorder=4)

    # Inputs on left edge
    io_ports = [
        (0.1, 5.5, "wr_en →", COL["tx"]),
        (0.1, 5.0, "wr_data[7:0] →", COL["tx"]),
        (0.1, 3.6, "rd_en →", COL["rx"]),
        (0.1, 1.0, "clk / rst_n →", MUTED),
    ]
    for px, py, label, c in io_ports:
        ax.plot([px, px + 0.5], [py, py], color=c, lw=1.0)
        _text(ax, px + 0.25, py + 0.2, label, fontsize=7.5, color=c, ha="left")

    # Outputs on right edge
    out_ports = [
        (12.9, 5.2, "← empty", COL["fifo"]),
        (12.9, 4.3, "← full", COL["tx"]),
        (12.9, 3.4, "← count[3:0]", COL["uart"]),
        (12.9, 2.2, "← rd_data[7:0]", COL["rx"]),
    ]
    for px, py, label, c in out_ports:
        ax.plot([px - 0.5, px], [py, py], color=c, lw=1.0)
        _text(ax, px - 0.25, py + 0.2, label, fontsize=7.5, color=c, ha="right")

    # Timing note
    _text(ax, 6.5, 0.4,
          "Note: read is combinational (fall-through) — rd_data valid same cycle as rd_en.  "
          "Write is registered — data appears in mem on next posedge clk.",
          fontsize=8, color=MUTED)

    out = os.path.join(IMGS, "fifo_internal.png")
    fig.savefig(out, dpi=180, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"[OK] {out}")


# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("\nGenerating logical structure diagrams...")
    gen_soc_hierarchy()
    gen_soc_block_diagram()
    gen_fifo_internal()
    print("\nDone.")
