#!/usr/bin/env bash
# Set up the benchmark environment. This is the ONLY step that may use the
# network. After it succeeds, ./benchmark.sh runs fully offline.
#
# Python discovery mirrors the reference challenges' toolchain discipline:
# an explicit ${PYTHON} override wins, then progressively generic names,
# gated on the version floor. The venv lives at ./.venv-bench and
# benchmark.sh re-derives it from that absolute path — exported variables do
# NOT persist between Yukon's setupCommand and benchmarkCommand.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIN_MINOR=11   # requires-python >= 3.11 (pyproject.toml)

find_python() {
  local candidate
  for candidate in "${PYTHON:-}" python3.13 python3.12 python3.11 python3 python; do
    [[ -n "${candidate}" ]] || continue
    command -v "${candidate}" >/dev/null 2>&1 || continue
    if "${candidate}" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, ${MIN_MINOR}) else 1)" 2>/dev/null; then
      command -v "${candidate}"
      return 0
    fi
  done
  return 1
}

python_bin="$(find_python)" || {
  cat >&2 <<EOF
setup.sh: no Python >= 3.${MIN_MINOR} found.

Install Python 3.${MIN_MINOR}+ or point the PYTHON environment variable at
one, e.g.:  PYTHON=/opt/python3.12/bin/python3 ./setup.sh
EOF
  exit 1
}
echo "python:  ${python_bin} ($("${python_bin}" -c 'import sys; print(sys.version.split()[0])'))"

venv="${root}/.venv-bench"
if [[ ! -x "${venv}/bin/python" && ! -x "${venv}/Scripts/python.exe" ]]; then
  "${python_bin}" -m venv "${venv}"
fi
if [[ -x "${venv}/bin/python" ]]; then
  vpy="${venv}/bin/python"
else
  vpy="${venv}/Scripts/python.exe"
fi

# The one networked step: install the harness (stdlib-only runtime deps;
# the pinned build backend comes from pyproject's [build-system]).
"${vpy}" -m pip install --quiet --upgrade pip
"${vpy}" -m pip install --quiet "${root}"

# Proof checkers (record tier, architecture §13): compiled from the vendored,
# hash-pinned sources into tools/bin. The harness locates them explicitly
# (HEESCH_CHECKER_DIR or <repo>/tools/bin) because it runs from the installed
# package. On x86-64 Linux — the benchmark runner — all three must build;
# elsewhere cake_lpr cannot, and proof-carrying submissions are rejected as
# CHECKER_UNAVAILABLE (fail closed).
if command -v cc >/dev/null 2>&1 || command -v gcc >/dev/null 2>&1; then
  bash "${root}/tools/build_checkers.sh"
else
  echo "!! no C compiler found; proof checkers not built (proof-carrying submissions will be rejected CHECKER_UNAVAILABLE)" >&2
fi
if [[ "$(uname -s)" == "Linux" && "$(uname -m)" == "x86_64" ]]; then
  for c in drat-trim lrat-check cake_lpr; do
    [[ -x "${root}/tools/bin/${c}" ]] || { echo "!! ${c} missing after build" >&2; exit 1; }
  done
fi

# Optional: bubblewrap gives benchmark.sh its no-network sandbox on Linux.
# Best effort; benchmark.sh warns and continues without it.
if [[ "$(uname -s)" == "Linux" ]] && ! command -v bwrap >/dev/null 2>&1; then
  SUDO=""
  if [[ ${EUID:-$(id -u)} -ne 0 ]] && command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
    SUDO="sudo -n"
  fi
  if command -v apt-get >/dev/null 2>&1 && [[ -n "${SUDO}" || ${EUID:-$(id -u)} -eq 0 ]]; then
    ${SUDO} apt-get install -y --no-install-recommends bubblewrap || true
  fi
fi

echo "venv:    ${vpy}"
echo "harness: $("${vpy}" -c 'import heesch_verify; print(heesch_verify.__version__)')"
