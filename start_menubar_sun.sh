#!/bin/zsh
# Launch menubar monitor for Sun transits

cd /Users/Tom/flymoon
python3 menubar_monitor.py \
  --latitude 21.659 \
  --longitude -105.22 \
  --elevation 0 \
  --target sun \
  --interval 15 \
  > /dev/null 2>&1 &

echo "Transit Monitor (Sun) started. Check your menu bar for the ☀️ icon."
