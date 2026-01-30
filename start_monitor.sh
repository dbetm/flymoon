#!/bin/bash
# Example script to start the transit monitor
# Edit the coordinates below to match your location

# Your observer position
LATITUDE=21.659
LONGITUDE=-105.22
ELEVATION=0

# Target: moon or sun
TARGET=moon

# Check interval in minutes
INTERVAL=15

# Activate virtual environment
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
fi

# Start monitoring (add --test flag to use cached data)
python3 monitor.py \
    --latitude $LATITUDE \
    --longitude $LONGITUDE \
    --elevation $ELEVATION \
    --target $TARGET \
    --interval $INTERVAL
