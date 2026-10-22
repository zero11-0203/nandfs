#!/bin/sh
# synth.sh TOP OUT.json FILE.v...: Verilog to a netlist of only NAND gates
# and rising-edge D flip-flops, keeping the module hierarchy.
#   SYNTH_OPTS   extra options for Yosys's synth (e.g. -nofsm)
set -eu
top=$1 out=$2 opts=${SYNTH_OPTS:-}
shift 2
yosys -q -l "${out%.json}.log" -p "
    read_verilog -sv $*
    hierarchy -check -top $top
    synth -top $top $opts
    dfflegalize -cell \$_DFF_P_ 01
    abc -g NAND
    opt_clean -purge
    tee -o ${out%.json}.stat stat
    write_json $out"
