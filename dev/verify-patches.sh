#!/usr/bin/env bash
# Fast sanity check, no compile: fetch the pinned VS Code, run prepare_vscode.sh (our branding, overlay, product.json
# and every patch) and fail if anything does not apply. `npm ci` is stubbed out. Run after bumping upstream/stable.json.
# Needs: git, jq, GNU sed (Linux). Takes a few minutes, ~1 GB disk.
set -euo pipefail
cd "$( dirname "${BASH_SOURCE[0]}" )/.."
ROOT="$( pwd )"

export VSCODE_QUALITY=stable OS_NAME="${OS_NAME:-linux}" VSCODE_ARCH="${VSCODE_ARCH:-x64}" CI_BUILD=no SHOULD_BUILD=yes DISABLE_UPDATE=yes
export MS_TAG="$( jq -r .tag upstream/stable.json )" MS_COMMIT="$( jq -r .commit upstream/stable.json )"
export RELEASE_VERSION="${MS_TAG}00000"
export APP_NAME="${APP_NAME:-Loophole}" BINARY_NAME="${BINARY_NAME:-loophole}" ORG_NAME="${ORG_NAME:-loophole-ai}"
export GH_REPO_PATH="${GH_REPO_PATH:-${ORG_NAME}/loophole-ide}"
export ASSETS_REPOSITORY="${ASSETS_REPOSITORY:-${GH_REPO_PATH}}"

if [[ ! -d vscode/.git ]]; then
  mkdir -p vscode && git -C vscode init -q && git -C vscode remote add origin https://github.com/microsoft/vscode.git
fi
git -C vscode fetch --depth 1 -q origin "${MS_COMMIT}"
git -C vscode checkout -q -f FETCH_HEAD && git -C vscode clean -fdq

# stub the heavy install step only; everything else in prepare_vscode.sh runs for real
STUBS="$( mktemp -d )"; trap 'rm -rf "${STUBS}"' EXIT
printf '#!/bin/sh\nexit 0\n' > "${STUBS}/npm"
printf '#!/bin/sh\ncase "$*" in *preinstall.ts*) exit 0;; esac\nexec "%s" "$@"\n' "$( command -v node )" > "${STUBS}/node"
chmod +x "${STUBS}/npm" "${STUBS}/node"
PATH="${STUBS}:${PATH}" bash ./prepare_vscode.sh
echo "OK: all patches applied to VS Code ${MS_TAG} (${MS_COMMIT:0:8})"
