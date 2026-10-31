#!/bin/sh
# Install the MV-SILICON USB Speaker fix. Uses sudo.
set -eu
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

echo "Installing MV-SILICON USB Speaker fix (requires sudo)..."
if [ ! -e /etc/default/usb-speaker ]; then
	sudo install -m 644 "$DIR/etc/default/usb-speaker" /etc/default/usb-speaker
else
	echo "Keeping existing /etc/default/usb-speaker (edit it to change levels)."
fi
sudo install -m 644 "$DIR/etc/udev/rules.d/99-usb-speaker-pcm.rules" \
	/etc/udev/rules.d/99-usb-speaker-pcm.rules
sudo install -m 644 "$DIR/etc/systemd/system/reset-usb-speaker-pcm.service" \
	/etc/systemd/system/reset-usb-speaker-pcm.service
sudo install -m 755 "$DIR/bin/reset-usb-speaker-audio.sh" \
	/usr/local/bin/reset-usb-speaker-audio.sh
sudo install -m 755 "$DIR/bin/reset-usb-speaker-pipewire-session.sh" \
	/usr/local/bin/reset-usb-speaker-pipewire-session.sh
sudo install -m 644 "$DIR/etc/systemd/user/reset-usb-speaker-pipewire.service" \
	/etc/systemd/user/reset-usb-speaker-pipewire.service
sudo udevadm control --reload-rules
sudo systemctl daemon-reload
sudo systemctl --global enable reset-usb-speaker-pipewire.service
# Take effect in the current session too (best effort; ignore if no user manager):
systemctl --user daemon-reload 2>/dev/null || true
systemctl --user start reset-usb-speaker-pipewire.service 2>/dev/null || true

echo
echo "Installed. Re-plug the speaker, or apply now with:"
echo "  sudo systemctl start reset-usb-speaker-pcm.service"
echo "The PipeWire session unit runs automatically at each login (repair + once-per-boot default)."
