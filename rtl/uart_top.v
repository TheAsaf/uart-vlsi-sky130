// ============================================================================
// Module:  uart_top
// Project: UART Controller IP — Sky130 OpenLane
// Description:
//   Register-mapped UART peripheral integrating:
//     - uart_tx   (transmitter with optional parity)
//     - uart_rx   (receiver with 2-FF sync and optional parity)
//     - sync_fifo (8-deep TX FIFO for burst writes)
//
//   Designed as a bus-agnostic IP block. The simple addr/data interface
//   maps trivially onto APB, Wishbone, or any SoC fabric.
//
// Register Map (active on wen/ren + addr):
//   0x0  TX_DATA  [W]   Write a byte into the TX FIFO
//   0x1  RX_DATA  [R]   Read the last received byte (clears rx_ready)
//   0x2  STATUS   [RW]  {2'b0, parity_err, frame_err,
//                         rx_ready, fifo_full, fifo_empty, tx_busy}
//                        Error flags are W1C (write-1-to-clear).
//   0x3  CTRL     [RW]  {5'b0, irq_en, parity_odd, parity_en}
//
// Interrupt:
//   irq asserts when a valid byte is received and irq_en is set.
//
// Parameters:
//   CLKS_PER_BIT — Baud divider. Default 868 (100 MHz / 115 200).
//   FIFO_DEPTH   — TX FIFO depth. Must be a power of two.
// ============================================================================

module uart_top #(
    parameter CLKS_PER_BIT = 868,
    parameter FIFO_DEPTH   = 8
) (
    input  wire       clk,
    input  wire       rst_n,
    // ---- Register interface ----
    input  wire [2:0] addr,
    input  wire [7:0] wdata,
    output reg  [7:0] rdata,
    input  wire       wen,
    input  wire       ren,
    // ---- UART pins ----
    input  wire       uart_rx,
    output wire       uart_tx,
    // ---- Interrupt ----
    output wire       irq
);

    // ================================================================
    // Register addresses
    // ================================================================
    localparam [2:0] REG_TX_DATA = 3'h0,
                     REG_RX_DATA = 3'h1,
                     REG_STATUS  = 3'h2,
                     REG_CTRL    = 3'h3;

    // ================================================================
    // Control register fields
    // ================================================================
    reg parity_en;
    reg parity_odd;
    reg irq_en;

    // ================================================================
    // TX FIFO
    // ================================================================
    wire       fifo_wr_en = wen && (addr == REG_TX_DATA);
    wire       fifo_rd_en;
    wire [7:0] fifo_rd_data;
    wire       fifo_full, fifo_empty;

    sync_fifo #(
        .DATA_WIDTH (8),
        .DEPTH      (FIFO_DEPTH)
    ) u_tx_fifo (
        .clk     (clk),
        .rst_n   (rst_n),
        .wr_en   (fifo_wr_en && !fifo_full),
        .wr_data (wdata),
        .rd_en   (fifo_rd_en),
        .rd_data (fifo_rd_data),
        .full    (fifo_full),
        .empty   (fifo_empty),
        .count   ()                // unused — status uses full/empty
    );

    // ================================================================
    // TX: pull one byte from FIFO when the serialiser is idle
    // The FIFO has fall-through (combinational) read, so we latch
    // rd_data into tx_data_reg on the same cycle as fifo_rd_en,
    // then assert tx_start one cycle later.
    // ================================================================
    wire tx_busy, tx_done;
    reg  tx_start;
    reg  [7:0] tx_data_reg;

    assign fifo_rd_en = !fifo_empty && !tx_busy && !tx_start;

    always @(posedge clk) begin
        if (!rst_n) begin
            tx_start    <= 1'b0;
            tx_data_reg <= 8'd0;
        end else begin
            tx_start <= fifo_rd_en;
            if (fifo_rd_en)
                tx_data_reg <= fifo_rd_data;  // latch before pointer advances
        end
    end

    uart_tx #(.CLKS_PER_BIT(CLKS_PER_BIT)) u_tx (
        .clk        (clk),
        .rst_n      (rst_n),
        .tx_start   (tx_start),
        .tx_data    (tx_data_reg),
        .parity_en  (parity_en),
        .parity_odd (parity_odd),
        .tx         (uart_tx),
        .tx_busy    (tx_busy),
        .tx_done    (tx_done)
    );

    // ================================================================
    // RX
    // ================================================================
    wire [7:0] rx_data_w;
    wire       rx_valid_w;
    wire       frame_err_w;
    wire       parity_err_w;

    uart_rx #(.CLKS_PER_BIT(CLKS_PER_BIT)) u_rx (
        .clk        (clk),
        .rst_n      (rst_n),
        .rx         (uart_rx),
        .parity_en  (parity_en),
        .parity_odd (parity_odd),
        .rx_data    (rx_data_w),
        .rx_valid   (rx_valid_w),
        .frame_err  (frame_err_w),
        .parity_err (parity_err_w)
    );

    // ================================================================
    // RX data latch & sticky error flags
    // ================================================================
    reg [7:0] rx_data_reg;
    reg       rx_ready;
    reg       frame_err_sticky;
    reg       parity_err_sticky;

    always @(posedge clk) begin
        if (!rst_n) begin
            rx_data_reg       <= 8'd0;
            rx_ready          <= 1'b0;
            frame_err_sticky  <= 1'b0;
            parity_err_sticky <= 1'b0;
        end else begin
            // Latch new received byte
            if (rx_valid_w) begin
                rx_data_reg <= rx_data_w;
                rx_ready    <= 1'b1;
            end
            // Clear rx_ready on RX_DATA read
            if (ren && addr == REG_RX_DATA)
                rx_ready <= 1'b0;
            // Sticky error accumulation
            if (frame_err_w)
                frame_err_sticky <= 1'b1;
            if (parity_err_w)
                parity_err_sticky <= 1'b1;
            // W1C: write 1 to a status bit to clear it
            if (wen && addr == REG_STATUS) begin
                if (wdata[4]) frame_err_sticky  <= 1'b0;
                if (wdata[5]) parity_err_sticky <= 1'b0;
            end
        end
    end

    // ================================================================
    // Control register
    // ================================================================
    always @(posedge clk) begin
        if (!rst_n) begin
            parity_en  <= 1'b0;
            parity_odd <= 1'b0;
            irq_en     <= 1'b0;
        end else if (wen && addr == REG_CTRL) begin
            parity_en  <= wdata[0];
            parity_odd <= wdata[1];
            irq_en     <= wdata[2];
        end
    end

    // ================================================================
    // Read mux (combinational — active whenever addr changes)
    // ================================================================
    always @(*) begin
        case (addr)
            REG_RX_DATA: rdata = rx_data_reg;
            REG_STATUS:  rdata = {2'b00,
                                  parity_err_sticky,
                                  frame_err_sticky,
                                  rx_ready,
                                  fifo_full,
                                  fifo_empty,
                                  tx_busy};
            REG_CTRL:    rdata = {5'b00000, irq_en, parity_odd, parity_en};
            default:     rdata = 8'd0;
        endcase
    end

    // ================================================================
    // Interrupt — level-sensitive, asserts while rx_ready && irq_en
    // ================================================================
    assign irq = irq_en & rx_ready;

endmodule
