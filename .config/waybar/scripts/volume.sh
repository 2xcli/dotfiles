#!/bin/bash

# --- НАСТРОЙКИ (Твои реальные ID устройств) ---
# Steinberg UR12 (Наушники)
HEADPHONES="alsa_output.usb-Yamaha_Corporation_Steinberg_UR12-00.analog-stereo"
# Ryzen HD Audio (Колонки)
SPEAKERS="alsa_output.pci-0000_12_00.6.analog-stereo"

# --- ИКОНКИ ---
ICON_HEADPHONES="󰋋"
ICON_SPEAKERS="󰗅"
ICON_MUTED_HEADPHONES="󰋋 "
ICON_MUTED_SPEAKERS="󰗅  "  # Как ты просил: колонка + крестик

# 1. ПОЛУЧЕНИЕ ИНФОРМАЦИИ
get_status() {
    # Узнаем, кто сейчас активен
    CURRENT_SINK=$(pactl get-default-sink)
    
    # Получаем громкость (берем первую цифру процента)
    VOLUME=$(pactl get-sink-volume "$CURRENT_SINK" | grep -oP '\d+(?=%)' | head -1)
    
    # Проверяем Mute (yes/no)
    IS_MUTED=$(pactl get-sink-mute "$CURRENT_SINK" | grep -oP 'Mute: \K.*')
    
    # Определяем, какую иконку показать
    if [ "$CURRENT_SINK" == "$HEADPHONES" ]; then
        if [ "$IS_MUTED" == "yes" ]; then
             # Наушники + Мьют
            echo "$ICON_MUTED_HEADPHONES $ICON_MUTED" 
        else
            # Наушники + Громкость
            echo "$ICON_HEADPHONES $VOLUME"
        fi
    elif [ "$CURRENT_SINK" == "$SPEAKERS" ]; then
        if [ "$IS_MUTED" == "yes" ]; then
            # Колонки + Мьют
            echo "$ICON_MUTED_SPEAKERS"
        else
            # Колонки + Громкость
            echo "$ICON_SPEAKERS $VOLUME"
        fi
    else
        # Если вдруг HDMI или что-то левое
        echo "? $VOLUME"
    fi
}

# 2. УПРАВЛЕНИЕ
case "$1" in
    "increase")
        # Получаем текущую громкость
        CURRENT_VOL=$(pactl get-sink-volume @DEFAULT_SINK@ | grep -oP '\d+(?=%)' | head -1)
        
        # Если меньше 100, прибавляем
        if [ "$CURRENT_VOL" -lt 100 ]; then
            pactl set-sink-volume @DEFAULT_SINK@ +5%
        else
            # Если уже 100 или больше - ставим ровно 100 (на всякий случай)
            pactl set-sink-volume @DEFAULT_SINK@ 100%
        fi
        ;;
    "decrease")
        pactl set-sink-volume @DEFAULT_SINK@ -5%
        ;;
    "toggle_mute")
        # Мьютим ТОЛЬКО текущий
        pactl set-sink-mute @DEFAULT_SINK@ toggle
        ;;
    "switch_device")
        # Переключаем: Если сейчас Наушники -> Включаем Колонки, иначе -> Наушники
        CURRENT=$(pactl get-default-sink)
        if [ "$CURRENT" == "$HEADPHONES" ]; then
            pactl set-default-sink "$SPEAKERS"
        else
            pactl set-default-sink "$HEADPHONES"
        fi
        ;;
    *)
        get_status
        ;;
esac
