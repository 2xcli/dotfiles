#!/usr/bin/env bash

current=$(gsettings get org.gnome.desktop.interface color-scheme)

    gsettings set org.gnome.desktop.interface color-scheme prefer-light
#    sleep 1
#    gsettings set org.gnome.desktop.interface color-scheme prefer-dark
