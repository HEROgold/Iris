# Disclaimer

This project isn't finished yet! and in a alpha phase.
There are a lot of things that could get changed at any moment in time.
Furthermore there's a lot of lines that could use some refactoring, or fixing.

## State of project

Due to University this project is being put to a pause.
there is however still plenty of time to review Pr's of fix some issues.

Most of this project/toolkit is in a usable state.
With Iris it should be quite quick to make custom (data related) patches.
(see patches/custom.py for examples)

## Supported patches

- Vanilla (unheadered/headered)
- GameGenie codes (applies them to rom)

## Planned Support

- Frue v7
- Spekkio v7
- Kureji v7

## Documentation

Currently there's no official documentation, however this is planned!
In it's current state, the advice is to look through the main file, and through the patches directory. patches/HEROgold contains the patches i've writting using this toolkit. Hopefully it'll give you an idea on how to write you own in a easy way.
For deeper knowledge, the structures directory contains a every(?) object the game uses, and in those file we define how we load/read and patch/write it from and to a rom.
The tables directory contains tables and pointer information for a given object, which are then used by the right objects in the structures directory. The way these tables are setup and imported, allows for different patches to import the correct tables data. However, this approach has the tendancy to mess up some linters. Only the vanilla tables have been tested so far.

So far, it's been tested on the vanilla Lufia 2 USA rom.

- file: Lufia II - Rise of the Sinistrals (U).smc
- md5: 0268E8E3B4822ABBB8578823ADD5B8DA

## Generating lookup helpers

For convenient, named access to game data there's a generator that dumps every
structure from a vanilla ROM and writes helper namespaces (mirroring the
hand-written `Players` in `characters.py`). The generated `lookups/` package is
**not** committed — regenerate it locally whenever you need it.

Run from the `src` directory, forcing the vanilla table set (the default
suggested patch is Frue):

```sh
cd src
python -m tools.generate_lookups --file "roms/Lufia II - Rise of the Sinistrals (USA).sfc" --vanilla
```

Note: this project requires Python 3.12 (`>=3.12`). It does **not** run on Python
3.14, where the stdlib gained a `_types` module that shadows this repo's
`src/_types/` package. With `uv` you can pin the interpreter without touching your
environment:

```sh
cd src
uv run --no-project --python 3.12 --with "bitstring>=4.2.3" python -m tools.generate_lookups --file "roms/Lufia II - Rise of the Sinistrals (USA).sfc" --vanilla
```

This writes `src/lookups/` with one module per structure (`players.py`,
`items.py`, `monsters.py`, `spells.py`, `zones.py`, `capsules.py`, `shops.py`,
`words.py`, `events.py`, `map_events.py`, `ip_attacks.py`, the formation and chest
tables, `maidens.py`, …) plus an `__init__.py` that re-exports every namespace.
Each member is the live structure instance read from the ROM, so you can write
e.g.:

```python
from lookups import Items, Monsters, Spells

Items.POTION        # the Item instance
Monsters.GOBLIN     # the Monster instance
Spells.THUNDER      # the Spell instance
```

Member names come from the in-game names (upper-snake-cased); duplicates get an
index suffix, and structures without a name (shops, formations) are named by
index, e.g. `Shops.SHOP_0`. Output is deterministic for a given ROM. To add or
change what's generated, edit `tools/generate_lookups.py` (the `SPECS` table) and
re-run — don't hand-edit files under `lookups/`.

## Thanks

There's a list of people who helped a lot while making this project.

- Inspired by [@Absynnonym/terrorwave](https://github.com/abyssonym/terrorwave)'s project. (some of his patches are included!)
- RealCritical has helped me with some monster script's and helped sourcing information.
- Artemis for his Frue, Spekko and Kureji patches, which ofcource also contained a lot of information about the game. Like object structures.
- RndMeme for helping with the Shop layouts.

Did i miss you? Just let me know!
