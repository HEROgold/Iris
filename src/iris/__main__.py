from collections.abc import Sequence
from pathlib import Path

from iris.args import Args, parse_args
from iris.build import Options, build
from iris.helpers import files
from iris.helpers.files import output_path, save
from iris.logger import iris


def main(argv: Sequence[str] | None = None) -> Args:
    """Build the ROM described by ``argv`` (default: the command line) in the ROM session. :func:`save` writes it."""
    args = parse_args(argv)
    if args.debug:
        iris.setLevel("DEBUG")

    if not args.file:
        msg = "Pass the ROM to randomize with --file."
        raise SystemExit(msg)
    build(Path(args.file), Options.from_args(args))
    return args


def cli() -> None:
    """The ``iris`` command: build the ROM from the command line and write it."""
    options = main()
    save(output_path(files.original_file, options.seed))  # the one disk write of the run


if __name__ == "__main__":
    cli()

# TODO: Implement the following:
# Create own rom extractor, which can and should extract data from the rom. > well on its way
# This **SHOULD** work for different versions of the rom.
# TODO: Add some form of caching to avoid cloning and for faster access.
