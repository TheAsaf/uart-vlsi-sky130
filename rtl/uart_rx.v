// ============================================================================
// Module:  uart_rx
// Project: UART Controller IP — Sky130 OpenLane
// Description:
//   UART receiver with 2-FF metastability synchronizer, mid-bit sampling,
//   and optional parity checking. Reports framing errors (bad stop bit) and
//   parity errors as single-cycle pulses alongside rx_valid.
//
//   Sampling strategy: after detecting a falling edge (start bit), the
//   receiver waits CLKS_PER_BIT/2 cycles to reach the midpoint of the start
//   bit. If the line is still LOW, reception proceeds; otherwise the glitch
//   is rejected. Subsequent data bits are sampled one full CLKS_PER_BIT
//   after the previous sample, keeping every sample near the bit centre.
//
// Parameters:
//   CLKS_PER_BIT — Must match the transmitter.
// ============================================================================

module uart_rx #(
    parameter CLKS_PER_BIT = 868
) (
    input  wire       clk,
    input  wire       rst_n,
    // Serial input
    input  wire       rx,
    // Configuration
    input  wire       parity_en,
    input  wire       parity_odd,
    // Parallel output
    output reg  [7:0] rx_data,
    output reg        rx_valid,
    output reg        frame_err,
    output reg        parity_err
);

    // ----------------------------------------------------------------
    // 2-FF synchronizer — prevents metastability when rx is driven
    // from an asynchronous domain (which is always the case for UART).
    // ----------------------------------------------------------------
    reg rx_meta, rx_sync;
    always @(posedge clk) begin
        if (!rst_n) begin
            rx_meta <= 1'b1;
            rx_sync <= 1'b1;
        end else begin
            rx_meta <= rx;
            rx_sync <= rx_meta;
        end
    end

    // FSM states
    localparam [2:0] S_IDLE   = 3'd0,
                     S_START  = 3'd1,
                     S_DATA   = 3'd2,
                     S_PARITY = 3'd3,
                     S_STOP   = 3'd4;

    reg  [2:0]  state;
    reg  [15:0] baud_cnt;
    reg  [2:0]  bit_idx;
    reg  [7:0]  shift_reg;
    reg         rx_parity;         // running XOR of received data bits
    reg         parity_fail;       // latched within a frame

    wire baud_tick      = (baud_cnt == CLKS_PER_BIT - 1);
    wire half_baud_tick = (baud_cnt == (CLKS_PER_BIT / 2) - 1);

    // ----------------------------------------------------------------
    // Main FSM
    // ----------------------------------------------------------------
    always @(posedge clk) begin
        if (!rst_n) begin
            state       <= S_IDLE;
            baud_cnt    <= 16'd0;
            bit_idx     <= 3'd0;
            shift_reg   <= 8'd0;
            rx_data     <= 8'd0;
            rx_valid    <= 1'b0;
            frame_err   <= 1'b0;
            parity_err  <= 1'b0;
            rx_parity   <= 1'b0;
            parity_fail <= 1'b0;
        end else begin
            // Defaults — all status outputs are single-cycle pulses
            rx_valid   <= 1'b0;
            frame_err  <= 1'b0;
            parity_err <= 1'b0;

            case (state)
                // ------------------------------------------------
                // IDLE: wait for a falling edge on the synced line
                // ------------------------------------------------
                S_IDLE: begin
                    baud_cnt <= 16'd0;
                    if (rx_sync == 1'b0) begin
                        state <= S_START;
                    end
                end

                // ------------------------------------------------
                // START: verify at midpoint that start bit is real
                // ------------------------------------------------
                S_START: begin
                    if (half_baud_tick) begin
                        if (rx_sync == 1'b0) begin
                            // Confirmed — begin data sampling
                            baud_cnt    <= 16'd0;
                            bit_idx     <= 3'd0;
                            shift_reg   <= 8'd0;
                            rx_parity   <= 1'b0;
                            parity_fail <= 1'b0;
                            state       <= S_DATA;
                        end else begin
                            // Glitch — return to idle
                            state <= S_IDLE;
                        end
                    end else begin
                        baud_cnt <= baud_cnt + 16'd1;
                    end
                end

                // ------------------------------------------------
                // DATA: sample 8 bits at their midpoints (LSB first)
                // ------------------------------------------------
                S_DATA: begin
                    if (baud_tick) begin
                        baud_cnt           <= 16'd0;
                        shift_reg[bit_idx] <= rx_sync;
                        rx_parity          <= rx_parity ^ rx_sync;
                        if (bit_idx == 3'd7)
                            state <= parity_en ? S_PARITY : S_STOP;
                        else
                            bit_idx <= bit_idx + 3'd1;
                    end else begin
                        baud_cnt <= baud_cnt + 16'd1;
                    end
                end

                // ------------------------------------------------
                // PARITY: sample and check parity bit
                // ------------------------------------------------
                S_PARITY: begin
                    if (baud_tick) begin
                        baud_cnt <= 16'd0;
                        // For even parity: data XOR == 0, so parity bit == rx_parity
                        // For odd  parity: data XOR == 1, so parity bit == ~rx_parity
                        if (parity_odd)
                            parity_fail <= (rx_parity ^ rx_sync) != 1'b1;
                        else
                            parity_fail <= (rx_parity ^ rx_sync) != 1'b0;
                        state <= S_STOP;
                    end else begin
                        baud_cnt <= baud_cnt + 16'd1;
                    end
                end

                // ------------------------------------------------
                // STOP: verify stop bit, output result
                // ------------------------------------------------
                S_STOP: begin
                    if (baud_tick) begin
                        baud_cnt <= 16'd0;
                        if (rx_sync == 1'b1) begin
                            // Valid stop bit
                            rx_data    <= shift_reg;
                            rx_valid   <= ~parity_fail;
                            parity_err <= parity_fail;
                        end else begin
                            // Framing error — stop bit expected HIGH
                            frame_err <= 1'b1;
                        end
                        state <= S_IDLE;
                    end else begin
                        baud_cnt <= baud_cnt + 16'd1;
                    end
                end

                default: state <= S_IDLE;
            endcase
        end
    end

endmodule
