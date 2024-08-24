import logging
from logger import iris

logger = logging.getLogger(f"{iris.name}.Addresses")

def address_to_lorom(address: int):
    logger.debug(f"Transforming to lorom {address=}")
    if address > 0x3fffff:
        raise Exception('LOROM address out of range.')
    base = ((address << 1) & 0xFFFF0000)
    lorom_address = base | 0x8000 | (address & 0x7FFF)
    assert (address_from_lorom(lorom_address & 0x7fffff) ==
            address_from_lorom(lorom_address | 0x800000))
    return lorom_address | 0x800000



def address_from_lorom(lorom_address: int):
    logger.debug(f"Transforming from lorom {lorom_address=}")
    lorom_address &= 0x7FFFFF
    base = (lorom_address >> 1) & 0xFFFF8000
    address = base | (lorom_address & 0x7FFF)
    #assert lorom_address == map_to_lorom(address)
    return address
