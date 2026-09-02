"""Sinz AMO local correctness (exact model counts) and §6 DIMACS byte-format
micro-tests."""

import itertools

import pytest

from conftest import FIXTURES  # noqa: F401  (sys.path bootstrap)

from heesch_encoder.amo import aux_assignment, pairwise, sequential
from heesch_encoder.api import encode
from heesch_encoder.dimacs import cnf_digest, emit_dimacs
from heesch_encoder.types import Formula, Placement
from heesch_verify.grids import GRIDS
from heesch_verify.patch import check_corona
from heesch_verify.transform import Xform


def _eval(clauses, assign):
    return all(any((l > 0) == assign.get(abs(l), False) for l in cl) for cl in clauses)


@pytest.mark.parametrize("n", [2, 3, 5, 8])
def test_sequential_amo_exact_model_count(n):
    """Over the x variables, exactly the n+1 assignments with <= 1 true must
    extend to a satisfying assignment of the Sinz clauses — and every
    at-most-one assignment must be satisfied by the canonical aux extension."""
    variables = list(range(1, n + 1))
    clauses, aux_count = sequential(variables, n + 1)
    sat_x = set()
    for bits in itertools.product([False, True], repeat=n):
        x = {variables[i]: bits[i] for i in range(n)}
        # try all aux assignments
        ok = False
        for aux_bits in itertools.product([False, True], repeat=aux_count):
            a = dict(x)
            a.update({n + 1 + i: aux_bits[i] for i in range(aux_count)})
            if _eval(clauses, a):
                ok = True
                break
        if ok:
            sat_x.add(bits)
        if sum(bits) <= 1:
            # canonical extension must work directly
            a = dict(x)
            a.update(aux_assignment(variables, n + 1, aux_count, x))
            assert _eval(clauses, a), f"canonical aux extension fails for {bits}"
    expected = {b for b in itertools.product([False, True], repeat=n) if sum(b) <= 1}
    assert sat_x == expected


def test_pairwise_amo():
    cls = pairwise([1, 2, 3])
    assert cls == [(-1, -2), (-1, -3), (-2, -3)]


def _tiny_encoding():
    grid = GRIDS["O"]
    contact = grid.contact("point")
    tile = frozenset([(0, 0)])
    corona = check_corona(tile, [(0, Xform(1, 0, 0, 0, 1, 0))], grid, contact,
                          hole_mode="hc")
    return encode(tile, corona.patch_cells, grid, contact)


def test_dimacs_format_bytes():
    enc = _tiny_encoding()
    b = enc.dimacs
    assert b.startswith(b"p cnf ")
    assert b.endswith(b" 0\n") or b.endswith(b"\n0\n")
    text = b.decode("ascii")
    lines = text.split("\n")
    header = lines[0].split()
    assert header[:2] == ["p", "cnf"]
    assert int(header[2]) == enc.num_vars
    assert int(header[3]) == enc.num_clauses == len(lines) - 2  # trailing ""
    for ln in lines[1:-1]:
        assert ln.endswith(" 0") or ln == "0"
        assert not ln.startswith(" ") and not ln.endswith("  0")
    # \n endings only, no comments, no trailing whitespace
    assert "\r" not in text and "c " not in text
    for ln in lines:
        assert ln == ln.rstrip()


def test_digest_is_sha256_of_bytes():
    enc = _tiny_encoding()
    import hashlib

    assert enc.digest == hashlib.sha256(enc.dimacs).hexdigest()


def test_empty_clause_emitted_for_unreachable_cell():
    """The slotted block has an R-cell no copy can reach (slot bottom): the
    formula must contain a real empty clause (line '0'), not short-circuit
    (§4.3)."""
    grid = GRIDS["O"]
    contact = grid.contact("point")
    cells = [(x, y) for x in range(5) for y in range(3)
             if (x, y) not in ((2, 1), (2, 2))]
    tile = frozenset(cells)
    corona = check_corona(tile, [(0, Xform(1, 0, 0, 0, 1, 0))], grid, contact,
                          hole_mode="hc")
    enc = encode(tile, corona.patch_cells, grid, contact)
    lines = enc.dimacs.decode("ascii").split("\n")
    assert "0" in lines, "no empty clause despite unreachable required cells"


def test_literal_order_within_clauses():
    enc = _tiny_encoding()
    for cl in enc.formula.clauses:
        keys = [(abs(l), l > 0) for l in cl]
        assert keys == sorted(keys)
