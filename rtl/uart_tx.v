// ============================================================================
// Module:  uart_tx
// Project: UART Controller IP — Sky130 OpenLane
// Description:
//   UART transmitter with configurable baud rate and optional parity.
//   Supports 8N1, 8E1, and 8O1 frame formats. LSB-first transmission
//   per RS-232 convention.
//
// Parameters:
//   CLKS_PER_BIT — Number of clock cycles per UART bit period.
//                  Default 868 = 100 MHz / 115200 baud.
//
// Interface:
//   tx_start  — Pulse high for one clock to begin transmission.
//   tx_data   — Must be stable when tx_start is asserted.
//   tx        — Serial output line (idles HIGH).
//   tx_busy   — HIGH while a frame is in progress.
//   tx_done   — Single-cycle pulse when the stop bit completes.
// ============================================================================

module uart_tx #(
    parameter CLKS_PER_BIT = 868
) (
    input  wire       clk,
    input  wire       rst_n,       // Active-low synchronous reset
    // Control
    input  wire       tx_start,
    input  wire [7:0] tx_data,
    input  wire       parity_en,   // 1 = insert parity bit after data
    input  wire       parity_odd,  // 0 = even parity, 1 = odd parity
    // Output
    output reg        tx,
    output wire       tx_busy,
    output reg        tx_done
);

    // FSM states — one-hot-friendly encoding
    localparam [2:0] S_IDLE   = 3'd0,
                     S_START  = 3'd1,
                     S_DATA   = 3'd2,
                     S_PARITY = 3'd3,
                     S_STOP   = 3'd4;

    reg  [2:0]  state;
    reg  [15:0] baud_cnt;
    reg  [2:0]  bit_idx;
    reg  [7:0]  shift_reg;
    reg         parity_bit;

    wire baud_tick = (baud_cnt == CLKS_PER_BIT - 1);

    assign tx_busy = (state != S_IDLE);

    // ------------------------------------------------------------
    // Baud-rate counter — free-running within a frame, reset on
    // each bit boundary and when idle.
    // ------------------------------------------------------------
    always @(posedge clk) begin
        if (!rst_n)
            baud_cnt <= 16'd0;
        else if (state == S_IDLE || baud_tick)
            baud_cnt <= 16'd0;
        else
            baud_cnt <= baud_cnt + 16'd1;
    end

    // ------------------------------------------------------------
    // FSM + datapath
    // ------------------------------------------------------------
    always @(posedge clk) begin
        if (!rst_n) begin
            state      <= S_IDLE;
            tx         <= 1'b1;        // idle line = HIGH
            tx_done    <= 1'b0;
            bit_idx    <= 3'd0;
            shift_reg  <= 8'd0;
            parity_bit <= 1'b0;
        end else begin
            tx_done <= 1'b0;           // default: single-cycle pulse

            case (state)
                S_IDLE: begin
                    tx <= 1'b1;
                    if (tx_start) begin
                        shift_reg  <= tx_data;
                        parity_bit <= parity_odd ? ~(^tx_data) : (^tx_data);
                        bit_idx    <= 3'd0;
                        state      <= S_START;
                    end
                end

                S_START: begin
                    tx <= 1'b0;        // start bit = LOW
                    if (baud_tick) begin
                        bit_idx <= 3'd0;
                        state   <= S_DATA;
                    end
                end

                S_DATA: begin
                    tx <= shift_reg[bit_idx];  // LSB first
                    if (baud_tick) begin
                        if (bit_idx == 3'd7)
                            state <= parity_en ? S_PARITY : S_STOP;
                        else
                            bit_idx <= bit_idx + 3'd1;
                    end
                end

                S_PARITY: begin
                    tx <= parity_bit;
                    if (baud_tick)
                        state <= S_STOP;
                end

                S_STOP: begin
                    tx <= 1'b1;        // stop bit = HIGH
                    if (baud_tick) begin
                        tx_done <= 1'b1;
                        state   <= S_IDLE;
                    end
                end

                default: state <= S_IDLE;
            endcase
        end
    end

endmodule
