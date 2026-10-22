// An 8-bit adder and a counter with enable and synchronous reset, for
// checking the Yosys-to-folders pipeline.
module add8(input [7:0] a, input [7:0] b, output [8:0] sum);
    assign sum = a + b;
endmodule

module counter(input clk, input en, input rst, output reg [7:0] count);
    initial count = 8'd3;
    always @(posedge clk)
        if (rst) count <= 0;
        else if (en) count <= count + 1;
endmodule

module top(input clk, input en, input rst, input [7:0] a, input [7:0] b,
           output [8:0] sum, output [7:0] count);
    add8 adder(.a(a), .b(b), .sum(sum));
    counter ctr(.clk(clk), .en(en), .rst(rst), .count(count));
endmodule
