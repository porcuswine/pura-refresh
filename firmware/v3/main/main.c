#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "cJSON.h"
#include "driver/gpio.h"
#include "esp_app_desc.h"
#include "esp_event.h"
#include "esp_http_server.h"
#include "esp_mac.h"
#include "esp_flash.h"
#include "esp_netif.h"
#include "esp_ota_ops.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "mbedtls/base64.h"
#include "nvs.h"
#include "nvs_flash.h"

// V3 WROVER only. GPIO16/17 belong to internal PSRAM and are never driven.
static esp_netif_t *station;
static nvs_handle_t settings;
static char identity[32], mac_text[18], admin_password[64] = "pura-setup";
static char saved_ssid[33], saved_wifi_password[65];
static bool configured, updating, settings_available;
static esp_err_t settings_error;
void pura_link_legacy_boot(void);

// Read the stock table at 0x10000. Build-time CSV is not written by OTA.
static bool layout_compatible(void) {
    uint32_t flash_size=0;
    if (esp_flash_get_size(NULL, &flash_size)!=ESP_OK) return false;
    const esp_partition_t *a=esp_partition_find_first(ESP_PARTITION_TYPE_APP, ESP_PARTITION_SUBTYPE_APP_OTA_0, NULL);
    const esp_partition_t *b=esp_partition_find_first(ESP_PARTITION_TYPE_APP, ESP_PARTITION_SUBTYPE_APP_OTA_1, NULL);
    if (!a || !b || a->size<0xc0000 || b->size<0xc0000) return false;
    if ((a->address|b->address)&0xffff) return false;
    if (a->address>flash_size || a->size>flash_size-a->address ||
        b->address>flash_size || b->size>flash_size-b->address) return false;
    return a->address+a->size<=b->address || b->address+b->size<=a->address;
}

static void outputs_off(void) {
    const int heaters[] = {22, 23};
    const int status[] = {26, 2, 27};
    const int bays[] = {25, 33, 5, 19, 18, 21};
    for (int i=0; i<2; i++) {
        gpio_set_level(heaters[i], 0);
        gpio_set_direction(heaters[i], GPIO_MODE_OUTPUT);
    }
    for (int i=0; i<3; i++) {
        gpio_set_level(status[i], 1);
        gpio_set_direction(status[i], GPIO_MODE_OUTPUT);
    }
    for (int i=0; i<6; i++) {
        gpio_set_level(bays[i], 0);
        gpio_set_direction(bays[i], GPIO_MODE_OUTPUT);
    }
}

static bool authorized(httpd_req_t *req) {
    char plain[80], expected[128] = "Basic ", received[160];
    size_t written;
    snprintf(plain, sizeof(plain), "pura:%s", admin_password);
    if (mbedtls_base64_encode((unsigned char *)expected+6, sizeof(expected)-7,
            &written, (unsigned char *)plain, strlen(plain)) == 0) {
        expected[6+written] = 0;
        if (httpd_req_get_hdr_value_str(req, "Authorization", received, sizeof(received)) == ESP_OK &&
                strcmp(expected, received) == 0) return true;
    }
    httpd_resp_set_status(req, "401 Unauthorized");
    httpd_resp_set_hdr(req, "WWW-Authenticate", "Basic realm=\"Pura setup\"");
    httpd_resp_sendstr(req, "Sign in with username pura and your device password.");
    return false;
}

// Authenticated metadata-only diagnostics remain useful even if this SDK was
// built for a different stock table offset. Never return NVS contents or keys.
static void add_raw_table_diagnostics(cJSON *status, uint32_t flash_size) {
    typedef struct __attribute__((packed)) {
        uint16_t magic; uint8_t type, subtype;
        uint32_t offset, size; char label[16]; uint32_t flags;
    } raw_entry_t;
    cJSON *tables=cJSON_AddArrayToObject(status, "raw_partition_tables");
    for (uint32_t address=0x8000; address<=0x20000; address+=0x1000) {
        raw_entry_t first;
        if (esp_flash_read(NULL, &first, address, sizeof(first))!=ESP_OK ||
            first.magic!=0x50aa || first.type>1 || !first.size ||
            first.offset>=flash_size || first.size>flash_size-first.offset) continue;
        cJSON *table=cJSON_CreateObject();
        cJSON_AddNumberToObject(table, "address", address);
        cJSON *entries=cJSON_AddArrayToObject(table, "entries");
        for (unsigned i=0; i<95; i++) {
            raw_entry_t entry;
            if (esp_flash_read(NULL, &entry, address+i*sizeof(entry), sizeof(entry))!=ESP_OK ||
                entry.magic!=0x50aa || entry.type>1 || !entry.size ||
                entry.offset>=flash_size || entry.size>flash_size-entry.offset) break;
            char label[17]; memcpy(label, entry.label, 16); label[16]=0;
            cJSON *item=cJSON_CreateObject();
            cJSON_AddStringToObject(item, "label", label);
            cJSON_AddNumberToObject(item, "type", entry.type);
            cJSON_AddNumberToObject(item, "subtype", entry.subtype);
            cJSON_AddNumberToObject(item, "address", entry.offset);
            cJSON_AddNumberToObject(item, "size", entry.size);
            cJSON_AddItemToArray(entries, item);
        }
        cJSON_AddItemToArray(tables, table);
    }
}

static esp_err_t status_handler(httpd_req_t *req) {
    if (!authorized(req)) return ESP_OK;
    esp_netif_ip_info_t ip = {0};
    esp_netif_get_ip_info(station, &ip);
    char address[16];
    snprintf(address, sizeof(address), IPSTR, IP2STR(&ip.ip));
    bool compatible=layout_compatible();
    const esp_partition_t *running = compatible ? esp_ota_get_running_partition() : NULL;
    cJSON *s = cJSON_CreateObject();
    cJSON_AddStringToObject(s, "name", identity);
    cJSON_AddStringToObject(s, "mac", mac_text);
    cJSON_AddStringToObject(s, "version", esp_app_get_description()->version);
    cJSON_AddStringToObject(s, "ip", address);
    cJSON_AddStringToObject(s, "partition", running ? running->label : "unknown");
    cJSON_AddStringToObject(s, "hardware", "pura-v3");
    uint32_t flash_size=0, physical_size=0;
    esp_flash_get_size(NULL, &flash_size);
    esp_flash_get_physical_size(NULL, &physical_size);
    cJSON_AddNumberToObject(s, "flash_bytes", flash_size);
    cJSON_AddNumberToObject(s, "physical_flash_bytes", physical_size);
    add_raw_table_diagnostics(s, physical_size);
    cJSON *parts=cJSON_AddArrayToObject(s, "partitions");
    esp_partition_iterator_t it=esp_partition_find(ESP_PARTITION_TYPE_ANY, ESP_PARTITION_SUBTYPE_ANY, NULL);
    for (; it; it=esp_partition_next(it)) {
        const esp_partition_t *p=esp_partition_get(it);
        cJSON *item=cJSON_CreateObject();
        cJSON_AddStringToObject(item, "label", p->label);
        cJSON_AddNumberToObject(item, "type", p->type);
        cJSON_AddNumberToObject(item, "subtype", p->subtype);
        cJSON_AddNumberToObject(item, "address", p->address);
        cJSON_AddNumberToObject(item, "size", p->size);
        cJSON_AddItemToArray(parts, item);
    }
    cJSON_AddBoolToObject(s, "setup_required", !configured);
    cJSON_AddBoolToObject(s, "settings_available", settings_available);
    cJSON_AddBoolToObject(s, "layout_compatible", compatible);
    cJSON_AddNumberToObject(s, "settings_error", settings_error);
    cJSON_AddBoolToObject(s, "heaters_off", true);
    cJSON_AddNumberToObject(s, "uptime_seconds", esp_timer_get_time()/1000000);
    char *body = cJSON_PrintUnformatted(s);
    httpd_resp_set_type(req, "application/json");
    httpd_resp_set_hdr(req, "Cache-Control", "no-store");
    esp_err_t result = httpd_resp_sendstr(req, body ? body : "{}");
    free(body);
    cJSON_Delete(s);
    return result;
}

static esp_err_t home_handler(httpd_req_t *req) {
    if (!authorized(req)) return ESP_OK;
    httpd_resp_set_type(req, "text/html");
    httpd_resp_set_hdr(req, "Cache-Control", "no-store");
    httpd_resp_set_hdr(req, "X-Content-Type-Options", "nosniff");
    httpd_resp_set_hdr(req, "Content-Security-Policy", "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; frame-ancestors 'none'");
    return httpd_resp_sendstr(req,
        "<!doctype html><meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Pura setup</title><style>body{font:18px system-ui;max-width:36rem;margin:2rem auto;padding:1rem}"
        "input,button{box-sizing:border-box;font:inherit;padding:.6rem;margin:.3rem 0;width:100%}label{display:block;margin-top:1rem}</style>"
        "<h1>Pura setup</h1><p id='state'>Checking device…</p>"
        "<form id='setup'><h2>Connect to your Wi-Fi</h2>"
        "<label>Network name<input id='ssid' maxlength='32' required autocomplete='off'></label>"
        "<label>Wi-Fi password<input id='wifi' type='password' maxlength='64' autocomplete='new-password'></label>"
        "<label>New device password<input id='admin' type='password' minlength='12' maxlength='63' required autocomplete='new-password'></label>"
        "<p>Use the new device password for this page and the Pura recovery Wi-Fi. Keep it somewhere safe.</p>"
        "<button>Save and restart</button></form><p id='message' role='status'></p>"
        "<h2>Install firmware</h2><p>Choose firmware made for Pura V3.</p>"
        "<input id='file' type='file' accept='.bin'><button id='update'>Install update</button>"
        "<script>const byId=id=>document.getElementById(id);"
        "fetch('/status').then(r=>r.json()).then(s=>{byId('state').textContent=s.name+' · '+s.version+' · '+s.ip;"
        "if(!s.setup_required)byId('admin').required=false});"
        "byId('setup').onsubmit=async e=>{e.preventDefault();const b=e.submitter;b.disabled=true;try{"
        "let r=await fetch('/setup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({"
        "ssid:byId('ssid').value,password:byId('wifi').value,admin:byId('admin').value})});"
        "byId('message').textContent=await r.text()}catch(e){byId('message').textContent='Connection interrupted. Check the recovery Wi-Fi.'}b.disabled=false};"
        "byId('update').onclick=async()=>{const f=byId('file').files[0];if(!f)return;byId('update').disabled=true;try{"
        "let r=await fetch('/update',{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:f});"
        "byId('message').textContent=await r.text()}catch(e){byId('message').textContent='Connection interrupted. Check the device before retrying.'}"
        "byId('update').disabled=false}</script>");
}

static void reboot_task(void *unused) {
    vTaskDelay(pdMS_TO_TICKS(2000));
    esp_restart();
}

static bool valid_password(const char *p) {
    size_t n = strlen(p);
    if (n < 12 || n > 63 || strcmp(p, "pura-setup") == 0) return false;
    for (size_t i=0; i<n; i++) if ((unsigned char)p[i]<32 || (unsigned char)p[i]>126) return false;
    return true;
}

static esp_err_t setup_handler(httpd_req_t *req) {
    if (!authorized(req)) return ESP_OK;
    if (!settings_available) return httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR,
        "Stock settings storage could not be opened. Recovery Wi-Fi and firmware updates remain available; no stock data has been erased.");
    if (updating || req->content_len < 2 || req->content_len > 512) {
        return httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "Invalid setup request.");
    }
    char body[513];
    size_t got = 0;
    while (got < req->content_len) {
        int n = httpd_req_recv(req, body+got, req->content_len-got);
        if (n <= 0) return httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "Setup upload interrupted.");
        got += n;
    }
    body[got] = 0;
    cJSON *json = cJSON_ParseWithLength(body, got+1);
    cJSON *ssid = cJSON_GetObjectItemCaseSensitive(json, "ssid");
    cJSON *wifi = cJSON_GetObjectItemCaseSensitive(json, "password");
    cJSON *admin = cJSON_GetObjectItemCaseSensitive(json, "admin");
    if (!cJSON_IsString(ssid) || !cJSON_IsString(wifi) || !cJSON_IsString(admin) ||
            strlen(ssid->valuestring)<1 || strlen(ssid->valuestring)>32 ||
            strlen(wifi->valuestring)>64 ||
            (strlen(admin->valuestring) ? !valid_password(admin->valuestring) : !configured)) {
        cJSON_Delete(json);
        return httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST,
            "Enter a network name and a device password of 12–63 printable ASCII characters.");
    }
    // Store a single atomic blob in our own namespace. Never erase stock NVS.
    struct { char ssid[33], wifi[65], admin[64]; } config = {0};
    strlcpy(config.ssid, ssid->valuestring, sizeof(config.ssid));
    strlcpy(config.wifi, wifi->valuestring, sizeof(config.wifi));
    strlcpy(config.admin, strlen(admin->valuestring) ? admin->valuestring : admin_password, sizeof(config.admin));
    esp_err_t err = nvs_set_blob(settings, "config", &config, sizeof(config));
    if (err == ESP_OK) err = nvs_commit(settings);
    cJSON_Delete(json);
    memset(body, 0, sizeof(body));
    memset(&config, 0, sizeof(config));
    if (err != ESP_OK) return httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR,
        "Could not save settings. Original settings have not been erased.");
    httpd_resp_sendstr(req, "Saved. Pura will restart and join your Wi-Fi. If it cannot connect, join its Pura-Setup Wi-Fi using your new device password and open http://172.29.241.1.");
    xTaskCreate(reboot_task, "reboot", 2048, NULL, 3, NULL);
    return ESP_OK;
}

static esp_err_t upload_handler(httpd_req_t *req) {
    if (!authorized(req)) return ESP_OK;
    if (!layout_compatible()) return httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST,
        "This board has an unsupported partition layout. No flash writes were started.");
    const esp_partition_t *next = esp_ota_get_next_update_partition(NULL);
    if (updating || !next || req->content_len<32 || req->content_len>next->size)
        return httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "Image does not fit, or an update is in progress.");
    updating = true;
    esp_ota_handle_t handle = 0;
    esp_err_t error = esp_ota_begin(next, req->content_len, &handle);
    char buffer[2048];
    size_t received = 0;
    int timeouts = 0;
    while (error == ESP_OK && received < req->content_len) {
        int n = httpd_req_recv(req, buffer,
            req->content_len-received < sizeof(buffer) ? req->content_len-received : sizeof(buffer));
        if (n == HTTPD_SOCK_ERR_TIMEOUT && ++timeouts<4) continue;
        if (n<=0 || (!received && (unsigned char)buffer[0]!=0xe9)) { error=ESP_FAIL; break; }
        timeouts=0;
        error=esp_ota_write(handle, buffer, n);
        received+=n;
    }
    if (error==ESP_OK) { error=esp_ota_end(handle); handle=0; }
    if (handle) esp_ota_abort(handle);
    if (error==ESP_OK) error=esp_ota_set_boot_partition(next);
    updating=false;
    if (error!=ESP_OK) return httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST,
        "Image failed validation. Current firmware remains selected.");
    httpd_resp_sendstr(req, "Update installed. Pura is restarting.");
    xTaskCreate(reboot_task, "reboot", 2048, NULL, 3, NULL);
    return ESP_OK;
}

static void network_event(void *unused, esp_event_base_t base, int32_t event, void *data) {
    if (base==WIFI_EVENT && (event==WIFI_EVENT_STA_START || event==WIFI_EVENT_STA_DISCONNECTED)) {
        gpio_set_level(GPIO_NUM_2, 1);
        esp_wifi_connect();
    }
    if (base==IP_EVENT && event==IP_EVENT_STA_GOT_IP) gpio_set_level(GPIO_NUM_2, 0);
}

void app_main(void) {
    pura_link_legacy_boot(); // Link anchor; the compatibility hook itself ran before flash init.
    outputs_off();
    uint8_t mac[6];
    esp_read_mac(mac, ESP_MAC_WIFI_STA);
    snprintf(identity, sizeof(identity), "Pura-Setup-%02X%02X", mac[4], mac[5]);
    snprintf(mac_text, sizeof(mac_text), "%02x:%02x:%02x:%02x:%02x:%02x", MAC2STR(mac));
    // Never prevent recovery Wi-Fi from starting just because stock NVS is incompatible/full.
    settings_error=nvs_flash_init();
    if (settings_error==ESP_OK) settings_error=nvs_open("pura_setup", NVS_READWRITE, &settings);
    settings_available=(settings_error==ESP_OK);
    struct { char ssid[33], wifi[65], admin[64]; } stored = {0};
    size_t size = sizeof(stored);
    if (settings_available && nvs_get_blob(settings, "config", &stored, &size)==ESP_OK && size==sizeof(stored) &&
            memchr(stored.ssid, 0, sizeof(stored.ssid)) && memchr(stored.wifi, 0, sizeof(stored.wifi)) &&
            memchr(stored.admin, 0, sizeof(stored.admin)) && valid_password(stored.admin)) {
        configured=true;
        strlcpy(saved_ssid, stored.ssid, sizeof(saved_ssid));
        strlcpy(saved_wifi_password, stored.wifi, sizeof(saved_wifi_password));
        strlcpy(admin_password, stored.admin, sizeof(admin_password));
    }
    memset(&stored, 0, sizeof(stored));
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    station=esp_netif_create_default_wifi_sta();
    esp_netif_t *recovery=esp_netif_create_default_wifi_ap();
    ESP_ERROR_CHECK(esp_netif_dhcps_stop(recovery));
    esp_netif_ip_info_t recovery_ip={0};
    recovery_ip.ip.addr=ESP_IP4TOADDR(172, 29, 241, 1);
    recovery_ip.gw.addr=ESP_IP4TOADDR(172, 29, 241, 1);
    recovery_ip.netmask.addr=ESP_IP4TOADDR(255, 255, 255, 0);
    ESP_ERROR_CHECK(esp_netif_set_ip_info(recovery, &recovery_ip));
    ESP_ERROR_CHECK(esp_netif_dhcps_start(recovery));
    esp_netif_set_hostname(station, identity);
    wifi_init_config_t init=WIFI_INIT_CONFIG_DEFAULT();
    // First boot uses only our own recovery AP. Do not import stock Wi-Fi settings.
    // The installer switches its radio to this AP to verify boot independently of NVS.
    init.nvs_enable=0;
    ESP_ERROR_CHECK(esp_wifi_init(&init));
    wifi_config_t client={0};
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));
    if (configured) {
        memset(&client, 0, sizeof(client));
        memcpy(client.sta.ssid, saved_ssid, strlen(saved_ssid));
        memcpy(client.sta.password, saved_wifi_password, strlen(saved_wifi_password));
    }
    wifi_config_t access={0};
    strlcpy((char *)access.ap.ssid, identity, sizeof(access.ap.ssid));
    access.ap.ssid_len=strlen(identity);
    strlcpy((char *)access.ap.password, admin_password, sizeof(access.ap.password));
    access.ap.authmode=WIFI_AUTH_WPA2_PSK;
    access.ap.max_connection=2;
    access.ap.channel=1;
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, network_event, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, network_event, NULL));
    ESP_ERROR_CHECK(esp_wifi_set_mode(configured ? WIFI_MODE_APSTA : WIFI_MODE_AP));
    if (configured) ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &client));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP, &access));
    ESP_ERROR_CHECK(esp_wifi_start());
    esp_wifi_set_ps(WIFI_PS_NONE);
    gpio_set_level(GPIO_NUM_27, 0);
    httpd_config_t config=HTTPD_DEFAULT_CONFIG();
    config.max_uri_handlers=4;
    config.recv_wait_timeout=10;
    httpd_handle_t server=NULL;
    ESP_ERROR_CHECK(httpd_start(&server, &config));
    httpd_uri_t routes[]={
        {.uri="/", .method=HTTP_GET, .handler=home_handler},
        {.uri="/status", .method=HTTP_GET, .handler=status_handler},
        {.uri="/setup", .method=HTTP_POST, .handler=setup_handler},
        {.uri="/update", .method=HTTP_POST, .handler=upload_handler}
    };
    for (int i=0; i<4; i++) ESP_ERROR_CHECK(httpd_register_uri_handler(server, &routes[i]));
    // Harmless when rollback is disabled; confirms a pending image after recovery services start.
    if (layout_compatible()) esp_ota_mark_app_valid_cancel_rollback();
}
