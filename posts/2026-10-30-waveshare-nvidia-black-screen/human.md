# WaveShare works during boot, goes black in Linux

The screen had a malformed EDID: the data it sends to describe its supported modes. NVIDIA rejected it. A corrected software copy fixed the picture; separate Xorg and kernel handling made both the login screen and Wayland work.

**Tested setup:** CachyOS, NVIDIA 580.178.04, SDDM, Niri, Mini DisplayPort → HDMI, portrait-native 1080×1920 WaveShare. This saved fix targets NVIDIA PCI `0000:02:00.0`, **DP-2**, and its specific DDC adapter. It checks the exact faulty EDID before applying anything. For other ports or panels, [read the AI context](ai-context.md#adapting-to-another-machine) first.

## Install the saved fix

Run from a working terminal or SSH session. Requires Git, Python 3, sudo, and the existing SDDM/Niri setup.

```sh
git clone https://github.com/0xbenc/linux-fu-shitposts.git
cd linux-fu-shitposts/posts/2026-10-30-waveshare-nvidia-black-screen

# Install only the eight listed files. The helper generates the Xorg override.
(
    set -e
    while IFS= read -r file; do
        sudo install -D -o root -g root -m 0644 "files/root/$file" "/$file"
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

# If already signed into Niri: apply after its config reload settles.
sleep 1
niri msg output DP-2 mode 1080x1920@61.343
niri msg output DP-2 transform 270
```

The panel keeps its native **1080×1920 @ 61.343 Hz** signal. Rotation gives a **1920×1080 landscape desktop**. In this mounting, `90` was upside down; `270` was correct.

## Check it

```sh
journalctl -b -u waveshare-edid.service --no-pager
niri msg outputs
```

Expect a matching WaveShare EDID, native timing, logical `1920x1080`, and transform `270`. The user confirmed the login screen and a fresh desktop login were correct. The first reboot exposed an Xorg gap that was fixed in that boot; the final revision has not had a second reboot test.

To undo, use the [exact removal and recovery steps](ai-context.md#rollback). This restores the panel's original bad EDID and can bring the black screen back.

[Full AI context and evidence](ai-context.md)
