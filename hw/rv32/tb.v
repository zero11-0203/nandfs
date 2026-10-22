// Icarus Verilog testbench for rv32.v: runs a program and prints one trace
// line per instruction in the format of tools/rvref.c -t (from PicoRV32's
// RVFI trace port, so compile with -DRISCV_FORMAL), then a summary.
//   +ram=FILE     RAM image (binary), loaded at address 0
//   +rom=FILE     ROM image (binary)
//   +n=N          stop after N instructions
`timescale 1ns/1ns
module tb;
    reg clk = 0;
    wire halted;
    wire [31:0] instret;
    rv32 dut(.clk(clk), .keys(16'd0), .halted(halted), .instret(instret));

    reg [8*256-1:0] file;
    integer fd, k, n, limit, off, size;
    reg [7:0] byte_;
    reg [63:0] cycles;
    reg [31:0] v;
    task load(input [8*256-1:0] name, input integer rom);
        begin
            fd = $fopen(name, "rb");
            if (fd == 0) $fatal(1, "cannot open %0s", name);
            k = 0;
            while ($fread(byte_, fd) == 1) begin
                if (rom) dut.rom.m[k >> 2][8 * (k & 3) +: 8] = byte_;
                else dut.ram.m[k >> 2][8 * (k & 3) +: 8] = byte_;
                k = k + 1;
            end
            $fclose(fd);
        end
    endtask

    wire rv = dut.cpu.rvfi_valid & ~dut.cpu.rvfi_trap;
    wire [31:0] pc = dut.cpu.rvfi_pc_rdata, ir = dut.cpu.rvfi_insn;
    wire [4:0] rd = dut.cpu.rvfi_rd_addr;
    wire [3:0] wm = dut.cpu.rvfi_mem_wmask;

    initial begin
        #1;
        if ($value$plusargs("ram=%s", file)) load(file, 0);
        if ($value$plusargs("rom=%s", file)) load(file, 1);
        if (!$value$plusargs("n=%d", limit)) limit = -1;
        n = 0;
        cycles = 0;
        forever begin
            #4;
            if (halted || n == limit) begin
                $display("halted=%0d after %0d instructions, %0d cycles; pc=%08x a0=%0d",
                         halted, n, cycles, dut.cpu.reg_pc, dut.cpu.cpuregs[10]);
                $finish;
            end
            if (rv) begin
                n = n + 1;
                if (wm != 0) begin
                    off = wm[0] ? 0 : wm[1] ? 1 : wm[2] ? 2 : 3;
                    size = wm == 4'b1111 ? 4 : (wm == 4'b0011 || wm == 4'b1100) ? 2 : 1;
                    v = dut.cpu.rvfi_mem_wdata >> (8 * off);
                    if (size == 1) v = v & 32'hff;
                    if (size == 2) v = v & 32'hffff;
                    $display("%0d %08x %08x [%08x]=%08x/%0d", n, pc, ir,
                             dut.cpu.rvfi_mem_addr + off, v, size);
                end else if (rd != 0)
                    $display("%0d %08x %08x x%0d=%08x", n, pc, ir, rd, dut.cpu.rvfi_rd_wdata);
                else
                    $display("%0d %08x %08x", n, pc, ir);
            end
            #1 clk = 1;
            cycles = cycles + 1;
            #5 clk = 0;
        end
    end
endmodule
