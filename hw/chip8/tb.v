// Icarus Verilog testbench: runs a ROM image and prints a trace line each
// time an instruction finishes, in the format of tools/chip8ref.py.
//   +rom=FILE   4096 bytes as hex, one per line ($readmemh)
//   +keys=FILE  pairs of hex lines "slot mask": key mask from that slot on
//   +slots=N    how many slots to run
//   +screen     print the screen at the end
`timescale 1ns/1ns
module tb;
    reg clk = 0;
    reg [15:0] keys = 0;
    wire buzzer;
    wire [15:0] icount;
    chip8 dut(.clk(clk), .keys(keys), .buzzer(buzzer), .icount(icount));

    reg [7:0] rom [0:4095];
    reg [31:0] kev [0:2047];
    integer slots, slot, nk, ki, r, c;
    reg [8*256-1:0] romfile, keyfile;

    wire [63:0] screen [0:31];
    genvar a, b, d;
    generate
        for (a = 0; a < 32; a = a + 1)
            assign screen[a] = dut.display.r[a].row.px;
        for (a = 0; a < 16; a = a + 1)
            for (b = 0; b < 16; b = b + 1)
                for (d = 0; d < 16; d = d + 1)
                    initial #1 dut.memory.ram.h_hex[a].sub.m.h_hex[b].sub.m.h_hex[d].leaf.m.q
                        = rom[a * 256 + b * 16 + d];
    endgenerate

    initial begin
        for (r = 0; r < 4096; r = r + 1) rom[r] = 0;
        for (r = 0; r < 2048; r = r + 1) kev[r] = 32'hFFFFFFFF;
        if (!$value$plusargs("rom=%s", romfile)) $fatal(1, "need +rom=FILE");
        $readmemh(romfile, rom);
        if ($value$plusargs("keys=%s", keyfile)) $readmemh(keyfile, kev);
        if (!$value$plusargs("slots=%d", slots)) slots = 1000;
        slot = -1;
        ki = 0;
        #5;
        forever begin
            if (dut.slot_start) begin
                slot = slot + 1;
                while (kev[ki] != 32'hFFFFFFFF && kev[ki] <= slot) begin
                    keys = kev[ki + 1];
                    ki = ki + 2;
                end
                if (slot == slots) begin
                    if ($test$plusargs("screen"))
                        for (r = 0; r < 32; r = r + 1) begin
                            for (c = 0; c < 64; c = c + 1)
                                $write("%s", screen[r][c] ? "#" : ".");
                            $write("\n");
                        end
                    $finish;
                end
            end
            #5 clk = 1;
            #5 clk = 0;
        end
    end

    // After a tick in which an instruction finished, print the machine state.
    always @(posedge clk) begin
        if (dut.cpu.retire) begin
            #1 $display("%0d %0h %0h %0h %0h %0h %0h %0h %0h %0h %0h %0h %0h %0h %0h %0h %0h %0h %0h %0h %0h %0h",
                slot, dut.cpu.pc,
                dut.cpu.regs.v_hex[0].r.q, dut.cpu.regs.v_hex[1].r.q, dut.cpu.regs.v_hex[2].r.q,
                dut.cpu.regs.v_hex[3].r.q, dut.cpu.regs.v_hex[4].r.q, dut.cpu.regs.v_hex[5].r.q,
                dut.cpu.regs.v_hex[6].r.q, dut.cpu.regs.v_hex[7].r.q, dut.cpu.regs.v_hex[8].r.q,
                dut.cpu.regs.v_hex[9].r.q, dut.cpu.regs.v_hex[10].r.q, dut.cpu.regs.v_hex[11].r.q,
                dut.cpu.regs.v_hex[12].r.q, dut.cpu.regs.v_hex[13].r.q, dut.cpu.regs.v_hex[14].r.q,
                dut.cpu.regs.v_hex[15].r.q, dut.cpu.i, dut.cpu.sp, dut.cpu.dt, dut.cpu.st);
        end
    end
endmodule
