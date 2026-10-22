// Benchmark: 4 KB of RAM exercised by a tiny state machine. Each cycle either
// writes a pseudo-random byte to a pseudo-random address or reads one back and
// folds it into a checksum, the way a CPU touches memory one byte at a time.
module rambench(input clk, output reg [7:0] check);
    reg [7:0] mem [0:4095];
    reg [15:0] lfsr = 16'hACE1;
    reg phase = 0;
    initial check = 0;
    wire [11:0] addr = lfsr[11:0];
    always @(posedge clk) begin
        lfsr <= {lfsr[14:0], lfsr[15] ^ lfsr[13] ^ lfsr[12] ^ lfsr[10]};
        phase <= ~phase;
        if (phase) mem[addr] <= lfsr[15:8];
        else check <= check ^ mem[addr];
    end
endmodule
