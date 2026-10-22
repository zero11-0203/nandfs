// The rambench workload on the tree-structured memory (hw/chip8/memtree.v).
module rambench2(input clk, output reg [7:0] check);
    reg [15:0] lfsr = 16'hACE1;
    reg phase = 0;
    initial check = 0;
    wire [7:0] dout;
    memtree #(2) mem(.clk(clk), .sel(1'b1), .addr(lfsr[11:0]), .we(phase),
                     .din(lfsr[15:8]), .dout(dout));
    always @(posedge clk) begin
        lfsr <= {lfsr[14:0], lfsr[15] ^ lfsr[13] ^ lfsr[12] ^ lfsr[10]};
        phase <= ~phase;
        if (!phase) check <= check ^ dout;
    end
endmodule
