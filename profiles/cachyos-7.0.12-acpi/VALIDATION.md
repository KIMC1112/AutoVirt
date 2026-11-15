# Validation record — 2026-11-15

- Linux: 18 unit tests passed (including external-symlink refusal), no skips.
- bash -n passed for setup-cachyos7012-acpi.sh and modules/deploy.sh.
- profile.py --help passed on Linux.
- Applied the locked repository AMD patch to a separate checkout of QEMU commit aeec49e8170de7846f476124602cf7acd400c3df.
- With the reference host identity input, generated identity-only.patch exactly matched the already deployed ACPI identity patch (line-ending normalized for Windows comparison).
- The two pre-overlay source SHA256 values matched the deployed reference build records: aml-build.c c0c855dd588f2a3f31b5fff9647796a2d5e89981b5c55f9457511784a341d4c5; acpi-build.c e59d0638adcf96c683ccb3c908d4c79bdb577f8fd1febc1156c98890c7b5f567.
- Source restore and pacman configuration restore were tested on extra copies; edited artifacts were retained.

Not performed: full new QEMU compilation, staged ELF installation, kernel package replacement, reboot, or a guest boot using a newly compiled binary. Those require a maintenance/build host and must not be inferred from unit-test success.

Host identity inputs and raw audit logs are deliberately excluded from this public repository.
