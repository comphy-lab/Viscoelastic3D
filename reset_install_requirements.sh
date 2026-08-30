#!/usr/bin/env bash
# Install the CoMPhy ref-locked Basilisk tree into ./basilisk (gitignored).
set -euo pipefail

REF="${1:-v2026-08-30}"
curl -sL "https://raw.githubusercontent.com/comphy-lab/basilisk-C/${REF}/reset_install_basilisk-ref-locked.sh" \
  | bash -s -- --ref="${REF}" --hard
