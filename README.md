# UART Controller IP — RTL to GDSII (Sky130)

A register-mapped UART peripheral designed and taken through the full RTL-to-GDSII flow using **OpenLane** and the **SkyWater 130 nm** PDK. Built as a realistic, portfolio-quality hardware IP block demonstrating end-to-end ASIC design methodology.

## Architecture

```
                        ┌─────────────────────────────────────────────┐
                        │               uart_top                      │
                        │                                             │
   addr[2:0] ──────────┤  ┌───────────┐   ┌──────────┐              │
   wdata[7:0] ─────────┤  │ Register  │   │ sync_fifo│   ┌────────┐ │
   wen ────────────────┤  │ Interface │──▶│ (8-deep) │──▶│ uart_tx │──── uart_tx
   ren ────────────────┤  │           │   └──────────┘   └────────┘ │
   rdata[7:0] ◀────────┤  │ TX_DATA   │                             │
                        │  │ RX_DATA   │                  ┌────────┐ │
   clk ────────────────┤  │ STATUS    │◀─────────────────│ uart_rx │◀─── uart_rx
   rst_n ──────────────┤  │ CTRL      │                  │ (2-FF   │ │
                        │  └───────────┘                  │  sync)  │ │
   irq ◀───────────────┤                                 └────────┘ │
                        └─────────────────────────────────────────────┘
```

### Modules

| Module | Description | Lines |
|--------|-------------|-------|
| `uart_top` | Register-mapped peripheral wrapper with TX FIFO, status/ctrl registers, interrupt | ~170 |
| `uart_tx` | UART transmitter with configurable parity (8N1 / 8E1 / 8O1) | ~110 |
| `uart_rx` | UART receiver with 2-FF metastability synchronizer and parity checking | ~150 |
| `sync_fifo` | Parameterised synchronous FIFO (pointer-based, fall-through read) | ~55 |

### Register Map

| Addr | Name | Access | Description |
|------|------|--------|-------------|
| 0x0 | TX_DATA | W | Write a byte into the 8-deep TX FIFO |
| 0x1 | RX_DATA | R | Read last received byte (clears `rx_ready`) |
| 0x2 | STATUS | R/W1C | `{2'b0, parity_err, frame_err, rx_ready, fifo_full, fifo_empty, tx_busy}` |
| 0x3 | CTRL | RW | `{5'b0, irq_en, parity_odd, parity_en}` |

Error flags in STATUS use the **W1C** (write-1-to-clear) convention — write a `1` to a bit position to acknowledge and clear it.

## Key Design Decisions

1. **2-FF Synchronizer on RX** — The UART receive line is, by definition, asynchronous to the local clock. A dual flip-flop synchronizer prevents metastability from propagating into the FSM. This is a hard requirement for any real silicon implementation.

2. **Mid-bit Sampling** — After detecting a falling edge (start bit), the receiver waits half a bit period to reach the centre of the start bit. If the line is still LOW, reception proceeds; otherwise the glitch is rejected. All subsequent samples occur one full bit period apart, keeping every sample near the bit centre for maximum noise immunity.

3. **TX FIFO** — An 8-deep synchronous FIFO decouples the bus write rate from the serialiser. Software can burst-write multiple bytes without polling `tx_busy` between each one. The FIFO uses pointer-based full/empty detection with an extra MSB bit for disambiguation — no subtraction or counter needed.

4. **W1C Error Flags** — Sticky error flags (frame error, parity error) use write-1-to-clear semantics. This is the industry-standard pattern (seen in ARM AMBA peripherals, RISC-V PLIC, etc.) that avoids race conditions between hardware setting a flag and software clearing it.

5. **Bus-Agnostic Interface** — The register interface uses a simple `addr/wdata/rdata/wen/ren` protocol that maps trivially onto APB, Wishbone, or any SoC fabric — no bus-specific boilerplate in the IP itself.

6. **Configurable Parity** — Runtime-selectable even/odd parity via the CTRL register. The TX computes the parity bit combinationally from the data byte; the RX accumulates a running XOR and checks against the received parity bit.

## Design Tradeoffs

| Decision | Alternative | Rationale |
|----------|-------------|-----------|
| Synchronous reset (active-low) | Async reset | Cleaner timing closure; `rst_n` meets setup/hold like any other input. Sky130 DFFs support both. |
| Fixed baud divider (parameter) | Runtime-configurable divider register | Keeps the synthesised counter width minimal. For a multi-baud design, adding a 16-bit divisor register is straightforward. |
| Single-clock FIFO | Dual-clock async FIFO | TX and bus share the same clock; no CDC needed. An async FIFO would only be necessary if the bus and UART clocks were independent. |
| No RX FIFO | RX FIFO with watermark IRQ | Simplifies the design. A production UART would add an RX FIFO to tolerate interrupt latency; easily extensible with the existing `sync_fifo` module. |
| Fall-through FIFO read | Registered FIFO read | Removes one cycle of latency between FIFO pop and TX start. Requires a data latch register (`tx_data_reg`) to hold the value after the read pointer advances. |

## Verification

Self-checking testbench with **6 test groups** covering functional correctness, error detection, and FIFO ordering:

| # | Test | What it verifies |
|---|------|------------------|
| 1 | 8N1 loopback | Basic TX→RX with 5 data patterns (0xA5, 0x00, 0xFF, 0x55, 0xAA) |
| 2 | Even parity (8E1) | Parity generation and checking (even mode) |
| 3 | Odd parity (8O1) | Parity generation and checking (odd mode) |
| 4 | FIFO burst | Write 4 bytes back-to-back, verify in-order delivery |
| 5 | Framing error | Manually injected bad stop bit, verify `frame_err` sticky flag |
| 6 | Status flags | Verify idle-state register values (`fifo_empty=1, tx_busy=0`) |

```
=== TEST 1: Basic 8N1 loopback ===
  PASS: 0xa5 / PASS: 0x00 / PASS: 0xff / PASS: 0x55 / PASS: 0xaa
=== TEST 2: 8E1 (even parity) ===
  PASS: 0x37 / PASS: 0xc3
=== TEST 3: 8O1 (odd parity) ===
  PASS: 0x42 / PASS: 0xbd
=== TEST 4: FIFO burst (4 bytes) ===
  PASS: 0x11 / PASS: 0x22 / PASS: 0x33 / PASS: 0x44
=== TEST 5: Framing error detection ===
  PASS: frame_err detected
=== TEST 6: Status register flags ===
  PASS: idle state correct
========================================
  ALL TESTS PASSED (6 tests)
========================================
```

## Physical Design Results (Sky130, OpenLane)

Results from the initial `uart_tx`-only synthesis run. The full `uart_top` with FIFO and RX can be re-synthesised for updated numbers.

| Metric | Value |
|--------|-------|
| Technology | SkyWater 130 nm (sky130_fd_sc_hd) |
| Clock period | 10 ns (100 MHz target) |
| Worst setup slack | **+78.59 ns** (wide positive margin) |
| Worst hold slack | **+0.34 ns** (met) |
| Total power (typical) | **61.2 uW** |
| Cell count | 145 |
| Cell area | 1 565 um^2 |
| Die dimensions | 60 x 71 um |
| DRC violations | **0** |
| LVS | **Clean** (no mismatches) |
| Antenna violations | **0** |

## Repository Structure

```
rtl/
  uart_top.v           # Top-level register-mapped controller
  uart_tx.v            # UART transmitter
  uart_rx.v            # UART receiver (with 2-FF sync)
  sync_fifo.v          # Parameterised synchronous FIFO
tb/
  uart_top_tb.v        # Self-checking testbench (6 tests)
  Makefile             # Simulation build/run
  simulation_results.txt
openlane/
  config.json          # OpenLane design configuration
  pin_order.cfg        # Pin placement constraints
```

## Running the Project

### Prerequisites

- [Icarus Verilog](http://iverilog.icarus.com/) for simulation
- [GTKWave](http://gtkwave.sourceforge.net/) for waveform viewing (optional)
- [Docker](https://www.docker.com/) + [OpenLane](https://github.com/The-OpenROAD-Project/OpenLane) for the ASIC flow

### Simulation

```bash
cd tb
make sim          # Compile and run all tests
make wave         # Open waveform in GTKWave
make clean        # Remove generated files
```

### OpenLane RTL-to-GDSII Flow

```bash
# Clone OpenLane and install (see OpenLane docs)
# Copy openlane/ contents into OpenLane/designs/uart_top/
# Copy rtl/ into OpenLane/designs/uart_top/src/

# Inside the OpenLane Docker container:
./flow.tcl -design uart_top
```

Outputs land in `designs/uart_top/runs/<timestamp>/`:
- `results/synthesis/` — Yosys netlist
- `results/signoff/uart_top.gds` — Final GDSII layout
- `results/signoff/uart_top.sdf` — Timing annotation for gate-level sim
- `reports/signoff/` — STA, DRC, LVS, power reports

## Tools

- **Icarus Verilog** — RTL simulation
- **OpenLane v1.0.2** — Full ASIC flow (synthesis, P&R, signoff)
- **SkyWater sky130A PDK** — 130 nm standard cell library
- **KLayout** — GDS layout viewer

## License

The UART IP source code is original work. The OpenLane flow infrastructure is licensed under [Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0) by Efabless Corporation.
