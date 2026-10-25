#!/usr/bin/env bash
# shellcheck disable=SC1091
# Sourced at the end of prepare_vscode.sh (cwd = vscode/). Re-points the installer/package metadata that
# upstream VSCodium hardcodes to "VSCodium"/"codium" at our own name, so upstream merges stay small:
# prepare_vscode.sh is untouched apart from one line that sources this file.

LOOPHOLE_URL="https://github.com/${GH_REPO_PATH}"

# display name + maintainer text (upstream already rewrote "Visual Studio Code" -> "VSCodium" in these)
for f in \
  package.json \
  build/lib/electron.ts \
  build/win32/code.iss \
  resources/linux/code.appdata.xml \
  resources/linux/debian/control.template \
  resources/linux/rpm/code.spec.template; do
  [[ -f "${f}" ]] || continue
  replace "s~https://github.com/VSCodium/vscodium(/graphs/contributors|#download-install)?~${LOOPHOLE_URL}~g" "${f}"
  replace "s~https://vscodium.com(/img/vscodium.png)?~${LOOPHOLE_URL}~g" "${f}"
  replace "s|VSCodium Team|${ORG_NAME}|g" "${f}"
  replace "s|VSCodium|${APP_NAME}|g" "${f}"
done

# upstream rewrites code-oss -> codium in the deb postinst; point it at our binary instead
if [[ -f resources/linux/debian/postinst.template ]]; then
  replace "s|codium|${BINARY_NAME}|g" resources/linux/debian/postinst.template
fi

# project links come from the repo this build runs in (GH_REPO_PATH), not a hardcoded name
setpath "product" "licenseUrl" "${LOOPHOLE_URL}/blob/master/LICENSE"
setpath "product" "reportIssueUrl" "${LOOPHOLE_URL}/issues/new"
setpath "product" "downloadUrl" "${LOOPHOLE_URL}/releases"
