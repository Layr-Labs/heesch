"""AST lint: no set/dict iteration on the emission path without an explicit
sort. Blunt by design — every unordered iteration must carry an
`# ordered-ok:` pragma, and the pragma count is pinned so adding one silently
fails CI and forces review."""

import ast
import pathlib

EMISSION_MODULES = [
    "ordering.py", "placements.py", "clauses.py", "amo.py", "dimacs.py",
    "multilevel/universe.py", "multilevel/clauses.py", "multilevel/api.py",
]
PKG = pathlib.Path(__file__).parents[2] / "heesch_encoder"

EXPECTED_PRAGMAS = {
    "ordering.py": 0,
    "placements.py": 0,
    "clauses.py": 3,
    "amo.py": 0,
    "dimacs.py": 0,
    "multilevel/universe.py": 4,
    "multilevel/clauses.py": 5,
    "multilevel/api.py": 0,
}


def _suspicious_nodes(tree):
    """Yield nodes iterating over obviously-unordered containers."""
    out = []
    for node in ast.walk(tree):
        iters = []
        if isinstance(node, ast.For):
            iters.append(node.iter)
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            iters.extend(g.iter for g in node.generators)
        for it in iters:
            if isinstance(it, ast.Call):
                f = it.func
                if isinstance(f, ast.Name) and f.id in ("set", "frozenset", "dict"):
                    out.append((node.lineno, ast.dump(f)))
                if isinstance(f, ast.Attribute) and f.attr in ("keys", "values", "items"):
                    out.append((node.lineno, f.attr))
            if isinstance(it, (ast.SetComp, ast.DictComp)) or isinstance(it, ast.Set):
                out.append((node.lineno, "set-literal"))
    return out


def test_no_unordered_iteration_without_pragma():
    for mod in EMISSION_MODULES:
        src = (PKG / mod).read_text(encoding="utf-8")
        lines = src.split("\n")
        tree = ast.parse(src)
        for lineno, what in _suspicious_nodes(tree):
            line = lines[lineno - 1]
            ctx = "\n".join(lines[max(0, lineno - 2):lineno])
            assert "ordered-ok" in line or "ordered-ok" in ctx, (
                f"{mod}:{lineno} iterates an unordered container ({what}) "
                "without an '# ordered-ok:' pragma"
            )


def test_pragma_count_pinned():
    for mod, expected in EXPECTED_PRAGMAS.items():
        src = (PKG / mod).read_text(encoding="utf-8")
        count = src.count("ordered-ok")
        assert count == expected, (
            f"{mod}: {count} ordered-ok pragmas, pinned count is {expected} — "
            "review the new site and bump deliberately"
        )


def test_no_hash_or_id_in_sort_keys():
    for mod in EMISSION_MODULES:
        src = (PKG / mod).read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in ("hash", "id"), (
                    f"{mod}:{node.lineno} calls {node.func.id}()"
                )
