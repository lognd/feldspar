"""The M9 acceptance criterion, run FROM THE PACK'S OWN test session
(WO-19: "a toy out-of-repo pack passing the kit from its own CI"): one
line, `assert_solverpack_conforms(register)`. This file is the whole
point of `fixtures/toy_solver_pack` existing -- it is the proof that
`feldspar.testing.assert_solverpack_conforms` is real plug-and-play
usable by a pack author who has never seen feldspar's own test suite."""

from toy_bearings import register

from feldspar.testing import assert_solverpack_conforms


def test_toy_bearings_conforms() -> None:
    assert_solverpack_conforms(register, name="toy_bearings", version="0.1.0")
