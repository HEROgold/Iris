# Open world step 3: prompts for the remaining work

One agent per prompt, run in order. Each brief = **Common context** + **Decisions** + its prompt.
Each session adds its sub-steps as boxes in `docs/ap/step3-progress.md`, ticks them as it goes, and commits each
tested checkpoint (no push), so a session that stops midway can resume with "continue from step3-progress.md".

## Common context

> Repo: worktree `C:\Users\marti\Documents\GitHub\Iris-src-read-write`, branch `ap/open-world` (package `iris.*`,
> apworld in `archipelago/lufia2ow/`). Not the `Iris` workspace.
> Tests: `uv run --no-project --python 3.12 --with bitstring --with bsdiff4 --with pytest python -m pytest tests/<file>
> --file /tmp/l2_headerless.sfc -q -p no:cacheprovider -p no:logging --rootdir .` (if the ROM is missing:
> `tail -c +513 C:/Users/marti/Documents/GitHub/Iris/rom.sfc > /tmp/l2_headerless.sfc`, md5 6efc477d…).
> Python scripts: same `uv run … python` prefix. After changing anything the base patches or export see, rerun
> `tools/build_ap_basepatch.py --file <rom>` and `tools/export_ap_data.py --file <rom>`; `tests/test_ap_export.py`
> fails while they're stale.
> Commit message style: `Open world: … (Iris-Dev#43)` / `apworld: … (Iris-Dev#43)`.
>
> Done on the ROM side (don't redo): open world (`iris/patches/open_world/__init__.py`: `apply_open_world(extras)`,
> `EXTRAS`, `EXCLUSIVE` = orb guard vs `orb_check`), leader (`leader.py` `set_leader`), boss NPCs (`bosses.py`:
> `SPOTS` (37 spots + `FINAL_SPOT` Daos), `BOSSES`, `fixed_placement`, `shuffled_placement(seed)`, `place_bosses`,
> `placed_bosses()` for the export), boss strength in the config block (`AP_OPT_BOSS_STRENGTH` 0 none/1 party/
> 2 per formation, `AP_OPT_BOSS_LEVELS` 39 bytes indexed by formation; `docs/ap/config_block.md`), received
> characters/capsules/maidens (rx_specials.asm: item index `$0200+c` character c, `$0210+s` capsule species s,
> `$0220+m` maiden m). The orb crash is not an Iris bug (commit 1df5ea9). `iris/build.py` `build()`: with
> `open_world` and `archipelago` and `boss_strength="unchanged"` it installs the boss hook in mode 0.
> The linear AP base patch: `tools/build_ap_basepatch.py` `OPTIONS = Options(0, selected_patch=Patch.VANILLA,
> archipelago=True, unlock_warps=False)`; the apworld loads it in `archipelago/lufia2ow/rom.py` `base_patch()` and
> writes tokens with `L2OWProcedurePatch.write_*` (see `write_auth`) from `__init__.py` `generate_output`.

## Decisions (the user's, 2026-10-12)

> - Packaging: a second base patch inside `lufia2ow` (`basepatch_open_world.bsdiff4` + its data), picked by an
>   `open_world` option. Linear seeds stay byte-identical.
> - Boss placement: an apworld option, fixed or shuffled. The base patch holds `fixed_placement`; shuffled writes the
>   per-spot boss bytes with tokens (a spot's boss only changes fixed-size operands: the NPC-load sprite, the talk
>   script's MUSIC bgm and BOSS_BATTLE formation, see `bosses._prefix_npc_load` / `_talk`).
> - Boss strength: an apworld option, default unchanged (unchanged / party_level / by_depth), written as tokens.
> - Leader: a per-seed apworld option (Maxim default, the six others, random), written as tokens.
> - Extras: ideally all four (`orb_check`, `escapable_dungeons`, the NPC tips, the orb guard NPC) are apworld options.
>   If one can only be per seed by shipping Iris inside the apworld, don't: leave it out of the apworld and document
>   it as an Iris flag instead (they already are CLI flags: `iris/args.py`, one per `EXTRAS` entry).
> - Ship Upgrades = vanilla in open world is treated as progressive (say so in the option text).

## Prompt 1: open-world base patch, data export, `open_world` option

> Add an open-world AP base patch and data export next to the linear ones.
> - `tools/build_ap_basepatch.py`: a second options set `OPEN_WORLD_OPTIONS` = the linear `OPTIONS` plus
>   `open_world=True, boss_placement="fixed"` (no extras, no leader) → `archipelago/lufia2ow/basepatch_open_world.bsdiff4`.
>   `--check` checks both. Keep the linear patch byte-identical.
> - `tools/export_ap_data.py`: export the open-world data from the open-world base ROM into
>   `archipelago/lufia2ow/data_open_world.py` (same literal-only style), adding the boss NPCs from `placed_bosses()`:
>   spot name, map, flag, talk-script signature, and the ROM offsets of the per-spot operands a shuffle rewrites
>   (NPC-load sprite, MUSIC bgm, BOSS_BATTLE formation) and of each reward's ITEM operand; plus `BOSSES`/`DAOS`
>   (name, sprite, formation, bgm), the spot order, and the orb-check grant if present. Check the grant export
>   (`tools/dump_item_grants.py` `collect`) picks up the boss reward ITEMs; if not, export them as above.
> - `tests/test_ap_export.py`: parametrize the current-ness and config-header tests over both.
> - apworld: an `open_world` Toggle (default off) in `options.py`; `rom.py` `base_patch()` and the `data` module used
>   by the world come from the open-world pair when it's on. Only the plumbing: open-world logic is prompt 2.
> Done when both patches build, `--check` passes for both, `tests/test_ap_export.py` and `tests/test_open_world_bosses.py`
> pass, and the linear outputs are unchanged.

## Prompt 2: open-world region map

> With `open_world` on, `logic.py`'s story-stage regions don't apply: build a region map where areas are reachable
> from the start (Elcid) and gated by travel only: Ship (sea), Submarine (seafloor), Engine/airship (sky), using the
> existing `ShipUpgrades` items (`items.py`; `__init__.py` around line 136), plus the key items/tools that still lock
> doors (`logic.py` reads key doors from the ROM). `ShipUpgrades` vanilla → progressive in open world (option text).
> Goals that need the story (e.g. `chaed`) must still be reachable or be rejected with an OptionError in open world.
> Linear seeds generate the same as before. Done when an open-world and a linear seed both generate and
> `tools/build_apworld.py` still packages.

## Prompt 3: characters, capsules, maidens as items; boss NPCs and the orb as locations

> In open world only: each character, capsule species and maiden is an AP item (index `$0200+c`, `$0210+s`,
> `$0220+m`); characters and maidens progression (maidens open the Doom Island barrier), capsules useful; no vanilla
> joins left in the pool. Every placed boss NPC's reward(s) and the orb check (if in the base) are locations, using
> prompt 1's export; rewards are written like grants (`rom.write_grant`). Region per spot from prompt 2.
> Done when an open-world seed places these and the generated tokens write the boss and orb grants.

## Prompt 4: boss placement and boss strength options

> `boss_placement` (fixed / shuffled, default fixed) and `boss_strength` (unchanged / party_level / by_depth, default
> unchanged), open world only. Shuffled: port `bosses.shuffled_placement` to the apworld (seeded by the AP random)
> and write each spot's sprite/bgm/formation bytes from prompt 1's export with tokens. Strength: write
> `AP_OPT_BOSS_STRENGTH` (0/1/2); by_depth writes `AP_OPT_BOSS_LEVELS[formation]` for each placed boss, computed
> the way `bosses.scale_to_depth` ranks depth. A boss placed at several spots gets one level (mean, as there).
> Add `write_*` helpers to `rom.py`. Done when tests read the tokens back for each choice.

## Prompt 5: leader and extras as per-seed options

> Make `leader` and each extra per-seed apworld options, as token variants over the open-world base patch.
> Method: for a variant, build the open-world base with it on and diff against the base. A variant is token-able if
> the diff is small, in place (no moved containers) and composes with the others (base + all chosen diffs == a build
> with all of them on; test that). Where a variant isn't, first try making the base hold room for it (e.g. the
> opening's leader-swap block always present, with the leader byte the token sets, Maxim = skip); if it still can't
> be done without shipping Iris, leave it out of the apworld and document it as an Iris flag in
> `archipelago/lufia2ow/docs/setup_en.md`. Export the variant diffs in `data_open_world.py`.
> Done when each shipped variant has a composition test and the left-out ones are documented.

## Findings from prompt 1 (commits 4533afe..a3929bb)

- The world picks `self.data` (`data` or `data_open_world`) and `self.grant_offsets` per instance in `generate_early`;
  `rom.base_patch(open_world)`; `write_grant(offset, item_index)` takes the offset. Linear and open-world players can
  share a multiworld. `CHESTS`, `CONFIG`, `EVENT_FLAGS`, `GOAL_FLAG`, `KEY_DOORS`, `MAP_NAMES` are equal in both
  modules; `GRANTS` (44 vs 30) and `HINT_NPCS` differ.
- Open world replaces 13 story scripts (14 grants: 07-C-01, 14-C-03, 26-B-18, 2A-B-18, 3D-C-01, 3F-B-1B, 7E-C-01,
  8B-B-25, BF-B-2D, D6-C-02, DC-C-01, E0-C-01, E4-C-01 ×2), so an open-world player has no grant locations today.
- `data_open_world.BOSS_NPCS`: (spot, map, flag, talk signature, sprite offset, bgm offset, formation offset,
  reward item-byte offsets), Daos last; 37 spots (24 one reward, 13 two) + Daos (none). A reward is placed like a
  grant: `[0x20|0x21, item & 0xFF]` at offset-1. The boss's beaten flag is the check. Also `BOSS_SPOTS`, `FINAL_SPOT`,
  `BOSSES`, `DAOS`, `PLACEHOLDER_ITEM`. Boss NPC signatures use Iris's letter B (e.g. 05-B-57).
- Another base-patch variant = one more entry in `tools/build_ap_basepatch.py` `PATCHES`, `tools/export_ap_data.py`
  `MODULES` and `rom.BASE_PATCHES`.
- No real AP generation ran: `GitHub\Archipelago` is an old LoL fork. The user chose a fresh upstream clone at
  `C:\Users\marti\Documents\GitHub\Archipelago-upstream` for generation tests (2026-10-12).

## Findings from prompt 2

- Open-world regions are `logic.OPEN_AREAS` (one region per travel area, each entered from its `parent`): "Elcid to
  Aleyn" (maps 0x02-0x5F, on foot), "Sea" (Ship), "Seafloor" (Submarine), "Chaed and Dragon Mountain" (Submarine or
  airship), "Gratze" (Submarine, airship, or Bomb+Hook+Dankirk key), "Sky" (airship), "Shrine of Daos" (Sky +
  Submarine). `logic.area_of_map(map)` gives a map's area, so a boss spot's region is `area_of_map(spot map)`; the boss
  spot maps 0xED (darbi_shrine) and 0xEF (zeppy_cave) already have areas. Locations keep their map's tool/key rule
  through `logic.OPEN_MAP_RULES`.
- Travel needs are terrorwave's `tables/requirements.txt`; terrorwave starts on the Ship, so "needs the Ship" for all
  maps from 0x60 is ours (the story only reaches them after Aleyn). Door key/Shrine key gate nothing in open world
  (terrorwave's useless_keys; the Door key isn't even in the open-world pool). Worth an emulator check: that Elcid to
  Aleyn really is walkable without the Ship in Iris's open world.
- terrorwave's Daos spot also needs the three maidens, all tools and all keys; only the Submarine/airship part is in
  the logic now. Prompt 3: gate "Shrine of Daos" (or the "Defeat Daos" event location) on the maiden items.
- In open world the world rewrites options in `generate_early`: own_stage -> own_world (keys/tools), ship_upgrades
  vanilla -> progressive; a goal outside `logic.OPEN_GOALS` (daos, dragon_eggs) raises OptionError. No Merix egg in
  open world (its grant is gone), so the eggs goal pools 8 per wish. With open world all areas are always in.
- The open-world pool is the chests' vanilla items plus the ship items; each extra item drops one filler
  (`_drop_filler`), so adding boss reward locations and character/capsule/maiden items in prompt 3 must keep
  `len(itempool) == empty locations` (test `test_pool_fits_locations`).
