import sys
import pytest

def pytest_addoption(parser: pytest.Parser) -> None:
    sys.argv.pop(1)
    parser.addoption("--file", type=str, help="File to randomize.", required=True)
