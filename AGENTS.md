# Working on linux-fu-shitposts

- Read the README and the relevant post's `ai-context.md` before editing.
- Every post needs `human.md` and `ai-context.md`; add both to the README index.
- State the tested Linux distribution and relevant subsystem near the top of each version. Keep historical test environments separate from the user's current preference for CachyOS. Label cross-distro guidance and new package examples that have not had hardware testing.
- Keep the human version concise, concrete and action focused. Give the working directory, prerequisites, exact commands, expected result and an undo path. State machine-specific assumptions before commands that depend on them.
- Put the full environment, chronology, failed attempts, evidence, implementation, validation, rollback and unresolved questions in the AI version. Link substantial supporting data instead of repeating it everywhere.
- Distinguish observations, inferences, proposals, deployed changes and untested examples. Never turn an incomplete reboot or partial validation into a full-pass claim.
- Preserve original broken inputs and useful negative results. Keep versions when a later correction supersedes an earlier implementation.
- Bundle the actual files required by copy-and-paste instructions. Preserve the relationship between bundled sources and the versions tested on the host; label later changes as later changes.
- Keep each post's supporting files and evidence inside its own directory. Do not store credentials, authentication cookies or unrelated personal data.
- Anonymize personal hostnames, login names, private addresses, boot/session identifiers and unrelated project details. Keep the public `0xbenc` handle and technical identifiers needed for reproduction. Label redacted evidence; do not claim it is a byte-identical raw capture. Keep original broken hardware inputs intact when the fix depends on their exact bytes, explaining any retained dummy identifiers.
- **Hardware disclosure is contextual, not a blanket ban on specs.** The user explicitly permits naming hardware they own when it matters to the post. A GPU/CPU compatibility or tuning guide should name the relevant models; a device-specific fix should name the relevant model or VID:PID. Do not anonymize away information needed to understand or reproduce the result.
- **A full hardware dump is not the post standard.** Do not make a complete machine inventory a mandatory template section, default checklist or evidence attachment. Include the distro and relevant software stack, then add only the hardware details the subject calls for. Incidental CPU/GPU models, memory/storage quantities and unrelated peripherals should not be included merely because they were collected during debugging. Apply this judgment to the human version, AI version and supporting evidence alike.
- The repository is MIT under Ben Chapman's real name, as explicitly requested. Preserve original copyright notices and licences in migrated sources. Do not include unredacted Git history or personal commit emails in public evidence merely for completeness.
- Documentation work does not itself authorize applying a fix to a live machine. Respect the user's current task scope.
- Before finishing, check local Markdown links, referenced file paths, relevant syntax, and any checks needed to substantiate the post's claims. Summarize the actual validation in the AI version.
- Do not commit, push or publish unless the user requests it.
