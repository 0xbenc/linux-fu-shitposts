# Saved speaker implementation

`usb-speaker-fix/` contains all 10 tracked files from source commit `c614350e1fab9ea508ef27b945703d0dcb83e6ca`, unchanged, including the original MIT licence. Its historical README still references the old repository. Use [the post's current human instructions](../human.md) for the new clone path.

Run `usb-speaker-fix/install.sh` as your desktop user; it invokes sudo for system changes. The installer finds assets relative to its own directory, so it works from this nested location without fetching the old repo. The original uninstaller is included too.

`check-behavior.py` verifies source hashes, shell syntax, and 13 isolated behavior cases. It runs fixture copies with fake audio tools and redirected inputs; it does not install anything or access a real mixer or sound server.

From the parent post directory:

```sh
python3 files/check-behavior.py
```

Original hardware success was reported on Pop!_OS/Ubuntu + PipeWire. The migration's checks do not establish a new CachyOS hardware result. See [the AI context](../ai-context.md) for exact policies, known limits and rollback.
