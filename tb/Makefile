# ============================================================================
# Simulation Makefile for UART Controller IP
# Requires: Icarus Verilog (iverilog) and optionally GTKWave
# ============================================================================

RTL_DIR    := ../rtl
TB_DIR     := .
SRC_FILES  := $(RTL_DIR)/uart_tx.v \
              $(RTL_DIR)/uart_rx.v \
              $(RTL_DIR)/sync_fifo.v \
              $(RTL_DIR)/uart_top.v
TB_FILE    := $(TB_DIR)/uart_top_tb.v
SIM_BIN    := uart_sim
VCD_FILE   := uart_top_tb.vcd
RESULTS    := simulation_results.txt

.PHONY: all sim wave clean

all: sim

sim: $(SIM_BIN)
	@echo "Running simulation..."
	@./$(SIM_BIN) | tee $(RESULTS)
	@echo ""
	@echo "Results saved to $(RESULTS)"

$(SIM_BIN): $(SRC_FILES) $(TB_FILE)
	iverilog -g2012 -Wall -o $@ $(SRC_FILES) $(TB_FILE)

wave: $(VCD_FILE)
	gtkwave $(VCD_FILE) &

$(VCD_FILE): sim

clean:
	rm -f $(SIM_BIN) $(VCD_FILE) $(RESULTS)
