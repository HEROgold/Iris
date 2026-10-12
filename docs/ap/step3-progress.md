# Open world step 3: progress log

Update this after every finished sub-step, so a session that stops midway can resume from here.
Branch `ap/open-world`, worktree `C:\Users\marti\Documents\GitHub\Iris-src-read-write`. Tests: see the
`iris-src-read-write-tests` memory (headerless ROM at `/tmp/l2_headerless.sfc`, md5 6efc477d…).

## Boss strength as a per-seed setting (config block v2)

- [x] scale_bosses.asm reads mode/levels from the config block (0 none, 1 party, 2 per formation)
- [x] `install_boss_scaling(mode)`; an Archipelago build installs it with mode 0
- [x] Formation bounds check in mode 2 (`!boss_level_count` = `AP_OPT_BOSS_LEVELS_SIZE`)
- [x] Regenerate `archipelago/lufia2ow/basepatch.bsdiff4` (`tools/build_ap_basepatch.py`) and `data.py` (`tools/export_ap_data.py`)
- [x] `docs/ap/config_block.md`: boss strength / boss levels rows
- [x] Tests green: `test_open_world_bosses`, `test_ap_config_block`, `test_ap_export`, `test_ap_hint_slots`
- [x] Commit
- [ ] apworld: boss strength option writes `AP_OPT_BOSS_STRENGTH` / `AP_OPT_BOSS_LEVELS` tokens
- [ ] Commit

## Still open in step 3 (each has a prompt in `docs/ap/step3-next-prompts.md`)

- Orb crash on Cave Bridge B5 (emulator run)
- apworld open-world option, region map (ship, submarine, airship)
- Open-world base patch and data export next to the linear ones (ask the user first)
