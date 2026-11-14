#include "settings.h"

#include <string.h>
#include <stdio.h>
#include <esp_log.h>
#include <esp_mac.h>
#include <nvs.h>
#include <nvs_flash.h>
#include <sdkconfig.h>

static const char *TAG = "settings";
static const char *NS = "home";

settings_t g_settings;
char g_dev_id[16];

static void get_str(nvs_handle_t h, const char *key, char *out, size_t cap, const char *def)
{
    size_t len = cap;
    if (nvs_get_str(h, key, out, &len) != ESP_OK) {
        strlcpy(out, def, cap);
    }
}

static int get_int(nvs_handle_t h, const char *key, int def)
{
    int32_t v;
    return nvs_get_i32(h, key, &v) == ESP_OK ? (int)v : def;
}

esp_err_t settings_load(void)
{
    uint8_t mac[6];
    esp_read_mac(mac, ESP_MAC_WIFI_STA);
    snprintf(g_dev_id, sizeof g_dev_id, "sw-%02x%02x%02x", mac[3], mac[4], mac[5]);

    settings_t *s = &g_settings;
    memset(s, 0, sizeof *s);
    nvs_handle_t h;
    esp_err_t err = nvs_open(NS, NVS_READONLY, &h);
    if (err == ESP_ERR_NVS_NOT_FOUND) {
        /* First boot: compile-time defaults only. */
        strlcpy(s->ssid, CONFIG_HOME_WIFI_SSID, sizeof s->ssid);
        strlcpy(s->pass, CONFIG_HOME_WIFI_PASSWORD, sizeof s->pass);
        strlcpy(s->mqtt_uri, CONFIG_HOME_MQTT_URI, sizeof s->mqtt_uri);
        s->press_deg = CONFIG_SWROBOT_SERVO_PRESS_DEG;
        s->hold_ms = CONFIG_SWROBOT_PRESS_HOLD_MS;
        s->neutral_us = CONFIG_SWROBOT_SERVO_NEUTRAL_US;
        return ESP_OK;
    }
    if (err != ESP_OK) {
        return err;
    }
    get_str(h, "ssid", s->ssid, sizeof s->ssid, CONFIG_HOME_WIFI_SSID);
    get_str(h, "pass", s->pass, sizeof s->pass, CONFIG_HOME_WIFI_PASSWORD);
    get_str(h, "uri", s->mqtt_uri, sizeof s->mqtt_uri, CONFIG_HOME_MQTT_URI);
    get_str(h, "muser", s->mqtt_user, sizeof s->mqtt_user, "");
    get_str(h, "mpass", s->mqtt_pass, sizeof s->mqtt_pass, "");
    get_str(h, "name", s->name, sizeof s->name, "");
    s->press_deg = get_int(h, "press", CONFIG_SWROBOT_SERVO_PRESS_DEG);
    s->hold_ms = get_int(h, "hold", CONFIG_SWROBOT_PRESS_HOLD_MS);
    s->neutral_us = get_int(h, "neutral", CONFIG_SWROBOT_SERVO_NEUTRAL_US);
    s->invert = get_int(h, "invert", 0) != 0;
    s->power = get_int(h, "power", 0) != 0;
    nvs_close(h);
    ESP_LOGI(TAG, "id %s, wifi '%s', mqtt '%s', press %d deg / %d ms / neutral %d us%s", g_dev_id, s->ssid,
             s->mqtt_uri, s->press_deg, s->hold_ms, s->neutral_us, s->invert ? " (inverted)" : "");
    return ESP_OK;
}

esp_err_t settings_save(void)
{
    const settings_t *s = &g_settings;
    nvs_handle_t h;
    esp_err_t err = nvs_open(NS, NVS_READWRITE, &h);
    if (err != ESP_OK) {
        return err;
    }
    nvs_set_str(h, "ssid", s->ssid);
    nvs_set_str(h, "pass", s->pass);
    nvs_set_str(h, "uri", s->mqtt_uri);
    nvs_set_str(h, "muser", s->mqtt_user);
    nvs_set_str(h, "mpass", s->mqtt_pass);
    nvs_set_str(h, "name", s->name);
    nvs_set_i32(h, "press", s->press_deg);
    nvs_set_i32(h, "hold", s->hold_ms);
    nvs_set_i32(h, "neutral", s->neutral_us);
    nvs_set_i32(h, "invert", s->invert);
    nvs_set_i32(h, "power", s->power);
    err = nvs_commit(h);
    nvs_close(h);
    return err;
}

esp_err_t settings_clear_network(void)
{
    g_settings.ssid[0] = g_settings.pass[0] = 0;
    g_settings.mqtt_uri[0] = g_settings.mqtt_user[0] = g_settings.mqtt_pass[0] = 0;
    return settings_save();
}
