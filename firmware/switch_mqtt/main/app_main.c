/* Switch robot (Switch Robot Carrier V0.5, ESP32-C3) for the home hub on your own computer.
 *
 * Joins the home Wi-Fi, connects to the MQTT broker on the computer, and presses the 86
 * switch when told: home/<id>/set ON|OFF|TOGGLE. Calibration (press angle, hold time,
 * neutral pulse, direction) comes from the hub and is kept in flash. No cloud involved. */
#include "actuator.h"
#include "console.h"
#include "net.h"
#include "settings.h"

#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <driver/gpio.h>
#include <esp_log.h>
#include <esp_system.h>
#include <nvs_flash.h>
#include <sdkconfig.h>

static const char *TAG = "app";
volatile unsigned g_presses;

void switch_set(bool on, const char *source)
{
    ESP_LOGI(TAG, "%s -> %s", source, on ? "ON" : "OFF");
    g_settings.power = on;
    settings_save();
    g_presses++;
    actuator_request(on);       /* always press, even if the state did not change: the switch is
                                   open loop, someone may have flipped it by hand */
    net_publish_state(source);
}

#if CONFIG_SWROBOT_BUTTON_GPIO >= 0
/* BOOT button (SW2): short press toggles, hold 5 s forgets Wi-Fi/MQTT and restarts. */
static void button_task(void *arg)
{
    const gpio_num_t pin = (gpio_num_t)CONFIG_SWROBOT_BUTTON_GPIO;
    gpio_config_t io = {.pin_bit_mask = 1ULL << pin, .mode = GPIO_MODE_INPUT, .pull_up_en = GPIO_PULLUP_ENABLE};
    gpio_config(&io);
    int held_ms = 0;
    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(20));
        if (gpio_get_level(pin) == 0) {
            held_ms += 20;
            if (held_ms == 5000) {
                ESP_LOGW(TAG, "button held 5 s: forgetting Wi-Fi and MQTT");
                settings_clear_network();
                esp_restart();
            }
        } else {
            if (held_ms >= 40 && held_ms < 1000) {
                switch_set(!g_settings.power, "button");
            }
            held_ms = 0;
        }
    }
}
#endif

void app_main(void)
{
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);
    ESP_ERROR_CHECK(settings_load());
    ESP_ERROR_CHECK(actuator_init());
    console_start();
    net_start();
#if CONFIG_SWROBOT_BUTTON_GPIO >= 0
    xTaskCreate(button_task, "button", 3072, NULL, 4, NULL);
#endif
    ESP_LOGI(TAG, "switch %s ready (%s mode)", g_dev_id, actuator_mode());
}
