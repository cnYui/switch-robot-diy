#pragma once

#include <stdbool.h>
#include <esp_err.h>

/* Everything the device remembers across power loss (NVS namespace "home"). */
typedef struct {
    char ssid[33];
    char pass[65];
    char mqtt_uri[128];
    char mqtt_user[33];
    char mqtt_pass[65];
    char name[48];
    int press_deg;
    int hold_ms;
    int neutral_us;
    bool invert;
    bool power;       /* last commanded state (open loop: the switch may have been flipped by hand) */
} settings_t;

extern settings_t g_settings;
extern char g_dev_id[16];   /* "sw-1a2b3c" from the Wi-Fi MAC */

esp_err_t settings_load(void);
esp_err_t settings_save(void);
esp_err_t settings_clear_network(void);   /* forget Wi-Fi and MQTT, keep calibration */
