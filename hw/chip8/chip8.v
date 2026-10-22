// A CHIP-8 computer (COSMAC VIP flavor), to be built out of NAND gates and
// flip-flops. tools/chip8ref.py is its specification: the two must agree on
// every instruction, slot for slot.
//
// Timing: the master clock is split into slots of 2^SLOT_BITS ticks. Each
// slot starts one instruction, which finishes inside it. FRAME slots make a
// 60 Hz frame; the timers count down at each frame start and DXYN waits for
// one. With the defaults the master clock is 60 * 12 * 32 = 23,040 Hz and the
// CPU runs 720 instructions per second.
//
// Design rule for speed: nothing changes unless it has to. Wide blocks (the
// memory tree, the display rows, the font) only see their inputs move while
// they are being used, so the simulator re-evaluates few gates per tick.
module chip8 #(parameter SLOT_BITS = 5, parameter FRAME = 12) (
    input clk,
    input [15:0] keys,
    output buzzer,
    output [15:0] icount
);
    wire slot_start, frame_start;
    clockgen #(SLOT_BITS, FRAME) clockgen(.clk(clk), .slot_start(slot_start),
                                          .frame_start(frame_start));

    wire [11:0] mem_addr;
    wire mem_we;
    wire [7:0] mem_din, mem_dout;
    memory memory(.clk(clk), .addr(mem_addr), .we(mem_we), .din(mem_din), .dout(mem_dout));

    wire disp_clr, disp_we, disp_hit;
    wire [4:0] disp_y;
    wire [5:0] disp_x;
    wire [7:0] disp_sprite;
    display display(.clk(clk), .clr(disp_clr), .we(disp_we), .y(disp_y), .x(disp_x),
                    .sprite(disp_sprite), .hit(disp_hit));

    cpu cpu(.clk(clk), .slot_start(slot_start), .frame_start(frame_start), .keys(keys),
            .mem_addr(mem_addr), .mem_we(mem_we), .mem_din(mem_din), .mem_dout(mem_dout),
            .disp_clr(disp_clr), .disp_we(disp_we), .disp_y(disp_y), .disp_x(disp_x),
            .disp_sprite(disp_sprite), .disp_hit(disp_hit), .buzzer(buzzer), .icount(icount));
endmodule

// Divides the master clock into instruction slots and 60 Hz frames.
module clockgen #(parameter SLOT_BITS = 5, parameter FRAME = 12) (
    input clk,
    output slot_start,
    output frame_start
);
    reg [SLOT_BITS-1:0] tick = 0;
    reg [3:0] slot = 0;
    assign slot_start = tick == 0;
    assign frame_start = slot_start && slot == 0;
    always @(posedge clk) begin
        tick <= tick + 1'b1;
        if (slot_start) slot <= slot == FRAME - 1 ? 4'd0 : slot + 1'b1;
    end
endmodule

// 4 KB of RAM, with the hex-digit font in ROM over 0x000-0x04F.
module memory(input clk, input [11:0] addr, input we, input [7:0] din, output [7:0] dout);
    wire is_font = addr < 12'h050;
    wire [7:0] font_out, ram_out;
    font font(.addr(addr[6:0] & {7{is_font}}), .dout(font_out));
    memtree #(2) ram(.clk(clk), .sel(1'b1), .addr(addr), .we(we), .din(din), .dout(ram_out));
    assign dout = is_font ? font_out : ram_out;
endmodule

// The sixteen 4x5 hex-digit sprites; every bit is a wire to vcc or gnd.
module font(input [6:0] addr, output reg [7:0] dout);
    always @* case (addr)
        0: dout = 8'hF0;  1: dout = 8'h90;  2: dout = 8'h90;  3: dout = 8'h90;  4: dout = 8'hF0;
        5: dout = 8'h20;  6: dout = 8'h60;  7: dout = 8'h20;  8: dout = 8'h20;  9: dout = 8'h70;
        10: dout = 8'hF0; 11: dout = 8'h10; 12: dout = 8'hF0; 13: dout = 8'h80; 14: dout = 8'hF0;
        15: dout = 8'hF0; 16: dout = 8'h10; 17: dout = 8'hF0; 18: dout = 8'h10; 19: dout = 8'hF0;
        20: dout = 8'h90; 21: dout = 8'h90; 22: dout = 8'hF0; 23: dout = 8'h10; 24: dout = 8'h10;
        25: dout = 8'hF0; 26: dout = 8'h80; 27: dout = 8'hF0; 28: dout = 8'h10; 29: dout = 8'hF0;
        30: dout = 8'hF0; 31: dout = 8'h80; 32: dout = 8'hF0; 33: dout = 8'h90; 34: dout = 8'hF0;
        35: dout = 8'hF0; 36: dout = 8'h10; 37: dout = 8'h20; 38: dout = 8'h40; 39: dout = 8'h40;
        40: dout = 8'hF0; 41: dout = 8'h90; 42: dout = 8'hF0; 43: dout = 8'h90; 44: dout = 8'hF0;
        45: dout = 8'hF0; 46: dout = 8'h90; 47: dout = 8'hF0; 48: dout = 8'h10; 49: dout = 8'hF0;
        50: dout = 8'hF0; 51: dout = 8'h90; 52: dout = 8'hF0; 53: dout = 8'h90; 54: dout = 8'h90;
        55: dout = 8'hE0; 56: dout = 8'h90; 57: dout = 8'hE0; 58: dout = 8'h90; 59: dout = 8'hE0;
        60: dout = 8'hF0; 61: dout = 8'h80; 62: dout = 8'h80; 63: dout = 8'h80; 64: dout = 8'hF0;
        65: dout = 8'hE0; 66: dout = 8'h90; 67: dout = 8'h90; 68: dout = 8'h90; 69: dout = 8'hE0;
        70: dout = 8'hF0; 71: dout = 8'h80; 72: dout = 8'hF0; 73: dout = 8'h80; 74: dout = 8'hF0;
        75: dout = 8'hF0; 76: dout = 8'h80; 77: dout = 8'hF0; 78: dout = 8'h80; 79: dout = 8'h80;
        default: dout = 8'h00;
    endcase
endmodule

// The 64x32 screen: 32 rows of 64 pixel flip-flops. Bit c of a row is column
// c, counted from the left. One sprite row is XORed in per tick.
module display(input clk, input clr, input we, input [4:0] y, input [5:0] x,
               input [7:0] sprite, output hit);
    wire [7:0] rev = {sprite[0], sprite[1], sprite[2], sprite[3],
                      sprite[4], sprite[5], sprite[6], sprite[7]};
    wire [63:0] mask = {56'd0, rev} << x;
    wire [31:0] sel = we ? 32'd1 << y : 32'd0;
    wire [31:0] hits;
    genvar k;
    generate
        for (k = 0; k < 32; k = k + 1) begin : r
            display_row row(.clk(clk), .clr(clr), .sel(sel[k]), .mask(mask), .hit(hits[k]));
        end
    endgenerate
    assign hit = |hits;
endmodule

module display_row(input clk, input clr, input sel, input [63:0] mask, output hit);
    reg [63:0] px = 0;
    always @(posedge clk)
        if (clr) px <= 0;
        else if (sel) px <= px ^ mask;
    assign hit = sel && |(px & mask);
endmodule

module register #(parameter W = 8) (input clk, input we, input [W-1:0] d, output reg [W-1:0] q);
    initial q = 0;
    always @(posedge clk)
        if (we) q <= d;
endmodule

// V0-VF. Port f writes VF and wins over a write to VF through port w, so an
// ALU result in VF is replaced by its flag, as on the VIP.
module regfile(input clk, input [3:0] xa, input [3:0] ya, output [7:0] x, output [7:0] y,
               output [7:0] v0, input we, input [3:0] wa, input [7:0] wd, input fwe, input fd);
    wire [127:0] all;
    genvar k;
    generate
        for (k = 0; k < 16; k = k + 1) begin : v_hex
            wire flag = fwe && k == 15;
            register #(8) r(.clk(clk), .we(flag || (we && wa == k)),
                            .d(flag ? {7'd0, fd} : wd), .q(all[8*k+7:8*k]));
        end
    endgenerate
    assign x = all[8*xa +: 8];
    assign y = all[8*ya +: 8];
    assign v0 = all[7:0];
endmodule

// Sixteen 12-bit return addresses.
module stack(input clk, input we, input [3:0] wa, input [11:0] d, input [3:0] ra, output [11:0] q);
    wire [191:0] all;
    genvar k;
    generate
        for (k = 0; k < 16; k = k + 1) begin : s_hex
            register #(12) r(.clk(clk), .we(we && wa == k), .d(d), .q(all[12*k+11:12*k]));
        end
    endgenerate
    assign q = all[12*ra +: 12];
endmodule

// Delay and sound timers, counting down once per frame.
module timers(input clk, input tick, input load_dt, input load_st, input [7:0] value,
              output reg [7:0] dt, output reg [7:0] st);
    initial begin
        dt = 0;
        st = 0;
    end
    always @(posedge clk) begin
        if (load_dt) dt <= value;
        else if (tick && dt != 0) dt <= dt - 1'b1;
        if (load_st) st <= value;
        else if (tick && st != 0) st <= st - 1'b1;
    end
endmodule

module cpu(
    input clk,
    input slot_start,
    input frame_start,
    input [15:0] keys,
    output reg [11:0] mem_addr,
    output mem_we,
    output reg [7:0] mem_din,
    input [7:0] mem_dout,
    output disp_clr,
    output disp_we,
    output [4:0] disp_y,
    output [5:0] disp_x,
    output [7:0] disp_sprite,
    input disp_hit,
    output buzzer,
    output reg [15:0] icount
);
    localparam IDLE = 4'd0, FETCH1 = 4'd1, FETCH2 = 4'd2, EXEC = 4'd3, WAIT = 4'd4,
               DRAW = 4'd5, BCD = 4'd6, STORE = 4'd7, LOAD = 4'd8;

    reg [3:0] state = IDLE;
    reg [11:0] pc = 12'h200;
    reg [11:0] i = 0;
    reg [7:0] hi = 0, lo = 0;
    reg [3:0] sp = 0;
    reg [3:0] cnt = 0;
    reg [15:0] lfsr = 16'hACE1;
    reg hit = 0;
    reg key_pressed = 0;
    reg [3:0] key_seen = 0;
    initial icount = 0;

    wire [3:0] top = hi[7:4], x = hi[3:0], y = lo[7:4], n = lo[3:0];
    wire [11:0] nnn = {hi[3:0], lo};

    // registers and stack
    wire [7:0] vx, vy, v0;
    reg we, fwe, fd;
    reg [3:0] wa;
    reg [7:0] wd;
    regfile regs(.clk(clk), .xa(x), .ya(state == STORE ? cnt : y), .x(vx), .y(vy), .v0(v0),
                 .we(we), .wa(wa), .wd(wd), .fwe(fwe), .fd(fd));
    wire [11:0] ret;
    wire call = state == EXEC && top == 4'h2;
    stack stack(.clk(clk), .we(call), .wa(sp), .d(pc), .ra(sp - 1'b1), .q(ret));

    // timers
    wire [7:0] dt, st;
    wire exec_f = state == EXEC && top == 4'hF;
    timers timers(.clk(clk), .tick(frame_start), .load_dt(exec_f && lo == 8'h15),
                  .load_st(exec_f && lo == 8'h18), .value(vx), .dt(dt), .st(st));
    assign buzzer = st != 0;

    // ALU for 8XYN
    reg [7:0] alu;
    reg alu_we, alu_fwe, alu_flag;
    always @* begin
        alu = 0;
        alu_we = 1;
        alu_fwe = 1;
        alu_flag = 0;
        case (n)
            4'h0: begin alu = vy; alu_fwe = 0; end
            4'h1: alu = vx | vy;
            4'h2: alu = vx & vy;
            4'h3: alu = vx ^ vy;
            4'h4: {alu_flag, alu} = vx + vy;
            4'h5: begin alu = vx - vy; alu_flag = vx >= vy; end
            4'h6: begin alu = vy >> 1; alu_flag = vy[0]; end
            4'h7: begin alu = vy - vx; alu_flag = vy >= vx; end
            4'hE: begin alu = vy << 1; alu_flag = vy[7]; end
            default: begin alu_we = 0; alu_fwe = 0; end
        endcase
    end

    // FX33: binary to decimal by shift-and-add-3, only fed while it is in use
    function [11:0] to_bcd(input [7:0] b);
        integer k;
        reg [19:0] s;
        begin
            s = {12'd0, b};
            for (k = 0; k < 8; k = k + 1) begin
                if (s[11:8] >= 5) s[11:8] = s[11:8] + 3;
                if (s[15:12] >= 5) s[15:12] = s[15:12] + 3;
                if (s[19:16] >= 5) s[19:16] = s[19:16] + 3;
                s = s << 1;
            end
            to_bcd = s[19:8];
        end
    endfunction
    wire [11:0] digits = to_bcd(state == BCD ? vx : 8'd0);

    // lowest key held, for FX0A
    reg [3:0] first_key;
    integer k;
    always @* begin
        first_key = 0;
        for (k = 15; k >= 0; k = k - 1)
            if (keys[k]) first_key = k;
    end
    wire key_x = keys[vx[3:0]];

    // drawing
    wire [5:0] row_y = {1'b0, vy[4:0]} + cnt;
    wire drawing = state == DRAW && cnt < n && !row_y[5];
    assign disp_we = drawing;
    assign disp_y = row_y[4:0];
    assign disp_x = state == DRAW ? vx[5:0] : 6'd0;
    assign disp_sprite = drawing ? mem_dout : 8'd0;
    assign disp_clr = state == EXEC && hi == 8'h00 && lo == 8'hE0;

    // memory
    wire [11:0] i_cnt = i + cnt;
    assign mem_we = state == BCD || state == STORE;
    always @* begin
        case (state)
            FETCH2: mem_addr = pc + 1'b1;
            DRAW, BCD, STORE, LOAD: mem_addr = i_cnt;
            default: mem_addr = pc;
        endcase
        case (cnt[1:0])
            2'd0: mem_din = state == BCD ? {4'd0, digits[11:8]} : vy;
            2'd1: mem_din = state == BCD ? {4'd0, digits[7:4]} : vy;
            default: mem_din = state == BCD ? {4'd0, digits[3:0]} : vy;
        endcase
    end

    wire last = cnt == x;
    wire draw_done = state == DRAW && !drawing;

    // register writes
    always @* begin
        we = 0;
        wa = x;
        wd = 0;
        fwe = 0;
        fd = 0;
        if (state == EXEC) begin
            case (top)
                4'h6: begin we = 1; wd = lo; end
                4'h7: begin we = 1; wd = vx + lo; end
                4'h8: begin we = alu_we; wd = alu; fwe = alu_fwe; fd = alu_flag; end
                4'hC: begin we = 1; wd = lfsr[7:0] & lo; end
                4'hF: begin
                    if (lo == 8'h07) begin we = 1; wd = dt; end
                    if (lo == 8'h0A && key_pressed && !keys[key_seen]) begin
                        we = 1;
                        wd = {4'd0, key_seen};
                    end
                end
                default: ;
            endcase
        end else if (draw_done) begin
            fwe = 1;
            fd = hit;
        end else if (state == LOAD) begin
            we = 1;
            wa = cnt;
            wd = mem_dout;
        end
    end

    wire retire = (state == EXEC && top != 4'hD &&
                   !(top == 4'hF && (lo == 8'h33 || lo == 8'h55 || lo == 8'h65)))
                || draw_done || (state == BCD && cnt == 2)
                || ((state == STORE || state == LOAD) && last);

    always @(posedge clk) begin
        if (slot_start) lfsr <= {lfsr[14:0], lfsr[15] ^ lfsr[13] ^ lfsr[12] ^ lfsr[10]};
        if (retire) icount <= icount + 1'b1;
        case (state)
            IDLE: if (slot_start) state <= FETCH1;
            FETCH1: begin hi <= mem_dout; state <= FETCH2; end
            FETCH2: begin lo <= mem_dout; pc <= pc + 2'd2; state <= EXEC; end
            EXEC: begin
                state <= IDLE;
                cnt <= 0;
                case (top)
                    4'h0: if (hi == 8'h00 && lo == 8'hEE) begin sp <= sp - 1'b1; pc <= ret; end
                    4'h1: pc <= nnn;
                    4'h2: begin sp <= sp + 1'b1; pc <= nnn; end
                    4'h3: if (vx == lo) pc <= pc + 2'd2;
                    4'h4: if (vx != lo) pc <= pc + 2'd2;
                    4'h5: if (n == 0 && vx == vy) pc <= pc + 2'd2;
                    4'h9: if (n == 0 && vx != vy) pc <= pc + 2'd2;
                    4'hA: i <= nnn;
                    4'hB: pc <= nnn + v0;
                    4'hD: state <= WAIT;
                    4'hE: begin
                        if (lo == 8'h9E && key_x) pc <= pc + 2'd2;
                        if (lo == 8'hA1 && !key_x) pc <= pc + 2'd2;
                    end
                    4'hF: case (lo)
                        8'h0A:
                            if (!key_pressed) begin
                                if (keys != 0) begin
                                    key_pressed <= 1;
                                    key_seen <= first_key;
                                end
                                pc <= pc - 2'd2;
                            end else if (!keys[key_seen]) key_pressed <= 0;
                            else pc <= pc - 2'd2;
                        8'h1E: i <= i + vx;
                        8'h29: i <= vx[3:0] * 5;
                        8'h33: state <= BCD;
                        8'h55: state <= STORE;
                        8'h65: state <= LOAD;
                        default: ;
                    endcase
                    default: ;
                endcase
            end
            WAIT: if (frame_start) begin state <= DRAW; cnt <= 0; hit <= 0; end
            DRAW:
                if (drawing) begin
                    cnt <= cnt + 1'b1;
                    hit <= hit | disp_hit;
                end else state <= IDLE;
            BCD: begin
                cnt <= cnt + 1'b1;
                if (cnt == 2) state <= IDLE;
            end
            STORE, LOAD: begin
                cnt <= cnt + 1'b1;
                if (last) begin
                    i <= i + x + 1'b1;
                    state <= IDLE;
                end
            end
            default: state <= IDLE;
        endcase
    end
endmodule
