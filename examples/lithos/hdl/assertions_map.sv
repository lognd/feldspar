// assertions_map.sv -- foreign fixture for cuprite/09 sec. 2 rows:
//   SVA immediate assertions | SVA concurrent properties (PARTIAL) |
//   covergroups (DIFFERENT BY DESIGN)
// SystemVerilog-2017 (verification subset; simulation-legal, checker
// content is not synthesized). Embedded by assertions_map.cupr.
//
// TWO concurrent properties, chosen to sit on the two sides of the
// matrix's PARTIAL verdict:
//   p_grant_bounded -- a bounded-window implication. MAPS natively to
//       the temporal claim vocabulary (`within d after e`).
//   p_burst_shape   -- consecutive-repetition + `throughout` sequence
//       algebra. Does NOT map natively; stays here, and its
//       simulation run enters regolith as `by test(...)` evidence.
// Plus one immediate assertion and one covergroup, for their rows.

module req_gnt_checker (
    input logic       clk,
    input logic       rst_n,
    input logic       req,
    input logic       gnt,
    input logic       busy,
    input logic       done,
    input logic       valid,
    input logic [1:0] prio
);

    // Immediate assertion row: maps FULLY to a `require:` comparison.
    always_comb begin
        a_prio_legal : assert (prio != 2'b11)
            else $error("prio 3 is reserved");
    end

    // Bounded-window property: req must be granted in 1..4 cycles.
    // THIS ONE MAPS: `within 4 cycles after req: gnt` on the cuprite
    // side, same clock, same disable condition (reset window).
    property p_grant_bounded;
        @(posedge clk) disable iff (!rst_n)
            req |-> ##[1:4] gnt;
    endproperty
    a_grant_bounded : assert property (p_grant_bounded);

    // Deep sequence property: after a grant, busy holds for 2 to 5
    // consecutive cycles, then exactly one done -- and valid must
    // hold THROUGHOUT the busy-to-done window. Consecutive repetition
    // ([*2:5]) and `throughout` are sequence-algebra operators with
    // no native cuprite temporal-claim equivalent (deliberately --
    // matrix sec. 2). The property stays HERE; its simulation run is
    // the evidence.
    property p_burst_shape;
        @(posedge clk) disable iff (!rst_n)
            gnt |=> (valid throughout (busy [*2:5] ##1 done));
    endproperty
    a_burst_shape : assert property (p_burst_shape);

    // Covergroup row: stimulus coverage lives WITH the testbench (this
    // file), and enters regolith through the evidence coverage
    // statement -- regolith states coverage of CLAIM domains instead.
    covergroup cg_prio @(posedge clk);
        coverpoint prio {
            bins low  = {2'b00};
            bins mid  = {2'b01};
            bins high = {2'b10};
        }
        coverpoint req;
        req_x_prio : cross prio, req;
    endgroup

    cg_prio cov = new();

endmodule
