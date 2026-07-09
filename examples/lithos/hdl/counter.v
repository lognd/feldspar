// counter.v -- foreign fixture for cuprite/09 matrix rows:
//   module/entity+ports | hierarchy/instantiation | always_ff |
//   always_comb | typed signals
// Verilog-2005, synthesizable, self-contained. Embedded by
// counter.cupr via `by extern("counter.v", verilog2005)` (transparent
// route) with an equivalence obligation against the native `spec:`.
//
// A loadable up-counter with enable and a terminal-count output; the
// terminal-count decode lives in a SUBMODULE so the fixture exercises
// hierarchy/instantiation, not just a flat always block.

module tc_decode #(
    parameter W = 8
) (
    input  wire [W-1:0] value,
    output wire         tc
);
    // always_comb equivalent: continuous assignment.
    assign tc = &value;
endmodule

module counter #(
    parameter W = 8
) (
    input  wire         clk,
    input  wire         rst_n,   // async assert, sync release
    input  wire         en,
    input  wire         load,
    input  wire [W-1:0] d,
    output reg  [W-1:0] q,
    output wire         tc
);

    // Clocked process (the always_ff row): priority load over count.
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            q <= {W{1'b0}};
        else if (load)
            q <= d;
        else if (en)
            q <= q + {{(W-1){1'b0}}, 1'b1};
    end

    // Hierarchy row: instantiate the decode submodule.
    tc_decode #(.W(W)) u_tc (
        .value (q),
        .tc    (tc)
    );

endmodule
