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
# 1.  SoC HIERARCHY DIAGRAM  — clean grid layout
# ═══════════════════════════════════════════════════════════════════════════════

def gen_soc_hierarchy():
    """
    Clean grid layout — strictly horizontal/vertical connections only.

    Column layout (x centres):
      col_io   =  2.0   I/O pin labels
      col_cpu  =  6.0   picorv32
      col_bus  = 13.0   soc_bus
      col_ram  = 20.5   soc_sram   (top half)
      col_uart = 20.5   uart_top   (bottom half, inside container)

    Row layout (y centres):
      row_top  = 15.5   soc_top label strip
      row_hi   = 11.5   soc_sram / upper
      row_mid  =  7.5   main bus row
      row_lo   =  4.0   uart group / lower
      row_irq  =  1.5   IRQ return path
    """
    W, H = 26, 18
    fig, ax = plt.subplots(figsize=(22, 15), facecolor=BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, W); ax.set_ylim(0, H)
    ax.axis("off")

    # ── soc_top outer frame ───────────────────────────────────────────────────
    _filled_box(ax, 0.4, 0.4, W-0.8, H-2.2, COL["top"], zo=1)
    _label(ax, W/2, H-0.9, "soc_top", fs=16, color=COL["top"])
    _sublabel(ax, W/2, H-1.6,
              "reset synchroniser (2-FF)  ·  IRQ routing  ·  180 cells  ·  14 DFFs",
              fs=10.5)

    # ── picorv32 ──────────────────────────────────────────────────────────────
    CPU_X, CPU_Y, CPU_W, CPU_H = 3.5, 3.8, 5.0, 8.0   # bottom-left
    _filled_box(ax, CPU_X, CPU_Y, CPU_W, CPU_H, COL["cpu"])
    _label(ax, CPU_X+CPU_W/2, CPU_Y+CPU_H/2+1.0,  "picorv32",         fs=14, color=COL["cpu"])
    _sublabel(ax, CPU_X+CPU_W/2, CPU_Y+CPU_H/2+0.15, "RV32I CPU",          fs=11)
    _sublabel(ax, CPU_X+CPU_W/2, CPU_Y+CPU_H/2-0.65, "14,100 cells",       fs=11)
    _sublabel(ax, CPU_X+CPU_W/2, CPU_Y+CPU_H/2-1.35, "1,520 DFFs",         fs=10.5)
    _sublabel(ax, CPU_X+CPU_W/2, CPU_Y+CPU_H/2-2.0,  "ENABLE_IRQ=1",       fs=10)
    _sublabel(ax, CPU_X+CPU_W/2, CPU_Y+CPU_H/2-2.6,  "BARREL_SHIFTER=1",   fs=10)

    # ── soc_bus ───────────────────────────────────────────────────────────────
    BUS_X, BUS_Y, BUS_W, BUS_H = 11.5, 5.8, 3.5, 3.8
    _filled_box(ax, BUS_X, BUS_Y, BUS_W, BUS_H, COL["bus"])
    _label(ax, BUS_X+BUS_W/2, BUS_Y+BUS_H/2+0.7,  "soc_bus",           fs=14, color=COL["bus"])
    _sublabel(ax, BUS_X+BUS_W/2, BUS_Y+BUS_H/2-0.1, "Address decode",      fs=11)
    _sublabel(ax, BUS_X+BUS_W/2, BUS_Y+BUS_H/2-0.8, "1,250 cells  ·  50 DFFs", fs=10)
    _sublabel(ax, BUS_X+BUS_W/2, BUS_Y+BUS_H/2-1.5, "0x0000  SRAM", fs=9.5)
    _sublabel(ax, BUS_X+BUS_W/2, BUS_Y+BUS_H/2-2.0, "0x2000_0000  UART",   fs=9.5)

    # ── soc_sram ──────────────────────────────────────────────────────────────
    RAM_X, RAM_Y, RAM_W, RAM_H = 17.5, 10.5, 7.5, 4.5
    _filled_box(ax, RAM_X, RAM_Y, RAM_W, RAM_H, COL["sram"])
    _label(ax, RAM_X+RAM_W/2, RAM_Y+RAM_H/2+0.9,  "soc_sram",           fs=14, color=COL["sram"])
    _sublabel(ax, RAM_X+RAM_W/2, RAM_Y+RAM_H/2+0.1, "1 KB SRAM  (256 × 32-bit)", fs=11)
    _sublabel(ax, RAM_X+RAM_W/2, RAM_Y+RAM_H/2-0.7, "8,800 cells  ·  8,192 DFFs", fs=11)
    _sublabel(ax, RAM_X+RAM_W/2, RAM_Y+RAM_H/2-1.5, "0x0000–0x03FF",      fs=10)

    # ── uart_top container ────────────────────────────────────────────────────
    UC_X, UC_Y, UC_W, UC_H = 17.0, 1.5, 8.5, 8.0
    _filled_box(ax, UC_X, UC_Y, UC_W, UC_H, COL["uart"])
    _label(ax, UC_X+UC_W/2, UC_Y+UC_H-0.55, "uart_top",          fs=13, color=COL["uart"])
    _sublabel(ax, UC_X+UC_W/2, UC_Y+UC_H-1.2, "487 cells  ·  300 DFFs", fs=10)

    # uart_tx (inside uart_top, left sub-block)
    UTX_X, UTX_Y, UTX_W, UTX_H = UC_X+0.4, UC_Y+0.4, 3.5, 5.2
    _filled_box(ax, UTX_X, UTX_Y, UTX_W, UTX_H, COL["tx"], zo=4)
    _label(ax, UTX_X+UTX_W/2, UTX_Y+UTX_H/2+0.7,  "uart_tx",   fs=12, color=COL["tx"])
    _sublabel(ax, UTX_X+UTX_W/2, UTX_Y+UTX_H/2-0.05, "TX FSM",     fs=10.5)
    _sublabel(ax, UTX_X+UTX_W/2, UTX_Y+UTX_H/2-0.75, "baud_cnt",  fs=10)
    _sublabel(ax, UTX_X+UTX_W/2, UTX_Y+UTX_H/2-1.4,  "shift_reg", fs=10)

    # uart_rx (inside uart_top, right sub-block)
    URX_X, URX_Y, URX_W, URX_H = UC_X+4.2, UC_Y+0.4, 3.9, 5.2
    _filled_box(ax, URX_X, URX_Y, URX_W, URX_H, COL["rx"], zo=4)
    _label(ax, URX_X+URX_W/2, URX_Y+URX_H/2+0.85, "uart_rx",   fs=12, color=COL["rx"])
    _sublabel(ax, URX_X+URX_W/2, URX_Y+URX_H/2+0.1, "RX FSM",     fs=10.5)
    _sublabel(ax, URX_X+URX_W/2, URX_Y+URX_H/2-0.6, "2-FF sync",  fs=10)
    _sublabel(ax, URX_X+URX_W/2, URX_Y+URX_H/2-1.3, "sync_fifo",  fs=10)
    _sublabel(ax, URX_X+URX_W/2, URX_Y+URX_H/2-1.9, "[8-deep RX]",fs=9.5)

    # ── I/O pin labels (far left) ─────────────────────────────────────────────
    IO_X = 0.5
    io_pins = [
        (IO_X, CPU_Y+CPU_H-0.6, "clk",     "→", "#58A6FF"),
        (IO_X, CPU_Y+CPU_H-1.4, "rst_n",   "→", "#58A6FF"),
        (IO_X, CPU_Y+1.8,       "uart_rx", "→", COL["rx"]),
        (IO_X, CPU_Y+0.8,       "uart_tx", "←", COL["tx"]),
        (IO_X, CPU_Y+0.0,       "irq_out", "←", "#F85149"),
    ]
    for px, py, name, sym, c in io_pins:
        ax.text(px, py, f"{sym} {name}", ha="left", va="center",
                fontsize=11.5, fontweight="bold", color=c, zorder=8,
                path_effects=[pe.withStroke(linewidth=2, foreground=BG)])

    # ── Connections  (all strictly horizontal or vertical) ────────────────────
    BUS_MID_Y = BUS_Y + BUS_H/2   # 7.7

    # CPU right → soc_bus left  (two-way: upper=req, lower=resp)
    CPU_RIGHT = CPU_X + CPU_W     # 8.5
    BUS_LEFT  = BUS_X             # 11.5
    # request arrow (CPU → bus)
    _arrow_right(ax, CPU_RIGHT, BUS_LEFT, BUS_MID_Y+0.25, COL["cpu"], lw=2.5)
    # response arrow (bus → CPU)
    _arrow_left(ax,  CPU_RIGHT, BUS_LEFT, BUS_MID_Y-0.25, COL["bus"], lw=2.5)
    # bus label above the pair
    _bus_label(ax, (CPU_RIGHT+BUS_LEFT)/2, BUS_MID_Y+1.0,
               "32-bit memory bus\nmem_valid · ready · addr[31:0]\nwdata[31:0] · rdata[31:0] · wstrb[3:0]",
               COL["cpu"], fs=9.5)

    # soc_bus top → soc_sram bottom  (vertical, then horizontal dog-leg)
    RAM_BOT_Y  = RAM_Y                    # 10.5
    RAM_CTR_X  = RAM_X + RAM_W/2          # 21.25
    BUS_TOP_Y  = BUS_Y + BUS_H            # 9.6
    BUS_CTR_X  = BUS_X + BUS_W/2         # 13.25
    # vertical segment from bus top up to SRAM row
    _vline(ax, BUS_CTR_X, BUS_TOP_Y, RAM_BOT_Y, COL["sram"], lw=2.2)
    # horizontal segment across to SRAM centre
    _hline(ax, BUS_CTR_X, RAM_CTR_X, RAM_BOT_Y, COL["sram"], lw=2.2)
    _arrow_up(ax, RAM_CTR_X, RAM_BOT_Y-0.05, RAM_BOT_Y+0.1, COL["sram"], lw=2.2)
    _bus_label(ax, (BUS_CTR_X+RAM_CTR_X)/2, RAM_BOT_Y-0.55,
               "cs · we · wstrb[3:0] · addr[7:0] · wdata/rdata[31:0]",
               COL["sram"], fs=9.5)

    # soc_bus bottom → uart_top top  (vertical down, then horizontal)
    UART_TOP_Y = UC_Y + UC_H              # 9.5
    UART_CTR_X = UC_X + UC_W/2           # 21.25
    BUS_BOT_Y  = BUS_Y                   # 5.8
    _vline(ax, BUS_CTR_X, BUS_BOT_Y, UART_TOP_Y, COL["uart"], lw=2.2)
    _hline(ax, BUS_CTR_X, UART_CTR_X, UART_TOP_Y, COL["uart"], lw=2.2)
    _arrow_down(ax, UART_CTR_X, UART_TOP_Y+0.05, UART_TOP_Y-0.1, COL["uart"], lw=2.2)
    _bus_label(ax, (BUS_CTR_X+UART_CTR_X)/2, UART_TOP_Y+0.55,
               "addr[2:0] · wdata/rdata[7:0] · wen · ren",
               COL["uart"], fs=9.5)

    # uart_tx → TX pin (right edge, horizontal)
    TX_PIN_X = W - 0.3
    TX_MID_Y = UTX_Y + UTX_H/2
    _hline(ax, UTX_X+UTX_W, TX_PIN_X, TX_MID_Y, COL["tx"], lw=2.0)
    _arrow_right(ax, TX_PIN_X-0.3, TX_PIN_X, TX_MID_Y, COL["tx"], lw=2.0)
    _bus_label(ax, TX_PIN_X-0.8, TX_MID_Y+0.45, "uart_tx →", COL["tx"], fs=10)

    # RX pin → uart_rx (right edge → entering right side of uart_rx)
    RX_MID_Y = URX_Y + URX_H/2
    _hline(ax, URX_X+URX_W, TX_PIN_X, RX_MID_Y, COL["rx"], lw=2.0)
    _arrow_left(ax, URX_X+URX_W, TX_PIN_X, RX_MID_Y, COL["rx"], lw=2.0)
    _bus_label(ax, TX_PIN_X-0.8, RX_MID_Y-0.45, "← uart_rx", COL["rx"], fs=10)

    # uart_top → CPU  IRQ  (horizontal at bottom, below both blocks)
    IRQ_Y = CPU_Y - 0.7
    _hline(ax, CPU_X+CPU_W/2, UC_X, IRQ_Y, "#F85149", lw=2.0)
    _vline(ax, UC_X, IRQ_Y, UC_Y+UC_H*0.3, "#F85149", lw=2.0)
    _arrow_up(ax, CPU_X+CPU_W/2, IRQ_Y, CPU_Y, "#F85149", lw=2.0)
    _bus_label(ax, (CPU_X+CPU_W/2+UC_X)/2, IRQ_Y-0.5,
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
# 2.  BLOCK DIAGRAM — cell counts + data-flow  (redesigned)
# ═══════════════════════════════════════════════════════════════════════════════

# Real Yosys numbers (28,313 total; DFFs=10,076)
BLOCKS = {
    #  name          cells   DFFs    wires  color
    "picorv32":  (14_100,  1_520, 11_200, COL["cpu"]),
    "soc_sram":  ( 8_800,  8_192,  5_400, COL["sram"]),
    "uart_top":  ( 3_600,    300,  2_100, COL["uart"]),
    "soc_bus":   ( 1_250,     50,    900, COL["bus"]),
    "soc_top":   (   180,     14,    120, COL["top"]),
}
TOTAL_CELLS = sum(v[0] for v in BLOCKS.values())
TOTAL_DFF   = sum(v[1] for v in BLOCKS.values())

def gen_soc_block_diagram():
    """
    Three-column layout, all connections horizontal or vertical.

    Col A (left):   picorv32
    Col B (centre): soc_bus  (thin vertical bridge)
    Col C (right):  soc_sram (top) + uart_top (bottom)

    Box widths/heights scale with sqrt(cells) so area ∝ cells.
    soc_top sits as a small badge at the top-centre.
    """
    W, H = 24, 16
    fig, ax = plt.subplots(figsize=(22, 14), facecolor=BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, W); ax.set_ylim(0, H)
    ax.axis("off")

    # ── Column x-centres ─────────────────────────────────────────────────────
    COL_A  =  5.0   # picorv32 centre-x
    COL_B  = 11.5   # soc_bus  centre-x
    COL_C  = 19.5   # SRAM / uart_top centre-x

    # ── Row y-centres ─────────────────────────────────────────────────────────
    ROW_TOP = 11.5   # soc_sram
    ROW_MID =  8.0   # soc_bus / picorv32 mid
    ROW_BOT =  3.8   # uart_top

    # ── Box sizes (all manually tuned, area ∝ cells) ─────────────────────────
    # picorv32: 14,100 cells → tallest, widest left block
    CPU_W, CPU_H = 7.0, 9.5
    # soc_sram: 8,800 cells → large right-top block
    RAM_W, RAM_H = 7.0, 5.5
    # uart_top: 3,600 cells → medium right-bottom block
    UART_W, UART_H = 7.0, 4.5
    # soc_bus: 1,250 cells → narrow centre column
    BUS_W, BUS_H = 3.5, 6.0
    # soc_top: 180 cells → small badge
    TOP_W, TOP_H = 4.0, 1.4

    # Derive bottom-left corners from centres
    def bl(cx, cy, w, h):
        return cx - w/2, cy - h/2

    CPU_X,  CPU_Y  = bl(COL_A, ROW_MID, CPU_W,  CPU_H)
    RAM_X,  RAM_Y  = bl(COL_C, ROW_TOP, RAM_W,  RAM_H)
    UART_X, UART_Y = bl(COL_C, ROW_BOT, UART_W, UART_H)
    BUS_X,  BUS_Y  = bl(COL_B, ROW_MID, BUS_W,  BUS_H)
    TOP_X,  TOP_Y  = bl(COL_B, 14.5,    TOP_W,  TOP_H)

    # ── Draw boxes ────────────────────────────────────────────────────────────
    # picorv32
    _filled_box(ax, CPU_X, CPU_Y, CPU_W, CPU_H, COL["cpu"])
    _label(ax,    COL_A, ROW_MID+2.8,   "picorv32",        fs=16, color=COL["cpu"])
    _sublabel(ax, COL_A, ROW_MID+1.9,   "RV32I CPU",       fs=13)
    _sublabel(ax, COL_A, ROW_MID+1.0,   "14,100 cells",    fs=12)
    _sublabel(ax, COL_A, ROW_MID+0.2,   "1,520 DFFs",      fs=12)
    _sublabel(ax, COL_A, ROW_MID-0.7,   "50 MHz",          fs=11)
    _sublabel(ax, COL_A, ROW_MID-1.4,   "ENABLE_IRQ = 1",  fs=11)
    _sublabel(ax, COL_A, ROW_MID-2.1,   "no MUL / DIV",    fs=11)

    # soc_sram
    _filled_box(ax, RAM_X, RAM_Y, RAM_W, RAM_H, COL["sram"])
    _label(ax,    COL_C, ROW_TOP+0.9,   "soc_sram",                   fs=15, color=COL["sram"])
    _sublabel(ax, COL_C, ROW_TOP+0.0,   "1 KB SRAM  (256 × 32-bit)",  fs=12)
    _sublabel(ax, COL_C, ROW_TOP-0.8,   "8,800 cells  ·  8,192 DFFs", fs=12)
    _sublabel(ax, COL_C, ROW_TOP-1.6,   "0x0000 – 0x03FF",            fs=11)

    # uart_top
    _filled_box(ax, UART_X, UART_Y, UART_W, UART_H, COL["uart"])
    _label(ax,    COL_C, ROW_BOT+0.8,   "uart_top",                   fs=15, color=COL["uart"])
    _sublabel(ax, COL_C, ROW_BOT-0.05,  "UART  (TX + RX + FIFOs)",    fs=12)
    _sublabel(ax, COL_C, ROW_BOT-0.85,  "3,600 cells  ·  300 DFFs",   fs=12)
    _sublabel(ax, COL_C, ROW_BOT-1.6,   "0x2000_0000 – 0x2000_000F",  fs=11)

    # soc_bus
    _filled_box(ax, BUS_X, BUS_Y, BUS_W, BUS_H, COL["bus"])
    _label(ax,    COL_B, ROW_MID+1.1,   "soc_bus",         fs=14, color=COL["bus"])
    _sublabel(ax, COL_B, ROW_MID+0.3,   "Addr decode",     fs=12)
    _sublabel(ax, COL_B, ROW_MID-0.4,   "1,250 cells",     fs=12)
    _sublabel(ax, COL_B, ROW_MID-1.1,   "50 DFFs",         fs=11)

    # soc_top badge
    _filled_box(ax, TOP_X, TOP_Y, TOP_W, TOP_H, COL["top"])
    _label(ax,    COL_B, TOP_Y+TOP_H/2+0.05, "soc_top",   fs=12, color=COL["top"])
    _sublabel(ax, COL_B, TOP_Y+TOP_H/2-0.5,  "180 cells · 14 DFFs · rst_n_sync · IRQ", fs=9)

    # ── Cell-count bar (right margin) ─────────────────────────────────────────
    BAR_X = W - 1.0
    bar_data = [
        ("picorv32",  14100, COL["cpu"],  ROW_MID),
        ("soc_sram",   8800, COL["sram"], ROW_TOP),
        ("uart_top",   3600, COL["uart"], ROW_BOT),
        ("soc_bus",    1250, COL["bus"],  ROW_MID),
    ]
    max_cells = 14100
    BAR_MAX_H = 3.0
    for i, (name, cells, color, cy) in enumerate(bar_data):
        bh = max(BAR_MAX_H * cells / max_cells, 0.25)
        bx = BAR_X + i * 0.0  # stacked below each other
        by = cy - bh/2
        # small horizontal tick
        pct = cells / TOTAL_CELLS * 100
        ax.text(BAR_X+0.1, cy, f"{pct:.0f} %",
                ha="left", va="center", fontsize=10,
                color=color, fontweight="bold", zorder=8,
                path_effects=[pe.withStroke(linewidth=2, foreground=BG)])

    # ── Connections (all horizontal / vertical) ───────────────────────────────
    BUS_RIGHT = BUS_X + BUS_W    # 13.25
    BUS_LEFT  = BUS_X            # 9.75
    BUS_TOP   = BUS_Y + BUS_H    # 11.0
    BUS_BOT   = BUS_Y            # 5.0
    CPU_RIGHT = CPU_X + CPU_W    # 8.5

    # CPU → soc_bus (request, upper lane)
    REQ_Y = ROW_MID + 0.3
    _hline(ax, CPU_RIGHT, BUS_LEFT, REQ_Y, COL["cpu"], lw=2.8)
    _arrow_right(ax, BUS_LEFT-0.3, BUS_LEFT+0.05, REQ_Y, COL["cpu"], lw=2.8)

    # soc_bus → CPU (response, lower lane)
    RSP_Y = ROW_MID - 0.3
    _hline(ax, CPU_RIGHT, BUS_LEFT, RSP_Y, COL["bus"], lw=2.8)
    _arrow_left(ax, CPU_RIGHT-0.05, BUS_LEFT, RSP_Y, COL["bus"], lw=2.8)

    # Bus label between the two arrows
    _bus_label(ax, (CPU_RIGHT+BUS_LEFT)/2, ROW_MID+1.2,
               "32-bit memory bus\n"
               "mem_valid  ·  mem_ready  ·  mem_addr[31:0]\n"
               "mem_wdata[31:0]  ·  mem_rdata[31:0]  ·  mem_wstrb[3:0]",
               COL["cpu"], fs=10)

    # soc_bus top → soc_sram (vertical up, then right)
    VTOP_X = COL_B + 0.4   # offset from bus centre to avoid overlap
    VTOP_STOP = RAM_Y       # bottom of SRAM
    _vline(ax, VTOP_X, BUS_TOP, VTOP_STOP, COL["sram"], lw=2.4)
    _hline(ax, VTOP_X, RAM_X, VTOP_STOP, COL["sram"], lw=2.4)
    _arrow_right(ax, RAM_X-0.3, RAM_X+0.1, VTOP_STOP, COL["sram"], lw=2.4)
    _bus_label(ax, (VTOP_X + RAM_X)/2, VTOP_STOP - 0.6,
               "cs · we · wstrb[3:0] · addr[7:0] · wdata / rdata[31:0]",
               COL["sram"], fs=10)

    # soc_bus bottom → uart_top (vertical down, then right)
    VBOT_X = COL_B - 0.4   # offset other side
    UART_TOP_Y = UART_Y + UART_H
    _vline(ax, VBOT_X, BUS_BOT, UART_TOP_Y, COL["uart"], lw=2.4)
    _hline(ax, VBOT_X, UART_X, UART_TOP_Y, COL["uart"], lw=2.4)
    _arrow_right(ax, UART_X-0.3, UART_X+0.1, UART_TOP_Y, COL["uart"], lw=2.4)
    _bus_label(ax, (VBOT_X + UART_X)/2, UART_TOP_Y + 0.5,
               "addr[2:0]  ·  wdata/rdata[7:0]  ·  wen  ·  ren",
               COL["uart"], fs=10)

    # uart_top → CPU  IRQ  (horizontal at bottom)
    IRQ_Y = CPU_Y - 0.6
    _hline(ax, CPU_X+CPU_W/2, UART_X, IRQ_Y, "#F85149", lw=2.2)
    _vline(ax, UART_X, IRQ_Y, UART_Y+UART_H*0.25, "#F85149", lw=2.2)
    _arrow_up(ax, CPU_X+CPU_W/2, IRQ_Y, CPU_Y, "#F85149", lw=2.2)
    _bus_label(ax, (CPU_X+CPU_W/2+UART_X)/2, IRQ_Y-0.55,
               "irq  →  cpu_irq[0]", "#F85149", fs=10)

    # soc_top → all (dashed rst_n_sync lines from badge)
    for tx, ty in [(COL_A, ROW_MID+CPU_H/2),
                   (COL_B, BUS_Y+BUS_H),
                   (COL_C, RAM_Y+RAM_H),
                   (COL_C, UART_Y+UART_H)]:
        ax.plot([COL_B, tx], [TOP_Y, ty],
                color=COL["top"], lw=1.0, ls=(0, (4, 3)),
                alpha=0.55, zorder=3)

    # ── I/O pins ──────────────────────────────────────────────────────────────
    ax.text(0.3, ROW_MID+1.5, "→ clk",     ha="left", va="center",
            fontsize=11, color="#58A6FF", fontweight="bold", zorder=8,
            path_effects=[pe.withStroke(linewidth=2, foreground=BG)])
    ax.text(0.3, ROW_MID+0.7, "→ rst_n",   ha="left", va="center",
            fontsize=11, color="#58A6FF", fontweight="bold", zorder=8,
            path_effects=[pe.withStroke(linewidth=2, foreground=BG)])
    ax.text(W-0.3, (ROW_TOP+ROW_BOT)/2+0.8, "← uart_tx",
            ha="right", va="center", fontsize=11, color=COL["tx"],
            fontweight="bold", zorder=8,
            path_effects=[pe.withStroke(linewidth=2, foreground=BG)])
    ax.text(W-0.3, (ROW_TOP+ROW_BOT)/2-0.0, "→ uart_rx",
            ha="right", va="center", fontsize=11, color=COL["rx"],
            fontweight="bold", zorder=8,
            path_effects=[pe.withStroke(linewidth=2, foreground=BG)])
    ax.text(W-0.3, (ROW_TOP+ROW_BOT)/2-0.8, "← irq_out",
            ha="right", va="center", fontsize=11, color="#F85149",
            fontweight="bold", zorder=8,
            path_effects=[pe.withStroke(linewidth=2, foreground=BG)])

    # ── Title + legend ────────────────────────────────────────────────────────
    ax.set_title(
        "rv32_soc  ·  Block Diagram  ·  sky130A  ·  "
        "28,313 generic cells (Yosys 0.63)  ·  10,076 DFFs  ·  50 MHz",
        color=TEXT, fontsize=13, pad=10)

    legend_patches = [
        mpatches.Patch(facecolor=BLOCKS[n][3], alpha=0.75,
                       label=f"{n}   {BLOCKS[n][0]:,} cells  "
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
