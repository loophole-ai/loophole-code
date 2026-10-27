#!/usr/bin/env bash
# Builds the Loophole agent extension (our fork of Kilo Code) for THIS machine's OS/arch and drops it
# into vscode/.build/extensions/, where VS Code's packaging step bundles it as a built-in extension.
#
# Run from inside vscode/ (the build scripts do this) right before `gulp vscode-*-min-packing`.
#
# Inputs (env):
#   AGENT_REPO   owner/name of the agent fork, e.g. loophole-ai/kilocode. Unset => skipped (plain IDE build).
#   AGENT_REF    branch or tag to build (default: the repo's default branch).
#   AGENT_TOKEN  token with read access, only needed if the repo is private.
#   AGENT_VSIX   path to a prebuilt .vsix; skips the build (used to test the injection itself).
#   AGENT_EXT_DIR  folder name inside .build/extensions (default: loophole-agent).
set -euo pipefail

if [[ -z "${AGENT_REPO:-}" && -z "${AGENT_VSIX:-}" ]]; then
  echo "build_agent_extension: AGENT_REPO not set, building the IDE without the agent extension."
  exit 0
fi

HERE="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DEST="$( pwd )/.build/extensions/${AGENT_EXT_DIR:-loophole-agent}"
ARCH="${VSCODE_ARCH:-x64}"

# The engine binary is compiled for the machine running this script, so only inject when it matches the target.
case "$( uname -m )" in
  x86_64|amd64)  HOST_ARCH=x64 ;;
  aarch64|arm64) HOST_ARCH=arm64 ;;
  *)             HOST_ARCH="$( uname -m )" ;;
esac
if [[ -z "${AGENT_VSIX:-}" && "${HOST_ARCH}" != "${ARCH}" ]]; then
  echo "build_agent_extension: WARNING host arch '${HOST_ARCH}' != target '${ARCH}'; the agent engine is not built for this target, skipping." >&2
  exit 0
fi

WORK="$( mktemp -d )"
trap 'rm -rf "${WORK}"' EXIT

if [[ -n "${AGENT_VSIX:-}" ]]; then
  VSIX="${AGENT_VSIX}"
  REQUIRE_FROM="${AGENT_REQUIRE_FROM:-$( pwd )}"
else
  CLONE_URL="https://github.com/${AGENT_REPO}.git"
  if [[ -n "${AGENT_TOKEN:-}" ]]; then
    CLONE_URL="https://x-access-token:${AGENT_TOKEN}@github.com/${AGENT_REPO}.git"
  fi
  git clone --depth 1 ${AGENT_REF:+--branch "${AGENT_REF}"} "${CLONE_URL}" "${WORK}/agent"
  # don't leave the token in the cloned repo's config
  git -C "${WORK}/agent" remote set-url origin "https://github.com/${AGENT_REPO}.git"

  # Use the exact bun the agent repo pins (its lockfile format depends on the version).
  BUN_WANT="$( node -p "(require(process.argv[1]).packageManager || '').split('@')[1] || ''" "${WORK}/agent/package.json" )"
  if [[ -n "${BUN_WANT}" ]]; then
    if ! command -v bun >/dev/null 2>&1 || [[ "$( bun --version )" != "${BUN_WANT}" ]]; then
      npm install -g "bun@${BUN_WANT}"
    fi
  else
    command -v bun >/dev/null 2>&1 || npm install -g bun
  fi
  hash -r
  echo "build_agent_extension: using bun $( bun --version )"
  pushd "${WORK}/agent" >/dev/null
  bun install --frozen-lockfile
  cd packages/kilo-vscode
  bun run package                                  # engine binary + SDK + type-check + production bundle
  bunx vsce package --no-dependencies --skip-license -o "${WORK}/agent.vsix"
  REQUIRE_FROM="$( pwd )"
  popd >/dev/null
  VSIX="${WORK}/agent.vsix"
fi

rm -rf "${DEST}"
node "${HERE}/build/agent/unzip_vsix.cjs" "${VSIX}" "${DEST}" "${REQUIRE_FROM}"
find "${DEST}" -name '*.map' -type f -delete        # source maps are large and not needed at runtime

test -f "${DEST}/package.json" || { echo "build_agent_extension: no package.json in ${DEST}" >&2; exit 1; }
# pass the path as an argument (not inside the JS string) so Git Bash on Windows converts it for node
echo "build_agent_extension: installed $( node -p "const p = require(process.argv[1]); p.name + '@' + p.version" "${DEST}/package.json" ) into ${DEST}"
