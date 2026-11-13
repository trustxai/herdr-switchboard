#!/usr/bin/env bash
# Install a pinned release of fzf or gitleaks for CI.
#
#   .github/scripts/install-pinned.sh <fzf|gitleaks> <destination-dir>
#
# The archive comes from the tool's GitHub release and is only unpacked after
# its SHA-256 matches the value recorded below. The values are pinned here, not
# read from the release's own checksums file, so a release asset replaced after
# the fact fails the job instead of being trusted.
#
# Why not the system package: Ubuntu's apt ships fzf 0.44 and switchboard needs
# 0.71 or newer (it relies on --id-nth). Pinning the same build on Linux and
# macOS also keeps both test legs on one fzf version.
#
# Dependabot does not see these pins. To bump one, change the version and copy
# each archive's SHA-256 from the release's checksums file (fzf_<v>_checksums.txt,
# gitleaks_<v>_checksums.txt); GitHub also shows the digest next to every asset.
set -euo pipefail

FZF_VERSION=0.74.5
GITLEAKS_VERSION=8.30.1

tool=${1:?usage: install-pinned.sh <fzf|gitleaks> <destination-dir>}
dest=${2:?usage: install-pinned.sh <fzf|gitleaks> <destination-dir>}

case "$(uname -s)/$(uname -m)" in
  Linux/x86_64)  platform=linux-amd64 ;;
  Linux/aarch64) platform=linux-arm64 ;;
  Darwin/arm64)  platform=darwin-arm64 ;;
  Darwin/x86_64) platform=darwin-amd64 ;;
  *) echo "install-pinned: unsupported platform $(uname -s)/$(uname -m)" >&2; exit 1 ;;
esac

case "$tool/$platform" in
  fzf/linux-amd64)  asset=fzf-${FZF_VERSION}-linux_amd64.tar.gz;  sha256=d47d7f882972c7d674dbbba998ffa4116e68379616ffac7695d0671e9a722c5f ;;
  fzf/linux-arm64)  asset=fzf-${FZF_VERSION}-linux_arm64.tar.gz;  sha256=cf058001da21724a469b714a29cf4aab9cbe860d218a0d6c1b5b661efad7784c ;;
  fzf/darwin-arm64) asset=fzf-${FZF_VERSION}-darwin_arm64.tar.gz; sha256=ada808c7401b9949ce8842274ac16a6b6193fd32dcada396884a6a9a89e5985a ;;
  fzf/darwin-amd64) asset=fzf-${FZF_VERSION}-darwin_amd64.tar.gz; sha256=aca6cab692e6c069e724a43070a448e18586c7c0fdd1139f6d487ec1680599ed ;;
  gitleaks/linux-amd64)  asset=gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz;    sha256=551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb ;;
  gitleaks/linux-arm64)  asset=gitleaks_${GITLEAKS_VERSION}_linux_arm64.tar.gz;  sha256=e4a487ee7ccd7d3a7f7ec08657610aa3606637dab924210b3aee62570fb4b080 ;;
  gitleaks/darwin-arm64) asset=gitleaks_${GITLEAKS_VERSION}_darwin_arm64.tar.gz; sha256=b40ab0ae55c505963e365f271a8d3846efbc170aa17f2607f13df610a9aeb6a5 ;;
  gitleaks/darwin-amd64) asset=gitleaks_${GITLEAKS_VERSION}_darwin_x64.tar.gz;   sha256=dfe101a4db2255fc85120ac7f3d25e4342c3c20cf749f2c20a18081af1952709 ;;
  *) echo "install-pinned: no pinned build of '$tool' for $platform" >&2; exit 1 ;;
esac

case "$tool" in
  fzf)      url=https://github.com/junegunn/fzf/releases/download/v${FZF_VERSION}/${asset} ;;
  gitleaks) url=https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/${asset} ;;
esac

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
  --retry 3 --retry-delay 2 --output "$work/$asset" "$url"

if command -v sha256sum >/dev/null 2>&1; then
  actual=$(sha256sum "$work/$asset" | cut -d ' ' -f 1)
else
  actual=$(shasum -a 256 "$work/$asset" | cut -d ' ' -f 1)
fi
if [ "$actual" != "$sha256" ]; then
  echo "install-pinned: checksum mismatch for $asset" >&2
  echo "  expected $sha256" >&2
  echo "  actual   $actual" >&2
  exit 1
fi
echo "install-pinned: $asset sha256 verified"

tar -xzf "$work/$asset" -C "$work" "$tool"
mkdir -p "$dest"
install -m 0755 "$work/$tool" "$dest/$tool"
"$dest/$tool" --version
