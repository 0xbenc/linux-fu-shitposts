# Saved display repair files

- `root/` contains the eight static host installation inputs, preserving their deployed content.
- `install-paths.txt` lists those inputs, relative to `/`. The human procedure installs only these paths.
- `generated-xorg.conf` is a reference copy of the ninth, conditionally generated file. **Do not copy it unconditionally into `/etc`**; the identity-checked helper owns its creation/removal.
- `niri-output.kdl` is the saved, monitor-matched rotation block.
- `check-guard.py` checks hashes, the precise EDID repair, and eight fixture guard cases without root or hardware access.

Run checks from the parent post directory:

```sh
python3 files/check-guard.py
```

The EDIDs intentionally retain their exact bytes, including the known dummy serial 1. Public host observations are separately redacted in `../evidence/`. See [the human procedure](../human.md) before installing; this bundle is for the exact tested PCI/connector/DDC profile.
