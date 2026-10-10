from iris.structures.zone import Zone
from iris.tables import ZoneObject
from tests.reset_file import test_equal


def test_read() -> None:
    for index in range(ZoneObject.count):
        assert Zone.from_index(index)


def test_write() -> None:
    for index in range(ZoneObject.count):
        inst = Zone.from_index(index)
        inst.write()
        test_equal()
