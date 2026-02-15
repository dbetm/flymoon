#!/bin/zsh
# Launch menubar monitor for Moon transits

# TODO: we can't assume all the user have the project at home, need a refactor to be able to pass the route
# issue oppened #
cd ~/flymoon
python3 menubar_monitor.py \
  --latitude 21.659 \
  --longitude -105.22 \
  --elevation 0 \
  --target moon \
  --interval 15 \
  > /dev/null 2>&1 &

echo "Transit Monitor (Moon) started. Check your menu bar for the 🌙 icon."
