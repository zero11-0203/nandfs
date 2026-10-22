// Host memory: 2^AW words of 32 bits, read combinationally at address a; on a
// clock edge, byte k takes w[8k+7:8k] if we[k]. It is not built from gates:
// tools/netlist2folders.py turns each instance into a .mem folder whose words
// live in a file (see fs/nandfs.c). hostmem_sim.v is the model for Icarus.
(* blackbox *)
module hostmem #(parameter AW = 10) (
    input clk,
    input [AW-1:0] a,
    input [31:0] w,
    input [3:0] we,
    output [31:0] r
);
endmodule
