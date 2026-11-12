/* Switch robot: exposes the 86-box switch robot as a Matter On/Off plug-in unit
 * over Wi-Fi. Matter "on" -> press the ON side, "off" -> press the OFF side. */

#include <esp_err.h>
#include <esp_log.h>
#include <nvs_flash.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <driver/gpio.h>
#include <sdkconfig.h>

#include <esp_matter.h>
#include <app/server/Server.h>
#include <platform/CHIPDeviceLayer.h>

#include "actuator.h"

static const char *TAG = "app_main";
static uint16_t s_endpoint_id;

using namespace esp_matter;
using namespace esp_matter::attribute;
using namespace esp_matter::endpoint;
using namespace chip::app::Clusters;

static void app_event_cb(const chip::DeviceLayer::ChipDeviceEvent *event, intptr_t)
{
    using namespace chip::DeviceLayer;
    switch (event->Type) {
    case DeviceEventType::kCommissioningComplete:
        ESP_LOGI(TAG, "Commissioning complete");
        break;
    case DeviceEventType::kFailSafeTimerExpired:
        ESP_LOGW(TAG, "Commissioning failed, fail-safe timer expired");
        break;
    case DeviceEventType::kInterfaceIpAddressChanged:
        ESP_LOGI(TAG, "IP address changed");
        break;
    default:
        break;
    }
}

static esp_err_t app_identification_cb(identification::callback_type_t, uint16_t endpoint_id, uint8_t effect_id,
                                       uint8_t, void *)
{
    ESP_LOGI(TAG, "Identify on endpoint %u, effect %u", endpoint_id, effect_id);
    return ESP_OK;
}

static esp_err_t app_attribute_update_cb(attribute::callback_type_t type, uint16_t endpoint_id, uint32_t cluster_id,
                                         uint32_t attribute_id, esp_matter_attr_val_t *val, void *)
{
    if (type == PRE_UPDATE && endpoint_id == s_endpoint_id && cluster_id == OnOff::Id &&
        attribute_id == OnOff::Attributes::OnOff::Id) {
        actuator_request(val->val.b);
    }
    return ESP_OK;
}

#if CONFIG_SWROBOT_BUTTON_GPIO >= 0
/* Local button: short press toggles through Matter (so the phone app stays in
 * sync), holding 5 s erases pairing and Wi-Fi and reboots into pairing mode. */
static void toggle_from_button(void)
{
    lock::chip_stack_lock(portMAX_DELAY);
    attribute_t *attr = attribute::get(s_endpoint_id, OnOff::Id, OnOff::Attributes::OnOff::Id);
    esp_matter_attr_val_t val = esp_matter_invalid(NULL);
    attribute::get_val(attr, &val);
    val.val.b = !val.val.b;
    attribute::update(s_endpoint_id, OnOff::Id, OnOff::Attributes::OnOff::Id, &val);
    lock::chip_stack_unlock();
}

static void button_task(void *)
{
    const gpio_num_t pin = (gpio_num_t)CONFIG_SWROBOT_BUTTON_GPIO;
    gpio_config_t io = {};
    io.pin_bit_mask = 1ULL << pin;
    io.mode = GPIO_MODE_INPUT;
    io.pull_up_en = GPIO_PULLUP_ENABLE;
    gpio_config(&io);

    int held_ms = 0;
    while (true) {
        vTaskDelay(pdMS_TO_TICKS(20));
        if (gpio_get_level(pin) == 0) {
            held_ms += 20;
            if (held_ms == 5000) {
                ESP_LOGW(TAG, "Factory reset");
                esp_matter::factory_reset();
            }
        } else {
            if (held_ms >= 40 && held_ms < 1000) {
                toggle_from_button();
            }
            held_ms = 0;
        }
    }
}
#endif

extern "C" void app_main()
{
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);

    ESP_ERROR_CHECK(actuator_init());

    node::config_t node_config;
    node_t *node = node::create(&node_config, app_attribute_update_cb, app_identification_cb);
    if (!node) {
        ESP_LOGE(TAG, "Failed to create Matter node");
        abort();
    }

    on_off_plug_in_unit::config_t plug_config;
    endpoint_t *endpoint = on_off_plug_in_unit::create(node, &plug_config, ENDPOINT_FLAG_NONE, NULL);
    if (!endpoint) {
        ESP_LOGE(TAG, "Failed to create plug endpoint");
        abort();
    }
    s_endpoint_id = endpoint::get_id(endpoint);
    ESP_LOGI(TAG, "Switch robot endpoint %u", s_endpoint_id);

    ESP_ERROR_CHECK(esp_matter::start(app_event_cb));

#if CONFIG_SWROBOT_BUTTON_GPIO >= 0
    xTaskCreate(button_task, "button", 3072, nullptr, 4, nullptr);
#endif
}
