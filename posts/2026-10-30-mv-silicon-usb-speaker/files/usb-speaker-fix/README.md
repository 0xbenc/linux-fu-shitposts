# MV-SILICON USB Speaker fix (USB `8888:1719`) — no sound on Linux / PipeWire

Permanent fix for a **MV-SILICON USB Speaker** that connects fine but plays **no sound** on
Linux, even though the system volume slider looks completely normal.

### Symptoms this fixes
- USB speaker is detected (`aplay -l`, `lsusb`) but is **totally silent**
- The sound slider / PipeWire volume looks fine — still no audio
- It worked before, then silently went quiet after a **reboot, replug, or suspend**
- `pavucontrol` shows the sink active and unmuted, but nothing comes out

### Affected hardware
- Any USB audio device reporting USB ID **`8888:1719`** — *"MV-SILICON USB Speaker"*.
- **MV-SILICON is the audio chip vendor**, not the speaker brand, so the same device is
  **rebadged under many brand names**. If `lsusb` shows `8888:1719`, this applies to you.
- (`8888` is a placeholder vendor ID used by low-cost OEMs — it is **not** registered with the
  USB-IF, so it isn't unique to one brand.)

---

## Root cause

Audio passes through **two** volume controls in series:

```
audio → [ PipeWire sink volume (software) ] → [ ALSA hardware "PCM" control ] → 🔊
```

If **either** is at 0, you get silence. On this speaker PipeWire selects the **digital
(`iec958`) profile**, where it can only do **software** volume — so it never touches the ALSA
hardware **`PCM`** control. Nothing else manages that control either, and it can end up stuck at
**0%**. The result: total silence while every on-screen volume looks correct.

---

## Quick manual fix

```sh
aplay -l                          # find your card number (look for "USB Speaker")
amixer -c 1 sset PCM 100% unmute  # raise the hardware PCM control (replace 1 with your card #)
```

If that restores sound, the permanent fix below stops it from happening again.

---

## Permanent fix

```sh
git clone https://github.com/0xbenc/mv-silicon-8888-1719-usb-speaker-fix.git
cd mv-silicon-8888-1719-usb-speaker-fix
./install.sh        # uses sudo
```

This installs a **udev rule** that, every time the speaker is plugged in, starts a **systemd
service** which:

1. sets the ALSA hardware **`PCM` → 100%** (the actual fix), and
2. sets the **PipeWire sink → 40%** (a sane default level; edit to taste).

It also installs a **per-user systemd service** that runs at each login, so the PipeWire half is
covered even when the speaker was **already plugged in at boot** (where the udev-triggered service
can fire before your PipeWire is up). See [Login-time PipeWire handling](#login-time-pipewire-handling).

Apply immediately without replugging:

```sh
sudo systemctl start reset-usb-speaker-pcm.service
```

---

## What gets installed

| File | Purpose |
|------|---------|
| `/etc/default/usb-speaker` | Single config (volume levels + device IDs) sourced by both scripts |
| `/etc/udev/rules.d/99-usb-speaker-pcm.rules` | Fires when USB `8888:1719` is plugged in; starts the service |
| `/etc/systemd/system/reset-usb-speaker-pcm.service` | Oneshot unit that runs the script |
| `/usr/local/bin/reset-usb-speaker-audio.sh` | Sets ALSA `PCM` (as root) + PipeWire volume (in the user session) |
| `/etc/systemd/user/reset-usb-speaker-pipewire.service` | Per-user unit; runs at login to handle the PipeWire half (enabled globally) |
| `/usr/local/bin/reset-usb-speaker-pipewire-session.sh` | Login-time PipeWire repair + once-per-boot default (runs in your session) |

The udev rule matches the **control device** (`controlC*`) only, so it fires **once per plug**,
and only after the ALSA mixer actually exists (no race).

---

## Login-time PipeWire handling

The udev-triggered service runs **as root** and resets ALSA `PCM` reliably — including for a speaker
that was already plugged in at boot (udev replays an `add` event during cold-plug). Its **PipeWire**
step, though, needs your user session to be alive, which it may not be yet at boot. So a small
**per-user** service (`reset-usb-speaker-pipewire.service`, enabled for all users) also runs at each
login and does two independent things:

1. **Repair (only when broken).** If the sink is **muted or near-zero** (`≤ 5%`), unmute and restore
   to `PW_VOLUME`. This is checked on every login but only acts when something is actually wrong, so
   it **never overrides a volume you set on purpose**.
2. **Default (once per boot).** On a healthy sink, apply `PW_VOLUME` the **first** time you log in
   after a reboot, then leave your level alone for the rest of that boot. "Once per boot" is tracked
   via the kernel `boot_id`, so it survives logout/login but resets on reboot.

These target different cases — repair fixes silence, the once-per-boot default just sets a comfortable
starting level — so they are not redundant.

---

## Configuring the levels

All levels live in one file, **`/etc/default/usb-speaker`**, which both scripts source:

```sh
PCM_VOLUME=100%   # ALSA hardware control — keep at 100% unless you have a reason not to
PW_VOLUME=40%     # PipeWire sink default (on plug-in, and once per boot at login)
LOW_VOLUME=5      # muted or ≤ this percent counts as "broken" and is repaired at login
USB_ID="8888:1719"
SINK_MATCH="MV-SILICON_USB_Speaker"
```

The scripts read it **live**, so just edit it and re-run the unit(s) — no reinstall needed:

```sh
sudo systemctl start reset-usb-speaker-pcm.service        # ALSA + plug-in PipeWire path
systemctl --user  start reset-usb-speaker-pipewire.service # login-time PipeWire path
```

(`install.sh` won't overwrite an existing `/etc/default/usb-speaker`, so your edits survive a
reinstall. The scripts also carry the same values as built-in fallbacks if the file is missing.)

---

## Testing

```sh
# Drop the hardware control to 0, then fire the service exactly as udev would:
CARD=$(for f in /proc/asound/card*/usbid; do \
         [ "$(cat "$f")" = "8888:1719" ] && d=$(dirname "$f") && echo "${d##*card}"; done)
amixer -c "$CARD" sset PCM 0%
sudo systemctl start reset-usb-speaker-pcm.service
amixer -c "$CARD" sget PCM        # should read [100%]
```

For the full chain, physically re-plug the speaker and check the log:

```sh
journalctl -u reset-usb-speaker-pcm --since '2 min ago' --no-pager
```

---

## Uninstall

```sh
./uninstall.sh
```

---

## Notes & caveats

- **The PipeWire half is best-effort, but covered at login too.** On plug-in it runs only if a
  desktop session is alive; for a speaker present at boot, the per-user
  [login-time service](#login-time-pipewire-handling) handles it instead. The ALSA `PCM` half
  always runs (as root).
- **`8888` is a placeholder VID**, so the rule matches both vendor *and* product (`8888:1719`)
  to stay specific to this speaker chip.
- **Profile-dependent.** This targets the device's default `iec958` (digital) profile. On an
  `analog` profile, WirePlumber manages `PCM` itself and this generally isn't needed.
- Tested on Pop!_OS / Ubuntu with PipeWire + WirePlumber. Works with PulseAudio too
  (`pactl` is used for the software-volume step).

## License

MIT — see [LICENSE](LICENSE).
