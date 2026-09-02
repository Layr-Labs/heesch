"""`#PROOF` block grammar (architecture §13.2) — every field is checked, the
block must be last, and `--emit-epoch` strips it."""

import pytest

from util import ROOT, domino_hc1, monomino_hc1  # noqa: F401

from heesch_verify import cli
from heesch_verify.parse import ProofBlock, parse_submission
from heesch_verify.result import ErrorCode, VerifyError

H = "a" * 64
G = "b" * 64


def block(m=2, enc="heesch-encoder/v2", revision="2", cnf=H, nv="10", nc="20",
          name="proof.drat", fmt="drat", comp="none", payload=G, header="#PROOF 1"):
    return (f"{header}\nencoder {enc} {revision} {m}\ncnf {cnf} {nv} {nc}\n"
            f"file {name} {fmt} {comp} {payload}\n")


def test_valid_block_round_trips():
    sub = parse_submission(monomino_hc1() + block())
    assert sub.proof == ProofBlock(
        m=2, encoder_version="heesch-encoder/v2", revision=2, cnf_digest=H, num_vars=10,
        num_clauses=20, file_name="proof.drat", fmt="drat", compression="none",
        payload_sha256=G,
    )


def test_xz_and_lrat_forms():
    assert parse_submission(monomino_hc1() + block(name="p.lrat.xz", fmt="lrat", comp="xz")).proof.compression == "xz"
    assert parse_submission(monomino_hc1() + block(name="x.lrat", fmt="lrat")).proof.fmt == "lrat"


def test_no_block_is_none():
    assert parse_submission(monomino_hc1()).proof is None


@pytest.mark.parametrize("bad", [
    block(header="#PROOF"),                # missing schema version
    block(header="#PROOF 2"),              # unknown schema
    block(header="#PROOFX 1"),             # marker must be exact (audit V7 rule)
    block(enc="heesch-encoder/v1"),        # v1 is not accepted (E8)
    block(revision="1"),
    block(m=0), block(m=9), block(m="two"),
    block(cnf="A" * 64), block(cnf="a" * 63), block(cnf="a" * 65),
    block(nv="0"), block(nc="0"), block(nv="-1"),
    block(name="../proof.drat"), block(name="sub/proof.drat"), block(name="-S.drat"),
    block(name=".proof.drat"), block(name="best.heesch"), block(name="p" * 70 + ".drat"),
    block(name="proof.lrat"),              # extension/format mismatch
    block(name="proof.drat", comp="xz"),   # xz requires .xz suffix
    block(name="proof.drat.xz", comp="none"),
    block(fmt="lrat"),                     # name says drat
    block(fmt="binary"), block(comp="gz"),
    block(payload="z" * 64),
    block() + "trailing 1\n",
    block() + block(),                     # duplicate
    block().replace("\ncnf ", "\ncnf extra "),   # arity
    "#PROOF 1\nencoder heesch-encoder/v2 2 2\n",  # truncated block
])
def test_bad_blocks_are_parse_syntax(bad):
    with pytest.raises(VerifyError) as ei:
        parse_submission(monomino_hc1() + bad)
    assert ei.value.code is ErrorCode.PARSE_SYNTAX


def test_marker_must_be_exact_token():
    # '#PROOFX 1' is not a marker: it is trailing garbage -> PARSE_SYNTAX, and
    # never a proof block.
    with pytest.raises(VerifyError):
        parse_submission(monomino_hc1() + block(header="#PROOFX 1"))


def test_defect_must_precede_proof():
    defect = "#DEFECT 2 0 0 0\n0\n"
    ok = parse_submission(monomino_hc1() + defect + block())
    assert ok.defect is not None and ok.proof is not None
    with pytest.raises(VerifyError) as ei:
        parse_submission(monomino_hc1() + block() + defect)
    assert ei.value.code is ErrorCode.PARSE_SYNTAX
    assert "precede" in ei.value.message


def test_stray_proof_marker_inside_patch_is_count_mismatch():
    text = monomino_hc1().replace("~ 1 1 1\n9\n", "~ 1 1 1\n10\n") + block()
    with pytest.raises(VerifyError) as ei:
        parse_submission(text)
    assert ei.value.code is ErrorCode.PARSE_COUNT_MISMATCH
    assert "#PROOF" in ei.value.message


def test_emit_epoch_strips_proof_block(tmp_path):
    src = tmp_path / "in.heesch"
    out = tmp_path / "out.txt"
    src.write_text(monomino_hc1() + "#DEFECT 2 0 0 0\n0\n" + block(), encoding="ascii")
    assert cli.main([str(src), "--emit-epoch", str(out)]) == 0
    body = out.read_text()
    assert "#PROOF" not in body and "#DEFECT" not in body
    assert body == monomino_hc1()
    src.write_text(monomino_hc1() + block(), encoding="ascii")
    assert cli.main([str(src), "--emit-epoch", str(out)]) == 0
    assert out.read_text() == monomino_hc1()


CORE = "core core.txt.xz xz " + "c" * 64 + " 6305\n"


def test_core_line_round_trips():
    sub = parse_submission(monomino_hc1() + block(name="p.lrat.xz", fmt="lrat", comp="xz") + CORE)
    assert sub.proof.core_file == "core.txt.xz" and sub.proof.core_compression == "xz"
    assert sub.proof.core_sha256 == "c" * 64 and sub.proof.core_clauses == 6305


@pytest.mark.parametrize("bad", [
    block() + CORE,                                                    # core with drat
    block(name="p.lrat", fmt="lrat") + "core core.txt xz " + "c" * 64 + " 5\n",   # xz says .xz
    block(name="p.lrat", fmt="lrat") + "core core.txt.xz none " + "c" * 64 + " 5\n",
    block(name="p.lrat", fmt="lrat") + "core ../c.txt none " + "c" * 64 + " 5\n",
    block(name="p.lrat", fmt="lrat") + "core p.lrat none " + "c" * 64 + " 5\n",     # same as proof
    block(name="p.lrat", fmt="lrat") + "core best.heesch none " + "c" * 64 + " 5\n",
    block(name="p.lrat", fmt="lrat") + "core c.txt none " + "C" * 64 + " 5\n",
    block(name="p.lrat", fmt="lrat") + "core c.txt none " + "c" * 64 + " 0\n",
    block(name="p.lrat", fmt="lrat") + "core c.txt none " + "c" * 64 + "\n",
    block(name="p.lrat", fmt="lrat") + CORE.replace(".xz", "") + CORE,     # duplicate core
])
def test_bad_core_lines(bad):
    with pytest.raises(VerifyError) as ei:
        parse_submission(monomino_hc1() + bad)
    assert ei.value.code is ErrorCode.PARSE_SYNTAX
