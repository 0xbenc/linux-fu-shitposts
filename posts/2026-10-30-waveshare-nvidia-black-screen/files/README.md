# Saved display repair files

- `root/` contains the eight static host installation inputs, preserving their 2026-10-30 deployed content.
- `v2/` preserves the two-port revision briefly deployed on 2026-10-31.
- `v3/root/` contains the current three-file overlay: helper, greeter setup and unit. Install it over the corresponding `root/` inputs. `v3/check-guard.py` checks all four profiles and a port move; `v3/query-port-map.py` is a diagnostic, not an install input.
- `install-paths.txt` lists those inputs, relative to `/`. The human procedure installs only these paths, choosing `v3/root/` when present.
- `generated-xorg.conf` is a reference copy of the ninth, conditionally generated file. **Do not copy it unconditionally into `/etc`**; the identity-checked helper owns its creation/removal.
- `niri-output.kdl` is the saved, monitor-matched rotation block.
- `check-guard.py` checks hashes, the precise EDID repair, and eight fixture guard cases without root or hardware access.

Run checks from the parent post directory:

```sh
python3 files/check-guard.py     # historical bundle / eight checks
python3 files/v3/check-guard.py  # current guard / 25 checks
```

The EDIDs intentionally retain their exact bytes, including the known dummy serial 1. Public host observations are separately redacted in `../evidence/`. See [the human procedure](../human.md) before installing; this bundle is for the exact tested PCI/connector/DDC profile.
