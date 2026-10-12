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
- [x] Prompt 1: open-world base patch, data export, `open_world` option
  - [x] `tools/build_ap_basepatch.py`: `OPEN_WORLD_OPTIONS` -> `basepatch_open_world.bsdiff4`; default writes both, `--check` checks both
  - [x] `tools/export_ap_data.py`: `data_open_world.py` (data.py content + boss NPC operand offsets, BOSSES/DAOS, spot order)
  - [x] `tests/test_ap_export.py`: both pairs current; boss operand offsets read back
  - [x] apworld: `open_world` Toggle; base patch + data module per world instance
  - [x] Linear `basepatch.bsdiff4`/`data.py` byte-identical; tests green; committed
  - Note: open world replaces 13 story scripts with grant-less ones (14 grants), so `data_open_world.GRANTS` has 30
    rows and all 12 current grant locations drop out for open-world players (`locations.grant_offsets`).
    Boss reward grants are only in `BOSS_NPCS`, not in `GRANTS`.
- [x] Prompt 2: open-world region map (ship, submarine, airship)
  - [x] logic.py: open-world areas (travel + key/tool rules) from terrorwave's requirements.txt
  - [x] __init__.py: open-world regions/goal; linear unchanged
  - [x] options: goals (daos, dragon_eggs only), own_stage -> own_world, ship vanilla -> progressive, docs
  - [x] Pool fits the locations in open world (no grants, no Merix egg)
  - [x] Upstream clone set up (commands below); linear, open-world and mixed seeds generate
  - [x] archipelago/lufia2ow/test/ (WorldTestBase) passes in the upstream clone
  - [x] build_apworld packages; export/basepatch --check green; committed
- [ ] Prompt 3: characters, capsules, maidens as items; boss NPCs and the orb as locations
  - [x] Check the open-world base for free sources of characters, capsules and maidens (ROM change only if needed): none left, no ROM change
  - [x] items.py: character (not Maxim), capsule and maiden items (ids BASE_ID + $0200/$0210/$0220 + n)
  - [x] locations.py: 48 boss reward locations (BASE_ID + 0x2000 + spot*2 + n), BOSS_FLAGS for the client
  - [x] __init__.py: specials in the open-world pool, boss reward regions/rules, Daos gated on the maidens, tokens
  - [x] client.py: report boss rewards from the boss flag; own specials delivered through the receive list
  - [ ] Tests (apworld + Iris), linear/open/mixed seeds, linear spoiler unchanged; commit
  - [ ] Findings in step3-next-prompts.md
- [ ] Prompt 4: boss placement and boss strength options (tokens)
- [ ] Prompt 5: leader and extras as per-seed options (token variants, else documented Iris flags)

## Generation testing in upstream Archipelago (set up in prompt 2, reuse it)

Clone: `C:\Users\marti\Documents\GitHub\Archipelago-upstream` (upstream main, Python 3.12 venv). The world is a directory
junction `worlds\lufia2ow` -> this worktree's `archipelago\lufia2ow`, so edits are live (no copies). Player yamls live in
`l2ow_players\<set>\` there (linear, open, mixed, variants, bad), outputs in `l2ow_out\`.

```sh
cd /c/Users/marti/Documents/GitHub
git clone --depth 1 https://github.com/ArchipelagoMW/Archipelago Archipelago-upstream
cd Archipelago-upstream
uv venv --python 3.12 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements.txt pytest pip
.venv/Scripts/python.exe ModuleUpdate.py --yes          # the other worlds' requirements
cmd //c "mklink /J worlds\\lufia2ow C:\\Users\\marti\\Documents\\GitHub\\Iris-src-read-write\\archipelago\\lufia2ow"
.venv/Scripts/python.exe -c "import settings; s = settings.get_settings(); s.lufia2ow_options.rom_file = r'C:\Users\marti\AppData\Local\Temp\l2_headerless.sfc'; s.save()"
# generate (stdin from /dev/null: on an error Generate waits for Enter)
.venv/Scripts/python.exe Generate.py --player_files_path l2ow_players/open --outputpath l2ow_out/open --seed 12345 --spoiler 2 < /dev/null
# the apworld's own tests (archipelago/lufia2ow/test, WorldTestBase)
.venv/Scripts/python.exe -m pytest worlds/lufia2ow/test -q -p no:cacheprovider
```

`C:\Users\marti\AppData\Local\Temp\l2_headerless.sfc` is `/tmp/l2_headerless.sfc` in Git Bash. A player yaml is just
`name: X`, `game: Lufia II Overworld`, and the options under `Lufia II Overworld:`.
