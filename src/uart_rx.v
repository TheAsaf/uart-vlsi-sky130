module uart_rx (
    input  wire       clk,
    input  wire       rst,
    input  wire       rx,
    output reg  [7:0] data,
    output reg        valid
);

// ---- Parameters ----
// Must match uart_tx: clock = 10MHz, baud = 9600 -> CLKS_PER_BIT = 1042
parameter CLKS_PER_BIT = 1042;

// ---- States ----
localparam IDLE  = 3'd0;
localparam START = 3'd1;
localparam DATA  = 3'd2;
localparam STOP  = 3'd3;

// ---- Registers ----
reg [2:0]  state;
reg [10:0] clk_count;   // counts clock cycles within each bit period
reg [2:0]  bit_index;   // current bit being received (0-7)
reg [7:0]  rx_data;     // shift register collecting incoming bits

always @(posedge clk or posedge rst) begin
    if (rst) begin
        state     <= IDLE;
        clk_count <= 0;
        bit_index <= 0;
        rx_data   <= 0;
        data      <= 0;
        valid     <= 1'b0;
    end
    else begin
        valid <= 1'b0;  // valid is a single-cycle pulse

        case (state)

            IDLE: begin
                // wait for falling edge = start bit detected
                if (rx == 1'b0) begin
                    state     <= START;
                    clk_count <= 0;
                end
            end

            START: begin
                // sample at the middle of the start bit to confirm it's valid
                if (clk_count < (CLKS_PER_BIT/2) - 1)
                    clk_count <= clk_count + 1;
                else begin
                    if (rx == 1'b0) begin
                        // confirmed valid start bit
                        clk_count <= 0;
                        bit_index <= 0;
                        state     <= DATA;
                    end
                    else begin
                        // false start, return to idle
                        state <= IDLE;
                    end
                end
            end

            DATA: begin
                // sample each bit at its midpoint for maximum noise immunity
                if (clk_count < CLKS_PER_BIT - 1)
                    clk_count <= clk_count + 1;
                else begin
                    clk_count          <= 0;
                    rx_data[bit_index] <= rx;   // sample and store the bit
                    if (bit_index < 7)
                        bit_index <= bit_index + 1;
                    else begin
                        bit_index <= 0;
                        state     <= STOP;
                    end
                end
            end

            STOP: begin
                // wait for stop bit (HIGH), then output the received byte
                if (clk_count < CLKS_PER_BIT - 1)
                    clk_count <= clk_count + 1;
                else begin
                    if (rx == 1'b1) begin
                        // valid stop bit received
                        data      <= rx_data;
                        valid     <= 1'b1;
                    end
                    // if stop bit is LOW = framing error, data is discarded
                    clk_count <= 0;
                    state     <= IDLE;
                end
            end

            default: state <= IDLE;

        endcase
    end
end

endmodule