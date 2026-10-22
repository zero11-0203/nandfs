// A RISC-V (RV32IM) computer to be built out of NAND gates and flip-flops:
// the CPU is PicoRV32 (YosysHQ, ISC license, fetched by
// scripts/fetch-picorv32.sh), unmodified. Its RAM and ROM are host memory
// (hostmem, which becomes a .mem folder). tools/rvref.c is the reference:
// the two must agree on every instruction.
//
// Memory map
//   0x00000000  RAM, 16 MB
//   0x10000000  ROM, 8 MB (writes are ignored)
//   0x20000000  TIME: instructions fetched since reset / 1000, counted by gates
//               (a clock that ticks with the program, so it is reproducible)
//   0x20000004  KEYS: the key pins
//   elsewhere   reads 0, writes are ignored
// Memory answers in the same cycle (mem_ready = mem_valid). ECALL, EBREAK,
// an illegal instruction or a misaligned access traps, which halts the CPU.
module rv32(input clk, input [15:0] keys, output halted, output [31:0] instret);
    // Power-on reset: resetn rises after two clock ticks.
    reg [1:0] boot = 0;
    always @(posedge clk) boot <= {boot[0], 1'b1};
    wire resetn = boot[1];

    wire mem_valid, mem_instr;
    wire [31:0] addr, wdata, rdata, ram_r, rom_r;
    wire [3:0] wstrb;
    picorv32 #(
        .ENABLE_COUNTERS(0), .ENABLE_COUNTERS64(0), .CATCH_MISALIGN(1), .CATCH_ILLINSN(1),
        .ENABLE_MUL(1), .ENABLE_DIV(1), .REGS_INIT_ZERO(1),
        .PROGADDR_RESET(32'h0000_0000)
    ) cpu (
        .clk(clk), .resetn(resetn), .trap(halted),
        .mem_valid(mem_valid), .mem_instr(mem_instr), .mem_ready(mem_valid),
        .mem_addr(addr), .mem_wdata(wdata), .mem_wstrb(wstrb), .mem_rdata(rdata),
        .pcpi_wr(1'b0), .pcpi_rd(32'd0), .pcpi_wait(1'b0), .pcpi_ready(1'b0), .irq(32'd0)
    );

    // Instructions fetched so far, and TIME = that / 1000.
    reg [31:0] fetched = 0, ms = 0;
    reg [9:0] sub = 0;
    always @(posedge clk)
        if (mem_valid & mem_instr) begin
            fetched <= fetched + 1'b1;
            sub <= sub == 10'd999 ? 10'd0 : sub + 1'b1;
            if (sub == 10'd999) ms <= ms + 1'b1;
        end
    assign instret = fetched;

    wire in_ram = addr[31:24] == 8'h00;
    wire in_rom = addr[31:23] == 9'h020;
    wire in_io = addr[31:3] == 29'h04000000;
    hostmem #(22) ram(.clk(clk), .a(addr[23:2]), .w(wdata), .we(wstrb & {4{mem_valid & in_ram}}),
                      .r(ram_r));
    hostmem #(21) rom(.clk(clk), .a(addr[22:2]), .w(32'd0), .we(4'd0), .r(rom_r));
    wire [31:0] io_r = addr[2] ? {16'd0, keys} : ms;
    assign rdata = (ram_r & {32{in_ram}}) | (rom_r & {32{in_rom}}) | (io_r & {32{in_io}});
endmodule
