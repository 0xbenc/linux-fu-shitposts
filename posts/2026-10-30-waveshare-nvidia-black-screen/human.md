# WaveShare works during boot, goes black in Linux

The screen had a malformed EDID: the data it sends to describe its supported modes. NVIDIA rejected it. A corrected software copy restored the picture. A later boot exposed a port limitation: the screen was on DP-1, while the original helper only checked DP-2. The current repair covers all four GPU DisplayPort connectors.

**Tested setup:** CachyOS, NVIDIA 580.178.04, SDDM, Niri, Mini DisplayPort → HDMI, portrait-native 1080×1920 WaveShare. This saved fix targets NVIDIA PCI `0000:02:00.0`, **DP-1 through DP-4**, using per-port DDC mappings and Xorg names. It checks the exact faulty EDID before applying anything. DP-1 has remote verification and user confirmation of a visible login screen on the current revision; DP-2 had a confirmed picture on the previous revision. DP-3/DP-4 mappings come from driver metadata and have **not had physical panel tests**. The current revision has not had a reboot test. For other GPUs or panels, [read the AI context](ai-context.md#adapting-to-another-machine) first.

## Install the saved fix

Run from a working terminal or SSH session. Requires Git, Python 3, sudo, and the existing SDDM/Niri setup.

```sh
git clone https://github.com/0xbenc/linux-fu-shitposts.git
cd linux-fu-shitposts/posts/2026-10-30-waveshare-nvidia-black-screen

# Install eight files, selecting the current three-file overlay.
# The original 2026-10-30 sources remain in files/root for comparison.
(
    set -e
    while IFS= read -r file; do
        source_file="files/root/$file"
        if [ -f "files/v3/root/$file" ]; then
            source_file="files/v3/root/$file"
        fi
        sudo install -D -o root -g root -m 0644 "$source_file" "/$file"
    done < files/install-paths.txt
    sudo chmod 0755 /usr/local/libexec/waveshare-edid-prepare.py \
        /usr/local/libexec/waveshare-greeter-setup
    sudo systemctl daemon-reload
    sudo udevadm control --reload-rules
    sudo systemctl start waveshare-edid.service
)
```

The helper repairs the kernel's monitor data and prepares Xorg's `CustomEDID` separately. It can refresh the login screen; it preserves a logged-in desktop.

## Save the rotation

For our Niri layout, `cfg/display.kdl` is already included by `config.kdl`. From the same post directory:

```sh
display_config="$HOME/.config/niri/cfg/display.kdl"
if [ -f "$display_config" ] && ! grep -Fq 'output "PNP(HOT) WaveShare 0x00000001"' "$display_config"; then
    cp -p "$display_config" "$display_config.before-waveshare"
    cat files/niri-output.kdl >> "$display_config"
fi
niri validate

# If already signed into Niri, first find its connected output name.
niri msg outputs
# These commands assume it is DP-1, as on the 2026-10-31 host.
# Substitute the actual Niri output name when using another port.
sleep 1
niri msg output DP-1 mode 1080x1920@61.343
niri msg output DP-1 transform 270
```

The panel keeps its native **1080×1920 @ 61.343 Hz** signal. Rotation gives a **1920×1080 landscape desktop**. In this mounting, `90` was upside down; `270` was correct.

## Check it

```sh
journalctl -b -u waveshare-edid.service --no-pager
niri msg outputs
```

Expect a matching WaveShare EDID, native timing, logical `1920x1080`, and transform `270`. On the 2026-10-31 follow-up, the service and greeter mode/rotation passed remote checks on DP-1; the user confirmed the login screen was visible on 2026-11-01. A fresh desktop login and a reboot of the all-port revision remain pending. The 2026-10-30 user confirmation applies to the historical DP-2 revision. The current installation loop is a replay procedure; it was not rerun wholesale on the host.

To undo, use the [exact removal and recovery steps](ai-context.md#rollback). This restores the panel's original bad EDID and can bring the black screen back.

[Full AI context and evidence](ai-context.md)
