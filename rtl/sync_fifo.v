// ============================================================================
// Module:  sync_fifo
// Project: UART Controller IP — Sky130 OpenLane
// Description:
//   Parameterised synchronous FIFO using a circular buffer with an extra
//   pointer bit for full/empty disambiguation. Read data appears
//   combinationally on rd_data when the FIFO is not empty (fall-through).
//
//   Depth must be a power of two (enforced by the pointer arithmetic).
//
// Typical use in this project:
//   8-deep TX FIFO allowing burst writes from the bus while the UART
//   serialiser drains one byte at a time.
// ============================================================================

module sync_fifo #(
    parameter DATA_WIDTH = 8,
    parameter DEPTH      = 8,              // must be power-of-two
    parameter ADDR_WIDTH = $clog2(DEPTH)   // derived — do not override
) (
    input  wire                    clk,
    input  wire                    rst_n,
    // Write port
    input  wire                    wr_en,
    input  wire [DATA_WIDTH-1:0]   wr_data,
    // Read port
    input  wire                    rd_en,
    output wire [DATA_WIDTH-1:0]   rd_data,
    // Status
    output wire                    full,
    output wire                    empty,
    output wire [ADDR_WIDTH:0]     count
);

    // Pointers: ADDR_WIDTH+1 bits — MSB distinguishes full from empty
    reg [ADDR_WIDTH:0] wr_ptr;
    reg [ADDR_WIDTH:0] rd_ptr;

    // Memory array
    reg [DATA_WIDTH-1:0] mem [0:DEPTH-1];

    // Status flags
    assign full  = (wr_ptr[ADDR_WIDTH] != rd_ptr[ADDR_WIDTH]) &&
                   (wr_ptr[ADDR_WIDTH-1:0] == rd_ptr[ADDR_WIDTH-1:0]);
    assign empty = (wr_ptr == rd_ptr);
    assign count = wr_ptr - rd_ptr;

    // Combinational read (fall-through)
    assign rd_data = mem[rd_ptr[ADDR_WIDTH-1:0]];

    always @(posedge clk) begin
        if (!rst_n) begin
            wr_ptr <= {(ADDR_WIDTH+1){1'b0}};
            rd_ptr <= {(ADDR_WIDTH+1){1'b0}};
        end else begin
            if (wr_en && !full) begin
                mem[wr_ptr[ADDR_WIDTH-1:0]] <= wr_data;
                wr_ptr <= wr_ptr + 1'b1;
            end
            if (rd_en && !empty) begin
                rd_ptr <= rd_ptr + 1'b1;
            end
        end
    end

endmodule
