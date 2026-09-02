#!/usr/bin/env bash
# Benchmark a submission.
#
#   1. Wipe the stale score.json before ANY fallible work, so a failed run
#      can never expose a result from an older invocation.
#   2. Resolve the venv created by ./setup.sh; fail closed if absent
#      (environment does not persist between Yukon's setup and benchmark
#      commands).
#   3. Run `python -I -m harness.verify`. The harness executes NO competitor
#      code — the submission is a plain-text shape file plus, optionally, a
#      proof file — but both are hostile input to our own parser and to the
#      vendored proof checkers, so on Linux the verify stage runs under
#      bubblewrap (read-only filesystem, no network, no capabilities,
#      writable only in a throwaway scratch dir) and on macOS under
#      sandbox-exec. The checkers (tools/bin, built by setup.sh) run inside
#      the same sandbox; HEESCH_CHECKER_DIR tells the harness where they are
#      (it runs from the installed package, not the source tree). If no
#      sandbox is available we warn and run unconfined (dev fallback).
#   4. The harness writes score.json into the scratch dir
#      (HEESCH_SCORE_DIR); it is copied to ./score.json only after success.
#      Nonzero exit therefore always means: no score file.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${root}"

# 1. Clean slate (review finding 2; flock pattern).
rm -f score.json

# 2. Venv from setup.sh.
if [[ -x "${root}/.venv-bench/bin/python" ]]; then
  vpy="${root}/.venv-bench/bin/python"
elif [[ -x "${root}/.venv-bench/Scripts/python.exe" ]]; then
  vpy="${root}/.venv-bench/Scripts/python.exe"
else
  echo "!! venv missing; run ./setup.sh first" >&2
  exit 1
fi

# 3. Sandboxed verification. Scratch lives under HEESCH_SCRATCH (the record
# runner's NVMe mount, docs/RUNNER.md) or the default temp dir; the harness
# derives its resource profile from this disk's free space and the machine's
# memory (heesch_verify/profile.py).
scratch="$(cd "$(mktemp -d -p "${HEESCH_SCRATCH:-${TMPDIR:-/tmp}}")" && pwd -P)"
cleanup() { [[ -z "${scratch:-}" ]] || rm -rf "${scratch}" 2>/dev/null || true; }
trap cleanup EXIT
chmod 1777 "${scratch}"   # sandboxed process may run as a different uid

run_verify=()
if command -v bwrap >/dev/null 2>&1; then
  # Unprivileged bwrap cannot configure the loopback device inside a fresh
  # network namespace on some hosts (RTM_NEWADDR EPERM on GitHub runners);
  # mirror ecdsafail's escalation: passwordless sudo, then setpriv, then
  # plain bwrap.
  bw=( bwrap )
  if [[ "$(id -u)" -ne 0 ]] && command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
    bw=( sudo -n bwrap )
  elif command -v setpriv >/dev/null 2>&1; then
    bw=( setpriv --no-new-privs bwrap )
  fi
  # With --cap-drop ALL even a root-run sandbox loses CAP_DAC_OVERRIDE and
  # cannot traverse a 0750 $HOME (GitHub runners). Re-bind the repo at a
  # world-traversable scratch-anchored path and run from there — the staging
  # move the reference challenge makes for the same reason.
  sandbox_repo="${scratch}/repo"
  mkdir -p "${sandbox_repo}"
  sandbox_vpy="${sandbox_repo}${vpy#"${root}"}"
  run_verify=(
    "${bw[@]}"
      --ro-bind / / --dev /dev --ro-bind /proc /proc
      --bind "${scratch}" "${scratch}"
      --ro-bind "${root}" "${sandbox_repo}"
      --setenv TMPDIR "${scratch}"
      --setenv HEESCH_SCORE_DIR "${scratch}"
      --setenv HEESCH_CHECKER_DIR "${sandbox_repo}/tools/bin"
      --setenv PYTHONHASHSEED 0
      --chdir "${sandbox_repo}"
      --unshare-net --unshare-ipc --unshare-uts --unshare-cgroup
      --cap-drop ALL --new-session --die-with-parent
      -- "${sandbox_vpy}" -I -m harness.verify
  )
elif [[ "$(uname -s)" == "Darwin" ]] && command -v sandbox-exec >/dev/null 2>&1; then
  profile="(version 1)(allow default)(deny network*)(deny file-write*)(allow file-write* (subpath \"${scratch}\"))(allow file-write* (subpath \"/dev\"))"
  run_verify=(
    sandbox-exec -p "${profile}"
      /usr/bin/env TMPDIR="${scratch}" HEESCH_SCORE_DIR="${scratch}"
      HEESCH_CHECKER_DIR="${root}/tools/bin" PYTHONHASHSEED=0
      "${vpy}" -I -m harness.verify
  )
else
  echo "!! no sandbox available (bubblewrap/sandbox-exec); running verify UNCONFINED (dev fallback)" >&2
  run_verify=(
    env TMPDIR="${scratch}" HEESCH_SCORE_DIR="${scratch}"
    HEESCH_CHECKER_DIR="${root}/tools/bin" PYTHONHASHSEED=0
    "${vpy}" -I -m harness.verify
  )
fi

"${run_verify[@]}"

# 4. Copy the score out only after full success.
if [[ ! -s "${scratch}/score.json" ]]; then
  echo "!! harness exited 0 but produced no score.json" >&2
  exit 1
fi
cp "${scratch}/score.json" "${root}/score.json"
