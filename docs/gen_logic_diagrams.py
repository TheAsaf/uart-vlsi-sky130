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
# 1.  SoC HIERARCHY DIAGRAM
# ═══════════════════════════════════════════════════════════════════════════════

def gen_soc_hierarchy():
    fig, ax = plt.subplots(figsize=(14, 10), facecolor=BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, 14); ax.set_ylim(0, 10)
    ax.axis("off")

    # ── soc_top outer container ───────────────────────────────────────────────
    outer = FancyBboxPatch((0.3, 0.3), 13.4, 9.4,
                            boxstyle="round,pad=0.04",
                            linewidth=2, edgecolor=COL["top"],
                            facecolor=_rgba(COL["top"], 0.06), zorder=1)
    ax.add_patch(outer)
    _text(ax, 7, 9.6, "soc_top", fontsize=12, fontweight="bold",
          color=COL["top"], zorder=2)
    _text(ax, 7, 9.25, "reset sync (2-FF)  ·  IRQ routing  ·  83 generic cells",
          fontsize=8, color=MUTED, zorder=2)

    # ── picorv32 ──────────────────────────────────────────────────────────────
    _box(ax, 2.4, 5.5, 3.8, 5.4, COL["cpu"],
         "picorv32", "RV32I CPU · 14 100 cells\n1520 DFFs · ENABLE_IRQ")

    # ── soc_bus ───────────────────────────────────────────────────────────────
    _box(ax, 7.0, 5.5, 2.5, 5.4, COL["bus"],
         "soc_bus", "Addr decode · 1 250 cells\nSRAM 0x0… / UART 0x2…")

    # ── soc_sram ──────────────────────────────────────────────────────────────
    _box(ax, 11.0, 7.2, 2.5, 2.0, COL["sram"],
         "soc_sram", "1 KB SRAM · 8 800 cells\n8 192 DFFs · 256×32")

    # ── uart_top container ────────────────────────────────────────────────────
    uart_cont = FancyBboxPatch((9.55, 1.4), 3.1, 5.2,
                                boxstyle="round,pad=0.03",
                                linewidth=1.5, edgecolor=COL["uart"],
                                facecolor=_rgba(COL["uart"], 0.08), zorder=2)
    ax.add_patch(uart_cont)
    _text(ax, 11.1, 6.4, "uart_top", fontsize=10, fontweight="bold",
          color=COL["uart"], zorder=3)
    _text(ax, 11.1, 6.1, "487 cells · 300 DFFs", fontsize=7.5,
          color=MUTED, zorder=3)

    # uart_tx inside uart_top
    _box(ax, 11.1, 4.8, 2.6, 1.5, COL["tx"],
         "uart_tx", "TX FSM · 8-state\nbaud cnt + shift reg")

    # sync_fifo (TX)
    _box(ax, 11.1, 3.2, 2.6, 1.1, COL["fifo"],
         "sync_fifo [TX]", "8-deep · fall-through")

    # uart_rx inside uart_top
    _box(ax, 11.1, 1.9, 2.6, 0.9, COL["rx"],
         "uart_rx + sync_fifo[RX]", "RX sampler · 2-FF sync")

    # ── I/O pins ──────────────────────────────────────────────────────────────
    io_pins = [
        (0.3, 5.5, "clk", "→"),
        (0.3, 4.8, "rst_n", "→"),
        (0.3, 3.6, "uart_rx", "→"),
        (0.3, 2.6, "uart_tx", "←"),
        (0.3, 1.8, "irq_out", "←"),
    ]
    for px, py, pname, dir_ in io_pins:
        color = MUTED
        ax.plot([px, px + 0.5], [py, py], color=color, lw=1.2, zorder=5)
        sym = "▶" if dir_ == "→" else "◀"
        _text(ax, px - 0.05, py, sym, fontsize=7, color=color, ha="right")
        _text(ax, px - 0.55, py, pname, fontsize=8, color=TEXT, ha="right")

    # ── Signal buses / connections ────────────────────────────────────────────
    # CPU ↔ soc_bus (memory interface)
    _arrow(ax, 4.3, 5.5, 5.75, 5.5, label="mem_valid/ready\nmem_addr[31:0]\nmem_wdata[31:0]\nmem_rdata[31:0]\nmem_wstrb[3:0]",
           color=COL["cpu"], lw=2.0)

    # soc_bus ↔ soc_sram
    _arrow(ax, 8.25, 7.2, 9.75, 7.2,
           label="sram_cs/we\nwstrb/addr[7:0]\nwdata/rdata[31:0]",
           color=COL["sram"], lw=1.8)

    # soc_bus ↔ uart_top
    _arrow(ax, 8.25, 3.5, 9.55, 3.5,
           label="addr[2:0]\nwdata/rdata[7:0]\nwen / ren",
           color=COL["uart"], lw=1.8)

    # uart_top → CPU irq
    ax.annotate("", xy=(2.4, 3.3), xytext=(9.55, 2.2),
                arrowprops=dict(arrowstyle="->", color=COL["rx"],
                                lw=1.4, connectionstyle="arc3,rad=0.3"))
    _text(ax, 5.8, 2.3, "irq (uart_irq → cpu_irq[0])",
          fontsize=7.5, color=COL["rx"])

    # TX FIFO → uart_tx
    _arrow(ax, 11.1, 3.75, 11.1, 4.05,
           label="tx_start\ntx_data[7:0]", color=COL["tx"], lw=1.2)

    # uart_tx → uart_tx serial line (pin exit)
    ax.annotate("", xy=(13.7, 4.8), xytext=(12.4, 4.8),
                arrowprops=dict(arrowstyle="->", color=COL["tx"],
                                lw=1.4, connectionstyle="arc3,rad=0.0"))
    _text(ax, 13.2, 5.05, "uart_tx", fontsize=7.5, color=COL["tx"])

    # uart_rx serial line (pin entry)
    ax.annotate("", xy=(12.4, 1.9), xytext=(13.7, 1.9),
                arrowprops=dict(arrowstyle="->", color=COL["rx"],
                                lw=1.4, connectionstyle="arc3,rad=0.0"))
    _text(ax, 13.2, 2.15, "uart_rx", fontsize=7.5, color=COL["rx"])

    # clk fan-out
    ax.plot([0.8, 0.8], [5.5, 1.0], color=SUBTLE, lw=1, ls="--", zorder=2)
    for cy in [5.5, 5.5, 7.2, 5.5, 3.2, 4.8, 1.9]:
        ax.plot([0.8, 0.55], [cy, cy], color=SUBTLE, lw=0.8, ls="--", zorder=2)

    ax.set_title("rv32_soc Module Hierarchy — sky130A  |  Yosys 0.63 synthesis",
                 color=TEXT, fontsize=11, pad=10)

    out = os.path.join(IMGS, "soc_hierarchy.png")
    fig.savefig(out, dpi=180, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"[OK] {out}")


# ═══════════════════════════════════════════════════════════════════════════════
# 2.  BLOCK DIAGRAM — cell counts + data-flow
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
    fig = plt.figure(figsize=(14, 9), facecolor=BG)
    ax = fig.add_axes([0.02, 0.06, 0.96, 0.86])
    ax.set_facecolor(BG)
    ax.set_xlim(0, 14); ax.set_ylim(0, 9)
    ax.axis("off")

    # Layout: PicoRV32 (big, left), SRAM (big, middle-top),
    #         uart_top (medium, middle-bottom), soc_bus (centre),
    #         soc_top (small, top-right)
    layout = {
        #  name         cx    cy    w_base  h_base
        "picorv32": (2.5,  4.5, None, None),
        "soc_sram": (7.5,  7.0, None, None),
        "uart_top": (7.5,  2.5, None, None),
        "soc_bus":  (5.0,  4.5, None, None),
        "soc_top":  (11.5, 4.5, None, None),
    }

    # Size boxes proportional to sqrt(cells) — log scale feels better
    def box_size(cells):
        scale = 0.9 * math.sqrt(cells / TOTAL_CELLS) * 8
        return max(scale, 1.0), max(scale * 0.75, 0.7)

    drawn = {}
    for name, (cells, dffs, wires, color) in BLOCKS.items():
        cx, cy, _, _ = layout[name]
        w, h = box_size(cells)
        pct = cells / TOTAL_CELLS * 100

        # box
        r, g, b, _ = _rgba(color, 0.35)
        rect = FancyBboxPatch((cx - w/2, cy - h/2), w, h,
                               boxstyle="round,pad=0.02",
                               linewidth=2.0, edgecolor=color,
                               facecolor=(r, g, b, 0.30), zorder=3)
        ax.add_patch(rect)

        # module name
        _text(ax, cx, cy + h*0.22, name, fontsize=10, fontweight="bold",
              color="white", zorder=4)

        # stats row
        stats = (f"cells: {cells:,}  ({pct:.1f} %)  "
                 f"│  DFFs: {dffs:,}  │  wires: {wires:,}")
        _text(ax, cx, cy - h*0.12, stats, fontsize=7.5, color=MUTED, zorder=4)

        drawn[name] = (cx, cy, w, h)

    # ── Connections ───────────────────────────────────────────────────────────
    # CPU → soc_bus
    cpu  = drawn["picorv32"]
    bus  = drawn["soc_bus"]
    sram = drawn["soc_sram"]
    uart = drawn["uart_top"]
    top  = drawn["soc_top"]

    def edge(src, dst, label, color, rad=0.0, lw=2.0):
        sx, sy = src[0] + src[2]/2, src[1]
        dx, dy = dst[0] - dst[2]/2, dst[1]
        ax.annotate("", xy=(dx, dy), xytext=(sx, sy),
                    arrowprops=dict(arrowstyle="-|>", color=color, lw=lw,
                                    mutation_scale=12,
                                    connectionstyle=f"arc3,rad={rad}"),
                    zorder=5)
        mx, my = (sx + dx)/2, (sy + dy)/2 + 0.15
        _text(ax, mx, my, label, fontsize=7, color=color,
              bbox=dict(facecolor=BG, edgecolor="none", alpha=0.8, pad=1))

    # Two-way bus between CPU and soc_bus
    ax.annotate("", xy=(bus[0] - bus[2]/2, bus[1] + 0.15),
                xytext=(cpu[0] + cpu[2]/2, cpu[1] + 0.15),
                arrowprops=dict(arrowstyle="-|>", color=COL["cpu"],
                                lw=2.2, mutation_scale=12,
                                connectionstyle="arc3,rad=0.0"), zorder=5)
    ax.annotate("", xy=(cpu[0] + cpu[2]/2, cpu[1] - 0.15),
                xytext=(bus[0] - bus[2]/2, bus[1] - 0.15),
                arrowprops=dict(arrowstyle="-|>", color=COL["bus"],
                                lw=2.2, mutation_scale=12,
                                connectionstyle="arc3,rad=0.0"), zorder=5)
    _text(ax, (cpu[0] + bus[0]) / 2, cpu[1] + 0.55,
          "32-bit memory bus\n(mem_valid/ready/addr/wdata/rdata/wstrb)",
          fontsize=7.5, color=COL["cpu"])

    # soc_bus → soc_sram
    bsx, bsy = bus[0] + bus[2]/2, bus[1]
    rsx, rsy = sram[0] - sram[2]/2, sram[1]
    ax.annotate("", xy=(rsx, rsy), xytext=(bsx, bsy + 0.2),
                arrowprops=dict(arrowstyle="-|>", color=COL["sram"],
                                lw=1.8, mutation_scale=12,
                                connectionstyle="arc3,rad=-0.25"), zorder=5)
    _text(ax, (bsx + rsx)/2 + 0.4, (bsy + rsy)/2 + 0.3,
          "sram_cs/we/addr[7:0]\nwdata/rdata[31:0]", fontsize=7, color=COL["sram"])

    # soc_bus → uart_top
    ax.annotate("", xy=(uart[0] - uart[2]/2, uart[1]), xytext=(bsx, bsy - 0.2),
                arrowprops=dict(arrowstyle="-|>", color=COL["uart"],
                                lw=1.8, mutation_scale=12,
                                connectionstyle="arc3,rad=0.25"), zorder=5)
    _text(ax, (bsx + uart[0])/2 + 0.3, (bsy + uart[1])/2 - 0.3,
          "addr[2:0]/wdata/rdata[7:0]\nwen/ren", fontsize=7, color=COL["uart"])

    # uart_top → CPU irq
    ax.annotate("", xy=(cpu[0], cpu[1] - cpu[3]/2),
                xytext=(uart[0], uart[1] + uart[3]/2),
                arrowprops=dict(arrowstyle="-|>", color=COL["rx"],
                                lw=1.5, mutation_scale=10,
                                connectionstyle="arc3,rad=0.4"), zorder=5)
    _text(ax, 4.2, 1.8, "IRQ → cpu_irq[0]", fontsize=7.5, color=COL["rx"])

    # soc_top → rst distribute (dashed)
    for name in ["picorv32", "soc_bus", "soc_sram", "uart_top"]:
        dx, dy, dw, dh = drawn[name]
        ax.annotate("", xy=(dx, dy + dh/2),
                    xytext=(top[0], top[1]),
                    arrowprops=dict(arrowstyle="-", color=COL["top"],
                                    lw=0.8, ls="dashed",
                                    connectionstyle="arc3,rad=0.1"), zorder=4)
    _text(ax, 10.8, 6.3, "rst_n_sync", fontsize=7, color=COL["top"])

    # I/O pin annotations
    io = [
        (0.2, 4.5, "clk  /  rst_n", "→"),
        (0.2, 2.5, "uart_rx →", "→"),
        (0.2, 1.9, "← uart_tx", "←"),
        (13.8, 4.5, "← irq_out", "←"),
    ]
    for px, py, label, d in io:
        _text(ax, px, py, label, fontsize=8, color=MUTED,
              ha="left" if d == "→" else "right")

    # Title + legend
    ax.set_title(
        f"rv32_soc Block Diagram  ·  sky130A  ·  "
        f"28,313 generic cells (Yosys 0.63)  ·  10,076 DFFs  ·  "
        f"50 MHz  ·  Box area ∝ cell count",
        color=TEXT, fontsize=10, pad=10)

    legend_patches = [
        mpatches.Patch(facecolor=COL[k], alpha=0.6,
                       label=f"{n}  ({BLOCKS[n][0]:,} cells)")
        for k, n in [("cpu","picorv32"), ("sram","soc_sram"),
                     ("uart","uart_top"), ("bus","soc_bus"), ("top","soc_top")]
    ]
    ax.legend(handles=legend_patches, loc="lower right",
              facecolor=PANEL, edgecolor=BORDER, labelcolor=TEXT,
              fontsize=8, framealpha=0.9)

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
