import hashlib
import json
import struct
from pathlib import Path

from .boards import get_board

DEFAULT_IMAGES=Path(__file__).resolve().parent / "images"


def inspect_image(blob, board_name):
    board = get_board(board_name)
    if not 32<=len(blob)<=board.max_image or blob[0]!=0xe9 or not 1<=blob[1]<=16:
        raise ValueError("Expected a stock-slot-sized ESP application image, not a merged flash image.")
    if struct.unpack_from('<H',blob,12)[0]!=0 or blob[23]!=1:
        raise ValueError("Only SHA256-appended ESP32 images are supported.")
    if blob[2]!=2 or blob[3]!=board.header:
        raise ValueError(f'Image flash configuration does not match {board.title}.')
    pos, checksum, first = 24, 0xef, None
    for _ in range(blob[1]):
        if pos+8>len(blob): raise ValueError("Truncated segment header")
        address,size=struct.unpack_from('<II',blob,pos)
        regions=((0x3f400000,0x3f800000),(0x3ff80000,0x3ff82000),(0x3ffae000,0x40000000),
                 (0x40080000,0x400a0000),(0x400d0000,0x40400000),(0x50000000,0x50002000))
        if not any(low<=address and address+size<=high for low,high in regions):
            raise ValueError('Segment lies outside the legacy ESP32 bootloader-compatible memory regions.')
        pos+=8
        if pos+size>len(blob): raise ValueError("Truncated segment")
        segment=blob[pos:pos+size]
        if first is None: first=segment
        for value in segment: checksum^=value
        pos+=size
    checksum_at=(pos//16+1)*16-1
    if checksum_at>=len(blob) or blob[checksum_at]!=checksum:
        raise ValueError("ESP image checksum does not match")
    end=checksum_at+1
    if len(blob)!=end+32 or hashlib.sha256(blob[:end]).digest()!=blob[end:]:
        raise ValueError("ESP image validation hash does not match")
    if first is None or len(first)<80 or first[:4]!=bytes.fromhex('3254cdab'):
        raise ValueError("Missing ESP application descriptor")
    version=first[16:48].split(b'\0')[0].decode('ascii')
    project=first[48:80].split(b'\0')[0].decode('ascii')
    if project != board.project or version != board.version:
        raise ValueError("Image does not match the selected board's packaged firmware")
    return dict(bytes=len(blob),sha256=hashlib.sha256(blob).hexdigest(),version=version,project=project)


def load_image(board_name, folder=None):
    board = get_board(board_name)
    folder = Path(folder) if folder is not None else DEFAULT_IMAGES / board.name
    manifest = json.loads((folder / 'manifest.json').read_text())
    if manifest.get('board') != board.manifest_id or manifest.get('partition_table_offset') != 0x10000:
        raise ValueError('Firmware manifest does not match the selected board.')
    if manifest.get('startup_hook_order_checked') is not True:
        raise ValueError('Firmware lacks the checked startup compatibility hook.')
    if board.name == 'v2' and manifest.get('legacy_flash_cap_bytes') != 0x400000:
        raise ValueError('V2 firmware lacks its legacy flash-size cap.')
    if board.name == 'v3' and (manifest.get('partition_table_md5_required') is not False or
                              manifest.get('heater_off_gpio_level') != 0 or
                              manifest.get('psram_gpio_untouched') != [16, 17]):
        raise ValueError('V3 firmware lacks required legacy-table or GPIO compatibility settings.')
    blob = (folder / 'application.bin').read_bytes()
    actual = inspect_image(blob, board_name)
    if any(manifest.get(key) != value for key, value in actual.items()):
        raise ValueError('Firmware does not match its release manifest.')
    return blob, manifest
