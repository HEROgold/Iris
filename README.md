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

## Thanks

There's a list of people who helped a lot while making this project.

- Inspired by [@Absynnonym/terrorwave](https://github.com/abyssonym/terrorwave)'s project. (some of his patches are included!)
- RealCritical has helped me with some monster script's and helped sourcing information.
- Artemis for his Frue, Spekko and Kureji patches, which ofcource also contained a lot of information about the game. Like object structures.
- RndMeme for helping with the Shop layouts.

Did i miss you? Just let me know!
