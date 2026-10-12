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
- [x] Commit (b72ac04)
- [ ] apworld: boss strength option writes the tokens. Moved to prompt 4: the linear AP base patch has no
  boss hook, so the tokens only work once the open-world base patch exists (prompt 1).

## Still open in step 3 (prompts in `docs/ap/step3-next-prompts.md`, one agent each, in order)

- Orb crash: done, not an Iris bug (1df5ea9, Mesen). `orb_check` makes the orb an item check.
- [x] Decisions asked (2026-10-12), recorded in the prompts file
- [ ] Prompt 1: open-world base patch, data export, `open_world` option
- [ ] Prompt 2: open-world region map (ship, submarine, airship)
- [ ] Prompt 3: characters, capsules, maidens as items; boss NPCs and the orb as locations
- [ ] Prompt 4: boss placement and boss strength options (tokens)
- [ ] Prompt 5: leader and extras as per-seed options (token variants, else documented Iris flags)
