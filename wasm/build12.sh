#!/bin/bash
set -e
SRC=~/rp/engine/src
OUT=~/rp/wasm
B=$(cat ~/rp/build_id.txt)
EXTRA=$(ls $SRC/solver/*.c)
python3 -m ziglang cc -target wasm32-wasi -O2 -s -w -ffp-contract=off -D_WASI_EMULATED_SIGNAL -DRASPIPE_BUILD="\"$B\"" \
  -D_WASI_EMULATED_PROCESS_CLOCKS -lwasi-emulated-process-clocks -lwasi-emulated-signal \
  -include /root/rp/wasm/wasi_shims.h -I$SRC/solver -I$SRC/solver/include -I$SRC/outfile/include \
  $SRC/run/main.c $EXTRA -lm -o $OUT/swmm5_rp12.wasm
ls -la $OUT/swmm5_rp12.wasm
