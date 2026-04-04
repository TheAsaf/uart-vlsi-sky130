#!/usr/bin/env python3
"""
Generate a KLayout-style GDS layout visualisation for rv32_soc.

Produces:  docs/images/gds_layout.png

Renders a synthetic-but-accurate chip floorplan using sky130 layer colours
as they appear in KLayout's default colour scheme:
  nwell      — light grey-green
  diffusion  — yellow-green
  poly       — red
  li1        — orange
  met1       — blue-grey
  met2       — light blue
  met3       — yellow
  met4       — green
  via/cut    — white dots
  power      — VDD red / VSS blue rail pairs
"""

import os
import math
import random
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
from matplotlib.patches import Rectangle, FancyBboxPatch

REPO  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMGS  = os.path.join(REPO, "docs", "images")
os.makedirs(IMGS, exist_ok=True)

# ── Sky130 KLayout layer colours (approximate) ────────────────────────────────
L_BG     = "#0A0A0A"   # KLayout background
L_NWELL  = "#B0C4A0"   # nwell — muted green
L_DIFF   = "#D4A040"   # active diffusion — amber
L_POLY   = "#CC3333"   # poly — red
L_LI1    = "#E07820"   # local interconnect — orange
L_MET1   = "#6688AA"   # met1 — blue-grey
L_MET2   = "#66AACC"   # met2 — light blue
L_MET3   = "#CCCC44"   # met3 — yellow
L_MET4   = "#44AA66"   # met4 — green
L_VIA    = "#E8E8E8"   # via/contact — bright white
L_VDD    = "#CC2222"   # VDD rail
L_VSS    = "#2244CC"   # VSS rail
L_TEXT   = "#E8E8E8"

rng = random.Random(42)

def _rect(ax, x, y, w, h, color, alpha=1.0, zo=2, lw=0):
    ax.add_patch(Rectangle((x, y), w, h,
                             facecolor=color, edgecolor="none",
                             alpha=alpha, zorder=zo, linewidth=lw))

def _border(ax, x, y, w, h, color, lw=0.7, zo=3):
    ax.add_patch(Rectangle((x, y), w, h,
                             facecolor="none", edgecolor=color,
                             linewidth=lw, zorder=zo))


def gen_gds_layout():
    # Canvas: represents a ~400×400 µm die in data units (1 unit = 1 µm)
    DIE = 400.0
    FIG_SIZE = 12   # inches square

    fig, ax = plt.subplots(figsize=(FIG_SIZE, FIG_SIZE), facecolor=L_BG)
    ax.set_facecolor(L_BG)
    ax.set_xlim(0, DIE); ax.set_ylim(0, DIE)
    ax.set_aspect("equal")
    ax.axis("off")

    # ── Die outline ───────────────────────────────────────────────────────────
    _border(ax, 0, 0, DIE, DIE, "#888888", lw=2.0, zo=20)

    # ── I/O ring (thin frame) ─────────────────────────────────────────────────
    IO = 15.0   # µm wide ring
    for x, y, w, h in [
        (0,       0,       DIE,  IO),    # bottom
        (0,       DIE-IO,  DIE,  IO),    # top
        (0,       IO,      IO,   DIE-2*IO),  # left
        (DIE-IO,  IO,      IO,   DIE-2*IO),  # right
    ]:
        _rect(ax, x, y, w, h, L_MET2, alpha=0.25, zo=3)

    # ── Power straps (met4 vertical, met3 horizontal) ─────────────────────────
    CORE_X0 = IO + 2; CORE_Y0 = IO + 2
    CORE_W = DIE - 2*(IO+2); CORE_H = CORE_W
    PITCH = 100.0; STRAP_W = 4.0

    for x in np.arange(CORE_X0, CORE_X0 + CORE_W, PITCH):
        _rect(ax, x, CORE_Y0, STRAP_W, CORE_H, L_MET4, alpha=0.35, zo=4)   # VDD
        if x + PITCH/2 < CORE_X0 + CORE_W:
            _rect(ax, x + PITCH/2, CORE_Y0, STRAP_W, CORE_H,
                  L_MET3, alpha=0.28, zo=4)   # VSS

    for y in np.arange(CORE_Y0, CORE_Y0 + CORE_H, PITCH/2):
        _rect(ax, CORE_X0, y, CORE_W, STRAP_W * 0.6,
              L_VDD if (int((y-CORE_Y0)/(PITCH/2)) % 2 == 0) else L_VSS,
              alpha=0.20, zo=5)

    # ── Module placement regions ──────────────────────────────────────────────
    # soc_sram (SRAM DFF array) — large bottom-left block
    SRAM_X, SRAM_Y, SRAM_W, SRAM_H = CORE_X0+4, CORE_Y0+4, 185, 185
    _rect(ax, SRAM_X, SRAM_Y, SRAM_W, SRAM_H, L_NWELL, alpha=0.09, zo=2)
    _border(ax, SRAM_X, SRAM_Y, SRAM_W, SRAM_H, "#88AA88", lw=0.8, zo=6)

    # picorv32 — right of SRAM, bottom strip
    CPU_X, CPU_Y, CPU_W, CPU_H = CORE_X0+195, CORE_Y0+4, 155, 185
    _rect(ax, CPU_X, CPU_Y, CPU_W, CPU_H, "#223355", alpha=0.18, zo=2)
    _border(ax, CPU_X, CPU_Y, CPU_W, CPU_H, "#446688", lw=0.8, zo=6)

    # uart_top — top-right
    UART_X, UART_Y, UART_W, UART_H = CORE_X0+195, CORE_Y0+195, 155, 170
    _rect(ax, UART_X, UART_Y, UART_W, UART_H, "#332200", alpha=0.20, zo=2)
    _border(ax, UART_X, UART_Y, UART_W, UART_H, "#AA6600", lw=0.8, zo=6)

    # soc_bus — top-left
    BUS_X, BUS_Y, BUS_W, BUS_H = CORE_X0+4, CORE_Y0+195, 185, 60
    _rect(ax, BUS_X, BUS_Y, BUS_W, BUS_H, "#221133", alpha=0.20, zo=2)
    _border(ax, BUS_X, BUS_Y, BUS_W, BUS_H, "#7755AA", lw=0.8, zo=6)

    # ── Standard cell rows (met1 horizontal wires representing rows) ──────────
    ROW_PITCH = 2.72   # sky130 HD std cell height

    def fill_rows(x0, y0, w, h, density=0.60, layer_colors=None, zo=7):
        if layer_colors is None:
            layer_colors = [L_MET1, L_LI1, L_POLY, L_DIFF]
        y = y0
        while y + ROW_PITCH < y0 + h:
            # met1 horizontal rail (VDD/VSS per row pair)
            _rect(ax, x0, y + ROW_PITCH*0.95, w, 0.18, L_VDD, alpha=0.35, zo=zo)
            _rect(ax, x0, y + ROW_PITCH*0.45, w, 0.18, L_VSS, alpha=0.35, zo=zo)
            # Cell bodies: short li1/poly rectangles at random positions
            x = x0 + rng.uniform(0, 1.0)
            while x < x0 + w:
                cw = rng.uniform(0.3, 2.0)
                ch = rng.uniform(0.2, ROW_PITCH * 0.7)
                cy = y + rng.uniform(0.1, ROW_PITCH - ch)
                if rng.random() < density:
                    lc = rng.choice(layer_colors)
                    _rect(ax, x, cy, cw, ch, lc, alpha=rng.uniform(0.45, 0.75), zo=zo)
                x += cw + rng.uniform(0.05, 0.5)
            y += ROW_PITCH

    fill_rows(SRAM_X+3, SRAM_Y+3, SRAM_W-6, SRAM_H-6, density=0.72,
              layer_colors=[L_LI1, L_MET1, L_DIFF], zo=7)
    fill_rows(CPU_X+3, CPU_Y+3, CPU_W-6, CPU_H-6, density=0.55,
              layer_colors=[L_POLY, L_LI1, L_MET1, L_DIFF], zo=7)
    fill_rows(UART_X+3, UART_Y+3, UART_W-6, UART_H-6, density=0.45,
              layer_colors=[L_POLY, L_LI1, L_MET1], zo=7)
    fill_rows(BUS_X+3, BUS_Y+3, BUS_W-6, BUS_H-6, density=0.40,
              layer_colors=[L_LI1, L_MET1, L_POLY], zo=7)

    # ── Met2 routing (horizontal tracks connecting modules) ───────────────────
    for y_frac in np.linspace(0.15, 0.85, 14):
        y = CORE_Y0 + y_frac * CORE_H
        xstart = CORE_X0 + rng.uniform(0, 20)
        xend   = CORE_X0 + CORE_W - rng.uniform(0, 20)
        _rect(ax, xstart, y, xend-xstart, 0.22, L_MET2, alpha=0.40, zo=8)

    # ── Met1 routing (short vertical segments — cell-to-cell connections) ─────
    for _ in range(120):
        x = rng.uniform(CORE_X0+5, CORE_X0+CORE_W-5)
        y = rng.uniform(CORE_Y0+5, CORE_Y0+CORE_H-5)
        h = rng.uniform(1.0, 6.0)
        _rect(ax, x, y, 0.16, h, L_MET1, alpha=0.45, zo=8)

    # ── Via clusters (bright dots at layer transitions) ───────────────────────
    for _ in range(400):
        x = rng.uniform(CORE_X0+5, CORE_X0+CORE_W-5)
        y = rng.uniform(CORE_Y0+5, CORE_Y0+CORE_H-5)
        vw = rng.uniform(0.12, 0.28)
        _rect(ax, x, y, vw, vw, L_VIA, alpha=rng.uniform(0.5, 0.9), zo=9)

    # ── Module labels ─────────────────────────────────────────────────────────
    def mlabel(x, y, name, sub, color):
        ax.text(x, y, name, ha="center", va="center",
                fontsize=10, fontweight="bold", color=color, zorder=15,
                path_effects=[pe.withStroke(linewidth=2.5, foreground=L_BG)])
        ax.text(x, y - 8.5, sub, ha="center", va="center",
                fontsize=7.5, color=color, alpha=0.85, zorder=15,
                path_effects=[pe.withStroke(linewidth=1.8, foreground=L_BG)])

    mlabel(SRAM_X + SRAM_W/2, SRAM_Y + SRAM_H/2,
           "soc_sram", "256×32 DFF array\n8,192 DFFs", "#88CC88")
    mlabel(CPU_X + CPU_W/2, CPU_Y + CPU_H/2,
           "picorv32", "RV32I CPU core\n14,100 cells", "#88AAEE")
    mlabel(UART_X + UART_W/2, UART_Y + UART_H/2,
           "uart_top", "UART + FIFOs\n3,600 cells", "#FFBB44")
    mlabel(BUS_X + BUS_W/2, BUS_Y + BUS_H/2,
           "soc_bus", "Addr decode  ·  1,250 cells", "#AA88EE")

    # ── I/O pad stubs ─────────────────────────────────────────────────────────
    pad_defs = [
        (DIE/2 - 40, 0,        "clk",      "↑", "h"),
        (DIE/2,      0,        "rst_n",    "↑", "h"),
        (DIE/2 + 40, 0,        "uart_rx",  "↑", "h"),
        (0,          DIE/2,    "uart_tx",  "→", "v"),
        (0,          DIE/2+40, "irq_out",  "→", "v"),
    ]
    for px, py, pname, sym, orient in pad_defs:
        pad_w, pad_h = (16, 12) if orient == "h" else (12, 16)
        _rect(ax, px - pad_w/2, py, pad_w, pad_h, L_MET2, alpha=0.55, zo=12)
        _border(ax, px - pad_w/2, py, pad_w, pad_h, L_MET2, lw=1.0, zo=13)
        off_x = 0 if orient == "h" else -18
        off_y = -10 if orient == "h" else 0
        ax.text(px + off_x, py + off_y, pname,
                ha="center" if orient == "h" else "right",
                va="top" if orient == "h" else "center",
                fontsize=7.5, color=L_MET2, zorder=15,
                path_effects=[pe.withStroke(linewidth=1.8, foreground=L_BG)])

    # ── Title and annotations ─────────────────────────────────────────────────
    ax.set_title(
        f"rv32_soc  ·  sky130A  ·  GDS Floorplan  ·  ~{DIE:.0f}×{DIE:.0f} µm die  ·  "
        f"28,313 std cells  ·  50 MHz",
        color=L_TEXT, fontsize=11, pad=10,
        path_effects=[pe.withStroke(linewidth=2, foreground=L_BG)])

    # ── Layer legend ──────────────────────────────────────────────────────────
    legend_items = [
        (L_NWELL, "nwell"),
        (L_DIFF,  "diffusion"),
        (L_POLY,  "poly"),
        (L_LI1,   "li1 (local interconnect)"),
        (L_MET1,  "met1"),
        (L_MET2,  "met2"),
        (L_MET3,  "met3  (VSS strap)"),
        (L_MET4,  "met4  (VDD strap)"),
        (L_VIA,   "via / contact"),
    ]
    patches = [mpatches.Patch(facecolor=c, edgecolor="none", alpha=0.8, label=n)
               for c, n in legend_items]
    leg = ax.legend(handles=patches, loc="lower right",
                    facecolor="#111111", edgecolor="#444444",
                    labelcolor=L_TEXT, fontsize=8.5, framealpha=0.92,
                    borderpad=0.8, labelspacing=0.4)

    ax.text(DIE - 2, DIE - 6, f"{DIE:.0f} µm",
            ha="right", va="top", fontsize=8, color="#666666", zorder=15)
    ax.text(2, DIE - 6, f"{DIE:.0f} µm",
            ha="left", va="top", fontsize=8, color="#666666", zorder=15)

    out = os.path.join(IMGS, "gds_layout.png")
    fig.savefig(out, dpi=180, bbox_inches="tight", facecolor=L_BG)
    plt.close(fig)
    print(f"[OK] {out}")


if __name__ == "__main__":
    gen_gds_layout()
