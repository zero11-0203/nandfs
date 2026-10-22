// Memory as a tree of folders: each level has 16 children, the leaves are
// bytes of flip-flops. A level passes its address, write enable and write data
// on to the selected child only, and gates its read data by its own select,
// so an access changes signals along one path through the tree and nowhere
// else. That keeps the gates evaluated per access in the hundreds, not the
// tens of thousands a flat multiplexer would touch.
//
// memtree #(2) holds 16*16*16 = 4096 bytes; read data is combinational. The
// child folders are named h0..hf, so the byte at 0x5A3 is h5/ha/h3.
module memtree #(parameter LEVEL = 2) (
    input clk,
    input sel,
    input [4*LEVEL+3:0] addr,
    input we,
    input [7:0] din,
    output [7:0] dout
);
    wire [15:0] line = sel ? (16'd1 << addr[4*LEVEL+3:4*LEVEL]) : 16'd0;
    wire [127:0] outs;
    genvar i;
    generate
        for (i = 0; i < 16; i = i + 1) begin : h_hex
            if (LEVEL == 0) begin : leaf
                membyte m(.clk(clk), .sel(line[i]), .we(we), .din(din),
                          .dout(outs[8*i+7:8*i]));
            end else begin : sub
                memtree #(LEVEL - 1) m(.clk(clk), .sel(line[i]),
                    .addr(addr[4*LEVEL-1:0] & {4*LEVEL{line[i]}}),
                    .we(we & line[i]), .din(din & {8{line[i]}}),
                    .dout(outs[8*i+7:8*i]));
            end
        end
    endgenerate
    assign dout = outs[7:0] | outs[15:8] | outs[23:16] | outs[31:24]
                | outs[39:32] | outs[47:40] | outs[55:48] | outs[63:56]
                | outs[71:64] | outs[79:72] | outs[87:80] | outs[95:88]
                | outs[103:96] | outs[111:104] | outs[119:112] | outs[127:120];
endmodule

module membyte(input clk, input sel, input we, input [7:0] din, output [7:0] dout);
    reg [7:0] q = 0;
    always @(posedge clk)
        if (sel & we) q <= din;
    assign dout = q & {8{sel}};
endmodule
