#!/bin/bash

PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
WALLPAPER_DIR="$HOME/Pictures/Wpaps"
STATE_FILE="$HOME/.local/state/wallpaper_index.txt"
LOG_FILE="/tmp/wallpaper.log"
mkdir -p "$HOME/.local/state"

# Animation settings
TRANSITION="fade"
DURATION="1.2"
FPS="60"

# Ensure daemon is running
if ! pgrep -x awww-daemon >/dev/null; then
    echo "[$(date '+%H:%M:%S')] Starting awww-daemon" | tee -a "$LOG_FILE"
    awww-daemon &
    sleep 0.3
fi

# Load wallpapers
mapfile -t WALLPAPERS < <(find "$WALLPAPER_DIR" -maxdepth 1 \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.gif" -o -iname "*.png" \) | sort)

if [[ ${#WALLPAPERS[@]} -eq 0 ]]; then
    echo "No wallpapers found" | tee -a "$LOG_FILE"
    exit 1
fi

CURRENT_INDEX=$(cat "$STATE_FILE" 2>/dev/null || echo "0")

set_wallpaper() {
    local wallpaper="${WALLPAPERS[$CURRENT_INDEX]}"
    local filename=$(basename "$wallpaper")

    echo "[$(date '+%H:%M:%S')] Setting: $wallpaper" | tee -a "$LOG_FILE"

    # Apply wallpaper with animation
    awww img "$wallpaper" \
        --transition-type "$TRANSITION" \
        --transition-duration "$DURATION" \
        --transition-fps "$FPS"

    # Generate colors from the same wallpaper
    matugen image "$wallpaper" -m dark --type scheme-content --source-color-index 0 >> "$LOG_FILE" 2>&1
    if command -v pywalfox >/dev/null 2>&1; then
        pywalfox update >> "$LOG_FILE" 2>&1
    else
        echo "pywalfox not found, PATH=$PATH" >> "$LOG_FILE"
    fi

    pkill -SIGUSR2 -x btop 2>/dev/null || true

    echo "$CURRENT_INDEX" > "$STATE_FILE"
}

next_wallpaper() {
    CURRENT_INDEX=$(( (CURRENT_INDEX + 1) % ${#WALLPAPERS[@]} ))
    set_wallpaper
}

prev_wallpaper() {
    CURRENT_INDEX=$(( (CURRENT_INDEX - 1 + ${#WALLPAPERS[@]}) % ${#WALLPAPERS[@]} ))
    set_wallpaper
}

case "$1" in
    next) next_wallpaper ;;
    prev) prev_wallpaper ;;
    ""|restore) set_wallpaper ;;
    *) echo "Usage: $0 {next|prev|restore}" ;;
esac
