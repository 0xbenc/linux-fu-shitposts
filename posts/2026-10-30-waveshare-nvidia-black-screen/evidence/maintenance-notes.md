# example workstation host and display check — 2026-10-30

User requested SSH liveness/basic health, then reported a monitor working during
boot but going blank after the bootloader. Checked `example-workstation` as `user` via SSH
starting at approximately 20:11 PDT. Initial checks were read-only; the user then
explicitly requested repair ("make it work"). Remote changes are recorded below.

## Initial observations, before repair

- CachyOS kernel 7.2.8-1; current boot began 20:09:05 PDT.
- Initial system-health checks did not explain the display failure. Incidental
  hardware inventory, memory/storage quantities and unrelated network findings
  are omitted from this public derivative.
- Relevant graphics driver: NVIDIA580.178.04. Other GPU outputs were disconnected.
- SDDM and Xorg are running on tty2; greeter session started successfully.
- Only NVIDIA `card1-DP-2` reports connected. Its EDID is empty (0 bytes), with
  only fallback modes up to 1024×768. Xorg also reports no EDID and selected
  `DFP-2:nvidia-auto-select`, with a 1024×768 virtual screen.
- DRM reports DPMS Off/no assigned encoder for that connector. NVIDIA Xorg uses
  its own display handling; this alone does not prove the cause of blank output.
- Previous boot showed the same missing-EDID symptom on DFP-0, then connection
  changes to DFP-2. No monitor-specific custom Xorg configuration found.
- Initial direct X queries failed authorization and sudo required a password.
  Later administration used the account's existing Docker access: temporary,
  automatically removed containers, the SDDM authority file and host systemd.

## Confirmed diagnosis and repair

Mini DisplayPort to HDMI converter cable; user verified it previously worked with
other screens, including 4K60, and this screen worked before Linux took over.
A DPMS wake and 720p mode test still gave no signal. Direct reads at I2C address
0x50 on NVIDIA adapter 4 (`/dev/i2c-2`) recovered the screen's 256-byte EDID:
WaveShare / HOT model20300, native1080×1920 at61.342668Hz (150MHz pixel clock),
plus1920×1080 at60Hz. Both block checksums were valid, but a detailed timing
record was malformed. NVIDIA's explicit log: "The EDID has a bad detailed timing
descriptor." This establishes the rejection cause; it does not implicate cable
bandwidth. Exact retail model remains unidentified.

The repaired **software copy** replaces the malformed descriptor (bytes90–107)
and empty descriptor (108–125) with standard dummy records and recalculates the
base checksum. Valid native/landscape timings and the entire extension block
remain unchanged. Other preexisting EDID conformance warnings/CTA omissions were
preserved; this is not a claim of complete standards conformance. No display
firmware was flashed, no driver replaced and no bootloader/kernel arguments changed.

A temporary Xorg CustomEDID configuration restored the login screen; the user
confirmed it was on. Signing into Niri/Wayland went black because the kernel
still supplied the invalid EDID. Applying the corrected copy through NVIDIA's
per-connector DRM debugfs EDID override and reprobe fixed the active desktop.
The kernel now exposes256 bytes and both valid modes. User confirmed the final
270° Niri transform was upright and stable; logical desktop1920×1080, panel
1080×1920 at61.343Hz. The earlier90° transform was rejected as upside down.

[Installed sources, EDIDs, hashes, runtime state and guard checks](session.json)
are captured in the installation record. Host changes:

- `/usr/local/libexec/waveshare-edid-prepare.py`, raw/fixed EDIDs under
  `/usr/local/share/waveshare-display/`, `waveshare-edid.service`, its SDDM
  dependency drop-in and one DRM udev rule prepare/recheck the kernel override.
- The helper targets NVIDIA PCI0000:02:00.0 DP-2, verifies the exact original EDID
  hash through the corresponding DDC adapter, and applies the correction only on
  a match. It removes its own override for a different/disconnected screen and
  preserves unrelated overrides. It also generates/removes a matching Xorg
  CustomEDID config, since Xorg reads the hardware EDID independently of KMS.
  When that config changes, it refreshes an active greeter only if no user
  desktop is logged in. Current port is qualified; moving this panel
  to another GPU connector is not covered by this helper.
- `/usr/local/libexec/waveshare-greeter-setup` plus one SDDM X11 drop-in preserve
  the original Xsetup command and orient only the corrected monitor at login.
- Added one identity-matched WaveShare block to `~/.config/niri/cfg/display.kdl`
  for mode61.343Hz, scale1 and transform270. Original contents remain an exact
  prefix; a durable backup is now under
  `~/.local/state/waveshare-display-repair/2026-10-30/`.
- Removed the temporary Xorg config and stopped its automatic rollback timer.
  The `i2c-dev` module is now intentionally used by the startup/hotplug helper.

Validation: host `systemd-analyze verify` passed through a transient host service;
installed files match staged hashes and are root-owned; actual helper service
returned success and reported the matching corrected EDID already active. Eight
isolated guard checks passed in the final revision: the five EDID/Xorg guard
cases plus greeter refresh, preserving a logged-in desktop, and avoiding a
restart while SDDM is starting. `niri validate`
passed; repeated IPC queries verified native timing and transform270. A settings
reload briefly reset the temporary transform; reapplied after reload, then user
confirmed the orientation stayed correct. Reboot/fresh-login follow-up is below.

User reported the background image was messed up after the rotation. Refreshed
only the Noctalia wallpaper renderer by briefly toggling its enabled flag, then
restored the settings byte-for-byte. The image selection and preferences remained
unchanged. User confirmed: "Yes, looks normal". Final IPC query still showed
1920×1080 with transform270 after the wallpaper refresh.

To undo the host workaround: remove the nine installed paths enumerated in the
JSON record, reload systemd/udev, remove only the added WaveShare Niri block, and
reset this connector's debugfs `edid_override` followed by reprobe. Resetting on
this faulty panel restores its original blank-screen problem. Preserve unrelated
monitor configurations. The initial remote `/tmp`
diagnostic directory was cleared by reboot; raw/fixed EDIDs and both helper
revisions are preserved in the JSON record. Durable follow-up evidence and the
Niri backup are under `~/.local/state/waveshare-display-repair/2026-10-30/`.

## User reboot and fresh login follow-up

User rebooted the host. SSH returned on new boot
`ANONYMIZED_BOOT_1`; system running, no failed units.
The helper automatically applied the corrected kernel EDID at20:49:13 PDT;
subsequent hardware events were idempotent. This exposed one remaining gap:
Xorg independently reread the bad hardware EDID, despite correct kernel modes.

Extended the guard to generate the matching Xorg CustomEDID configuration before
SDDM starts, with the same monitor identity check. It removes that config for
other/absent screens and only restarts an existing greeter when no user desktop
is logged in. Refreshed the greeter in this boot. Xrandr then reported1920×1080,
right rotation and native1080×1920@61.34; Xorg logged the persistent corrected
EDID path and Rotation270. A subsequent fresh Niri login now correctly identifies
WaveShare and automatically uses1920×1080 with transform270. User confirmed
**both login screen and desktop look correct**. No second reboot after this final
helper extension was performed; do not describe the initial reboot as a clean
end-to-end pass without this follow-up correction. Detailed before/after evidence,
initial/final helper sources and eight guard cases are in the JSON record.

## Earlier notes search

A search of the account's 26 public repositories found no relevant display
setup. Private enumeration returned HTTP401, so private repositories were not
checked. Direct DDC reads later identified WaveShare and its timings without
GitHub access. Unrelated repository names are omitted from this public copy.
