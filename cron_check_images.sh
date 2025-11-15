#!/bin/bash
# Example cron script for automated image checking
# Place this in /etc/cron.weekly/ or add to crontab

# Path to your NoteKeep installation
NOTEKEEP_DIR="/path/to/notekeep"

# Activate virtual environment if using one
source "$NOTEKEEP_DIR/.venv/bin/activate"

# Run image checking
cd "$NOTEKEEP_DIR"
python3 check_link_images.py --mode missing --batch-size 50 --max-age-days 90

# Log the run
echo "Image check completed at $(date)" >> "$NOTEKEEP_DIR/logs/image_check.log"
