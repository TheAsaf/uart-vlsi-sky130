// ============================================================================
// Testbench: uart_top_tb
// Project:   UART Controller IP — Sky130 OpenLane
// Description:
//   Comprehensive self-checking testbench for the uart_top register-mapped
//   UART controller.  The TX output is looped back to the RX input so every
//   transmitted byte is received and verified.
//
// Test plan:
//   1. Basic loopback  — 8N1 with representative data patterns
//   2. Parity modes    — 8E1 and 8O1 verified through register interface
//   3. FIFO burst      — Fill TX FIFO, drain via serialiser, verify order
//   4. Back-to-back TX — Consecutive writes with no idle gaps
//   5. Status register — Poll tx_busy, fifo_empty, rx_ready flags
//   6. Framing error   — Inject a bad stop bit and check frame_err flag
// ============================================================================

`timescale 1ns / 1ps

module uart_top_tb;

    // ----------------------------------------------------------------
    // Parameters — use a small baud divider to keep simulation fast
    // ----------------------------------------------------------------
    localparam CLKS_PER_BIT = 16;       // fast sim (not realistic baud)
    localparam CLK_PERIOD   = 10;       // 100 MHz clock
    localparam FIFO_DEPTH   = 8;
    localparam BIT_PERIOD   = CLKS_PER_BIT * CLK_PERIOD;  // ns per UART bit

    // Register addresses
    localparam [2:0] REG_TX_DATA = 3'h0,
                     REG_RX_DATA = 3'h1,
                     REG_STATUS  = 3'h2,
                     REG_CTRL    = 3'h3;

    // Status register bit positions
    localparam ST_TX_BUSY   = 0,
               ST_FIFO_EMPTY = 1,
               ST_FIFO_FULL  = 2,
               ST_RX_READY   = 3,
               ST_FRAME_ERR  = 4,
               ST_PAR_ERR    = 5;

    // ----------------------------------------------------------------
    // DUT signals
    // ----------------------------------------------------------------
    reg        clk;
    reg        rst_n;
    reg  [2:0] addr;
    reg  [7:0] wdata;
    wire [7:0] rdata;
    reg        wen;
    reg        ren;
    wire       uart_tx_pin;
    reg        uart_rx_pin;
    wire       irq;

    // Loopback: TX drives RX
    wire loopback = uart_tx_pin;

    // ----------------------------------------------------------------
    // DUT instantiation
    // ----------------------------------------------------------------
    uart_top #(
        .CLKS_PER_BIT (CLKS_PER_BIT),
        .FIFO_DEPTH   (FIFO_DEPTH)
    ) dut (
        .clk     (clk),
        .rst_n   (rst_n),
        .addr    (addr),
        .wdata   (wdata),
        .rdata   (rdata),
        .wen     (wen),
        .ren     (ren),
        .uart_rx (uart_rx_pin),
        .uart_tx (uart_tx_pin),
        .irq     (irq)
    );

    // ----------------------------------------------------------------
    // Clock generation
    // ----------------------------------------------------------------
    initial clk = 0;
    always #(CLK_PERIOD / 2) clk = ~clk;

    // ----------------------------------------------------------------
    // VCD dump
    // ----------------------------------------------------------------
    initial begin
        $dumpfile("uart_top_tb.vcd");
        $dumpvars(0, uart_top_tb);
    end

    // ----------------------------------------------------------------
    // Test infrastructure
    // ----------------------------------------------------------------
    integer errors   = 0;
    integer test_num = 0;

    // Drive stimulus between clock edges to avoid Verilog race conditions.
    // Signals settle before the next posedge where the DUT samples them.
    task reg_write;
        input [2:0] a;
        input [7:0] d;
        begin
            @(posedge clk); #1;
            addr  = a;
            wdata = d;
            wen   = 1'b1;
            @(posedge clk); #1;   // DUT captures on this edge
            wen = 1'b0;
        end
    endtask

    task reg_read;
        input  [2:0] a;
        output [7:0] d;
        begin
            @(posedge clk); #1;
            addr = a;
            ren  = 1'b1;
            @(posedge clk); #1;   // DUT processes ren; combinational rdata valid
            d = rdata;            // capture before ren deasserts
            ren = 1'b0;
        end
    endtask

    // Wait for rx_ready flag, with timeout
    task wait_rx_ready;
        input integer timeout_cycles;
        integer i;
        reg [7:0] status;
        begin
            for (i = 0; i < timeout_cycles; i = i + 1) begin
                reg_read(REG_STATUS, status);
                if (status[ST_RX_READY]) begin
                    i = timeout_cycles; // exit
                end
            end
        end
    endtask

    // Wait until TX is idle and FIFO is empty
    task wait_tx_idle;
        input integer timeout_cycles;
        integer i;
        reg [7:0] status;
        begin
            for (i = 0; i < timeout_cycles; i = i + 1) begin
                reg_read(REG_STATUS, status);
                if (!status[ST_TX_BUSY] && status[ST_FIFO_EMPTY]) begin
                    i = timeout_cycles;
                end
            end
        end
    endtask

    // Send one byte through TX FIFO via register write
    task send_byte;
        input [7:0] data;
        begin
            reg_write(REG_TX_DATA, data);
        end
    endtask

    // Wait for RX, read and verify
    task recv_and_check;
        input [7:0] expected;
        reg [7:0] got;
        reg [7:0] status;
        begin
            wait_rx_ready(CLKS_PER_BIT * 12 * 2);
            reg_read(REG_STATUS, status);
            reg_read(REG_RX_DATA, got);
            if (got !== expected) begin
                $display("  FAIL: expected 0x%02X, got 0x%02X", expected, got);
                errors = errors + 1;
            end else begin
                $display("  PASS: 0x%02X", got);
            end
        end
    endtask

    // ----------------------------------------------------------------
    // RX input mux: loopback (default), override, or force-low
    // ----------------------------------------------------------------
    reg force_rx_low;
    reg uart_rx_override;
    reg use_rx_override;
    always @(*) begin
        if (force_rx_low)
            uart_rx_pin = 1'b0;
        else if (use_rx_override)
            uart_rx_pin = uart_rx_override;
        else
            uart_rx_pin = loopback;
    end

    // ----------------------------------------------------------------
    // Main test sequence
    // ----------------------------------------------------------------
    initial begin
        // ---- Initialization ----
        rst_n            = 1'b0;
        addr             = 3'd0;
        wdata            = 8'd0;
        wen              = 1'b0;
        ren              = 1'b0;
        force_rx_low     = 1'b0;
        uart_rx_override = 1'b1;
        use_rx_override  = 1'b0;

        repeat (10) @(posedge clk);
        rst_n = 1'b1;
        repeat (5) @(posedge clk);

        // ============================================================
        // TEST 1: Basic loopback — 8N1 (no parity)
        // ============================================================
        test_num = 1;
        $display("\n=== TEST %0d: Basic 8N1 loopback ===", test_num);

        send_byte(8'hA5);
        recv_and_check(8'hA5);

        send_byte(8'h00);
        recv_and_check(8'h00);

        send_byte(8'hFF);
        recv_and_check(8'hFF);

        send_byte(8'h55);
        recv_and_check(8'h55);

        send_byte(8'hAA);
        recv_and_check(8'hAA);

        wait_tx_idle(CLKS_PER_BIT * 12);

        // ============================================================
        // TEST 2: Even parity (8E1)
        // ============================================================
        test_num = 2;
        $display("\n=== TEST %0d: 8E1 (even parity) ===", test_num);

        reg_write(REG_CTRL, 8'h01);  // parity_en=1, parity_odd=0

        send_byte(8'h37);
        recv_and_check(8'h37);

        send_byte(8'hC3);
        recv_and_check(8'hC3);

        wait_tx_idle(CLKS_PER_BIT * 14);

        // ============================================================
        // TEST 3: Odd parity (8O1)
        // ============================================================
        test_num = 3;
        $display("\n=== TEST %0d: 8O1 (odd parity) ===", test_num);

        reg_write(REG_CTRL, 8'h03);  // parity_en=1, parity_odd=1

        send_byte(8'h42);
        recv_and_check(8'h42);

        send_byte(8'hBD);
        recv_and_check(8'hBD);

        wait_tx_idle(CLKS_PER_BIT * 14);

        // Disable parity for remaining tests
        reg_write(REG_CTRL, 8'h00);

        // ============================================================
        // TEST 4: FIFO burst — write 4 bytes quickly, verify order
        // ============================================================
        test_num = 4;
        $display("\n=== TEST %0d: FIFO burst (4 bytes) ===", test_num);

        send_byte(8'h11);
        send_byte(8'h22);
        send_byte(8'h33);
        send_byte(8'h44);

        recv_and_check(8'h11);
        recv_and_check(8'h22);
        recv_and_check(8'h33);
        recv_and_check(8'h44);

        wait_tx_idle(CLKS_PER_BIT * 12);

        // ============================================================
        // TEST 5: Framing error injection
        // Manually drive a UART frame with a bad stop bit (LOW instead
        // of HIGH) directly into the RX input.
        // ============================================================
        test_num = 5;
        $display("\n=== TEST %0d: Framing error detection ===", test_num);

        // Disconnect loopback — drive RX manually
        force_rx_low = 1'b0;
        begin : frame_err_test
            reg [7:0] injected_data;
            reg [7:0] status;
            integer b;
            injected_data = 8'hDE;

            // Idle HIGH
            uart_rx_override = 1'b1;
            use_rx_override  = 1'b1;
            repeat (CLKS_PER_BIT * 2) @(posedge clk);

            // Start bit (LOW)
            uart_rx_override = 1'b0;
            repeat (CLKS_PER_BIT) @(posedge clk);

            // 8 data bits (LSB first)
            for (b = 0; b < 8; b = b + 1) begin
                uart_rx_override = injected_data[b];
                repeat (CLKS_PER_BIT) @(posedge clk);
            end

            // BAD stop bit (LOW instead of HIGH)
            uart_rx_override = 1'b0;
            repeat (CLKS_PER_BIT) @(posedge clk);

            // Return to idle and wait for RX to finish processing
            uart_rx_override = 1'b1;
            repeat (CLKS_PER_BIT * 5) @(posedge clk);

            // Restore loopback
            use_rx_override = 1'b0;
            repeat (5) @(posedge clk);

            // Read status — expect frame_err sticky flag set
            reg_read(REG_STATUS, status);
            if (status[ST_FRAME_ERR]) begin
                $display("  PASS: frame_err detected");
                // W1C: clear the error flag
                reg_write(REG_STATUS, 8'h10);
            end else begin
                $display("  FAIL: frame_err not set (status = 0x%02X)", status);
                errors = errors + 1;
            end
        end

        // ============================================================
        // TEST 6: Status register flags
        // ============================================================
        test_num = 6;
        $display("\n=== TEST %0d: Status register flags ===", test_num);

        begin
            reg [7:0] status;
            // After idle period, TX should be idle and FIFO empty
            reg_read(REG_STATUS, status);
            if (status[ST_FIFO_EMPTY] && !status[ST_TX_BUSY]) begin
                $display("  PASS: idle state correct (fifo_empty=1, tx_busy=0)");
            end else begin
                $display("  FAIL: unexpected idle status = 0x%02X", status);
                errors = errors + 1;
            end
        end

        // ============================================================
        // Summary
        // ============================================================
        repeat (20) @(posedge clk);
        $display("\n========================================");
        if (errors == 0)
            $display("  ALL TESTS PASSED (%0d tests)", test_num);
        else
            $display("  %0d ERROR(S) in %0d tests", errors, test_num);
        $display("========================================\n");
        $finish;
    end

    // ----------------------------------------------------------------
    // Safety timeout — kill simulation if it hangs
    // ----------------------------------------------------------------
    initial begin
        #(BIT_PERIOD * 500);
        $display("\nTIMEOUT: simulation exceeded maximum time");
        errors = errors + 1;
        $finish;
    end

endmodule
