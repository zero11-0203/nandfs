# The CHIP-8 machine

CHIP-8 is a small virtual machine from 1977, first run as an interpreter on
the RCA COSMAC VIP. It has 4 KB of memory, sixteen 8-bit registers, a 64×32
monochrome screen, a hex keypad, two 60 Hz timers and 35 two-byte
instructions. There are hundreds of games for it, many in the public domain.
It's small enough to build from gates and big enough to play Pong on.

Here it is real hardware: `hw/chip8/chip8.v`, synthesized to NAND gates and
flip-flops, with nothing emulated in software.

## Where things are

```
chip8/
  clockgen/         counters that divide the master clock into slots and frames
  cpu/              the state machine; pc, i, sp, the fetched opcode (hi, lo)
    regs/v0 .. vf/  sixteen 8-bit registers, q_0.dff .. q_7.dff each
    stack/          sixteen 12-bit return addresses
    timers/         dt and st, the delay and sound timers
  memory/
    ram/h0 .. hf/   4 KB as a 16×16×16 tree: byte 0x5A3 is ram/h5/ha/h3/
    font/           the 80-byte hex digit font, as gates tied to vcc and gnd
  display/r0 .. r31/  one folder per screen row; px_0.dff .. px_63.dff
  pins/keys/        sixteen input pins, one per key
  keys              bus over the key pins: echo 4 > chip8/keys holds key 2
  buzzer            1 while the sound timer is running
  icount            instructions completed, mod 65536
```

Every register also has a bus, so `cat chip8/cpu/pc`, `cat chip8/cpu/i` and
`cat chip8/display/r5/px` print numbers.

| | |
|---|---|
| NAND gates | 327,027 |
| D flip-flops | 35,251 (32,768 of them RAM, 2,048 screen) |
| Folders / symlinks / regular files | 397,832 / 811,680 / 35,267 |
| On disk | 3.3 GB, nearly all of it directory blocks; the files hold 12 MB |

## Timing

The master clock runs at 23,040 Hz. The clock generator cuts it into slots of
32 ticks, and every slot starts exactly one instruction, which always
finishes within the slot. Twelve slots make a 60 Hz frame. So the machine runs
720 instructions per second, the timers count down once per frame, and there
are no cycle-counting surprises: every instruction takes one slot.

`DXYN` (draw a sprite) waits for the start of the next frame, as on the VIP,
and then draws one sprite row per tick. `00E0` clears the screen in one tick.
`FX33` converts to decimal with a shift-and-add-3 circuit that is only fed
while it is in use. `CXNN` takes its random number from a 16-bit LFSR that
steps once per slot, so runs are repeatable. `FX0A` waits for a key to be
pressed and released.

## Quirks

CHIP-8 interpreters disagree on a handful of details. This machine does what
the COSMAC VIP did:

- `8XY1`, `8XY2` and `8XY3` reset VF.
- `8XY6` and `8XYE` shift VY and store the result in VX.
- `FX55` and `FX65` leave I pointing past the last register.
- `BNNN` jumps to V0 + NNN.
- Sprites wrap their starting position but clip at the screen edge.
- `DXYN` waits for the next frame (display wait).
- I is 12 bits wide.

Timendus' quirks test passes with the VIP profile. Games written for modern
interpreters, which run hundreds of instructions per frame and don't wait for
the display, are playable but slow.

## The reference

`tools/chip8ref.py` is a 270-line Python emulator that models this hardware
exactly, down to which slot each instruction runs in. It is the
specification. Every test compares a machine against it: after every
instruction, the program counter, V0 to VF, I, SP and both timers must match,
and at the end of the run so must the screen.

`tests/suite.txt` lists the programs:

- six focused tests of our own in `roms/tests/` (ALU, drawing, control flow,
  keys, memory, timers), assembled by `tools/c8asm.py`
- Timendus' CHIP-8 test suite: the CHIP-8 logo, the IBM logo, the corax+
  opcode test, the flags test and the quirks test
- Pong (`roms/pong.asm`)
- two games from the CHIP-8 archive, dinorun and br8kout

They run at two levels:

1. `tests/lockstep_verilog.py`: the Verilog in Icarus against the reference.
   No folders are involved, so a logic bug shows up here first.
2. `tests/lockstep_folders.py`: the mounted folder machine against the
   reference. It clocks the machine 32 ticks at a time through `.ctl/clock`,
   and every time `icount` moves it reads the state the same way you would,
   with `cat chip8/cpu/pc` and friends.

All 14 programs match instruction for instruction at both levels.

## Writing programs

`tools/c8asm.py` is a small assembler using Cowgod's mnemonics:

```
loop:   LD V0, 0x12      ; comments start with ;
        ADD V0, V1
        LD I, sprite
        DRW V0, V1, 5
        JP loop
sprite: db 0xF0, 0x90, 0x90, 0x90, 0xF0
```

`scripts/play.sh` accepts `.asm` files directly, as well as `.ch8` binaries.
A test program can have a key script next to it (`keys.keys` for `keys.asm`)
that says which keys are held from which slot on.

## Loading a game

There's no loader circuit. `tools/loadrom.py` writes the `init` file of each
RAM flip-flop whose value changes, then writes `1` to `.ctl/reset`, which sets
every flip-flop to its `init` value. That's the folder version of flashing a
ROM chip.
