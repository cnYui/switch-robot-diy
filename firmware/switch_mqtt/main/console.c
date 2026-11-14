/* Text console on the USB-C port, used by `python -m homehub provision`.
 * Every command answers one line starting with OK or ERR. */
#include "console.h"
#include "net.h"
#include "actuator.h"
#include "settings.h"

#include <string.h>
#include <strings.h>
#include <stdio.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <driver/usb_serial_jtag.h>
#include <driver/usb_serial_jtag_vfs.h>
#include <esp_app_desc.h>
#include <esp_console.h>
#include <esp_log.h>
#include <esp_system.h>

static const char *TAG = "console";

static int cmd_wifi(int argc, char **argv)
{
    if (argc < 2 || argc > 3 || strlen(argv[1]) > 32 || (argc == 3 && strlen(argv[2]) > 64)) {
        printf("ERR usage: wifi \"<ssid>\" \"<password>\"\n");
        return 1;
    }
    strlcpy(g_settings.ssid, argv[1], sizeof g_settings.ssid);
    strlcpy(g_settings.pass, argc == 3 ? argv[2] : "", sizeof g_settings.pass);
    settings_save();
    printf("OK wifi saved (%s), reboot to use it\n", g_settings.ssid);
    return 0;
}

static int cmd_mqtt(int argc, char **argv)
{
    if (argc < 2 || argc > 4 || strncmp(argv[1], "mqtt://", 7) || strlen(argv[1]) > 127) {
        printf("ERR usage: mqtt \"mqtt://host:1883\" \"<user>\" \"<password>\"\n");
        return 1;
    }
    strlcpy(g_settings.mqtt_uri, argv[1], sizeof g_settings.mqtt_uri);
    strlcpy(g_settings.mqtt_user, argc > 2 ? argv[2] : "", sizeof g_settings.mqtt_user);
    strlcpy(g_settings.mqtt_pass, argc > 3 ? argv[3] : "", sizeof g_settings.mqtt_pass);
    settings_save();
    printf("OK mqtt saved (%s)\n", g_settings.mqtt_uri);
    return 0;
}

static int cmd_name(int argc, char **argv)
{
    if (argc != 2) {
        printf("ERR usage: name \"<name>\"\n");
        return 1;
    }
    strlcpy(g_settings.name, argv[1], sizeof g_settings.name);
    settings_save();
    printf("OK name saved\n");
    return 0;
}

static int cmd_status(int argc, char **argv)
{
    printf("OK id=%s fw=%s mode=%s wifi=\"%s\" wifi_up=%s ip=%s mqtt=%s mqtt_up=%s power=%s press_deg=%d "
           "hold_ms=%d neutral_us=%d invert=%d\n",
           g_dev_id, esp_app_get_description()->version, actuator_mode(), g_settings.ssid,
           net_wifi_up() ? "yes" : "no", net_ip()[0] ? net_ip() : "-",
           g_settings.mqtt_uri[0] ? g_settings.mqtt_uri : "-", net_mqtt_up() ? "yes" : "no",
           g_settings.power ? "ON" : "OFF", g_settings.press_deg, g_settings.hold_ms, g_settings.neutral_us,
           g_settings.invert);
    return 0;
}

static int cmd_press(int argc, char **argv)
{
    if (argc != 2 || (strcasecmp(argv[1], "on") && strcasecmp(argv[1], "off"))) {
        printf("ERR usage: press on|off\n");
        return 1;
    }
    switch_set(!strcasecmp(argv[1], "on"), "console");
    printf("OK pressing %s\n", argv[1]);
    return 0;
}

static int cmd_reboot(int argc, char **argv)
{
    printf("OK rebooting\n");
    fflush(stdout);
    vTaskDelay(pdMS_TO_TICKS(300));
    esp_restart();
    return 0;
}

static int cmd_forget(int argc, char **argv)
{
    settings_clear_network();
    printf("OK Wi-Fi and MQTT forgotten, rebooting\n");
    fflush(stdout);
    vTaskDelay(pdMS_TO_TICKS(300));
    esp_restart();
    return 0;
}

static void console_task(void *arg)
{
    char line[256];
    size_t len = 0;
    for (;;) {
        uint8_t c;
        if (usb_serial_jtag_read_bytes(&c, 1, portMAX_DELAY) != 1) {
            continue;
        }
        if (c == '\r' || c == '\n') {
            if (!len) {
                continue;
            }
            line[len] = 0;
            len = 0;
            int ret;
            esp_err_t err = esp_console_run(line, &ret);
            if (err == ESP_ERR_NOT_FOUND) {
                printf("ERR unknown command; try: wifi, mqtt, name, status, press, reboot, forget\n");
            } else if (err == ESP_ERR_INVALID_ARG) {
                /* empty line */
            } else if (err != ESP_OK) {
                printf("ERR %s\n", esp_err_to_name(err));
            }
            fflush(stdout);
        } else if (len < sizeof line - 1) {
            line[len++] = (char)c;
        }
    }
}

void console_start(void)
{
    usb_serial_jtag_driver_config_t cfg = USB_SERIAL_JTAG_DRIVER_CONFIG_DEFAULT();
    if (usb_serial_jtag_driver_install(&cfg) != ESP_OK) {
        ESP_LOGE(TAG, "USB serial driver install failed");
        return;
    }
    usb_serial_jtag_vfs_use_driver();
    esp_console_config_t cc = ESP_CONSOLE_CONFIG_DEFAULT();
    cc.max_cmdline_length = 256;
    cc.max_cmdline_args = 6;
    ESP_ERROR_CHECK(esp_console_init(&cc));
    const esp_console_cmd_t cmds[] = {
        {.command = "wifi", .help = "wifi \"<ssid>\" \"<password>\"", .func = cmd_wifi},
        {.command = "mqtt", .help = "mqtt \"mqtt://host:1883\" \"<user>\" \"<password>\"", .func = cmd_mqtt},
        {.command = "name", .help = "name \"<friendly name>\"", .func = cmd_name},
        {.command = "status", .help = "show settings and connection state", .func = cmd_status},
        {.command = "press", .help = "press on|off (test the arm)", .func = cmd_press},
        {.command = "reboot", .help = "restart", .func = cmd_reboot},
        {.command = "forget", .help = "forget Wi-Fi and MQTT, keep calibration", .func = cmd_forget},
    };
    for (size_t i = 0; i < sizeof cmds / sizeof cmds[0]; i++) {
        ESP_ERROR_CHECK(esp_console_cmd_register(&cmds[i]));
    }
    xTaskCreate(console_task, "console", 4096, NULL, 2, NULL);
}
