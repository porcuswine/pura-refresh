#include "esp_private/startup_internal.h"
#include "esp_rom_spiflash.h"

void pura_link_legacy_boot(void) {}

// Stock header sizes can exceed physical capacity. Preserve 16 MB on N16
// WROVER modules; cap only if the inherited JEDEC ID reports a smaller chip.
// JEDEC density encoding matches IDF spi_flash_chip_generic_detect_size for
// the supported 1--16 MB range. No flash writes or SPI commands are issued here.
ESP_SYSTEM_INIT_FN(pura_legacy_flash_limit, CORE, BIT(0), 129)
{
    unsigned density=g_rom_flashchip.device_id & 0xff;
    if (density>=20 && density<=24) {
        uint32_t physical_size=1U<<density;
        if (g_rom_flashchip.chip_size>physical_size)
            g_rom_flashchip.chip_size=physical_size;
    }
    return ESP_OK;
}
