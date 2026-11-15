"""Board selection is explicit: BluFi advertisements do not identify hardware."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Board:
    name: str
    manifest_id: str
    title: str
    hardware: str
    stock_versions: tuple[str, ...]
    model: str
    project: str
    version: str
    header: int
    max_image: int
    firmware_bytes: int

BOARDS = {
    'v2': Board('v2', 'pura-v2', 'V2 / ESP32-WROOM-32', '2.1', ('2.10', '2.10.0', '2.10.1'),
                'v2', 'pura_setup', 'pura-setup-3', 0x20, 0x12c000, 4 * 1024 * 1024),
    'v3': Board('v3', 'pura-v3', 'V3 / ESP32-WROVER-E', '3.0', ('2.7', '2.7.0'),
                'v3l', 'pura_v3_setup', 'pura-v3-setup-3', 0x40, 0xc0000, 16 * 1024 * 1024),
}

def get_board(name: str) -> Board:
    try:
        return BOARDS[name]
    except KeyError:
        raise ValueError('Choose v2 or v3. Other hardware is unsupported.') from None
