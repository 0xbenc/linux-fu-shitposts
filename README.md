# linux-fu-shitposts

Linux problems, fixes that actually worked, and enough context to pick the work up later.

Every post has two versions:

- **Human version:** concise, action focused, with commands you can copy and paste.
- **AI context dump:** the full investigation, environment, evidence, failed attempts, exact changes, verification, rollback, and open questions.

## Posts

| Date | Post | Tested Linux setup | Human version | AI context dump |
| --- | --- | --- | --- | --- |
| 2026-10-30 | WaveShare works during boot, goes black in Linux | CachyOS · NVIDIA · SDDM/Niri | [Fix it](posts/2026-10-30-waveshare-nvidia-black-screen/human.md) | [Everything](posts/2026-10-30-waveshare-nvidia-black-screen/ai-context.md) |
| 2026-10-30 | MV-SILICON USB speaker is detected, but silent | Original: Pop!_OS/Ubuntu · PipeWire | [Fix it](posts/2026-10-30-mv-silicon-usb-speaker/human.md) | [Everything](posts/2026-10-30-mv-silicon-usb-speaker/ai-context.md) |

## Organization

Each post lives in `posts/YYYY-MM-DD-short-name/`:

```text
human.md       # Symptoms, scope, commands, success check, undo.
ai-context.md  # Everything needed to understand or continue the work.
files/         # Scripts, configuration and other files used by the fix.
evidence/      # Observations, logs, original data and validation records.
```

Start new posts from [the templates](templates/). Keep the human version short; put the investigation and qualifications in the AI version. Link both here. A command being documented does not mean it was tested: say what actually ran and what remains unverified.

Anonymize personal hostnames, login names, addresses and session identifiers. Keep identifiers the fix actually depends on, and say when evidence has been redacted. Public attribution and original copyright notices stay intact.

State the distro and relevant stack for each fix. An old Pop!_OS result does not become a tested CachyOS result because that's what we're using now. Avoid incidental computer inventories.

[MIT licence](LICENSE), copyright Ben Chapman. The speaker implementation and its original licence are included here; its install instructions do not depend on the old repository remaining online.
