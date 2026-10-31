#!/bin/sh
# reset-usb-speaker-pipewire-session.sh
# Runs in the USER's session (systemd --user), so XDG_RUNTIME_DIR is already set
# and pactl talks to this user's PipeWire directly -- no runuser/UID guessing.
#
# Two independent jobs, each with its own guard:
#   1) REPAIR    -- if the sink is muted or near-zero, unmute + restore. Condition-gated,
#                   so it runs on every login but only acts when actually broken; it never
#                   stomps a healthy, deliberately-chosen volume.
#   2) PREFERENCE-- apply PW_VOLUME once per boot (gated on the kernel boot_id), then defer
#                   to the user for the rest of that boot.
# These cover different cases, so it is not belt-and-suspenders.

# ---- configuration -----------------------------------------------------------
# Fallback defaults; /etc/default/usb-speaker (if present) is the single source of truth.
PW_VOLUME=40%
LOW_VOLUME=5            # "near-zero" threshold (percent) that counts as broken
SINK_MATCH="MV-SILICON_USB_Speaker"   # substring of the PipeWire sink name
[ -r /etc/default/usb-speaker ] && . /etc/default/usb-speaker

command -v pactl >/dev/null 2>&1 || exit 0

# ---- find the sink (retry ~5s; it can appear a beat after login) --------------
sink=""
i=0
while [ "$i" -lt 10 ]; do
	sink=$(pactl list short sinks 2>/dev/null | awk -v m="$SINK_MATCH" '$0 ~ m {print $2; exit}')
	[ -n "$sink" ] && break
	i=$((i + 1))
	sleep 0.5
done
[ -n "$sink" ] || exit 0   # speaker not in this session -> nothing to do

# ---- read current state ------------------------------------------------------
muted=$(pactl get-sink-mute "$sink" 2>/dev/null | awk '{print $2}')        # "yes"/"no"
volpct=$(pactl get-sink-volume "$sink" 2>/dev/null | grep -o '[0-9]\+%' | head -1 | tr -d '%')
[ -n "$volpct" ] || volpct=0

apply() {
	pactl set-sink-mute "$sink" 0 2>/dev/null || true
	pactl set-sink-volume "$sink" "$PW_VOLUME" 2>/dev/null || true
}

# ---- per-boot marker ---------------------------------------------------------
boot_id=$(cat /proc/sys/kernel/random/boot_id 2>/dev/null)
state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/reset-usb-speaker"
state_file="$state_dir/last-boot-id"
seen_boot=$(cat "$state_file" 2>/dev/null)

mark_boot() {
	[ -n "$boot_id" ] || return 0
	mkdir -p "$state_dir" 2>/dev/null || return 0
	printf '%s\n' "$boot_id" > "$state_file" 2>/dev/null || true
}

# ---- 1) REPAIR: only when broken (any login) ---------------------------------
if [ "$muted" = "yes" ] || [ "$volpct" -le "$LOW_VOLUME" ]; then
	apply
	mark_boot
	exit 0
fi

# ---- 2) PREFERENCE: once per boot, on a healthy sink -------------------------
if [ -n "$boot_id" ] && [ "$seen_boot" != "$boot_id" ]; then
	apply
	mark_boot
	exit 0
fi

# Healthy and preference already applied this boot -> leave the user's level alone.
exit 0
