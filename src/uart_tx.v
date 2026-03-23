module uart_tx (
    input  wire       clk,
    input  wire       rst,
    input  wire       start,
    input  wire [7:0] data,
    output reg        tx,
    output reg        done
);

// ---- Parameters ----
// clock = 10MHz, baud = 9600 -> CLKS_PER_BIT = 1042
parameter CLKS_PER_BIT = 1042;

// ---- States ----
localparam IDLE  = 3'd0;
localparam START = 3'd1;
localparam DATA  = 3'd2;
localparam STOP  = 3'd3;

// ---- Registers ----
reg [2:0]  state;
reg [10:0] clk_count;   // counts clock cycles within each bit period
reg [2:0]  bit_index;   // current bit being transmitted (0-7)
reg [7:0]  tx_data;     // local copy of data to transmit

always @(posedge clk or posedge rst) begin
    if (rst) begin
        state     <= IDLE;
        tx        <= 1'b1;   // UART idle line = HIGH
        done      <= 1'b0;
        clk_count <= 0;
        bit_index <= 0;
        tx_data   <= 0;
    end
    else begin
        done <= 1'b0;  // done is a single-cycle pulse

        case (state)

            IDLE: begin
                tx <= 1'b1;
                if (start) begin
                    tx_data   <= data;
                    state     <= START;
                    clk_count <= 0;
                end
            end

            START: begin
                tx <= 1'b0;  // start bit = LOW
                if (clk_count < CLKS_PER_BIT - 1)
                    clk_count <= clk_count + 1;
                else begin
                    clk_count <= 0;
                    bit_index <= 0;
                    state     <= DATA;
                end
            end

            DATA: begin
                tx <= tx_data[bit_index];
                if (clk_count < CLKS_PER_BIT - 1)
                    clk_count <= clk_count + 1;
                else begin
                    clk_count <= 0;
                    if (bit_index < 7)
                        bit_index <= bit_index + 1;
                    else begin
                        bit_index <= 0;
                        state     <= STOP;
                    end
                end
            end

            STOP: begin
                tx <= 1'b1;  // stop bit = HIGH
                if (clk_count < CLKS_PER_BIT - 1)
                    clk_count <= clk_count + 1;
                else begin
                    done      <= 1'b1;
                    clk_count <= 0;
                    state     <= IDLE;
                end
            end

            default: state <= IDLE;

        endcase
    end
end

endmodule