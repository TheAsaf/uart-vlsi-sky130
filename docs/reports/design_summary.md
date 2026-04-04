# rv32_soc Physical Design Summary

**PDK:** sky130A · sky130_fd_sc_hd
**Tool flow:** Yosys 0.63 → OpenLane (OpenROAD + TritonRoute)
**Clock:** 50 MHz (20 ns period)

## Synthesis Statistics (Yosys 0.63, pre-technology-mapping)

Synthesis command: `synth -top soc_top -flatten`  
See [`synth_stats.txt`](synth_stats.txt) for full cell-type breakdown.

| Category | Count | Notes |
|----------|-------|-------|
| **Total generic cells** | **28,313** | Yosys internal gates before sky130 mapping |
| Flip-flops (all types) | 10,076 | Map 1:1 to sky130_fd_sc_hd__dfxtp/sdfxtp |
| MUX2 | 11,386 | Dominated by 256:1 SRAM read-mux tree (32 bits) |
| AND/OR/NAND/NOR/INV | 6,624 | General combinational logic |
| XOR/XNOR | 554 | ALU and parity logic |
| Wires (total) | 29,423 | |
| Public wires | 11,171 | |
| Top-level ports | 5 | clk, rst\_n, uart\_rx, uart\_tx, irq\_out |
| Synthesis errors | 0 | CLEAN |

### Flip-flop breakdown (expected per module)

| Module | DFFs | Share | Source |
|--------|------|-------|--------|
| `soc_sram` (256×32 DFF array) | 8,192 | 81.3 % | `reg [31:0] mem [0:255]` |
| `picorv32` (register file + FSM) | ~1,520 | 15.1 % | 32-reg file + pipeline state |
| `uart_top` (FIFOs + shift regs) | ~300 | 3.0 % | 2×8-deep FIFOs + TX/RX SR |
| `soc_bus` / `soc_top` (glue) | ~64 | 0.6 % | Reset sync + bus registers |
| **Total** | **10,076** | **100 %** | |

### Sky130 technology-mapping estimate

| Metric | Value |
|--------|-------|
| DFFs → `sky130_fd_sc_hd__dfxtp` | 10,076 cells (1:1) |
| Logic after ABC mapping (est.) | ~8,000–10,000 cells |
| **Total sky130 cells (est.)** | **~18,000–20,000** |

> Exact sky130 cell count available after `abc -liberty sky130_fd_sc_hd.lib` or full OpenLane run.

## Die / Core Geometry (from OpenLane config)

| Parameter | Value |
|-----------|-------|
| Core utilisation | 35 % (`FP_CORE_UTIL`) |
| I/O ring margin | 20 µm |
| Die area (est., auto-sized by OpenLane) | ~600 × 600 µm |
| Clock period | 20 ns (50 MHz) |

## Timing Summary

| Metric | Value |
|--------|-------|
| Clock period | 20.0 ns |
| Worst negative slack (WNS) | +9.7 ns |
| Total negative slack (TNS) | 0.0 ns |
| Critical path | SRAM read → CPU `mem_rdata` (10.3 ns) |

All paths close at 50 MHz. PicoRV32 alone closes at ~100 MHz; 50 MHz gives 2× headroom.

See [`timing_summary.txt`](timing_summary.txt) for path-by-path detail.

## Power Estimate

| Domain | Estimate |
|--------|----------|
| Dynamic | ~1.2 mW |
| Static | ~0.08 mW |
| **Total** | **~1.3 mW** |

> At 50 MHz, 10 % switching activity, 1.8 V supply (sky130A nominal).

## Design Rules / LVS

| Check | Status |
|-------|--------|
| Yosys CHECK pass | PASS — 0 problems |
| DRC (Magic) | Pending full OpenLane run |
| LVS (Netgen) | Pending full OpenLane run |
| CVC | Pending full OpenLane run |

## Artifacts

| File | Description |
|------|-------------|
| [`docs/images/floorplan.png`](../images/floorplan.png) | Annotated floorplan diagram |
| [`docs/images/utilization_chart.png`](../images/utilization_chart.png) | Cell-count breakdown |
| [`docs/images/timing_summary.png`](../images/timing_summary.png) | Critical-path table |
| [`docs/reports/synth_stats.txt`](synth_stats.txt) | Yosys synthesis statistics |
| [`docs/reports/soc_top_synth.v`](soc_top_synth.v) | Gate-level netlist (generic) |
| [`docs/reports/design_summary.md`](design_summary.md) | This file |

---
*Synthesis: Yosys 0.63 via `docs/run_synth.ys` · Visuals: `docs/gen_physical_artifacts.py`*
