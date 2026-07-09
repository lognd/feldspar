// dds_core.v -- quadrature DDS (direct digital synthesizer).
// Verilog-2005, synthesizable, self-contained (no $readmemh, no
// vendor primitives). This is the FOREIGN artifact linked by
// `impl DdsCore by extern("rtl/dds_core.v", verilog2005)` in
// ../dds_core.cupr; regolith never parses it -- it is hash-pinned and
// elaborated by the extern route, and its equivalence to the native
// `spec:` is a T3 obligation (formal LEC for this discrete subset).
//
// Architecture: PHASE_W-bit phase accumulator; the top 7 phase bits
// address a 32-entry quarter-wave sine LUT (2 quadrant bits + 5 index
// bits, quarter-wave symmetry folded in logic). Output is signed
// 10-bit I/Q; I leads Q by 90 degrees (I = cos, Q = sin).
// LUT entries are round(sin((i + 0.5) * pi / 64) * 511): the half-LSB
// phase offset keeps the folded waveform symmetric with no repeated
// zero sample.

module dds_core #(
    parameter PHASE_W = 32          // phase accumulator width
) (
    input  wire                clk,
    input  wire                rst_n,     // async assert, sync release
    input  wire                en,        // clock enable
    input  wire [PHASE_W-1:0]  fcw,       // frequency control word
    input  wire [PHASE_W-1:0]  phase_ofs, // static phase offset
    output reg  signed [9:0]   i_out,     // cosine channel
    output reg  signed [9:0]   q_out      // sine channel
);

    localparam OUT_W = 10;          // LUT table is 10-bit; fixed by data

    reg [PHASE_W-1:0] phase_acc;

    // Effective phase for each channel; cosine is sine advanced by a
    // quarter turn (2'b01 in the top two bits).
    wire [PHASE_W-1:0] ph_q = phase_acc + phase_ofs;
    wire [PHASE_W-1:0] ph_i = ph_q + {2'b01, {(PHASE_W-2){1'b0}}};

    // 32-entry quarter-wave amplitude LUT (unsigned magnitudes).
    function [8:0] quarter_lut;
        input [4:0] idx;
        begin
            case (idx)
                5'd0:  quarter_lut = 9'd13;
                5'd1:  quarter_lut = 9'd38;
                5'd2:  quarter_lut = 9'd63;
                5'd3:  quarter_lut = 9'd87;
                5'd4:  quarter_lut = 9'd112;
                5'd5:  quarter_lut = 9'd136;
                5'd6:  quarter_lut = 9'd160;
                5'd7:  quarter_lut = 9'd184;
                5'd8:  quarter_lut = 9'd207;
                5'd9:  quarter_lut = 9'd230;
                5'd10: quarter_lut = 9'd252;
                5'd11: quarter_lut = 9'd273;
                5'd12: quarter_lut = 9'd294;
                5'd13: quarter_lut = 9'd314;
                5'd14: quarter_lut = 9'd334;
                5'd15: quarter_lut = 9'd352;
                5'd16: quarter_lut = 9'd370;
                5'd17: quarter_lut = 9'd387;
                5'd18: quarter_lut = 9'd403;
                5'd19: quarter_lut = 9'd418;
                5'd20: quarter_lut = 9'd432;
                5'd21: quarter_lut = 9'd445;
                5'd22: quarter_lut = 9'd456;
                5'd23: quarter_lut = 9'd467;
                5'd24: quarter_lut = 9'd477;
                5'd25: quarter_lut = 9'd485;
                5'd26: quarter_lut = 9'd492;
                5'd27: quarter_lut = 9'd499;
                5'd28: quarter_lut = 9'd503;
                5'd29: quarter_lut = 9'd507;
                5'd30: quarter_lut = 9'd510;
                default: quarter_lut = 9'd511;
            endcase
        end
    endfunction

    // Fold quarter-wave symmetry: bit 6 selects sign (lower vs upper
    // half period), bit 5 selects rising vs falling quarter (index
    // reflection), bits 4:0 index the table.
    function signed [OUT_W-1:0] sine_val;
        input [6:0] p;
        reg [4:0] idx;
        reg [8:0] mag;
        begin
            idx = p[5] ? ~p[4:0] : p[4:0];
            mag = quarter_lut(idx);
            sine_val = p[6] ? -$signed({1'b0, mag})
                            :  $signed({1'b0, mag});
        end
    endfunction

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            phase_acc <= {PHASE_W{1'b0}};
            i_out     <= {OUT_W{1'b0}};
            q_out     <= {OUT_W{1'b0}};
        end else if (en) begin
            phase_acc <= phase_acc + fcw;
            i_out     <= sine_val(ph_i[PHASE_W-1:PHASE_W-7]);
            q_out     <= sine_val(ph_q[PHASE_W-1:PHASE_W-7]);
        end
    end

endmodule
