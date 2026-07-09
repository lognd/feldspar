// alu_generic.sv -- foreign fixture for cuprite/09 matrix rows:
//   parameters/generics | generate loops / arrays of instances
// SystemVerilog-2017, synthesizable, self-contained. Embedded by
// alu_generic.cupr via `by extern("alu_generic.sv", sv2017)` --
// OPAQUE-with-contracts in v1 (cuprite 09 sec. 3): linked as a
// pinned artifact with a retro-declared contract; the equivalence
// obligation discharges by simulation comparison, not elaboration.
//
// A width-parameterized ALU built from per-bit slices via a generate
// loop, with a typedef'd opcode enum -- the textbook shape of the
// two feature classes this fixture proves.

module alu_slice (
    input  logic a,
    input  logic b,
    input  logic cin,
    input  logic [1:0] op,     // 00 add, 01 and, 10 or, 11 xor
    output logic y,
    output logic cout
);
    always_comb begin
        unique case (op)
            2'b00:   {cout, y} = {1'b0, a} + {1'b0, b} + {1'b0, cin};
            2'b01:   {cout, y} = {1'b0, a & b};
            2'b10:   {cout, y} = {1'b0, a | b};
            default: {cout, y} = {1'b0, a ^ b};
        endcase
    end
endmodule

module alu_generic #(
    parameter int W = 8
) (
    input  logic [W-1:0] a,
    input  logic [W-1:0] b,
    input  logic [1:0]   op,
    output logic [W-1:0] y,
    output logic         cout
);

    typedef enum logic [1:0] {
        OP_ADD = 2'b00,
        OP_AND = 2'b01,
        OP_OR  = 2'b10,
        OP_XOR = 2'b11
    } opcode_e;

    logic [W:0] carry;
    assign carry[0] = 1'b0;

    // The generate row: W structurally identical slices, ripple
    // carry. In cuprite this textual expansion is an ORBIT -- a
    // checked symmetry fact, not W copies of text.
    genvar i;
    generate
        for (i = 0; i < W; i = i + 1) begin : g_slice
            alu_slice u_slice (
                .a    (a[i]),
                .b    (b[i]),
                .cin  (carry[i]),
                .op   (op),
                .y    (y[i]),
                .cout (carry[i+1])
            );
        end
    endgenerate

    assign cout = carry[W];

endmodule
