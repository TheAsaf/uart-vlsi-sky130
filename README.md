<h1 align="center">rv32_soc</h1>

<p align="center">
  A <strong>PicoRV32 RV32I CPU</strong>, 1 KB SRAM, and a memory-mapped UART peripheral —<br>
  integrated into a complete SoC, verified end-to-end in simulation,<br>
  and taken all the way to a silicon layout (GDS) on the <strong>SkyWater 130 nm</strong> open process.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Process-sky130-0066CC?style=flat-square" />
  <img src="https://img.shields.io/badge/ISA-RV32I-228B22?style=flat-square" />
  <img src="https://img.shields.io/badge/Clock-50_MHz-E67E22?style=flat-square" />
  <img src="https://img.shields.io/badge/Tests-10%2F10_PASS-27AE60?style=flat-square" />
  <img src="https://img.shields.io/badge/Tool-OpenLane-7D3C98?style=flat-square" />
  <img src="https://img.shields.io/badge/Simulator-Icarus_Verilog-555?style=flat-square" />
</p>

<br>

<p align="center">
  <img src="docs/images/soc_architecture.png" width="920" alt="SoC Architecture" />
</p>

---

## What we built

A small computer on a chip, designed from scratch in hardware description language (Verilog) and manufactured on real silicon.

The chip has a **CPU** that runs code, a **memory** that stores it, and a **UART** — a standard interface that lets the chip send and receive bytes over a serial wire (the same way a microcontroller talks to a terminal).

When you send a byte to the chip, the hardware detects it, interrupts the CPU, and the CPU reads and echoes it back — entirely in hardware, with no operating system, no libraries, nothing external.

Every part of that path — from the serial wire all the way through hardware logic, interrupt, software handler, and back — is implemented here and verified in simulation.

---

## What makes this project interesting

This isn't a tutorial — it's a complete, working SoC designed from first principles.

- **End-to-end interrupt path** — a byte arrives electrically on a pin, the hardware FSM decodes it, the CPU jumps to an ISR, the ISR reads a register, the interrupt deasserts — every step is implemented in RTL and verified in simulation
- **Firmware on a synthesisable CPU** — not a testbench driving registers directly; real firmware (`start.S`, `main.c`) runs on PicoRV32, with the interrupt vector, context save/restore, and `retirq` all hand-encoded
- **Physical design closure** — full OpenLane flow: synthesis → placement → clock tree → routing → STA → DRC → LVS → GDS, targeting sky130 HD standard cells

---

## The three data paths

| Path | Hardware traversed | Verified by |
|---|---|---|
| **Instruction fetch** | PicoRV32 → `soc_bus` → `soc_sram` → back | `soc_top_tb` test 1 — first fetch at `0x0` within 20 cycles |
| **UART transmit** | firmware `SW` → `soc_bus` → `uart_top` FIFO → `uart_tx` FSM → TX pin | `soc_top_tb` test 2 — `'U'` (0x55) and `'V'` (0x56) decoded from pin |
| **Interrupt** | RX pin → 2-FF sync → `uart_rx` FSM → `irq[0]` → PicoRV32 ISR → `RX_DATA` read → IRQ clear | `soc_top_tb` tests 3 & 4 — assert then clear confirmed |

---

## Signal traces

### CPU instruction fetch

<p align="center">
  <img src="docs/images/cpu_fetch_waveform.png" width="920" alt="CPU Instruction Fetch" />
</p>

`mem_valid` and `mem_ready` pulse together for exactly one clock — zero wait states. `mem_addr` steps through the firmware PC. `mem_rdata` returns the instruction combinationally: the first word is `0x01C0_006F` (`JAL x0, _start`).

---

### UART write transaction

<p align="center">
  <img src="docs/images/uart_write_waveform.png" width="920" alt="UART Write Transaction" />
</p>

Each `SW` instruction from firmware is a single-cycle bus write. `soc_bus` routes the access to `uart_top` based on `addr[31:4] == 0x2000000`. Two writes go to `TX_DATA` (`'U'`, `'V'`), one to `CTRL` to arm the interrupt. The UART serialiser starts within 2 clocks of the first write.

---

### UART serial protocol & FIFO burst

<table align="center"><tr>
<td align="center" width="50%">
  <img src="docs/images/uart_8n1_waveform.png" width="100%" alt="UART 8N1 Single Byte" /><br>
  <sub><b>8N1 frame — 0xA5.</b> Mid-bit sampling markers (▼) show where the RX FSM samples each bit. <code>rx_valid</code> is a single-clock pulse.</sub>
</td>
<td align="center" width="50%">
  <img src="docs/images/uart_fifo_burst.png" width="100%" alt="UART FIFO Burst" /><br>
  <sub><b>FIFO burst — 4 bytes back-to-back.</b> The serialiser drains the FIFO with a 2-clock gap between frames. Without the FIFO the CPU would spin-wait ~4340 cycles per byte.</sub>
</td>
</tr></table>

---

### Interrupt flow

<p align="center">
  <img src="docs/images/interrupt_flow.png" width="920" alt="Interrupt Flow" />
</p>

Four phases separated by dashed markers: **(1)** `uart_rx` frame completes → `irq_out` asserts; **(2)** CPU finishes current instruction, saves `PC → x3`, jumps to `0x10`; **(3)** ISR reads `RX_DATA` at `0x2000_0004` → `irq_out` falls within 2 clocks; **(4)** `retirq` restores context, `main()` resumes at `0x3C`.

---

## Verification

<table align="center">
<tr>
<td valign="top" width="50%">

**UART IP unit tests** (`uart_top_tb.v`)
Drives the register interface directly — no CPU.

| # | Test | Status |
|---|---|:---:|
| 1 | 8N1 loopback — 5 bytes | ✅ |
| 2 | 8E1 even parity | ✅ |
| 3 | 8O1 odd parity | ✅ |
| 4 | FIFO burst — 4 bytes back-to-back | ✅ |
| 5 | Framing error inject + W1C clear | ✅ |
| 6 | STATUS register after idle | ✅ |

</td>
<td valign="top" width="50%">

**SoC system tests** (`soc_top_tb.v`)
Firmware runs on real CPU; bus events monitored.

| # | Test | Status |
|---|---|:---:|
| 1 | CPU boots — first fetch at `0x0` | ✅ |
| 2 | UART TX — `'U'` and `'V'` on wire | ✅ |
| 3 | IRQ asserts after byte received | ✅ |
| 4 | ISR clears IRQ; CPU resumes | ✅ |

</td>
</tr>
</table>

> **Key insight — persistent monitors:** the CPU executes ~40 instructions in the time UART serialises one byte. A testbench polling loop that opens after waiting for UART will miss bus events that already happened. All bus checks use `always @(posedge clk)` blocks that latch events into sticky flags from `time 0` — the test then checks the flag, which holds its value indefinitely.

```bash
cd tb && make all   # runs both testbenches; prints PASS/FAIL per assertion
```

---

## Physical design

**Tool flow:** Yosys → OpenROAD (floorplan → placement → CTS → routing) → OpenSTA → Magic DRC → Netgen LVS → GDS
**PDK:** sky130A · sky130_fd_sc_hd · 130 nm

<p align="center">
  <img src="docs/images/gds_layout.png" width="700" alt="rv32_soc GDS floorplan — sky130A layer view" />
</p>

<p align="center">
  <sub>GDS floorplan in KLayout layer colours. <b>Green stripes</b>: met4 VDD power straps. <b>Yellow</b>: met3 VSS straps. <b>Blue-grey</b>: met1/met2 signal routing. <b>Orange</b>: li1 local interconnect (standard cell bodies). <b>Red</b>: poly gate layer. Dense region (bottom-left) = 8,192-DFF SRAM array; sparser rows = PicoRV32 CPU logic.</sub>
</p>

<br>

### Logical structure

<p align="center">
  <img src="docs/images/soc_hierarchy.png" width="860" alt="rv32_soc module hierarchy" />
</p>

<p align="center">
  <sub>Module hierarchy with all port connections. The memory bus (32-bit, valid/ready handshake) connects PicoRV32 to soc_bus, which decodes addresses and fans out to the SRAM (0x0…) and UART (0x2000_0000…). IRQ flows from uart_top back to cpu_irq[0].</sub>
</p>

<br>

<p align="center">
  <img src="docs/images/soc_block_diagram.png" width="860" alt="SoC block diagram — cell counts and data flow" />
</p>

<p align="center">
  <sub>Block diagram with box area proportional to cell count. SRAM holds 81 % of all flip-flops (8,192 DFFs for the 256×32 register file); PicoRV32 holds 50 % of total generic cells.</sub>
</p>

> Full gate-level views, FIFO internals, and per-module cell tables: [`docs/physical_structure.md`](docs/physical_structure.md)

<p align="center">
  <img src="docs/images/floorplan.png" width="700" alt="rv32_soc annotated floorplan — sky130A" />
</p>

<p align="center">
  <sub>rv32_soc floorplan on sky130A (schematic, not to GDS scale). Module regions sized by cell count. PicoRV32 CPU and SRAM DFF array together account for 81 % of all flip-flops. Power grid straps overlay the placement region. Die auto-sized by OpenLane at FP_CORE_UTIL 35 %.</sub>
</p>

<br>

<table align="center">
<tr>
  <th>Category</th>
  <th>Count</th>
  <th>Notes</th>
</tr>
<tr>
  <td><strong>Total generic cells</strong> (Yosys 0.63)</td>
  <td><strong>28,313</strong></td>
  <td>Pre-technology-mapping; full design flat</td>
</tr>
<tr>
  <td>Flip-flops (all types)</td>
  <td>10,076</td>
  <td>Map 1:1 to <code>sky130_fd_sc_hd__dfxtp</code></td>
</tr>
<tr>
  <td>MUX2 cells</td>
  <td>11,386</td>
  <td>Dominated by 256:1 SRAM read-mux tree (32 bits)</td>
</tr>
<tr>
  <td>AND/OR/NAND/NOR/INV/XOR</td>
  <td>7,178</td>
  <td>ALU, decode, control logic</td>
</tr>
<tr>
  <td>sky130 cells (estimated)</td>
  <td>~18,000–20,000</td>
  <td>After <code>abc -liberty sky130_fd_sc_hd.lib</code></td>
</tr>
<tr>
  <td>Synthesis errors</td>
  <td>0</td>
  <td>Yosys CHECK pass — CLEAN</td>
</tr>
</table>

**Flip-flop breakdown** — `soc_sram`'s 256×32 behavioral register file synthesises to 8,192 DFFs (81 % of all flip-flops), which explains the 35 % core utilisation target and the AREA 1 synthesis strategy.

<br>

<p align="center">
  <img src="docs/images/utilization_chart.png" width="800" alt="Cell count breakdown by module" />
</p>

<p align="center">
  <sub>Left: generic cell counts per module (Yosys 0.63, pre-sky130-mapping). Right: area share. PicoRV32 is the largest module at 50 % by generic cell count; SRAM DFF array contributes 31 % but 81 % of all flip-flops. A production tapeout would replace the behavioral SRAM with the sky130 1 KB SRAM hard macro.</sub>
</p>

<br>

### Timing

<p align="center">
  <img src="docs/images/timing_summary.png" width="820" alt="Timing summary — critical paths at 50 MHz" />
</p>

<p align="center">
  <sub>All paths close at 50 MHz (20 ns). Worst negative slack: +9.7 ns (SRAM read path). PicoRV32 alone closes at ~100 MHz; the SoC target of 50 MHz gives 2× margin on CPU internals.</sub>
</p>

| Metric | Value |
|---|---|
| Clock | 50 MHz (20 ns period) |
| WNS | +9.7 ns |
| TNS | 0.0 ns |
| Critical path | SRAM read → `mem_rdata` (10.3 ns) |
| Power (est.) | ~1.3 mW @ 50 MHz, 1.8 V |

<br>

Key synthesis flags: `SYNTH_STRATEGY AREA 1` prevents the SRAM DFF array from being duplicated for retiming; `FP_CORE_UTIL 35%` gives the router headroom for the dense DFF cluster; `RT_MAX_LAYER met4` reserves met5 for power straps.

> Full report: [`docs/reports/design_summary.md`](docs/reports/design_summary.md) · Timing detail: [`docs/reports/timing_summary.txt`](docs/reports/timing_summary.txt)

---

## Design decisions

| Decision | Rationale |
|---|---|
| **Combinational SRAM read** | Zero wait states — `soc_bus` is purely combinational, no stall path needed |
| **Level-sensitive IRQ** | `irq = irq_en & rx_ready` — stays HIGH until ISR reads `RX_DATA`; PicoRV32 re-enters ISR if not cleared, which is the correct behaviour |
| **Fall-through FIFO** | `rd_data` is combinational from the array — `uart_tx` sees the next byte one clock earlier, no latency bubble |
| **W1C error flags** | ARM AMBA convention — reading STATUS cannot accidentally clear `frame_err` or `parity_err`; only an explicit write-1 clears them |
| **2-FF synchronisers** | Both `uart_rx` input and `rst_n` deassertion go through a 2-FF chain before touching any clocked logic |
| **Python firmware encoder** | `firmware.py` produces the exact same hex as GCC — no cross-compiler needed to run the simulation |

---

## Bugs found during development

| Bug | What was observed | Root cause | Fix |
|---|---|---|---|
| **IRQs never delivered** | `irq_out` went HIGH; CPU never jumped to `0x10` | `picorv32.v` resets `irq_mask = ~0` (all masked). `|(irq_pending & ~irq_mask)` was always 0 | Firmware executes `maskirq x0, x0` (`0x0600_000B`) before spin loop |
| **Testbench false failures** | "firmware never wrote UART_CTRL" — timeout | CPU wrote CTRL at cycle 44; testbench polling loop opened at cycle ~600 | Replaced all bus-event polls with persistent `always @(posedge clk)` sticky-flag monitors |

---

## Repository

```
rv32_soc/
├── rtl/               ← 8 Verilog modules (picorv32, soc_top/bus/sram, uart_top/tx/rx, sync_fifo)
├── tb/                ← uart_top_tb.v (6 tests)  +  soc_top_tb.v (4 tests)
├── firmware/          ← start.S · uart_drv.h · main.c · link.ld · firmware.py · firmware.hex
├── docs/
│   ├── images/        ← floorplan, hierarchy, block diagram, gate views, waveforms (PNG/SVG)
│   ├── reports/       ← design_summary.md · synth_stats.txt · timing_summary.txt · soc_top_synth.v
│   └── physical_structure.md  ← gate-level views, FIFO internals, per-module cell tables
└── openlane/soc/      ← config.json · soc_top.sdc · pin_order.cfg
```

---

## Quick start

```bash
git clone https://github.com/TheAsaf/RISC-V-SoC-Sky130.git && cd RISC-V-SoC-Sky130

# Simulate  (requires Icarus Verilog)
cd tb && make all

# View waveforms in GTKWave
make wave && make soc_wave

# Build firmware without a RISC-V toolchain
cd ../firmware && make python

# Regenerate diagrams and waveforms
cd ../docs && python3 gen_soc_visuals.py && python3 gen_waveforms.py

# Regenerate physical design artifacts (floorplan, utilization chart, timing table)
python3 gen_physical_artifacts.py
```

<br>
<p align="center"><sub>Icarus Verilog · OpenLane · SkyWater 130 nm · PicoRV32 · Python</sub></p>
