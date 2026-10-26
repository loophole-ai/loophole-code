# Loophole IDE: build repo

This is a fork of [VSCodium](https://github.com/VSCodium/vscodium)'s build pipeline. It does not contain VS Code's
source: CI fetches Microsoft's VS Code at the commit pinned in `upstream/stable.json`, applies VSCodium's patches plus
our branding, bundles the agent extension, and produces installers.

## What we changed vs upstream VSCodium (keep this list short!)

| File | Change |
|---|---|
| `product.json` | Loophole identity: names, bundle id, **fresh Windows GUIDs** (never reuse another product's) |
| `prepare_loophole.sh` + 1 line in `prepare_vscode.sh` | Re-points installer metadata and project URLs that upstream hardcodes to "VSCodium" |
| `build_agent_extension.sh`, `build/agent/` | Builds the agent extension (our Kilo fork) and injects it as a built-in extension |
| `build.sh`, `build/linux/package_bin.sh`, `build/windows/package.sh` | One line each: call the script above right before packaging |
| `.github/workflows/ci-build-*.yml` | `APP_NAME`/`BINARY_NAME`, `DISABLE_UPDATE`, `AGENT_*` passed to the packaging step |
| `.github/workflows/publish-*.yml` | Removed (VSCodium's own release/store publishing) |
| `icons/loophole/`, `src/stable/resources/**`, `build/windows/msi/resources/stable/` | All app, installer, file-type and watermark images, generated from one vector mark by `icons/loophole/build_icons.py` |
| `dev/verify-patches.sh` | Fast check that every patch still applies (no compile) |

Custom core patches (when an extension can't do something) go in `patches/user/*.patch`.

## Changing the logo

Replace `icons/loophole/source-logo.png` (white mark on a dark square, 1024px or larger is best) and run:

```
pip install pillow potracer numpy
./dev/verify-patches.sh            # creates the vscode/ checkout the file-type icons are built from
python3 icons/loophole/build_icons.py --retrace icons/loophole/source-logo.png
```

Commit the regenerated files. Only the **stable** channel is generated; `src/insider/` and `icons/insider/` are unused leftovers from upstream.

## First build

1. Fork `VSCodium/vscodium` on GitHub, apply this change (`git am 0001-*.patch`), push.
2. Repo **Settings → Secrets and variables → Actions**:
   - Variable `AGENT_REPO` = `your-org/your-kilo-fork` (leave unset to build a plain branded IDE first, recommended)
   - Variable `AGENT_REF` = branch or tag (optional)
   - Secret `AGENT_TOKEN` = fine-grained token with *Contents: read* on that repo (only if private)
3. For the first run only, add variables `DISABLE_STABLE_LINUX_APP_ARM64`, `..._ARM32`, `..._RISCV64`, `..._LOONG64`,
   `..._PPC64` = `yes` so only linux-x64 builds. Leave the macOS and Windows workflows disabled in the Actions tab for now.
4. **Actions → CI - Build - Linux → Run workflow**, tick **Generate assets**. Binaries appear under the run's *Artifacts*.
5. Once that works: set `AGENT_REPO`, re-run, then enable macOS and Windows.

## Known limits

- Agent engine is compiled on the build machine, so it is injected only when the runner's CPU matches the target.
  Windows arm64 (built on an x64 runner), armhf, riscv64, loong64, ppc64le therefore ship **without** the agent.
- Windows MSI is switched off (`SHOULD_BUILD_MSI: 'no'` in `ci-build-windows.yml`): upstream's MSI still uses VSCodium's
  upgrade code, GUIDs and file names and must be rebranded first. The `.exe` installers and the zip are built.
- Installers are unsigned. macOS needs signing + notarization to open without a warning; Windows shows SmartScreen.
- Auto-update is disabled (`DISABLE_UPDATE=yes`) until we have our own versions feed.
- Upgrading VS Code: bump `upstream/stable.json`, run `dev/verify-patches.sh`, fix any patch that no longer applies.
