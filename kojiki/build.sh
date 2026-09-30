#!/usr/bin/env bash
# Full pipeline: frames (headless Chromium/WebGL2) -> score (numpy) -> H.264/AAC mp4
set -euo pipefail
cd "$(dirname "$0")"
export NODE_PATH="${NODE_PATH:-$(npm root -g)}"
TOTAL=$(python3 -c "import json;t=json.load(open('timeline.json'));print(round(t['duration']*t['fps']))")
HALF=$((TOTAL/2))
node render.js --frames 0 $HALF & node render.js --frames $HALF $TOTAL & wait
python3 audio.py
ffmpeg -y -framerate 24 -i out/frames/f_%05d.jpg -i out/score.wav \
  -vf "scale=1920:1080:flags=lanczos" -c:v libx264 -preset slow -crf 16 -pix_fmt yuv420p -tune film \
  -af "loudnorm=I=-16:TP=-1.0:LRA=14" -c:a aac -b:a 256k -ar 48000 -shortest -movflags +faststart out/kojiki.mp4
echo "done -> out/kojiki.mp4"
