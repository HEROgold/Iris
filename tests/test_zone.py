from helpers.files import original_file, new_file
from structures.zone import Zone
from tables import ZoneObject


def test_read():
    for index in range(ZoneObject.count):
        assert Zone.from_index(index)

def test_write():
    for index in range(ZoneObject.count):
        inst = Zone.from_index(index)
        inst.write()
        with open(original_file, "rb") as rf, open(new_file, "rb") as wf:
            assert rf.read() == wf.read()
