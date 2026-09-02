#!/usr/bin/env bash
# Build the proof checkers from the vendored, hash-pinned sources into
# tools/bin/. Run by setup.sh (the benchmark's only networked/build step) and
# by CI; participants can run it too — tools/prove.py uses drat-trim to
# convert DRAT to LRAT, and `python -m heesch_verify --check-proof` runs the
# same checkers the harness does.
#
# The harness demands all three checkers at record tier (cake_lpr is the
# formally-verified one and is x86-64-Linux-only). Elsewhere drat-trim and
# lrat-check still build; the harness then answers CHECKER_UNAVAILABLE for
# proof-carrying submissions, which is the intended fail-closed behaviour.
set -euo pipefail
cd "$(dirname "$0")/.."

sha256_of() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | cut -d' ' -f1
    else
        shasum -a 256 "$1" | cut -d' ' -f1
    fi
}

verify() { # file expected-sha256
    got=$(sha256_of "$1")
    if [ "$got" != "$2" ]; then
        echo "HASH MISMATCH: $1" >&2
        echo "  expected $2" >&2
        echo "  got      $got" >&2
        exit 1
    fi
}

verify third_party/drat-trim/drat-trim.c d834b649f437e091597f5347f259b9f681087f89ca0844d0cee250a1a1a0c2ee
verify third_party/drat-trim/lrat-check.c bf07c2ac96b9035da1ebcc578cb95e956a2b795629d613154cdb307f8a8f4a95
verify third_party/cake_lpr/cake_lpr.S 2f3af32d55083839b3fa0e693afd817679c0b8944bef41def05a8b0ec72b7d4a
verify third_party/cake_lpr/basis_ffi.c 8e30d84fdcb2177aa5571d7fa6661a2fae5ecfd56baa0ce49c65f9233a9f87cb

CC="${CC:-cc}"
mkdir -p tools/bin
"${CC}" -O2 -o tools/bin/drat-trim third_party/drat-trim/drat-trim.c
"${CC}" -O2 -o tools/bin/lrat-check third_party/drat-trim/lrat-check.c
if [ "$(uname -m)" = "x86_64" ] && [ "$(uname -s)" = "Linux" ]; then
    "${CC}" third_party/cake_lpr/cake_lpr.S third_party/cake_lpr/basis_ffi.c -o tools/bin/cake_lpr
else
    echo "skipping cake_lpr (x86-64 Linux only): record-tier proof checks are unavailable on this host" >&2
fi
echo "checkers built:"
ls -la tools/bin/
