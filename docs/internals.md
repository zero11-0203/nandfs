# How nandfs works

This covers the folder format, what the FUSE daemon does with it, and how a
Verilog design ends up as a few hundred thousand directories. The machines
themselves are described in [chip8.md](chip8.md) and [rv32.md](rv32.md).

## The folder format

A circuit is an ordinary directory tree. Folders whose names end in one of
these suffixes are primitives; every other folder is just a container for
organizing things (a module, a group of gates).

```
X.nand/      a, b       symlinks to the two input signals
             init       optional: the gate's output before the first settle
             out        (computed) NAND(a, b), "0" or "1"

X.dff/       d          symlink to the input signal
             init       value after reset
             q          (computed) the stored bit; takes d on each clock tick

X.pin/       value      a regular file you write 0 or 1 into
             out        (computed) the same bit, as a signal

X.bus/       0, 1, ...  symlinks to signals
             value      (computed) the bits read as one number, LSB first

X.mem/       a0, a1...  symlinks: word address
             w0..w31    symlinks: data to write
             we0..we3   symlinks: byte write enables
             data       a regular file holding the words, little endian
             r0..r31    (computed) the addressed word, one bit per file
```

At the root of the mount there are also `vcc/out` (always 1), `gnd/out`
(always 0) and `clk/out`, the clock itself. Nothing in the two machines uses
`clk/out`; it exists so a flip-flop built out of NAND gates (in
`tools/demos.py`) has something to latch on.

A signal is the path of a file that carries a bit: some gate's `out`, some
flip-flop's `q`, a pin's `out` or a memory's `rN`. A wire is a relative
symlink to such a file. Symlinks can point at other symlinks, which is how a
module's ports work: `cpu/out/mem_addr/3` is a link to the gate inside the
CPU that drives bit 3 of the memory address, and the memory, outside the
CPU, links to `cpu/out/mem_addr/3` rather than reaching in. The daemon
follows the chain until it lands on a primitive. A wire that leads nowhere
(you deleted its target, say) reads as 0, and `.ctl/stats` counts it under
`broken_wires`.

Because every link is relative, `cp -R` of any subtree gives you an
independent copy of that part of the circuit, wired the same way. (Use `-R`:
on macOS, `cp -r` follows symlinks and turns the wires into plain files.)

`.bus` and `.mem` need some justification. A bus has no behavior of its own:
it is a way to look at twelve flip-flops as one number, so that
`cat chip8/cpu/pc` prints `512`. Writing a number to a bus writes the pins and
flip-flops among its bits. It is a debugging aid, and the machines never read
a bus. `.mem` is real hardware and the one place the rules are bent; it
exists only for the RISC-V machine, which needs 24 MB of memory. See
[rv32.md](rv32.md#the-rule-change).

## The mount

`fs/nandfs.c` mounts a backing directory and passes almost everything through:
`ls`, `readlink`, `ln -s`, `rm`, `mkdir` and `mv` act on the backing tree as
usual. The daemon adds the computed files listed above and a control folder,
`.ctl/`:

| file | read | write |
|---|---|---|
| `clock` | ticks since reset | `N`: run N clock ticks now |
| `run` | current rate in Hz | `F`: tick at F Hz in the background; `0` stops |
| `reset` | | `1`: every flip-flop takes its `init` value |
| `reload` | number of loads so far | `1`: re-read the tree now |
| `stats` | gate and flip-flop counts, tick rate, gates evaluated per tick, ... | |
| `profile` | evaluations per folder, busiest first | `1` starts counting, `0` stops |

Writing to a flip-flop's `q` sets it (fault injection). Writing to a gate's
`out` is accepted and ignored, which is what lets `cp -R` copy a gate folder
through the mount.

## Evaluation

When the daemon starts, and after any structural edit, it walks the backing
tree and builds arrays: one node per primitive, and for each gate the two
nodes its symlinks resolve to. Then it does what any event-driven logic
simulator does.

1. Each gate gets a level: one more than the deepest gate feeding it.
   Feedback loops (latches built from gates) are cut where a depth-first
   search finds them.
2. When a node's value changes, the gates it feeds are queued by level. The
   queue is drained lowest level first, so a gate is normally evaluated once
   per change, after all of its inputs have settled.
3. A clock tick: every flip-flop whose `d` differs from its `q` flips, all at
   once; each `.mem` with a write enable set stores its write data at the
   current address; then the affected gates settle. If anything is wired to
   `clk/out`, it then goes high, settles, goes low and settles.
4. If a settle evaluates more than 64 times the number of gates, the circuit
   is oscillating. The daemon stops that settle and counts it in `stats`.

The gates evaluated per tick depend on how much of the circuit changes, not
on its size. Pong on the CHIP-8 averages about 85 per tick out of 327,027
gates.

The folders stay the source of truth. Every `rm`, `ln`, `mkdir` or `mv`
through the mount marks the circuit dirty, and the next read or tick loads it
again, keeping the value of every node that still exists. A big tree is
loaded once the edits have stopped for 0.2 s, so a `cp -R` of the whole
machine (a million edits) does not trigger a million loads. Loading the
CHIP-8 takes 3 to 4 seconds once its folders are in the page cache.

Edits that don't change the wiring skip the reload. Writing an `init` file
updates that one value, which is what makes loading a CHIP-8 program into
32,768 RAM flip-flops quick. Writing a `.mem`'s `data` file makes its read
bits update, as you would expect.

There used to be a second mode that answered every read by following the
symlinks on disk, recursively, with no arrays at all. It gave the same
answers and was far too slow to run either CPU, so it was removed.

## From Verilog to folders

`scripts/synth.sh` runs Yosys:

```
read_verilog -sv ...
hierarchy -check -top TOP
synth -top TOP
dfflegalize -cell $_DFF_P_ 01     # only rising-edge D flip-flops
abc -g NAND                       # only NAND and NOT gates
opt_clean -purge
write_json ...
```

`synth` keeps the module hierarchy, so the netlist still says that these
5,000 gates are the ALU and those are the stack.

`tools/netlist2folders.py` writes the netlist out:

- Each module instance becomes a folder named after the instance, with its
  gates, flip-flops and sub-instances inside. A module with more than 1,000
  primitives spreads them over `g000/`, `g001/`, ... so no directory gets
  huge.
- A gate or flip-flop is named after the net it drives when Yosys kept the
  name: `pc_3.dff` is bit 3 of `pc`. Anonymous ones are `g123.nand`.
- A `$_NOT_` becomes a NAND with both inputs on the same wire.
- Every instance has `in/PORT/BIT` and `out/PORT/BIT` symlinks for its ports.
- A named register of 2 to 64 flip-flops also gets a bus, so
  `cat cpu/regs/v3/q` and `cat cpu/pc` work.
- The top module's inputs become pins under `pins/`, and each top-level port
  gets a bus: `echo 5 > chip8/keys` presses key 0 and key 2.
- Instances made by a `generate` loop are named by loop and index. A loop
  whose name ends in `_hex` counts in hex, which is how the RAM gets
  `h0`..`hf`.

There is one clock domain. The generator checks that every flip-flop is
clocked by the top-level `clk` and stops if not.

## Making it fast enough

The first try was the obvious one: write `reg [7:0] mem [0:4095]` and let
Yosys build the RAM. It builds a 4,096-way decoder and a read multiplexer.
Every access changes the address lines, which feed thousands of gates, so a
single random access costs about 27,000 gate evaluations.

`hw/chip8/memtree.v` builds the same 4 KB as a tree of 16-way nodes three
levels deep. A node passes the address, data and write enable only to its
selected child and forces the others' inputs to 0. An access disturbs one
path from the root to one byte: about 850 evaluations. The same idea runs
through the rest of the CHIP-8 design: the display rows, the font and the
BCD unit only see their inputs move while they are being used.

`tests/rambench.sh` measures both designs (`hw/test/rambench.v` and
`rambench2.v`).

## Building your own circuits

`tools/circuit.py` writes folders directly from Python. The demos in
`tools/demos.py` (XOR, a full adder, an 8-bit adder, a flip-flop built from
nine NAND gates) are about 60 lines:

```python
from circuit import Tree

t = Tree("out")
a, b = t.pin("xor/a"), t.pin("xor/b")
t.port("xor/out", t.xor("xor/x", a, b))
```

```sh
python3 tools/demos.py ~/demos
scripts/mount.sh ~/demos ~/demos-mnt
cd ~/demos-mnt
echo 5 > adder8/in_a; echo 7 > adder8/in_b; cat adder8/sum     # 12
```

For anything bigger, write Verilog and use `scripts/synth.sh` and
`tools/netlist2folders.py`, as `tests/run_all.sh` does with
`hw/test/counter.v`.
