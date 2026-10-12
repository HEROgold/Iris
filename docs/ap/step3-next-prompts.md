# Open world step 3: prompts for the remaining work

Paste one prompt per session, in order. Every prompt shares the **Common context** block; paste it first.
Each session ticks its boxes in `docs/ap/step3-progress.md` after every sub-step and commits each tested
checkpoint (no push), so a session that stops midway can be resumed with "continue from step3-progress.md".

## Common context

> Repo: worktree `C:\Users\marti\Documents\GitHub\Iris-src-read-write`, branch `ap/open-world` (package `iris.*`,
> apworld in `archipelago/lufia2ow/`). Not the `Iris` workspace.
> Tests: `uv run --no-project --python 3.12 --with bitstring --with bsdiff4 --with pytest python -m pytest tests/<file>
> --file /tmp/l2_headerless.sfc -q -p no:cacheprovider -p no:logging --rootdir .` (if the ROM is missing:
> `tail -c +513 C:/Users/marti/Documents/GitHub/Iris/rom.sfc > /tmp/l2_headerless.sfc`, md5 6efc477d…).
> After changing anything the base patch or export sees, rerun `tools/build_ap_basepatch.py --file <rom>` and
> `tools/export_ap_data.py --file <rom>`; `tests/test_ap_export.py` fails while they're stale.
> Progress log: `docs/ap/step3-progress.md`. Add your sub-steps as boxes before you start, tick each when done.
> Commit message style: `Open world: … (Iris-Dev#43)` / `apworld: … (Iris-Dev#43)`.
>
> Done on the ROM side (don't redo): open world (`iris/patches/open_world/__init__.py`, `apply_open_world`, `EXTRAS`
> incl. `orb_check` and `escapable_dungeons`), leader (`leader.py`), boss NPCs at 38 spots (`bosses.py`: `BOSSES`,
> `SPOTS`, `fixed_placement`, `shuffled_placement`, `place_bosses`), boss strength in the config block
> (`AP_OPT_BOSS_STRENGTH` mode 0/1/2, `AP_OPT_BOSS_LEVELS` 39 bytes indexed by formation; `docs/ap/config_block.md`),
> received characters/capsules/maidens (rx_specials.asm: item index `$0200+c` character c, `$0210+s` capsule
> species s, `$0220+m` maiden m). The orb crash is not an Iris bug (commit 1df5ea9, checked in Mesen).
> Today the AP base patch (`tools/build_ap_basepatch.py`) is built **linear**: `Options(0, selected_patch=Patch.VANILLA,
> archipelago=True, unlock_warps=False)`, no `open_world`.

## Prompt 1: open-world base patch and data export

**Needs the user's decisions first (see "Open decisions" below). Put them in the prompt before running it.**

> Add an open-world AP base patch and data export next to the linear ones.
> - `tools/build_ap_basepatch.py` and `tools/export_ap_data.py`: build a second set with `open_world=True` (plus the
>   extras decided below) into `archipelago/lufia2ow/basepatch_open_world.bsdiff4` and the matching data module
>   (layout decided below). Keep the linear outputs byte-identical.
> - `--check` covers both. `tests/test_ap_export.py`: parametrize the current-ness and config-header tests over both.
> - `archipelago/lufia2ow/rom.py` `base_patch()`: take which one to load; nothing chooses open world yet (prompt 2 does).
> - Export for open world as well: the boss spots (`bosses.SPOTS`, their maps and flags) and the orb-check grant, as
>   the apworld needs them for locations in prompt 3.
> Done when both patches build, `--check` passes for both, and the export tests pass for both.

## Prompt 2: apworld open-world option and region map

> Add an `open_world` option (Toggle, default off) to `archipelago/lufia2ow/options.py` and use it in
> `__init__.py`: it picks the open-world base patch/data from prompt 1. Open world has no story stages, so
> `logic.py`'s story-stage regions don't apply: build a region map where the areas are reachable from the
> start (Elcid) and gated only by travel: Ship (sea), Submarine (seafloor), Airship/Engine (sky), using the existing
> `ShipUpgrades` items (`items.py`: SHIP, SUBMARINE, PROGRESSIVE_SHIP; `__init__.py:136-140`) and the key
> items/tools that still lock doors (`logic.py` reads key doors from the ROM). The `ShipUpgrades` choice "vanilla"
> means nothing in open world: reject it there or treat it as progressive (pick one, say which in the option text).
> Linear seeds must generate the same as before.
> Done when an open-world seed and a linear seed both generate (`tests/` apworld tests, plus a generate run if the
> repo has one) and `tools/build_apworld.py` still packages.

## Prompt 3: characters, capsules, maidens, boss NPCs and the orb as AP items and locations

> In open world only:
> - Items: each character, capsule species and maiden is an AP item, with item index `$0200+c`, `$0210+s`,
>   `$0220+m` (already handled in the ROM by rx_specials.asm, commit 722de37). Characters and maidens are
>   progression (the maidens open the Doom Island barrier), capsules are useful. Remove the vanilla joins from the
>   pool so each one comes only as an item.
> - Locations: every placed boss NPC (from the prompt 1 export) and the orb check (`orb_check` extra,
>   flag 0x30, a script grant written with `rom.write_grant`).
> Done when an open-world seed places these and a generated ROM's tokens write the boss and orb grants.

## Prompt 4: boss strength option

> Add a `boss_strength` option (Choice: unchanged / party_level / by_depth, default unchanged) for open world. In
> `generate_output`, write `data.CONFIG["AP_OPT_BOSS_STRENGTH"]` (0/1/2) with a token. For by_depth, compute each placed
> boss formation's level the way `iris/patches/open_world/bosses.py` `scale_to_depth` does (by spot depth) and
> write the 39 bytes at `AP_OPT_BOSS_LEVELS` (index = formation, 0 = unchanged). If boss placement is shuffled per
> seed (prompt 1's decision), use the seed's placement. Add `write_boss_strength` to `rom.py` like `write_auth`.
> Done when a test reads the tokens back for each choice.

## Open decisions (ask the user before prompt 1)

A static base patch can't hold per-seed choices. These open-world features are per seed in the Iris CLI today:

1. **Boss placement** (`shuffled_placement(seed)`): bake in `fixed_placement` only, or make placement token-driven
   (write each spot's boss script per seed)?
2. **Leader** (`--leader`, incl. random): leave it out of AP, bake Maxim in, or make it a token?
3. **Extras** (`EXTRAS`: orb_check vs orb guard, escapable_dungeons, the NPC tips): which are baked into the open-world
   base patch? Making them options means one base patch per combination, or tokens.
4. **Packaging**: a second base patch inside `lufia2ow` (picked by the option), or a separate apworld?
