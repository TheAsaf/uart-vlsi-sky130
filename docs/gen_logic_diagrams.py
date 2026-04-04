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
# 1.  SoC HIERARCHY DIAGRAM  (redesigned — larger canvas, bigger text)
# ═══════════════════════════════════════════════════════════════════════════════

def gen_soc_hierarchy():
    # Coordinate space: 24 wide × 16 tall; figure 20×14 → plenty of px/unit
    W, H = 24, 16
    fig, ax = plt.subplots(figsize=(20, 14), facecolor=BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, W); ax.set_ylim(0, H)
    ax.axis("off")

    # ── helpers ───────────────────────────────────────────────────────────────
    def box(cx, cy, w, h, color, title, sub1="", sub2="", zo=3):
        r, g, b, _ = _rgba(color, 0.28)
        rect = FancyBboxPatch((cx - w/2, cy - h/2), w, h,
                               boxstyle="round,pad=0.04",
                               linewidth=2.2, edgecolor=color,
                               facecolor=(r, g, b, 0.32), zorder=zo)
        ax.add_patch(rect)
        lines = [(title, 13, "bold"), (sub1, 10.5, "normal"), (sub2, 10.5, "normal")]
        ys = [0.2, -0.55, -1.1] if sub2 else ([0.15, -0.52] if sub1 else [0])
        for (txt, fs, fw), dy in zip(lines, ys):
            if txt:
                ax.text(cx, cy + dy, txt, ha="center", va="center",
                        fontsize=fs, fontweight=fw,
                        color="white" if fw == "bold" else MUTED,
                        zorder=zo+1,
                        path_effects=[pe.withStroke(linewidth=1.8, foreground=BG)])

    def conn(x0, y0, x1, y1, color, label="", lw=2.2, rad=0.0, bidir=False):
        sty = "<|-|>" if bidir else "-|>"
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle=sty, color=color, lw=lw,
                                    mutation_scale=14,
                                    connectionstyle=f"arc3,rad={rad}"),
                    zorder=6)
        if label:
            mx, my = (x0+x1)/2, (y0+y1)/2
            ax.text(mx, my, label, ha="center", va="center",
                    fontsize=9.5, color=color, fontweight="bold",
                    zorder=7,
                    bbox=dict(facecolor=BG, edgecolor="none", alpha=0.85, pad=2))

    # ── soc_top outer frame ───────────────────────────────────────────────────
    outer = FancyBboxPatch((0.5, 0.5), W - 1.0, H - 2.5,
                            boxstyle="round,pad=0.05",
                            linewidth=2.5, edgecolor=COL["top"],
                            facecolor=_rgba(COL["top"], 0.04), zorder=1)
    ax.add_patch(outer)
    ax.text(W/2, H - 0.8, "soc_top",
            ha="center", fontsize=16, fontweight="bold",
            color=COL["top"], zorder=2,
            path_effects=[pe.withStroke(linewidth=2, foreground=BG)])
    ax.text(W/2, H - 1.35,
            "reset synchroniser (2-FF)  ·  IRQ routing  ·  180 generic cells  ·  14 DFFs",
            ha="center", fontsize=10.5, color=MUTED, zorder=2)

    # ── picorv32 (left column) ────────────────────────────────────────────────
    box(3.2, 7.5, 5.2, 12.0, COL["cpu"],
        "picorv32",
        "RV32I CPU  ·  14,100 cells  ·  1,520 DFFs",
        "ENABLE_IRQ · BARREL_SHIFTER · no MUL/DIV")

    # ── soc_bus (centre column) ───────────────────────────────────────────────
    box(9.2, 7.5, 3.6, 12.0, COL["bus"],
        "soc_bus",
        "Address decode  ·  1,250 cells",
        "SRAM: 0x0000–0x03FF  |  UART: 0x2000_000x")

    # ── soc_sram (top-right) ──────────────────────────────────────────────────
    box(17.2, 11.5, 5.8, 4.0, COL["sram"],
        "soc_sram",
        "1 KB SRAM  ·  8,800 cells  ·  8,192 DFFs",
        "256 × 32-bit · 0x0000–0x03FF")

    # ── uart_top container ────────────────────────────────────────────────────
    uc = FancyBboxPatch((13.5, 1.0), 9.5, 8.0,
                         boxstyle="round,pad=0.05",
                         linewidth=2.0, edgecolor=COL["uart"],
                         facecolor=_rgba(COL["uart"], 0.07), zorder=2)
    ax.add_patch(uc)
    ax.text(18.25, 8.75, "uart_top",
            ha="center", fontsize=14, fontweight="bold",
            color=COL["uart"], zorder=3,
            path_effects=[pe.withStroke(linewidth=2, foreground=BG)])
    ax.text(18.25, 8.2, "487 cells  ·  300 DFFs",
            ha="center", fontsize=10, color=MUTED, zorder=3)

    # uart_tx
    box(16.0, 6.0, 4.5, 3.2, COL["tx"],
        "uart_tx",
        "TX FSM  ·  5-state",
        "baud_cnt[15:0]  ·  shift_reg[7:0]")

    # sync_fifo [TX]
    box(16.0, 3.4, 4.5, 2.2, COL["fifo"],
        "sync_fifo [TX]",
        "8-deep  ·  fall-through read",
        "wr_ptr / rd_ptr [3:0]  (extra-bit scheme)")

    # uart_rx + sync_fifo[RX]
    box(20.6, 4.7, 3.8, 5.6, COL["rx"],
        "uart_rx",
        "RX FSM  ·  2-FF sync",
        "sync_fifo [RX]  8-deep")

    # ── I/O pins (left edge) ──────────────────────────────────────────────────
    pins = [
        (0.0, 9.8, "clk",      "in"),
        (0.0, 8.6, "rst_n",    "in"),
        (0.0, 3.8, "uart_rx",  "in"),
        (0.0, 2.4, "uart_tx",  "out"),
        (0.0, 1.2, "irq_out",  "out"),
    ]
    for px, py, pname, dir_ in pins:
        c = "#58A6FF" if dir_ == "in" else "#F85149"
        ax.plot([px, px + 0.5], [py, py], color=c, lw=2.0, zorder=5)
        sym = "▶" if dir_ == "in" else "◀"
        ax.text(px - 0.1, py, sym, ha="right", va="center",
                fontsize=9, color=c, zorder=6)
        ax.text(px - 0.5, py, pname, ha="right", va="center",
                fontsize=11, color=TEXT, fontweight="bold", zorder=6)

    # ── Connections ───────────────────────────────────────────────────────────
    # CPU ↔ soc_bus  (bidirectional 32-bit bus)
    conn(5.8, 7.8, 7.4, 7.8,
         COL["cpu"], bidir=True, lw=3.0,
         label="mem_valid / ready  ·  addr[31:0]  ·  wdata[31:0]  ·  rdata[31:0]  ·  wstrb[3:0]")

    # soc_bus → soc_sram
    conn(11.0, 10.5, 14.3, 11.5,
         COL["sram"], lw=2.4,
         label="cs / we / wstrb[3:0]  ·  addr[7:0]  ·  wdata / rdata[31:0]")

    # soc_bus → uart_top
    conn(11.0, 5.0, 13.5, 5.5,
         COL["uart"], lw=2.4,
         label="addr[2:0]  ·  wdata/rdata[7:0]  ·  wen / ren")

    # sync_fifo[TX] → uart_tx
    conn(16.0, 4.5, 16.0, 4.4,
         COL["tx"], lw=1.8,
         label="tx_data[7:0]  tx_start")

    # uart_tx → TX pin (right exit)
    ax.annotate("", xy=(24.0, 6.0), xytext=(18.25, 6.0),
                arrowprops=dict(arrowstyle="-|>", color=COL["tx"],
                                lw=2.2, mutation_scale=14), zorder=6)
    ax.text(23.5, 6.4, "uart_tx", ha="right", va="bottom",
            fontsize=11, fontweight="bold", color=COL["tx"], zorder=7)

    # uart_rx pin → uart_rx block (from right)
    ax.annotate("", xy=(22.5, 3.0), xytext=(24.0, 3.0),
                arrowprops=dict(arrowstyle="-|>", color=COL["rx"],
                                lw=2.2, mutation_scale=14), zorder=6)
    ax.text(23.5, 2.6, "uart_rx", ha="right", va="top",
            fontsize=11, fontweight="bold", color=COL["rx"], zorder=7)

    # uart_top → CPU irq (curved, below all blocks)
    ax.annotate("", xy=(3.2, 1.5), xytext=(14.0, 1.5),
                arrowprops=dict(arrowstyle="-|>", color=COL["rx"],
                                lw=2.0, mutation_scale=14,
                                connectionstyle="arc3,rad=0.15"), zorder=5)
    ax.text(8.6, 1.1, "irq  →  cpu_irq[0]",
            ha="center", fontsize=11, fontweight="bold",
            color=COL["rx"], zorder=6,
            bbox=dict(facecolor=BG, edgecolor=COL["rx"],
                      alpha=0.92, pad=3, linewidth=1.2,
                      boxstyle="round,pad=0.25"))

    # clk / rst_n dashed fan-out
    for cy in [7.5, 7.5, 11.5, 5.5]:
        ax.plot([0.5, 0.85], [cy, cy], color=SUBTLE, lw=0.9, ls="--", zorder=2)
    ax.plot([0.85, 0.85], [1.5, 12.5], color=SUBTLE, lw=0.9, ls="--", zorder=2)

    ax.set_title(
        "rv32_soc  Module Hierarchy  —  sky130A  ·  Yosys 0.63  ·  28,313 generic cells  ·  10,076 DFFs",
        color=TEXT, fontsize=13, pad=12,
        path_effects=[pe.withStroke(linewidth=2, foreground=BG)])

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
    W, H = 22, 14
    fig = plt.figure(figsize=(20, 13), facecolor=BG)
    ax = fig.add_axes([0.01, 0.04, 0.98, 0.90])
    ax.set_facecolor(BG)
    ax.set_xlim(0, W); ax.set_ylim(0, H)
    ax.axis("off")

    # Fixed positions — clear left / centre / right arrangement
    # CPU: left column; soc_bus: centre bridge; SRAM: top-right; uart_top: bottom-right
    positions = {
        "picorv32": (3.8, 7.0),
        "soc_bus":  (9.0, 7.0),
        "soc_sram": (16.0, 10.5),
        "uart_top": (16.0, 4.0),
        "soc_top":  (9.0, 12.5),
    }

    # Box size: area ∝ cells, constrained to reasonable min
    def box_dims(cells):
        s = 2.0 * math.sqrt(cells / TOTAL_CELLS) * 5.5
        s = max(s, 1.4)
        return s, max(s * 0.72, 1.0)

    drawn = {}
    for name, (cells, dffs, wires, color) in BLOCKS.items():
        cx, cy = positions[name]
        w, h = box_dims(cells)
        pct = cells / TOTAL_CELLS * 100

        r, g, b, _ = _rgba(color, 0.28)
        rect = FancyBboxPatch((cx - w/2, cy - h/2), w, h,
                               boxstyle="round,pad=0.03",
                               linewidth=2.2, edgecolor=color,
                               facecolor=(r, g, b, 0.30), zorder=3)
        ax.add_patch(rect)

        # Module name — large
        ax.text(cx, cy + h * 0.18, name,
                ha="center", va="center",
                fontsize=13, fontweight="bold", color="white", zorder=4,
                path_effects=[pe.withStroke(linewidth=2, foreground=BG)])

        # Stats below name
        stats_line1 = f"{cells:,} cells  ({pct:.0f} %)"
        stats_line2 = f"{dffs:,} DFFs  ·  {wires:,} wires"
        ax.text(cx, cy - h * 0.08, stats_line1,
                ha="center", va="center", fontsize=10, color=MUTED, zorder=4,
                path_effects=[pe.withStroke(linewidth=1.5, foreground=BG)])
        if h > 1.8:
            ax.text(cx, cy - h * 0.30, stats_line2,
                    ha="center", va="center", fontsize=9.5, color=SUBTLE, zorder=4,
                    path_effects=[pe.withStroke(linewidth=1.5, foreground=BG)])

        drawn[name] = (cx, cy, w, h)

    # ── Connections ───────────────────────────────────────────────────────────
    def arrow(x0, y0, x1, y1, color, label="", lw=2.2, rad=0.0, bidir=False):
        sty = "<|-|>" if bidir else "-|>"
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle=sty, color=color, lw=lw,
                                    mutation_scale=14,
                                    connectionstyle=f"arc3,rad={rad}"),
                    zorder=5)
        if label:
            mx, my = (x0+x1)/2 + 0.05, (y0+y1)/2 + 0.20
            ax.text(mx, my, label, ha="center", va="center",
                    fontsize=9.5, color=color, fontweight="bold", zorder=6,
                    bbox=dict(facecolor=BG, edgecolor="none", alpha=0.85, pad=2))

    cpu  = drawn["picorv32"]
    bus  = drawn["soc_bus"]
    sram = drawn["soc_sram"]
    uart = drawn["uart_top"]
    top  = drawn["soc_top"]

    # CPU ↔ soc_bus  (bidirectional, two parallel arrows for visual clarity)
    arrow(cpu[0]+cpu[2]/2, cpu[1]+0.2, bus[0]-bus[2]/2, bus[1]+0.2,
          COL["cpu"], lw=2.8, bidir=False)
    arrow(bus[0]-bus[2]/2, bus[1]-0.2, cpu[0]+cpu[2]/2, bus[1]-0.2,
          COL["bus"], lw=2.8, bidir=False)
    ax.text((cpu[0]+bus[0])/2, cpu[1]+0.75,
            "32-bit memory bus\nmem_valid / ready / addr[31:0] / wdata / rdata / wstrb[3:0]",
            ha="center", va="center", fontsize=10, color=COL["cpu"], zorder=6,
            bbox=dict(facecolor=BG, edgecolor=COL["cpu"], alpha=0.90,
                      pad=3, linewidth=1.0, boxstyle="round,pad=0.3"))

    # soc_bus → soc_sram
    arrow(bus[0]+bus[2]/2, bus[1]+0.3, sram[0]-sram[2]/2, sram[1],
          COL["sram"], lw=2.4, rad=-0.15,
          label="cs / we / wstrb[3:0]\naddr[7:0]  ·  wdata / rdata[31:0]")

    # soc_bus → uart_top
    arrow(bus[0]+bus[2]/2, bus[1]-0.3, uart[0]-uart[2]/2, uart[1],
          COL["uart"], lw=2.4, rad=0.15,
          label="addr[2:0]  ·  wdata/rdata[7:0]  ·  wen/ren")

    # uart_top → CPU  irq
    ax.annotate("", xy=(cpu[0], cpu[1]-cpu[3]/2+0.4),
                xytext=(uart[0]-uart[2]/2, uart[1]),
                arrowprops=dict(arrowstyle="-|>", color=COL["rx"],
                                lw=2.0, mutation_scale=14,
                                connectionstyle="arc3,rad=0.35"), zorder=5)
    ax.text(5.8, 2.2, "IRQ → cpu_irq[0]",
            ha="center", fontsize=11, fontweight="bold", color=COL["rx"], zorder=6,
            bbox=dict(facecolor=BG, edgecolor=COL["rx"],
                      alpha=0.92, pad=3, linewidth=1.2,
                      boxstyle="round,pad=0.3"))

    # soc_top → rst_n_sync distribute (dashed)
    for name in ["picorv32", "soc_bus", "soc_sram", "uart_top"]:
        dx, dy, dw, dh = drawn[name]
        ax.plot([top[0], dx], [top[1]-top[3]/2, dy+dh/2],
                color=COL["top"], lw=0.9, ls="--", alpha=0.6, zorder=3)
    ax.text(top[0]+1.0, top[1]-top[3]/2-0.5, "rst_n_sync",
            fontsize=9.5, color=COL["top"], ha="center", style="italic", zorder=5)

    # I/O labels
    ax.text(0.3, 7.0, "clk\nrst_n", ha="left", va="center",
            fontsize=11, color="#58A6FF", fontweight="bold", zorder=5)
    ax.text(0.3, 2.8, "uart_rx →\n← uart_tx\n← irq_out",
            ha="left", va="center", fontsize=11, color="#F85149",
            fontweight="bold", zorder=5)

    # ── Title + legend ────────────────────────────────────────────────────────
    ax.set_title(
        "rv32_soc  Block Diagram  ·  sky130A  ·  "
        "28,313 generic cells  (Yosys 0.63)  ·  10,076 DFFs  ·  50 MHz  ·  "
        "Box area ∝ cell count",
        color=TEXT, fontsize=12, pad=10,
        path_effects=[pe.withStroke(linewidth=2, foreground=BG)])

    legend_patches = [
        mpatches.Patch(facecolor=BLOCKS[n][3], alpha=0.7,
                       label=f"{n}  —  {BLOCKS[n][0]:,} cells  ({BLOCKS[n][0]/TOTAL_CELLS*100:.0f} %)")
        for n in ["picorv32", "soc_sram", "uart_top", "soc_bus", "soc_top"]
    ]
    ax.legend(handles=legend_patches, loc="lower right",
              facecolor=PANEL, edgecolor=BORDER, labelcolor=TEXT,
              fontsize=10.5, framealpha=0.95)

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
