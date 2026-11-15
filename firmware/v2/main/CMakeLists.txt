idf_component_register(SRCS "main.c" "legacy_boot.c" INCLUDE_DIRS "."
    REQUIRES esp_wifi esp_event esp_netif esp_http_server app_update
    esp_driver_gpio esp_timer nvs_flash json mbedtls)
