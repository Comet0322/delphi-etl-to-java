#!/usr/bin/env bash
# Seed inputs, build the legacy Pascal program and run it to produce baseline outputs.
set -euo pipefail
cd "$(dirname "$0")"
python3 seed.py
mkdir -p legacy/build
fpc -Mdelphi -FUlegacy/build -FElegacy/build legacy/src/LegacyEtl.pas >/dev/null
./legacy/build/LegacyEtl legacy/data/legacy.db legacy/data/cust_notes.txt
echo "baseline written to legacy/data/legacy.db"
