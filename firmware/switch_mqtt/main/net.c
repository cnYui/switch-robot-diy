#include "net.h"
#include "actuator.h"
#include "settings.h"

#include <string.h>
#include <strings.h>
#include <stdio.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <esp_app_desc.h>
#include <esp_event.h>
#include <esp_http_client.h>
#include <esp_https_ota.h>
#include <esp_log.h>
#include <esp_mac.h>
#include <esp_netif.h>
#include <esp_ota_ops.h>
#include <esp_system.h>
#include <esp_timer.h>
#include <esp_wifi.h>
#include <lwip/sockets.h>
#include <mqtt_client.h>
#include <cJSON.h>
#include <sdkconfig.h>

static const char *TAG = "net";

static esp_mqtt_client_handle_t s_mqtt;
static volatile bool s_wifi_up, s_mqtt_up, s_ota_busy;
static char s_ip[16] = "";
static char s_ota_url[160];
static int64_t s_last_mqtt_ok_us;   /* last time the broker was reachable (or Wi-Fi came up) */

bool net_wifi_up(void) { return s_wifi_up; }
bool net_mqtt_up(void) { return s_mqtt_up; }
const char *net_ip(void) { return s_ip; }

static void topic(char *out, size_t cap, const char *sub)
{
    snprintf(out, cap, "home/%s/%s", g_dev_id, sub);
}

static void pub(const char *sub, const char *payload, bool retain)
{
    if (!s_mqtt || !s_mqtt_up) {
        return;
    }
    char t[64];
    topic(t, sizeof t, sub);
    esp_mqtt_client_publish(s_mqtt, t, payload, 0, 1, retain);
}

static void pub_json(const char *sub, cJSON *j, bool retain)
{
    char *s = cJSON_PrintUnformatted(j);
    if (s) {
        pub(sub, s, retain);
        cJSON_free(s);
    }
    cJSON_Delete(j);
}

/* ------------------------------------------------------------------ messages out */
static cJSON *config_json(void)
{
    cJSON *c = cJSON_CreateObject();
    cJSON_AddNumberToObject(c, "press_deg", g_settings.press_deg);
    cJSON_AddNumberToObject(c, "hold_ms", g_settings.hold_ms);
    cJSON_AddNumberToObject(c, "neutral_us", g_settings.neutral_us);
    cJSON_AddBoolToObject(c, "invert", g_settings.invert);
    return c;
}

static void publish_info(void)
{
    uint8_t mac[6];
    char macs[18];
    esp_read_mac(mac, ESP_MAC_WIFI_STA);
    snprintf(macs, sizeof macs, "%02X:%02X:%02X:%02X:%02X:%02X", mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
    cJSON *j = cJSON_CreateObject();
    cJSON_AddStringToObject(j, "kind", "switch");
    cJSON_AddStringToObject(j, "name", g_settings.name);
    cJSON_AddStringToObject(j, "fw", esp_app_get_description()->version);
    cJSON_AddStringToObject(j, "board", "switch-robot-carrier-v0.5");
    cJSON_AddStringToObject(j, "chip", CONFIG_IDF_TARGET);
    cJSON_AddStringToObject(j, "mode", actuator_mode());
    cJSON_AddStringToObject(j, "ip", s_ip);
    cJSON_AddStringToObject(j, "mac", macs);
    cJSON_AddItemToObject(j, "config", config_json());
    pub_json("info", j, true);
}

static void publish_state_only(void)
{
    cJSON *j = cJSON_CreateObject();
    cJSON_AddStringToObject(j, "power", g_settings.power ? "ON" : "OFF");
    pub_json("state", j, true);
}

void net_publish_state(const char *source)
{
    publish_state_only();
    cJSON *e = cJSON_CreateObject();
    cJSON_AddStringToObject(e, "type", "press");
    cJSON_AddStringToObject(e, "power", g_settings.power ? "ON" : "OFF");
    cJSON_AddStringToObject(e, "source", source);
    pub_json("event", e, false);
}

static void publish_event(const char *type, const char *key, const char *val)
{
    cJSON *e = cJSON_CreateObject();
    cJSON_AddStringToObject(e, "type", type);
    if (key) {
        cJSON_AddStringToObject(e, key, val);
    }
    pub_json("event", e, false);
}

static void publish_telemetry(void)
{
    wifi_ap_record_t ap;
    cJSON *j = cJSON_CreateObject();
    cJSON_AddNumberToObject(j, "uptime_s", (double)(esp_timer_get_time() / 1000000));
    if (esp_wifi_sta_get_ap_info(&ap) == ESP_OK) {
        cJSON_AddNumberToObject(j, "rssi", ap.rssi);
    }
    cJSON_AddNumberToObject(j, "heap", esp_get_free_heap_size());
    cJSON_AddNumberToObject(j, "presses", g_presses);
    pub_json("telemetry", j, false);
}

/* Home Assistant finds the switch by itself if you ever run it next to HomeHub. */
static void publish_ha_discovery(void)
{
    char t[80], cmd[64], st[64], av[64];
    snprintf(t, sizeof t, "homeassistant/switch/%s/config", g_dev_id);
    topic(cmd, sizeof cmd, "set");
    topic(st, sizeof st, "state");
    topic(av, sizeof av, "status");
    cJSON *j = cJSON_CreateObject();
    cJSON_AddNullToObject(j, "name");
    cJSON_AddStringToObject(j, "uniq_id", g_dev_id);
    cJSON_AddStringToObject(j, "cmd_t", cmd);
    cJSON_AddStringToObject(j, "stat_t", st);
    cJSON_AddStringToObject(j, "val_tpl", "{{ value_json.power }}");
    cJSON_AddStringToObject(j, "avty_t", av);
    cJSON *d = cJSON_AddObjectToObject(j, "dev");
    cJSON *ids = cJSON_AddArrayToObject(d, "ids");
    cJSON_AddItemToArray(ids, cJSON_CreateString(g_dev_id));
    cJSON_AddStringToObject(d, "name", g_settings.name[0] ? g_settings.name : g_dev_id);
    cJSON_AddStringToObject(d, "mf", "DIY");
    cJSON_AddStringToObject(d, "mdl", "Switch Robot V0.5");
    cJSON_AddStringToObject(d, "sw", esp_app_get_description()->version);
    char *s = cJSON_PrintUnformatted(j);
    if (s) {
        esp_mqtt_client_publish(s_mqtt, t, s, 0, 1, true);
        cJSON_free(s);
    }
    cJSON_Delete(j);
}

/* ------------------------------------------------------------------ messages in */
static void handle_set(const char *data)
{
    char word[12] = "";
    cJSON *j = cJSON_Parse(data);
    if (j) {
        cJSON *p = cJSON_GetObjectItem(j, "power");
        if (cJSON_IsString(p)) {
            strlcpy(word, p->valuestring, sizeof word);
        }
        cJSON_Delete(j);
    } else {
        sscanf(data, "%11s", word);
    }
    if (!strcasecmp(word, "ON")) {
        switch_set(true, "mqtt");
    } else if (!strcasecmp(word, "OFF")) {
        switch_set(false, "mqtt");
    } else if (!strcasecmp(word, "TOGGLE")) {
        switch_set(!g_settings.power, "mqtt");
    } else {
        ESP_LOGW(TAG, "unknown command '%s'", data);
        publish_event("error", "message", "unknown command; use ON, OFF or TOGGLE");
    }
}

static bool take_int(cJSON *j, const char *key, int lo, int hi, int *out)
{
    cJSON *v = cJSON_GetObjectItem(j, key);
    if (!cJSON_IsNumber(v)) {
        return true;                     /* absent: keep the current value */
    }
    if (v->valuedouble < lo || v->valuedouble > hi) {
        return false;
    }
    *out = (int)v->valuedouble;
    return true;
}

static void handle_config(const char *data)
{
    cJSON *j = cJSON_Parse(data);
    if (!j) {
        publish_event("error", "message", "config must be JSON");
        return;
    }
    settings_t s = g_settings;
    bool ok = take_int(j, "press_deg", 1, 60, &s.press_deg) && take_int(j, "hold_ms", 50, 3000, &s.hold_ms) &&
              take_int(j, "neutral_us", 500, 2500, &s.neutral_us);
    cJSON *inv = cJSON_GetObjectItem(j, "invert");
    if (cJSON_IsBool(inv)) {
        s.invert = cJSON_IsTrue(inv);
    }
    cJSON *name = cJSON_GetObjectItem(j, "name");
    if (cJSON_IsString(name)) {
        strlcpy(s.name, name->valuestring, sizeof s.name);
    }
    cJSON_Delete(j);
    if (!ok) {
        publish_event("error", "message", "out of range: press_deg 1-60, hold_ms 50-3000, neutral_us 500-2500");
        return;
    }
    g_settings = s;
    settings_save();
    ESP_LOGI(TAG, "config: press %d deg, hold %d ms, neutral %d us, invert %d", s.press_deg, s.hold_ms,
             s.neutral_us, s.invert);
    publish_info();
    publish_event("config", "result", "saved");
}

static void ota_task(void *arg)
{
    publish_event("ota", "stage", "start");
    esp_http_client_config_t http = {.url = s_ota_url, .timeout_ms = 20000, .keep_alive_enable = true};
    esp_https_ota_config_t ota = {.http_config = &http};
    ESP_LOGI(TAG, "OTA from %s", s_ota_url);
    esp_err_t err = esp_https_ota(&ota);
    if (err == ESP_OK) {
        publish_event("ota", "stage", "done, rebooting");
        vTaskDelay(pdMS_TO_TICKS(800));
        esp_restart();
    }
    ESP_LOGE(TAG, "OTA failed: %s", esp_err_to_name(err));
    publish_event("ota", "error", esp_err_to_name(err));
    s_ota_busy = false;
    vTaskDelete(NULL);
}

static void handle_ota(const char *data)
{
    if (s_ota_busy) {
        return;
    }
    if (strncmp(data, "http://", 7) && strncmp(data, "https://", 8)) {
        publish_event("error", "message", "ota needs an http:// URL");
        return;
    }
    strlcpy(s_ota_url, data, sizeof s_ota_url);
    s_ota_busy = true;
    if (xTaskCreate(ota_task, "ota", 8192, NULL, 4, NULL) != pdPASS) {
        s_ota_busy = false;
    }
}

static void mqtt_handler(void *arg, esp_event_base_t base, int32_t id, void *event_data)
{
    esp_mqtt_event_handle_t ev = event_data;
    char t[64];
    switch ((esp_mqtt_event_id_t)id) {
    case MQTT_EVENT_CONNECTED:
        s_mqtt_up = true;
        s_last_mqtt_ok_us = esp_timer_get_time();
        ESP_LOGI(TAG, "MQTT connected as %s", g_dev_id);
        pub("status", "online", true);
        publish_info();
        publish_state_only();
        publish_ha_discovery();
        for (const char **s = (const char *[]){"set", "config/set", "ota", NULL}; *s; s++) {
            topic(t, sizeof t, *s);
            esp_mqtt_client_subscribe(s_mqtt, t, 1);
        }
        /* A freshly updated image proved it can reach the hub: keep it. */
        esp_ota_mark_app_valid_cancel_rollback();
        break;
    case MQTT_EVENT_DISCONNECTED:
        if (s_mqtt_up) {
            ESP_LOGW(TAG, "MQTT disconnected");
        }
        s_mqtt_up = false;
        break;
    case MQTT_EVENT_DATA: {
        if (ev->current_data_offset != 0 || ev->data_len != ev->total_data_len || ev->data_len > 1024) {
            break;                       /* our commands are small; ignore fragments */
        }
        char tp[64], data[1025];
        snprintf(tp, sizeof tp, "%.*s", ev->topic_len, ev->topic);
        snprintf(data, sizeof data, "%.*s", ev->data_len, ev->data);
        const char *sub = tp + strlen("home/") + strlen(g_dev_id) + 1;
        if (strncmp(tp, "home/", 5) || strncmp(tp + 5, g_dev_id, strlen(g_dev_id))) {
            break;
        }
        if (!strcmp(sub, "set")) {
            handle_set(data);
        } else if (!strcmp(sub, "config/set")) {
            handle_config(data);
        } else if (!strcmp(sub, "ota")) {
            handle_ota(data);
        }
        break;
    }
    default:
        break;
    }
}

static void mqtt_start(void)
{
    char will[48];
    topic(will, sizeof will, "status");
    esp_mqtt_client_config_t cfg = {
        .broker.address.uri = g_settings.mqtt_uri,
        .credentials.username = g_settings.mqtt_user[0] ? g_settings.mqtt_user : NULL,
        .credentials.authentication.password = g_settings.mqtt_pass[0] ? g_settings.mqtt_pass : NULL,
        .credentials.client_id = g_dev_id,
        .session.last_will = {.topic = will, .msg = "offline", .qos = 1, .retain = 1},
        .session.keepalive = 30,
        .network.reconnect_timeout_ms = 5000,
        .network.timeout_ms = 5000,
    };
    if (s_mqtt) {
        esp_mqtt_client_stop(s_mqtt);
        esp_mqtt_client_destroy(s_mqtt);
        s_mqtt = NULL;
        s_mqtt_up = false;
    }
    s_mqtt = esp_mqtt_client_init(&cfg);
    if (!s_mqtt) {
        ESP_LOGE(TAG, "bad MQTT settings '%s'", g_settings.mqtt_uri);
        return;
    }
    esp_mqtt_client_register_event(s_mqtt, ESP_EVENT_ANY_ID, mqtt_handler, NULL);
    esp_mqtt_client_start(s_mqtt);
    ESP_LOGI(TAG, "MQTT -> %s", g_settings.mqtt_uri);
}

/* Broadcast "HOMEHUB?" and take the broker address from the hub's answer. */
static bool discover(char *uri, size_t cap)
{
    int s = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (s < 0) {
        return false;
    }
    int yes = 1;
    struct timeval tv = {.tv_sec = 2};
    setsockopt(s, SOL_SOCKET, SO_BROADCAST, &yes, sizeof yes);
    setsockopt(s, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof tv);
    struct sockaddr_in to = {.sin_family = AF_INET, .sin_port = htons(CONFIG_HOME_DISCOVERY_PORT),
                             .sin_addr.s_addr = htonl(INADDR_BROADCAST)};
    sendto(s, "HOMEHUB?", 8, 0, (struct sockaddr *)&to, sizeof to);
    char buf[200];
    int n = recvfrom(s, buf, sizeof buf - 1, 0, NULL, NULL);
    close(s);
    if (n <= 0) {
        return false;
    }
    buf[n] = 0;
    cJSON *j = cJSON_Parse(buf);
    cJSON *m = j ? cJSON_GetObjectItem(j, "mqtt") : NULL;
    bool ok = cJSON_IsString(m) && !strncmp(m->valuestring, "mqtt://", 7);
    if (ok) {
        strlcpy(uri, m->valuestring, cap);
    }
    cJSON_Delete(j);
    return ok;
}

/* Owns the MQTT client's lifecycle, finds the hub again when it moved, sends telemetry. */
static void supervisor_task(void *arg)
{
    int64_t last_tele = 0, last_disc = 0;
    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(1000));
        int64_t now = esp_timer_get_time();
        if (!s_wifi_up) {
            continue;
        }
        if (!s_mqtt && g_settings.mqtt_uri[0]) {
            mqtt_start();
        }
        bool lost = !g_settings.mqtt_uri[0] || (!s_mqtt_up && now - s_last_mqtt_ok_us > 30 * 1000000LL);
        if (lost && now - last_disc > 30 * 1000000LL) {
            last_disc = now;
            char uri[128];
            if (discover(uri, sizeof uri)) {
                if (strcmp(uri, g_settings.mqtt_uri)) {
                    ESP_LOGI(TAG, "hub found at %s", uri);
                    strlcpy(g_settings.mqtt_uri, uri, sizeof g_settings.mqtt_uri);
                    settings_save();
                    mqtt_start();
                }
            } else {
                ESP_LOGW(TAG, "no answer from the hub on UDP %d", CONFIG_HOME_DISCOVERY_PORT);
            }
        }
        if (s_mqtt_up && now - last_tele > 60 * 1000000LL) {
            last_tele = now;
            publish_telemetry();
        }
        /* New firmware that never reached the hub within 5 minutes goes back to the old one. */
        esp_ota_img_states_t st;
        if (now > 300 * 1000000LL && !s_mqtt_up &&
            esp_ota_get_state_partition(esp_ota_get_running_partition(), &st) == ESP_OK &&
            st == ESP_OTA_IMG_PENDING_VERIFY) {
            ESP_LOGE(TAG, "new firmware never reached the hub, rolling back");
            esp_ota_mark_app_invalid_rollback_and_reboot();
        }
    }
}

static void wifi_handler(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        if (s_wifi_up) {
            ESP_LOGW(TAG, "Wi-Fi lost, reconnecting");
        }
        s_wifi_up = false;
        s_ip[0] = 0;
        esp_wifi_connect();      /* keeps retrying; each attempt takes a few seconds */
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *e = data;
        snprintf(s_ip, sizeof s_ip, IPSTR, IP2STR(&e->ip_info.ip));
        ESP_LOGI(TAG, "Wi-Fi up, IP %s", s_ip);
        s_last_mqtt_ok_us = esp_timer_get_time();
        s_wifi_up = true;
    }
}

void net_start(void)
{
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_t *netif = esp_netif_create_default_wifi_sta();
    esp_netif_set_hostname(netif, g_dev_id);
    wifi_init_config_t init = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&init));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT, ESP_EVENT_ANY_ID, wifi_handler, NULL, NULL));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT, IP_EVENT_STA_GOT_IP, wifi_handler, NULL, NULL));
    if (!g_settings.ssid[0]) {
        ESP_LOGW(TAG, "no Wi-Fi set: plug into the computer and run `python -m homehub provision`");
        return;
    }
    wifi_config_t wc = {0};
    strlcpy((char *)wc.sta.ssid, g_settings.ssid, sizeof wc.sta.ssid);
    strlcpy((char *)wc.sta.password, g_settings.pass, sizeof wc.sta.password);
    wc.sta.threshold.authmode = g_settings.pass[0] ? WIFI_AUTH_WPA_PSK : WIFI_AUTH_OPEN;
    wc.sta.sae_pwe_h2e = WPA3_SAE_PWE_BOTH;
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wc));
    ESP_ERROR_CHECK(esp_wifi_start());
    esp_wifi_set_ps(WIFI_PS_MIN_MODEM);
    xTaskCreate(supervisor_task, "supervisor", 4096, NULL, 3, NULL);
}
