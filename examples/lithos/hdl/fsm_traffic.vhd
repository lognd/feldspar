-- fsm_traffic.vhd -- foreign fixture for cuprite/09 matrix rows:
--   FSMs (case-based or enum types) | VHDL enums / typed signals
-- VHDL-2008, synthesizable, self-contained. Embedded by
-- fsm_traffic.cupr via `by extern("fsm_traffic.vhd", vhdl2008)` --
-- OPAQUE-with-contracts in v1 (cuprite 09 sec. 3): pinned artifact,
-- retro-declared contract, equivalence by simulation comparison.
--
-- A traffic-light controller: enumerated state type, one clocked
-- process for state, one combinational process for next-state and
-- outputs, a pedestrian request latch. The classic two-process FSM.

library ieee;
use ieee.std_logic_1164.all;

entity traffic_fsm is
    generic (
        GREEN_TICKS  : natural := 30;
        YELLOW_TICKS : natural := 5
    );
    port (
        clk     : in  std_logic;
        rst_n   : in  std_logic;
        tick    : in  std_logic;   -- 1 Hz enable strobe
        ped_req : in  std_logic;   -- pedestrian button
        lamp_r  : out std_logic;
        lamp_y  : out std_logic;
        lamp_g  : out std_logic;
        walk    : out std_logic
    );
end entity traffic_fsm;

architecture rtl of traffic_fsm is

    type state_t is (S_RED, S_GREEN, S_YELLOW);

    signal state, state_nxt : state_t;
    -- Range allows GREEN_TICKS + 1: the default increment in nxt_p is
    -- evaluated (and subtype-checked) even on iterations where a case
    -- branch overrides it with 0.
    signal timer, timer_nxt : natural range 0 to GREEN_TICKS + 1;
    signal ped_latch        : std_logic;

begin

    -- State register: the clocked process.
    reg_p : process (clk, rst_n) is
    begin
        if rst_n = '0' then
            state     <= S_RED;
            timer     <= 0;
            ped_latch <= '0';
        elsif rising_edge(clk) then
            if ped_req = '1' then
                ped_latch <= '1';
            elsif state = S_RED then
                ped_latch <= '0';
            end if;
            if tick = '1' then
                state <= state_nxt;
                timer <= timer_nxt;
            end if;
        end if;
    end process reg_p;

    -- Next-state and timer: the combinational process, full case
    -- over the enum (no others clause needed: all choices covered).
    nxt_p : process (state, timer, ped_latch) is
    begin
        state_nxt <= state;
        timer_nxt <= timer + 1;
        case state is
            when S_RED =>
                if timer >= YELLOW_TICKS then
                    state_nxt <= S_GREEN;
                    timer_nxt <= 0;
                end if;
            when S_GREEN =>
                if timer >= GREEN_TICKS or ped_latch = '1' then
                    state_nxt <= S_YELLOW;
                    timer_nxt <= 0;
                end if;
            when S_YELLOW =>
                if timer >= YELLOW_TICKS then
                    state_nxt <= S_RED;
                    timer_nxt <= 0;
                end if;
        end case;
    end process nxt_p;

    -- Moore outputs, decoded from state alone.
    lamp_r <= '1' when state = S_RED    else '0';
    lamp_y <= '1' when state = S_YELLOW else '0';
    lamp_g <= '1' when state = S_GREEN  else '0';
    walk   <= '1' when state = S_RED    else '0';

end architecture rtl;
