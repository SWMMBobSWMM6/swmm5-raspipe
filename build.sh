#!/bin/bash
# Builds the native engine into bin/. The stamp is the first 12 hex digits of the SHA-256
# of every source file, in name order, and it appears in the report as the build id.
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/src"
B=$(find solver run outfile -type f \( -name '*.c' -o -name '*.h' -o -name '*.dat' \) | LC_ALL=C sort | xargs cat | sha256sum | cut -c1-12)
mkdir -p "$ROOT/bin"
gcc -O2 -g -DRASPIPE_BUILD="\"$B\"" -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0 -ffp-contract=off -w \
    -Isolver -Isolver/include -Ioutfile/include -o "$ROOT/bin/swmm5_rp" run/main.c solver/*.c -lm
echo "build $B: $ROOT/bin/swmm5_rp"
