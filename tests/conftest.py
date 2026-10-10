from pathlib import Path

import pytest

from iris.args import parse_args
from iris.helpers.files import open_rom
from iris.tables import select


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--file", type=str, help="File to randomize.", required=True)


def pytest_configure(config: pytest.Config) -> None:
    """Select the default patch's tables and open the ROM session before any test module is imported."""
    options = parse_args(["--file", config.getoption("--file")])
    select(options.selected_patch)
    open_rom(Path(options.file))
