#!/usr/bin/env bash
# Build CaDiCaL (participant-side SAT solver for tools/prove.py) into
# tools/bin/cadical from a pinned release tarball. NEVER used by the harness —
# the harness only checks proofs (tools/build_checkers.sh). Why a binary:
# python-sat's in-process proof tracing holds the whole DRAT in memory (~9x the
# DRAT; 27 GB for the 11-hex F(S,7)), while `cadical formula.cnf proof.drat`
# streams it to disk — the only practical way to produce record-scale proofs
# (F(S,7)/F(S,8) at 11-20 cells, DRATs of 3-30 GB). tools/prove.py picks
# tools/bin/cadical up automatically (--solver-bin to point elsewhere).
#
#   bash tools/build_solver.sh            # needs curl|wget, tar, a C++ compiler, make
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="2.1.3"
URL="https://github.com/arminbiere/cadical/archive/refs/tags/rel-${VERSION}.tar.gz"
SHA256="abfe890aa4ccda7b8449c7ad41acb113cfb8e7e8fbf5e49369075f9b00d70465"

mkdir -p "${root}/tools/bin" "${root}/build"
tarball="${root}/build/cadical-${VERSION}.tar.gz"
if [[ ! -f "${tarball}" ]]; then
  if command -v curl >/dev/null 2>&1; then curl -sL -o "${tarball}" "${URL}"
  else wget -qO "${tarball}" "${URL}"; fi
fi
echo "${SHA256}  ${tarball}" | (command -v sha256sum >/dev/null 2>&1 && sha256sum -c - || shasum -a 256 -c -)
src="${root}/build/cadical-rel-${VERSION}"
rm -rf "${src}"
tar -xzf "${tarball}" -C "${root}/build"
( cd "${src}" && ./configure >/dev/null && make -j"$(nproc 2>/dev/null || sysctl -n hw.ncpu)" >/dev/null )
cp "${src}/build/cadical" "${root}/tools/bin/cadical"
chmod +x "${root}/tools/bin/cadical"
"${root}/tools/bin/cadical" --version
echo "built ${root}/tools/bin/cadical (CaDiCaL ${VERSION})"
