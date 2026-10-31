# MV-SILICON USB speaker is detected, but silent

**Applies to:** USB `8888:1719`, usually named `MV-SILICON USB Speaker`, on the originally reported Pop!_OS/Ubuntu PipeWire setup. The hardware `PCM` mixer can sit at zero while the desktop volume slider looks normal.

## Confirm and get sound back

Install diagnostic tools if missing; choose your distro. CachyOS/Arch package guidance is included, but the original hardware testing was on Pop!_OS/Ubuntu.

| Linux | Command |
| --- | --- |
| CachyOS / Arch | `sudo pacman -S --needed alsa-utils libpulse usbutils` |
| Pop!_OS / Ubuntu | `sudo apt install alsa-utils pulseaudio-utils usbutils` |

```sh
lsusb -d 8888:1719
aplay -l
```

Find this device's ALSA card without assuming it is card1, then raise its hardware mixer:

```sh
speaker_card=$(
    for file in /proc/asound/card*/usbid; do
        [ -r "$file" ] && [ "$(cat "$file")" = '8888:1719' ] || continue
        card_dir=${file%/usbid}
        printf '%s\n' "${card_dir##*card}"
        break
    done
)
if [ -n "$speaker_card" ]; then
    amixer -c "$speaker_card" sget PCM
    amixer -c "$speaker_card" sset PCM 100% unmute
else
    printf 'No ALSA card with USB ID 8888:1719 found.\n' >&2
fi
```

If that restores sound, install the persistent fix below. If it does not, [check routing, profile and mixer controls](ai-context.md#troubleshooting) before installing.

## Keep it fixed

Run the installer **as your desktop user**; it calls sudo where needed. The complete implementation lives in this repo.

```sh
git clone https://github.com/0xbenc/linux-fu-shitposts.git
cd linux-fu-shitposts/posts/2026-10-30-mv-silicon-usb-speaker/files/usb-speaker-fix
./install.sh
sudo systemctl start reset-usb-speaker-pcm.service
```

It sets hardware PCM to 100%, software volume to 40% on plug-in, and installs a login helper. The login helper also resets a muted or ≤5% sink; on the first login each boot it applies 40% even if the sink was already healthy. Edit `/etc/default/usb-speaker` to change the levels. Reinstalling preserves that file.

## Check it / undo

```sh
journalctl -b -u reset-usb-speaker-pcm.service --no-pager
systemctl --user status reset-usb-speaker-pipewire.service --no-pager
pactl list short sinks
```

Play something through the selected USB output. A successful service exit alone does not prove audio played. For the hotplug path, physically unplug and replug the speaker.

From the installer directory, `./uninstall.sh` removes the six installed files, **including your `/etc/default/usb-speaker` configuration**. Save that file first if needed. It leaves the per-boot user state marker; [full cleanup and troubleshooting](ai-context.md#rollback) are in the AI version.

[Full AI context, source and migration evidence](ai-context.md). The original project reported hardware success; this migration checks the code and fixtures without performing a new physical-speaker test.
