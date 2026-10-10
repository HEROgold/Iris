# Archipelago config block

One bank-aligned 32KB bank at headerless `0x360000` (SNES `$EC:8000`), `AP_CONFIG_REGION` in `constants.py`. The Archipelago SNI client and our asm read it; Archipelago tokens (offset + bytes) fill it per seed on top of a static base patch, so every field has a fixed offset. Offsets are headerless.

| Field | Offset | SNES | Size | Meaning | Written by |
|---|---|---|---|---|---|
| Magic `IRISAP` | 0x360000 | $EC:8000 | 6 | Identifies an Iris AP ROM | base patch |
| Layout version | 0x360006 | $EC:8006 | 1 | Currently 1 | base patch |
| Reserved | 0x360007 | $EC:8007 | 1 | Zero | - |
| Auth name | 0x360008 | $EC:8008 | 32 | Seed/slot name the client authenticates with, zero-padded ASCII/UTF-8 | per-seed token |
| Reserved | 0x360028 | $EC:8028 | 24 | Zero, up to the option area | - |
| Goal | 0x360040 | $EC:8040 | 1 | Goal id | per-seed token |
| Goal parameter | 0x360041 | $EC:8041 | 1 | e.g. Iris treasures required | per-seed token |
| Start with Mermaid Jade | 0x360042 | $EC:8042 | 1 | 0/1 | per-seed token |
| Start with Engine | 0x360043 | $EC:8043 | 1 | 0/1 | per-seed token |
| Encounter scaling enabled | 0x360044 | $EC:8044 | 1 | 0/1 | per-seed token |
| Scaling band low | 0x360045 | $EC:8045 | 1 | Two's complement; as SCALE_ENCOUNTERS_LOW | per-seed token |
| Scaling band range | 0x360046 | $EC:8046 | 1 | As SCALE_ENCOUNTERS_RANGE | per-seed token |
| Scenario-item removal mode | 0x360047 | $EC:8047 | 1 | Mode id | per-seed token |
| Blue chests enabled | 0x360048 | $EC:8048 | 1 | 0/1, Ancient Cave blue chests are checks | per-seed token |
| Blue chest check count N | 0x360049 | $EC:8049 | 2 | Little-endian | per-seed token |
| Death link | 0x36004B | $EC:804B | 1 | 0/1 | per-seed token |
| Reserved options | 0x36004C | $EC:804C | 20 | Zero, pads options to 64 bytes (0x40-0x7F) | - |
| Hint table header | 0x360080 | $EC:8080 | 16 | u16 hint count, u16 arena bytes used, 12 reserved | per-seed token |
| Hint text arena | 0x360090 | $EC:8090 | 32624 | Hint text, to the end of the bank | per-seed token |

## Versioning

The version byte at `0x360006` is `AP_CONFIG_VERSION`. Bump it whenever the layout changes, and update this table, the constants and the tests together.
