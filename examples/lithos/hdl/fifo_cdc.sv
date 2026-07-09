// fifo_cdc.sv -- foreign fixture for cuprite/09 matrix rows:
//   SV interfaces/modports | clock/reset abstraction | CDC handling
// SystemVerilog-2017, synthesizable, self-contained. Embedded by
// fifo_cdc.cupr via `by extern("fifo_cdc.sv", sv2017)` -- OPAQUE-
// with-contracts in v1 (cuprite 09 sec. 3).
//
// A dual-clock FIFO: gray-coded pointers, 2-FF synchronizers in each
// direction, an SV interface with wr/rd modports as the port bundle.
// Everything a CDC LINTER would inspect by convention here is a
// static LEDGER row on the cuprite side -- that asymmetry is the
// point of the fixture.

interface fifo_if #(
    parameter int DW = 16
) ();
    logic          valid;
    logic          ready;
    logic [DW-1:0] data;

    modport wr (output valid, output data, input  ready);
    modport rd (input  valid, input  data, output ready);
endinterface

module fifo_cdc #(
    parameter int DW = 16,
    parameter int AW = 4            // depth = 2**AW
) (
    input  logic wclk,
    input  logic wrst_n,
    input  logic rclk,
    input  logic rrst_n,
    fifo_if.rd   wr_side,           // producer drives our rd modport
    fifo_if.wr   rd_side            // we drive the consumer
);

    localparam int DEPTH = 1 << AW;

    logic [DW-1:0] mem [DEPTH];

    // Binary + gray pointers, one extra wrap bit each.
    logic [AW:0] wptr_bin, wptr_gray, rptr_bin, rptr_gray;
    // Cross-domain copies, 2-FF synchronized.
    logic [AW:0] wptr_gray_rq1, wptr_gray_rq2;
    logic [AW:0] rptr_gray_wq1, rptr_gray_wq2;

    function automatic logic [AW:0] bin2gray(input logic [AW:0] b);
        return b ^ (b >> 1);
    endfunction

    wire full  = (wptr_gray ==
                  {~rptr_gray_wq2[AW:AW-1], rptr_gray_wq2[AW-2:0]});
    wire empty = (rptr_gray == wptr_gray_rq2);

    wire wr_fire = wr_side.valid & ~full;
    wire rd_fire = rd_side.ready & ~empty;

    assign wr_side.ready = ~full;
    assign rd_side.valid = ~empty;
    assign rd_side.data  = mem[rptr_bin[AW-1:0]];

    // ---- Write domain ----
    always_ff @(posedge wclk or negedge wrst_n) begin
        if (!wrst_n) begin
            wptr_bin  <= '0;
            wptr_gray <= '0;
        end else if (wr_fire) begin
            mem[wptr_bin[AW-1:0]] <= wr_side.data;
            wptr_bin  <= wptr_bin + 1'b1;
            wptr_gray <= bin2gray(wptr_bin + 1'b1);
        end
    end

    // Read pointer into write domain: the 2-FF synchronizer. In SV
    // this is a naming convention a linter may or may not catch; in
    // cuprite it is a declared cdc_sync mating -- a ledger row.
    always_ff @(posedge wclk or negedge wrst_n) begin
        if (!wrst_n) begin
            rptr_gray_wq1 <= '0;
            rptr_gray_wq2 <= '0;
        end else begin
            rptr_gray_wq1 <= rptr_gray;
            rptr_gray_wq2 <= rptr_gray_wq1;
        end
    end

    // ---- Read domain ----
    always_ff @(posedge rclk or negedge rrst_n) begin
        if (!rrst_n) begin
            rptr_bin  <= '0;
            rptr_gray <= '0;
        end else if (rd_fire) begin
            rptr_bin  <= rptr_bin + 1'b1;
            rptr_gray <= bin2gray(rptr_bin + 1'b1);
        end
    end

    always_ff @(posedge rclk or negedge rrst_n) begin
        if (!rrst_n) begin
            wptr_gray_rq1 <= '0;
            wptr_gray_rq2 <= '0;
        end else begin
            wptr_gray_rq1 <= wptr_gray;
            wptr_gray_rq2 <= wptr_gray_rq1;
        end
    end

endmodule
