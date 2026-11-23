#!/bin/bash
# Tune every channel the way the watch page does and grab one frame from each.
# Run it inside the ErsatzTV container, so it tests the engine itself:
#
#   docker exec -i -e FIRST=2 -e LAST=55 ersatztv bash -s < scripts/test_all_channels.sh
#   docker cp ersatztv:/tmp/channel-test ./channel-test     # the frames, one PNG per channel
#
# One channel at a time on purpose: opening many at once measures disk and GPU
# contention, not the channels. Each line: channel, ffmpeg exit code, time to the
# first frame, PNG size (a few hundred bytes = a black frame; look at it), errors.
# A channel that times out is usually airing a broken file, or the GPU refused an
# encoder (GeForce cards cap simultaneous NVENC sessions: see docs/GOTCHAS.md).
FIRST=${FIRST:-1}
LAST=${LAST:-50}
OUT=${OUT:-/tmp/channel-test}
FF=$(command -v ffmpeg || echo /usr/local/bin/ffmpeg)
mkdir -p "$OUT" && rm -f "$OUT"/*
ok=0; n_total=0
for n in $(seq "$FIRST" "$LAST"); do
  n_total=$((n_total + 1))
  s=$(date +%s%N)
  timeout 45 "$FF" -nostdin -loglevel error -rw_timeout 30000000 \
    -i "http://localhost:8409/iptv/channel/$n.m3u8" \
    -ss 2 -frames:v 1 -vf scale=320:180 -y "$OUT/$n.png" 2>"$OUT/$n.err"
  rc=$?
  ms=$(( ($(date +%s%N) - s) / 1000000 ))
  sz=$(stat -c %s "$OUT/$n.png" 2>/dev/null || echo 0)
  [ "$rc" = 0 ] && ok=$((ok + 1))
  echo "$n rc=$rc ms=$ms png=$sz err=$(head -c 160 "$OUT/$n.err" | tr '\n' ' ')"
done
echo "playing: $ok of $n_total"
