# MV-SILICON `8888:1719` silent speaker — AI context dump

**Original Linux setup:** Pop!_OS/Ubuntu with PipeWire and WirePlumber, according to the source project. Exact distro release, kernel, PipeWire version and speaker retail brand were not recorded. This is a different incident from the CachyOS/NVIDIA display post; do not merge their environments or infer a shared computer.

**Migration date:** 2026-10-30. Original implementation: June 16; login-time handling/shared configuration: June 21. The current user's preference for CachyOS explains the additional package guidance, not a new claim of successful CachyOS hardware testing.

## Current result and scope

The original repository reported a working fix for a USB speaker that enumerated normally but remained silent because its ALSA hardware `PCM` mixer was at zero. This post consolidates that implementation, explains its behavior accurately, and supplies a short [human procedure](human.md).

All **10 tracked files** from source commit `c614350e1fab9ea508ef27b945703d0dcb83e6ca` are preserved byte-for-byte under [files/usb-speaker-fix](files/usb-speaker-fix/). That includes executable scripts, configuration, units, udev rule, original README and MIT licence. The original README is a historical source document; use the new human version for current clone paths.

The migration's 13 isolated behavior checks and source/shell checks passed. **No new physical speaker playback, reboot, replug or suspend/resume test was performed.** The code was not installed on the current CachyOS display-repair machine. This post does not claim it has been.

## User intent, privacy and licensing

The user requested a complete migration into `linux-fu-shitposts` so the separate speaker repository could eventually be deleted. The new post must remain usable if the old repository disappears: no installer or current quick-start command fetches from it.

Both posts need a concise, copy-and-paste human version and a comprehensive AI context dump. Name the applicable Linux distro and relevant stack, not an unnecessary inventory of the user's computers. Hardware models are welcome when relevant; here the meaningful identifier is **USB VID:PID `8888:1719`**, not a CPU, motherboard or unrelated GPU.

The public `0xbenc` handle may remain. The user explicitly requested MIT for the new repository under their real name, **Ben Chapman**, and specifically chose to retain the original speaker copyright notice. Do not anonymize that licence notice. No personal hostnames, home paths, actual boot IDs, device serials or raw host dumps were present in the supplied source files. Public history summaries omit author emails; the complete Git history was backed up privately outside the publication tree.

## Symptoms and the useful diagnostic distinction

Reported symptoms: the speaker appears in `lsusb`/`aplay -l`, PipeWire's output looks present and unmuted, and the desktop volume slider appears normal, yet the speaker is silent. The source also mentions the problem appearing after reboot, replug or suspend.

Audio has more than one gain/mute stage:

```text
application → software sink volume/mute → ALSA hardware PCM volume/mute → speaker
```

On the source setup's digital `iec958` profile, software volume was not restoring the independent hardware PCM control. A healthy-looking software slider therefore did not establish that the hardware control was nonzero.

The actionable discriminator is **raising the target card's hardware PCM control restores audio**. USB ID alone does not prove that every silence problem on a device has this cause. If PCM is already healthy, or changing it does not restore sound, investigate routing, profile, other controls and the physical speaker rather than assuming this script will fix it.

The source calls the device MV-SILICON, but no retail speaker model was established. It also describes vendor ID 8888 as a placeholder/unregistered value. This migration did not establish that registry claim independently and does not rely on it. Match both vendor and product, then confirm the actual PCM symptom.

## Dependencies and distro guidance

Runtime tools used by the implementation:

| Tool | Role |
| --- | --- |
| `amixer` / `aplay` | ALSA mixer control / card discovery |
| `pactl` | Software sink inspection and control through the PulseAudio-compatible interface |
| `runuser`, `id` | Root hotplug helper enters a user's session context |
| systemd / udev | Device activation, system helper, per-user login helper |
| POSIX shell and standard text utilities | Script execution, matching and state handling |
| `lsusb` | Human diagnostic device identification |

Package examples:

```sh
# CachyOS / Arch: package guidance, not a new physical-device validation.
sudo pacman -S --needed alsa-utils libpulse usbutils

# Original Pop!_OS / Ubuntu family.
sudo apt install alsa-utils pulseaudio-utils usbutils
```

Arch's [libpulse file list](https://archlinux.org/packages/extra/x86_64/libpulse/files/) confirms that package supplies `pactl`. These are client/diagnostic package instructions, not a request to replace an existing PipeWire audio stack with a different sound server.

The scripts use `pactl`, but the supplied login unit explicitly wants `pipewire.service` and orders after PipeWire/WirePlumber. The upstream README claims PulseAudio compatibility; a pure-PulseAudio installation was not newly qualified here. Review the user unit's dependencies for that environment instead of equating a shared command interface with a tested startup configuration.

## Quick confirmation without a fixed card number

`aplay -l` identifies sound cards. For reliable automation, the root helper inspects `/proc/asound/card*/usbid` and selects the **first** card whose contents equal `USB_ID`.

The human version uses that lookup too. Do not copy the old README's example card1 blindly: ALSA card ordering changes. After finding the target card:

```sh
# Replace this value with the card found on the actual machine.
speaker_card=1
amixer -c "$speaker_card" sget PCM
amixer -c "$speaker_card" sset PCM 100% unmute
```

Expected evidence is the target PCM control changing from the broken state to its intended value and audio actually returning through that output. Root permission is not always required for `amixer` in an active desktop session; if access is denied, diagnose the session/device permissions or run that targeted mixer command with sudo.

Do not run the permanent installer as `sudo ./install.sh`. It already uses sudo for system files, while its current-session `systemctl --user` calls should run as the desktop user.

## Exact implementation

The executable installer is [install.sh](files/usb-speaker-fix/install.sh). It locates its assets relative to its own path, so moving the complete tree under a post does not break its source-file lookup. No implementation edits were needed for the migration.

### Installed files

| Host path | Source / purpose |
| --- | --- |
| `/etc/default/usb-speaker` | Shared shell configuration; retained if it already exists |
| `/etc/udev/rules.d/99-usb-speaker-pcm.rules` | Matches this USB device's ALSA control node |
| `/etc/systemd/system/reset-usb-speaker-pcm.service` | System one-shot helper |
| `/usr/local/bin/reset-usb-speaker-audio.sh` | Root ALSA correction and best-effort software volume |
| `/etc/systemd/user/reset-usb-speaker-pipewire.service` | Login-time one-shot, globally enabled for users |
| `/usr/local/bin/reset-usb-speaker-pipewire-session.sh` | Current-session repair and once-per-boot preference |

`systemctl --global enable` also creates the user-unit enablement symlink. Per-user runtime state is separate from these six regular files.

The installer copies scripts as 0755 and configuration/unit/rule files as 0644. It preserves an existing `/etc/default/usb-speaker`, reloads udev/systemd, enables the login unit globally, and best-effort reloads/starts it for the invoking user. It prints the manual system-unit command; it does not itself explicitly start the root hardware-reset unit.

### Shared configuration

Both scripts have fallback defaults, then source `/etc/default/usb-speaker` if readable:

```sh
PCM_VOLUME=100%
PW_VOLUME=40%
LOW_VOLUME=5
USB_ID="8888:1719"
SINK_MATCH="MV-SILICON_USB_Speaker"
```

Edits take effect on the next helper invocation. This is **shell code sourced by a root helper**, not a passive key/value parser; preserve root ownership and ordinary non-writable-by-other-users permissions.

`USB_ID` controls the root script's card lookup. The udev rule still contains literal `8888` and `1719`, so changing that config value does not automatically retarget the event trigger. `SINK_MATCH` is passed to AWK's `~` operator and is therefore a regular expression, despite the source comment calling it a substring. Its supplied default is straightforward; a customized expression can match more broadly.

### Plug-in / boot device path

The rule matches `ACTION=="add"`, subsystem `sound`, kernel node `controlC*`, and USB vendor/product attributes. It adds the `systemd` tag and requests `reset-usb-speaker-pcm.service` through `SYSTEMD_WANTS`.

Matching the control node means the ALSA mixer node exists before the service is requested. It avoids launching on every PCM subdevice; it does not prove that every possible restore service or startup ordering race has been eliminated. [systemd.device](https://www.freedesktop.org/software/systemd/man/258/systemd.device.html) explains that such wants are acted on when a device becomes active, with the required tag. The service itself is not an always-running daemon.

The root helper then:

1. Finds the first matching card by USB ID and runs `amixer ... sset PCM "$PCM_VOLUME" unmute`.
2. Enumerates active `/run/user/*` directories and resolves their numeric owners with `id`.
3. Uses `runuser` and the appropriate `XDG_RUNTIME_DIR` to query that session's software sinks.
4. Finds the first matching sink, unmutes it, sets `PW_VOLUME`, and exits. It retries the session/sink search ten times with 0.5-second delays, about 5 seconds in total.

At coldplug the root hardware correction can occur before a desktop sound server exists. That is why it has a separate login helper. The root script's ALSA and software searches are independent: failure to find an ALSA card does not prevent a matching software sink from being adjusted. Mixer errors, software setter errors and an absent session are deliberately tolerated, and the script exits 0.

### Login-time path: the exact state machine

The user unit is wanted by the user manager's `default.target`. It orders after `pipewire.service` and `wireplumber.service`, wants PipeWire, and executes the session script in that user's context.

Strictly, the trigger is **user-manager startup**, not every possible graphical login. A lingering or persistent user manager can outlive a logout. Do not promise that starting another desktop session always reruns this unit.

The script waits about 5 seconds for its first matching sink. If `pactl` is absent or the sink never appears, it exits without changing or marking a boot. It reads the mute state and the first reported channel percentage, then evaluates these branches **in order**:

| Condition | Action |
| --- | --- |
| Muted, or volume ≤ `LOW_VOLUME` | Unmute, set `PW_VOLUME`, mark current boot, exit |
| Otherwise healthy, and stored boot differs from current boot | Apply the same default once, mark boot, exit |
| Otherwise healthy and current boot already marked | Leave the user's level alone |

The marker is:

```text
${XDG_STATE_HOME:-$HOME/.local/state}/reset-usb-speaker/last-boot-id
```

It stores the current `/proc/sys/kernel/random/boot_id`, so it survives logout/login and changes on reboot. Actual boot UUIDs are not published in this post's evidence.

Two important consequences of the source code, which the shorter upstream prose obscures:

- An intentionally muted or ≤5% sink is still treated as broken at login. The script cannot infer intent and will override that state. It is inaccurate to say it never changes a deliberate user preference.
- A healthy volume is also changed on the first login of a new boot. Only later healthy logins in that boot are left alone. Plug-in applies the software default again independently of this marker.

The parser assumes the expected `pactl` text layout and reads only the first percentage. Setter failures are ignored; a boot can be marked even when the requested software update failed. A unit showing success therefore proves the script completed, not that audio played or all controls changed.

## Troubleshooting

### USB device or PCM control is missing

```sh
lsusb -d 8888:1719
aplay -l
amixer -c "$speaker_card" scontrols
amixer -c "$speaker_card" sget PCM
```

Do not guess another mixer control or apply this fix to all sound cards. Confirm the actual USB identity and control names. The implementation handles the first matching card/sink; multiple identical devices are not individually associated or fully supported.

### Hardware PCM is healthy, but still silent

Run sound-server commands as the desktop user:

```sh
pactl info
pactl list short sinks
pactl get-default-sink
pactl list cards
```

Check that the application is routed to the intended USB output and inspect its active profile. Use the actual sink name from the list for:

```sh
pactl get-sink-mute "$speaker_sink"
pactl get-sink-volume "$speaker_sink"
```

`speaker_sink` is a placeholder for the discovered name, not necessarily the default sink. The provided scripts do not select the default output, move existing application streams, or change the card's profile.

The original explanation concerned an `iec958` software-volume path. On an analog profile the session manager may manage hardware PCM itself. Do not force a profile change as part of reproducing this post without identifying that machine's actual behavior.

### Works manually, fails on replug or login

```sh
journalctl -b -u reset-usb-speaker-pcm.service --no-pager
systemctl --user is-enabled reset-usb-speaker-pipewire.service
journalctl --user -b -u reset-usb-speaker-pipewire.service --no-pager
sudo systemctl start reset-usb-speaker-pcm.service
systemctl --user start reset-usb-speaker-pipewire.service
```

The system unit and user unit solve different timing problems. Do not remove the login path merely because the root path successfully fixes ALSA. Conversely, do not call the root path unnecessary just because the user unit sets a visible slider.

### Silence after suspend

The rule is an **add-event** trigger; the login unit is a **user-manager startup** trigger. A resume that produces neither event is not covered automatically. Run the targeted system helper to recover, then inspect the actual device events before designing a resume-specific addition. This migration did not add a sleep hook or continuous watchdog.

### Healthy volume changes unexpectedly

Review `/etc/default/usb-speaker`, the state marker, and the branch table above. The defaults are deliberate behavior of this implementation. A desired permanent mute or very low level conflicts with its repair policy. Stop/disable the relevant automation or change the policy deliberately; do not describe repeated resets as a new hardware failure.

The shared config accepts numeric `LOW_VOLUME`; nonsensical settings and arbitrary shell content are not validated. A broader product could add policy validation, stable per-device association and resume handling, but none of that is implemented or claimed by this post.

## Validation performed for this migration

Run from this post directory:

```sh
python3 files/check-behavior.py
```

The harness verifies all 10 source hashes, checks shell syntax, and runs fixture copies of the scripts. Only those fixture copies redirect `/etc`, `/proc` and runtime inputs into temporary directories. Stub mixer/session commands record calls; a fixture boot token replaces the actual boot ID. There is no sudo, live sound-server connection, mixer change, host configuration write or real-user impersonation.

Thirteen cases passed:

1. Matching plug-in repairs the first target ALSA card and matching software sink.
2. A boot-time missing user sink still allows ALSA correction.
3. An unrelated device and sink receive no setters.
4. Shared config values override fallback defaults.
5. A muted sink is repaired even in an already-marked boot.
6. A zero software volume is repaired.
7. The low-volume threshold includes equality.
8. A healthy first login of a new boot gets the default.
9. A healthy same-boot login preserves the current level.
10. An absent sink does not create a boot marker.
11. A configured lower threshold preserves a higher level.
12. A configured software default is used for repair.
13. Missing `pactl` exits without changes.

These support code behavior and the migration's fidelity. They do not verify physical sound, a real udev event, systemd ordering on a new distro, sleep behavior, or all multi-user/multi-device scenarios. The installer/uninstaller were inspected and syntax checked; they were not executed against the documentation workstation.

The [saved local validation report](evidence/validation.json) records all 13 case results and the ten source-file checks.

The original project reported physical success on its Pop!_OS/Ubuntu setup. It did not supply a complete raw hardware test log, package versions or a preserved before/after mixer capture. Keep that as a provenance limit rather than inventing a new successful test.

## Rollback

Run from [the bundled implementation directory](files/usb-speaker-fix/). The uninstaller deletes `/etc/default/usb-speaker` even if it contains personal edits; save it before removal if it matters.

```sh
sudo cp -p /etc/default/usb-speaker /etc/default/usb-speaker.saved
sudo systemctl stop reset-usb-speaker-pcm.service
./uninstall.sh
systemctl --user daemon-reload
```

The uninstaller stops the invoking user's unit, globally disables it, removes the six regular installed files, and reloads udev/systemd. Other already-running user managers may need their own reload/logout. It does not revert the current hardware/software volume and does not remove the per-user marker. Optional marker removal for the current user:

```sh
rm -f "${XDG_STATE_HOME:-$HOME/.local/state}/reset-usb-speaker/last-boot-id"
```

Do not delete the whole state parent or other users' files. This rollback is documented, not an uninstall performed on the original working system during migration.

## Migration completeness and source retirement

[provenance.json](evidence/provenance.json) records every copied path/hash, original commit, three commit subjects/dates, audit results and privacy choices. Original source: [mv-silicon-8888-1719-usb-speaker-fix](https://github.com/0xbenc/mv-silicon-8888-1719-usb-speaker-fix). That is a provenance link, not a runtime dependency.

Migration audit: one branch (`main`), three commits, no tags, releases, issues or pull requests returned by the source API. The wiki feature was enabled, but its Git endpoint reported Repository not found; no accessible wiki was found. There were no release assets to download. The tracked tree contains10 small files and no submodule or LFS dependency.

All current install/uninstall assets and the original licence are local to this post. A complete Git bundle was separately created and verified in private storage so old author emails/history need not be republished to avoid losing the history. Public evidence includes commit identifiers and subjects, not personal commit metadata.

The historical copied README still shows the old clone URL. It is retained as source evidence, not the current installation route. Current human instructions clone `linux-fu-shitposts` and run the local scripts. Deleting the source repository would not redirect its old URLs automatically. Existing external links to that repo would still break.

The current clone commands use this new repository. Retire the source only after this copy is published and verified. Source retirement is a user action, not something this migration automatically performs. Do not describe an old repository as deleted, archived or redirected unless that action actually happened.

## Primary references

- [Bundled original README](files/usb-speaker-fix/README.md), [installer](files/usb-speaker-fix/install.sh), [root helper](files/usb-speaker-fix/bin/reset-usb-speaker-audio.sh) and [user helper](files/usb-speaker-fix/bin/reset-usb-speaker-pipewire-session.sh): exact implementation and original claims.
- [Original MIT licence](files/usb-speaker-fix/LICENSE): preserved unchanged under the user's requested real-name copyright.
- [PipeWire ALSA properties](https://pipewire.pages.freedesktop.org/pipewire/devel/page_man_pipewire-props_7.html): software mixer handling and independent hardware control. This explains the layer distinction; it does not itself prove this particular speaker's history.
- [systemd.device](https://www.freedesktop.org/software/systemd/man/258/systemd.device.html): device-triggered wants and activation semantics.
- [amixer manual](https://man.archlinux.org/man/amixer.1.en) and [pactl manual](https://man.archlinux.org/man/pactl.1.en): mixer/sink command behavior.
- [Arch libpulse package files](https://archlinux.org/packages/extra/x86_64/libpulse/files/): checked `pactl` package mapping for CachyOS/Arch guidance.

This post preserves a small working implementation and makes its scope explicit. It does not silently turn migration into an audio-system rewrite.
