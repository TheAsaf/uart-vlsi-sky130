`timescale 1ns/1ps

module uart_tb;

parameter CLKS_PER_BIT = 1042;
parameter CLK_PERIOD   = 100;

reg        clk;
reg        rst;
reg        start;
reg  [7:0] tx_data;
wire       tx_line;
wire       tx_done;
wire [7:0] rx_data;
wire       rx_valid;

uart_tx #(.CLKS_PER_BIT(CLKS_PER_BIT)) DUT_TX (
    .clk(clk), .rst(rst), .start(start),
    .data(tx_data), .tx(tx_line), .done(tx_done)
);

uart_rx #(.CLKS_PER_BIT(CLKS_PER_BIT)) DUT_RX (
    .clk(clk), .rst(rst), .rx(tx_line),
    .data(rx_data), .valid(rx_valid)
);

initial clk = 0;
always #(CLK_PERIOD/2) clk = ~clk;

initial begin
    $dumpfile("uart_tb.vcd");
    $dumpvars(0, uart_tb);
end

integer errors = 0;

task send_byte;
    input [7:0] byte_to_send;
    reg rx_caught;
    integer i;
    begin
        rx_caught = 0;

        @(posedge clk);
        tx_data = byte_to_send;
        start   = 1'b1;
        @(posedge clk);
        start   = 1'b0;

        // wait up to 15000 cycles for rx_valid
        for (i = 0; i < 15000; i = i + 1) begin
            @(posedge clk);
            if (rx_valid && !rx_caught) begin
                rx_caught = 1;
                if (rx_data === byte_to_send)
                    $display("PASS: sent 0x%02X  received 0x%02X", byte_to_send, rx_data);
                else begin
                    $display("FAIL: sent 0x%02X  received 0x%02X", byte_to_send, rx_data);
                    errors = errors + 1;
                end
            end
            // exit loop after tx_done + rx caught
            if (tx_done && rx_caught) begin
                i = 15000;
            end
        end

        if (!rx_caught) begin
            $display("FAIL: 0x%02X - rx_valid never asserted", byte_to_send);
            errors = errors + 1;
        end

        repeat(10) @(posedge clk);
    end
endtask

initial begin
    rst   = 1'b1;
    clk   = 0'b0;
    start = 1'b0;
    repeat(5) @(posedge clk);
    rst = 1'b0;
    repeat(5) @(posedge clk);

    send_byte(8'hA5);
    send_byte(8'hFF);
    send_byte(8'h00);
    send_byte(8'h55);
    send_byte(8'h37);

    $display("--------------------");
    if (errors == 0)
        $display("ALL TESTS PASSED");
    else
        $display("%0d TEST(S) FAILED", errors);

    $finish;
end

endmodule