"""Check the application image AND linked startup ordering before creating its manifest."""
import argparse
import json
from pathlib import Path
from elftools.elf.elffile import ELFFile
from pura_refresh.image import inspect_image


def verify(elf_path,sdkconfig,board):
    config=Path(sdkconfig).read_text()
    required=['CONFIG_PARTITION_TABLE_OFFSET=0x10000','CONFIG_ESP32_REV_MIN=0',
              '# CONFIG_ESP_SYSTEM_ESP32_SRAM1_REGION_AS_IRAM is not set',
              '# CONFIG_ESP_WIFI_NVS_ENABLED is not set']
    if board == 'v3':
        required += ['# CONFIG_PARTITION_TABLE_MD5 is not set', '# CONFIG_SPIRAM is not set']
    if any(line not in config.splitlines() for line in required):
        raise ValueError('Build settings are incompatible with the stock first-flash contract.')
    with Path(elf_path).open('rb') as stream:
        elf=ELFFile(stream)
        table=elf.get_section_by_name('.symtab')
        symbols={s.name:s['st_value'] for s in table.iter_symbols()}
        hook=symbols.get('esp_system_init_fn_pura_legacy_flash_limit')
        probe=symbols.get('esp_system_init_fn_init_flash')
        if hook is None or probe is None or not hook<probe:
            raise ValueError('Legacy flash-size hook is missing or runs after the flash probe.')
        if '__esp_system_init_fn_pura_legacy_flash_limit' not in symbols:
            raise ValueError('Legacy startup implementation was discarded by the linker.')
    return dict(startup_hook_order_checked=True)


if __name__ == '__main__':
    from pura_refresh.boards import get_board
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--board', choices=['v2','v3'], required=True)
    p.add_argument('--build',type=Path,required=True)
    p.add_argument('--sdkconfig',type=Path,required=True)
    p.add_argument('--images',type=Path,required=True)
    a=p.parse_args()
    board=get_board(a.board)
    blob=(a.build/(board.project+'.bin')).read_bytes()
    manifest=inspect_image(blob, a.board)
    manifest.update(verify(a.build/(board.project+'.elf'), a.sdkconfig, a.board))
    manifest.update(board=board.manifest_id, partition_table_offset=0x10000,
        release_status='development rebuild; hardware validation required', contains_personal_credentials=False)
    if a.board == 'v2':
        manifest.update(legacy_flash_cap_bytes=0x400000)
    else:
        manifest.update(partition_table_md5_required=False, heater_off_gpio_level=0,
            psram_gpio_untouched=[16,17], max_image_bytes=board.max_image,
            legacy_flash_size_handling='cap inherited descriptor to valid JEDEC density, retaining up to 16MB')
    a.images.mkdir(parents=True, exist_ok=True)
    (a.images/'application.bin').write_bytes(blob)
    (a.images/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))
