from pathlib import Path
from typing import Literal

from enums.patches import Patch


PROJECT_NAME = "Iris"
VERSION = "0.1"
TEXT_VERSION = "Zero One"
AUTHORS = [{"name":"HEROgold", "email":""}]
DESCRIPTION = "A Lufia II: Rise of the Sinistrals randomizer/patching toolkit."

DEBUG_MODE = False
PROFILE_MODE = True

scale_custom_boss = None
scale_custom_non_boss = None
rom = Path(f"{__file__}").parent / "test_roms" / "Lufia II - Rise of the Sinistrals (USA).sfc"
POINTER_SIZE = 2


EMPTY_BYES = [
    range(0x286a10, 0x30d80e),
    range(0x30d87b, 0x3e4038),
    range(0x3e700d, 0x3e7ffc),
    range(0x3ec8d6, 0x3ee0ff),
    range(0x3eed0b, 0x3fffff),
]


ASCII_ART = r"""
_________ _______ _________ _______ 
\__   __/(  ____ )\__   __/(  ____ \
   ) (   | (    )|   ) (   | (    \/
   | |   | (____)|   | |   | (_____ 
   | |   |     __)   | |   (_____  )
   | |   | (\ (      | |         ) |
___) (___| ) \ \_____) (___/\____) |
\_______/|/   \__/\_______/\_______)
"""

ASCII_ART_COLORIZED = """
\033[32m_________ \033[0m\033[33m_______ \033[0m\033[37m_________\033[0m \033[31m_______ \033[0m
\033[32m\\__   __/\033[0m\033[33m(  ____ )\033[0m\033[37m\\__   __/\033[0m\033[31m(  ____ \\\033[0m
   \033[32m) (   \033[0m\033[33m| (    )|\033[0m\033[37m   ) (   \033[0m\033[31m| (    \\/ \033[0m
   \033[32m| |   \033[0m\033[33m| (____)|\033[0m\033[37m   | |   \033[0m\033[31m| (_____ \033[0m
   \033[32m| |   \033[0m\033[33m|     __)\033[0m\033[37m   | |   \033[0m\033[31m(_____  )\033[0m
   \033[32m| |   \033[0m\033[33m| (\\ (   \033[0m\033[37m   | |     \033[0m\033[31m    ) |\033[0m
\033[32m___) (___\033[0m\033[33m| ) \\ \\_____\033[0m\033[37m) (___/\033[0m\033[31m\\____) |\033[0m
\033[32m\\_______/\033[0m\033[33m|/   \\__/\033[0m\033[37m\\_______/\033[0m\033[31m\\_______)\033[0m
"""

KNOWN_ROMS = {
    "LUFIA2_NA": {"md5": "6efc477d6203ed2b3b9133c1cd9e9c5d", "filename": "tables_list.txt"},
    "LUFIA2_JP": {"md5": "18567d21df6a95a7b52029d250bac721", "filename": "tables_list_jp.txt"},
    "LUFIA2_FIX": {"md5": "026b649ed316448e038349e39a6fe579", "filename": "tables_list.fixxxer.txt"},
    "LUFIA2_FRUE_V6": {"md5": "b58c76f2ac0b2aeb9b779e880d2bff18", "filename": "tables_list.frue.txt"},
    "LUFIA2_SPEKKIO_V6": {"md5": "b4c4973a5f1cfd40bb1863dbad260de4", "filename": "tables_list.spekkio.txt"},
    "LUFIA2_KUREJI_V6": {"md5": "5983201c45de814dc3672ab7d8279886", "filename": "tables_list.kureji.txt"},
    "!LUFIA2_NA->LUFIA2_FIX": {"md5": "", "filename": "lufia2_fixxxer_unheadered.ips"},
}

BYTE_LENGTH = 8
SHIFT_BYTE = 8
MAX_2_BYTE = 0xFFFF
BYTE_ORDER: Literal["big", "little"] = "little"
PROJECT_PATH = Path(__file__).parent
SUGGESTED_PATCH = Patch.FRUE
