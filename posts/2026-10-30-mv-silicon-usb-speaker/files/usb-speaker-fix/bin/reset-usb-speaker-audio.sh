#!/bin/sh
# reset-usb-speaker-audio.sh
# Reset the MV-SILICON USB Speaker (USB 8888:1719) to known-good levels on plug-in.
#   1) ALSA hardware "PCM" control -> PCM_VOLUME  (as root; the layer that silently drifts to 0)
#   2) PipeWire sink volume        -> PW_VOLUME   (in the user's session; best effort)

# ---- configuration -----------------------------------------------------------
# Fallback defaults; /etc/default/usb-speaker (if present) is the single source of truth.
PCM_VOLUME=100%
PW_VOLUME=40%
USB_ID="8888:1719"
SINK_MATCH="MV-SILICON_USB_Speaker"   # substring of the PipeWire sink name
[ -r /etc/default/usb-speaker ] && . /etc/default/usb-speaker

# ---- 1) ALSA hardware PCM (root) ---------------------------------------------
# Resolve the card index by USB id so we don't depend on card ordering.
CARD=""
for f in /proc/asound/card*/usbid; do
	[ -r "$f" ] || continue
	if [ "$(cat "$f")" = "$USB_ID" ]; then
		d=$(dirname "$f")
		CARD=${d##*card}
		break
	fi
done

if [ -n "$CARD" ]; then
	amixer -c "$CARD" sset PCM "$PCM_VOLUME" unmute >/dev/null 2>&1 || true
fi

# ---- 2) PipeWire software volume (user session, best effort) -----------------
# Loop over active user runtime dirs; set volume in whichever session owns the sink.
# Retry for ~5s because the sink can appear a beat after the ALSA card.
i=0
while [ "$i" -lt 10 ]; do
	for rt in /run/user/*; do
		[ -d "$rt" ] || continue
		uidn=${rt##*/}
		uname=$(id -un "$uidn" 2>/dev/null) || continue
		sink=$(runuser -u "$uname" -- env XDG_RUNTIME_DIR="$rt" \
			pactl list short sinks 2>/dev/null | awk -v m="$SINK_MATCH" '$0 ~ m {print $2; exit}')
		if [ -n "$sink" ]; then
			runuser -u "$uname" -- env XDG_RUNTIME_DIR="$rt" \
				pactl set-sink-mute "$sink" 0 2>/dev/null || true
			runuser -u "$uname" -- env XDG_RUNTIME_DIR="$rt" \
				pactl set-sink-volume "$sink" "$PW_VOLUME" 2>/dev/null || true
			exit 0
		fi
	done
	i=$((i + 1))
	sleep 0.5
done
exit 0
