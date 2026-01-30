#!/bin/zsh
# Launch menubar monitor for Moon transits

cd /Users/Tom/flymoon
python3 menubar_monitor.py \
  --latitude 21.659 \
  --longitude -105.22 \
  --elevation 0 \
  --target moon \
  --interval 15 \
  > /dev/null 2>&1 &

echo "Transit Monitor (Moon) started. Check your menu bar for the 🌙 icon."
