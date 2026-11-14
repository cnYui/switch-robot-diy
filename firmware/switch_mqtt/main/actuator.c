#include "actuator.h"
#include "settings.h"

#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>
#include <freertos/task.h>
#include <driver/gpio.h>
#include <driver/ledc.h>
#include <esp_log.h>
#include <sdkconfig.h>

static const char *TAG = "actuator";
static QueueHandle_t s_queue;

#if CONFIG_SWROBOT_MODE_SERVO

#define SERVO_TIMER LEDC_TIMER_0
#define SERVO_CHANNEL LEDC_CHANNEL_0
#define SERVO_MODE LEDC_LOW_SPEED_MODE
#define SERVO_RES LEDC_TIMER_14_BIT
#define SERVO_PERIOD_US 20000 /* 50 Hz */

const char *actuator_mode(void) { return "servo"; }

static void servo_write_us(int us)
{
    uint32_t duty = (uint32_t)(((uint64_t)us << 14) / SERVO_PERIOD_US);
    ledc_set_duty(SERVO_MODE, SERVO_CHANNEL, duty);
    ledc_update_duty(SERVO_MODE, SERVO_CHANNEL);
}

static void servo_release(void)
{
#if CONFIG_SWROBOT_SERVO_RELEASE_PWM
    ledc_stop(SERVO_MODE, SERVO_CHANNEL, 0); /* most hobby servos stop driving without pulses */
#endif
}

static int press_us(bool on)
{
    int offset = g_settings.press_deg * CONFIG_SWROBOT_SERVO_US_PER_DEG_X10 / 10;
    bool positive = g_settings.invert ? !on : on;
    int us = g_settings.neutral_us + (positive ? offset : -offset);
    return us < 500 ? 500 : us > 2500 ? 2500 : us;
}

static void hw_init(void)
{
    ledc_timer_config_t timer = {
        .speed_mode = SERVO_MODE,
        .duty_resolution = SERVO_RES,
        .timer_num = SERVO_TIMER,
        .freq_hz = 1000000 / SERVO_PERIOD_US,
        .clk_cfg = LEDC_AUTO_CLK,
    };
    ESP_ERROR_CHECK(ledc_timer_config(&timer));
    ledc_channel_config_t ch = {
        .gpio_num = CONFIG_SWROBOT_SERVO_GPIO,
        .speed_mode = SERVO_MODE,
        .channel = SERVO_CHANNEL,
        .timer_sel = SERVO_TIMER,
        .duty = 0,
        .hpoint = 0,
    };
    ESP_ERROR_CHECK(ledc_channel_config(&ch));
    /* Park at neutral on boot and never press: the rocker keeps its own position across
     * power loss, and a press on power-up would flip the light by surprise. */
    servo_write_us(g_settings.neutral_us);
    vTaskDelay(pdMS_TO_TICKS(500));
    servo_release();
}

static void do_press(bool on)
{
    int target = press_us(on);
    ESP_LOGI(TAG, "press %s: %d us for %d ms", on ? "ON" : "OFF", target, g_settings.hold_ms);
    servo_write_us(target);
    vTaskDelay(pdMS_TO_TICKS(g_settings.hold_ms));
    servo_write_us(g_settings.neutral_us);
    vTaskDelay(pdMS_TO_TICKS(300));
    servo_release();
}

#else /* CONFIG_SWROBOT_MODE_PHOTOMOS */

const char *actuator_mode(void) { return "photomos"; }

static void hw_init(void)
{
    gpio_config_t io = {
        .pin_bit_mask = (1ULL << CONFIG_SWROBOT_KEY_ON_GPIO) | (1ULL << CONFIG_SWROBOT_KEY_OFF_GPIO),
        .mode = GPIO_MODE_OUTPUT,
        .pull_down_en = GPIO_PULLDOWN_ENABLE, /* R3/R4 also pull down on the board */
    };
    ESP_ERROR_CHECK(gpio_config(&io));
    gpio_set_level(CONFIG_SWROBOT_KEY_ON_GPIO, 0);
    gpio_set_level(CONFIG_SWROBOT_KEY_OFF_GPIO, 0);
}

static void do_press(bool on)
{
    int pin = on ? CONFIG_SWROBOT_KEY_ON_GPIO : CONFIG_SWROBOT_KEY_OFF_GPIO;
    ESP_LOGI(TAG, "pulse %s button for %d ms", on ? "ON" : "OFF", g_settings.hold_ms);
    gpio_set_level(pin, 1);
    vTaskDelay(pdMS_TO_TICKS(g_settings.hold_ms));
    gpio_set_level(pin, 0);
    vTaskDelay(pdMS_TO_TICKS(200)); /* gap so the remote sees separate presses */
}

#endif

static void actuator_task(void *arg)
{
    bool on, latest;
    for (;;) {
        if (xQueueReceive(s_queue, &on, portMAX_DELAY) == pdTRUE) {
            while (xQueueReceive(s_queue, &latest, 0) == pdTRUE) {
                on = latest; /* a burst of commands collapses into the last one */
            }
            do_press(on);
        }
    }
}

esp_err_t actuator_init(void)
{
    s_queue = xQueueCreate(4, sizeof(bool));
    if (!s_queue) {
        return ESP_ERR_NO_MEM;
    }
    hw_init();
    return xTaskCreate(actuator_task, "actuator", 3072, NULL, 5, NULL) == pdPASS ? ESP_OK : ESP_FAIL;
}

void actuator_request(bool on)
{
    if (s_queue && xQueueSend(s_queue, &on, 0) != pdTRUE) {
        ESP_LOGW(TAG, "queue full, command dropped");
    }
}
