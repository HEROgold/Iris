"""Map names decode their 0x0A back-references, nested ones included."""

from iris.structures.zone import Zone


def test_back_references_are_expanded() -> None:
    assert Zone.from_index(0x06).clean_name == b"Cave to Sundletan B1"
    assert Zone.from_index(0x3B).clean_name == b"Gordovan West Tower 4F"
    assert Zone.from_index(0xE7).clean_name == b"Shrine of Daos 1F"
