#!/bin/sh
# Remove the MV-SILICON USB Speaker fix. Uses sudo.
set -eu

echo "Removing MV-SILICON USB Speaker fix (requires sudo)..."
systemctl --user stop reset-usb-speaker-pipewire.service 2>/dev/null || true
sudo systemctl --global disable reset-usb-speaker-pipewire.service 2>/dev/null || true
sudo rm -f /etc/udev/rules.d/99-usb-speaker-pcm.rules
sudo rm -f /etc/systemd/system/reset-usb-speaker-pcm.service
sudo rm -f /etc/systemd/user/reset-usb-speaker-pipewire.service
sudo rm -f /usr/local/bin/reset-usb-speaker-audio.sh
sudo rm -f /usr/local/bin/reset-usb-speaker-pipewire-session.sh
sudo rm -f /etc/default/usb-speaker
sudo udevadm control --reload-rules
sudo systemctl daemon-reload

echo "Removed."
