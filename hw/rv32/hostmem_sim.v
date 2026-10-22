// Simulation model of hostmem (see hostmem.v), for Icarus Verilog.
module hostmem #(parameter AW = 10) (
    input clk,
    input [AW-1:0] a,
    input [31:0] w,
    input [3:0] we,
    output [31:0] r
);
    reg [31:0] m [0:(1 << AW) - 1];
    integer i;
    initial for (i = 0; i < (1 << AW); i = i + 1) m[i] = 0;
    assign r = m[a];
    always @(posedge clk) begin
        if (we[0]) m[a][7:0] <= w[7:0];
        if (we[1]) m[a][15:8] <= w[15:8];
        if (we[2]) m[a][23:16] <= w[23:16];
        if (we[3]) m[a][31:24] <= w[31:24];
    end
endmodule
