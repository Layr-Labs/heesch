"""Regenerate the frozen formula, check core membership, run native lrat-check."""
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from heesch_encoder.multilevel.api import encode_multilevel_stream
from heesch_encoder.proofcheck.core import check_and_write_core, parse_core_file
from heesch_verify import canonical_form, verify_witness
from heesch_verify.proofgate import materialize_proof
from heesch_verify.profile import STANDARD, RECORD


def main():
    v = verify_witness((HERE.parent / "best.heesch").read_text())
    sub = v.submission
    proof = sub.proof
    shape = frozenset(canonical_form(sub.cells, sub.grid, True))
    assert STANDARD.in_band(len(shape), proof.m) and RECORD.in_band(len(shape), proof.m)
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        formula = root / "formula.cnf"
        enc = encode_multilevel_stream(shape, sub.grid, v.contact, proof.m, formula)
        assert (enc.digest, enc.num_vars, enc.num_clauses) == (proof.cnf_digest, proof.num_vars, proof.num_clauses)
        for name, compression, expected, target in (
                (proof.file_name, proof.compression, proof.payload_sha256, "proof.lrat"),
                (proof.core_file, proof.core_compression, proof.core_sha256, "core.txt")):
            size, actual = materialize_proof(HERE.parent / name, root / target, compression)
            assert actual == expected
        lines = parse_core_file(str(root / "core.txt"), STANDARD.core_max_clauses, STANDARD.core_max_bytes)
        core_cnf = root / "core.cnf"
        checked = check_and_write_core(lines, str(formula), enc.num_vars, str(core_cnf))
        assert checked.num_clauses == proof.core_clauses == 146793
        default = HERE.parents[1] / "tools/bin/lrat-check"
        checker = Path(sys.argv[1]) if len(sys.argv) == 2 else default
        cp = subprocess.run([str(checker.resolve()), str(core_cnf), str(root / "proof.lrat")],
                            capture_output=True, text=True, check=True)
        assert "c VERIFIED" in cp.stdout.splitlines()
        print(f"Exact formula {enc.digest}, {enc.num_vars} variables, {enc.num_clauses} clauses.")
        print("Every one of the 146793 submitted core clauses belongs to the regenerated formula.")
        print("Both materialized payload SHA-256 digests match. Native lrat-check: c VERIFIED.")


if __name__ == "__main__":
    main()
