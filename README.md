# UART Controller — Full RTL-to-GDS ASIC Implementation

A synthesizable UART (Universal Asynchronous Receiver-Transmitter) controller
implemented in Verilog and taken through a full ASIC flow using OpenLane on
the SkyWater sky130 130nm PDK.

## Results

| Metric | Value |
|--------|-------|
| Clock Frequency | 100 MHz |
| Process Node | sky130 (130nm) |
| Standard Cell Library | sky130_fd_sc_hd |
| Flow | RTL → Synthesis → Floorplan → Placement → CTS → Routing → GDS |

## Physical Design Results

| Metric | Value |
|--------|-------|
| WNS (Worst Negative Slack) | 0.0 ns |
| TNS (Total Negative Slack) | 0.0 ns |
| Critical Path | 1.34 ns |
| Core Area | 2387.29 µm² |
| Die Area | 0.004258 mm² |
| Total Cells | 340 |
| Non-Physical Cells | 181 |
| DFF count | 25 (7 AND + 8 NAND + 6 NOR + ...) |
| Wire Length | 3201 µm |
| Vias | 1172 |
| Routing DRC Violations | 0 |
| LVS Errors | 0 |
| Typical Power (internal) | 38.5 µW |
| Typical Power (switching) | 21.8 µW |

## Design Choices / Engineering Tradeoffs

**Baud rate clock divider (CLKS_PER_BIT = 1042)**
Chosen for 9600 baud at a 10MHz clock. A higher baud rate (e.g. 115200)
would require a faster clock or a smaller divider, reducing timing margin.
The current choice prioritizes simplicity and timing closure over throughput.

**Synchronous reset**
An asynchronous reset (`posedge rst`) was used to ensure the design reaches
a known state immediately on reset assertion, regardless of clock state.
The tradeoff is a slightly longer reset recovery path, visible in the STA
report as a recovery check on the flip-flops.

**Single-bit sampling vs. majority vote**
The RX samples each bit once at the midpoint of the bit period. A more
robust design would use a 3-sample majority vote to filter noise. The
single-sample approach was chosen to minimize logic complexity while still
providing adequate noise immunity for a simulation environment.

**Placement density (PL_TARGET_DENSITY = 0.75)**
A higher density was needed to pass global placement (OpenLane suggested
0.62 minimum). The final value of 0.75 leaves enough routing margin while
keeping core area compact at 2387 µm².

**No FIFO buffering**
The current design does not include TX/RX FIFOs. Back-to-back byte
transmission requires the host to assert `start` after each `done` pulse.
Adding a FIFO would increase cell count significantly but enable continuous
streaming.

## Simulation

All 5 test vectors passed:
```
PASS: sent 0xA5  received 0xA5
PASS: sent 0xFF  received 0xFF
PASS: sent 0x00  received 0x00
PASS: sent 0x55  received 0x55
PASS: sent 0x37  received 0x37
ALL TESTS PASSED
```

## Waveform

![Simulation Waveform](results/waveform.png)

## GDS Layout

![GDS Layout](results/layout.png)

## Project Structure
```
├── src/
│   ├── uart_tx.v            # Transmitter RTL
│   ├── uart_rx.v            # Receiver RTL
│   └── uart_tb.v            # Testbench
├── results/
│   ├── waveform.png         # Simulation waveform
│   ├── layout.png           # KLayout GDS view
│   ├── timing_report.txt    # OpenROAD STA report
│   └── simulation_results.txt
```

## Tools

- Icarus Verilog 13.0 — simulation
- OpenLane v1.0.2 — full ASIC flow
- SkyWater sky130A PDK — standard cell library
- KLayout 0.30.7 — GDS viewer

## How to Run Simulation
```bash
iverilog -o uart_sim src/uart_tb.v src/uart_tx.v src/uart_rx.v
vvp uart_sim
```

## Protocol

- Baud rate: 9600 (at 10MHz clock)
- Data bits: 8
- Stop bits: 1
- Parity: None (8N1)