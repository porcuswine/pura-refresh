#include "esp_private/startup_internal.h"
#include "esp_rom_spiflash.h"

// Referenced from main.c so the linker retains this unit and its startup entry.
void pura_link_legacy_boot(void) {}

// Stock Pura bootloaders can advertise 16 MB even on a physical 4 MB module.
// Modern IDF asserts before app_main when that inherited size exceeds the chip.
// Our supported stock partitions all fit within 4 MB. Cap only the inherited RAM
// descriptor, before IDF's priority-130 flash probe. Do not rewrite the bootloader.
ESP_SYSTEM_INIT_FN(pura_legacy_flash_limit, CORE, BIT(0), 129)
{
    if (g_rom_flashchip.chip_size > 4 * 1024 * 1024) {
        g_rom_flashchip.chip_size = 4 * 1024 * 1024;
    }
    return ESP_OK;
}
