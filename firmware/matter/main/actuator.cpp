#include "actuator.h"

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

static void servo_write_us(int us)
{
    uint32_t duty = (uint32_t)(((uint64_t)us << 14) / SERVO_PERIOD_US);
    ledc_set_duty(SERVO_MODE, SERVO_CHANNEL, duty);
    ledc_update_duty(SERVO_MODE, SERVO_CHANNEL);
}

static void servo_release(void)
{
    /* Idle low: most hobby servos stop driving when pulses disappear. */
    ledc_stop(SERVO_MODE, SERVO_CHANNEL, 0);
}

static int press_us(bool on)
{
    int offset = CONFIG_SWROBOT_SERVO_PRESS_DEG * CONFIG_SWROBOT_SERVO_US_PER_DEG / 10;
    bool positive = on;
#if CONFIG_SWROBOT_SERVO_INVERT
    positive = !positive;
#endif
    return CONFIG_SWROBOT_SERVO_NEUTRAL_US + (positive ? offset : -offset);
}

static void hw_init(void)
{
    ledc_timer_config_t timer = {};
    timer.speed_mode = SERVO_MODE;
    timer.duty_resolution = SERVO_RES;
    timer.timer_num = SERVO_TIMER;
    timer.freq_hz = 1000000 / SERVO_PERIOD_US;
    timer.clk_cfg = LEDC_AUTO_CLK;
    ESP_ERROR_CHECK(ledc_timer_config(&timer));

    ledc_channel_config_t ch = {};
    ch.gpio_num = CONFIG_SWROBOT_SERVO_GPIO;
    ch.speed_mode = SERVO_MODE;
    ch.channel = SERVO_CHANNEL;
    ch.timer_sel = SERVO_TIMER;
    ch.duty = 0;
    ch.hpoint = 0;
    ESP_ERROR_CHECK(ledc_channel_config(&ch));

    /* Park at neutral on boot. Never press on boot: the rocker keeps its own
     * position across power loss, and an unexpected press would flip the light. */
    servo_write_us(CONFIG_SWROBOT_SERVO_NEUTRAL_US);
    vTaskDelay(pdMS_TO_TICKS(500));
#if CONFIG_SWROBOT_SERVO_RELEASE_PWM
    servo_release();
#endif
}

static void do_press(bool on)
{
    int target = press_us(on);
    ESP_LOGI(TAG, "press %s: %d us for %d ms", on ? "ON" : "OFF", target, CONFIG_SWROBOT_PRESS_HOLD_MS);
    servo_write_us(target);
    vTaskDelay(pdMS_TO_TICKS(CONFIG_SWROBOT_PRESS_HOLD_MS));
    servo_write_us(CONFIG_SWROBOT_SERVO_NEUTRAL_US);
    vTaskDelay(pdMS_TO_TICKS(300));
#if CONFIG_SWROBOT_SERVO_RELEASE_PWM
    servo_release();
#endif
}

#else /* CONFIG_SWROBOT_MODE_PHOTOMOS */

static void hw_init(void)
{
    gpio_config_t io = {};
    io.pin_bit_mask = (1ULL << CONFIG_SWROBOT_KEY_ON_GPIO) | (1ULL << CONFIG_SWROBOT_KEY_OFF_GPIO);
    io.mode = GPIO_MODE_OUTPUT;
    io.pull_down_en = GPIO_PULLDOWN_ENABLE; /* R3/R4 also pull down on the board */
    ESP_ERROR_CHECK(gpio_config(&io));
    gpio_set_level((gpio_num_t)CONFIG_SWROBOT_KEY_ON_GPIO, 0);
    gpio_set_level((gpio_num_t)CONFIG_SWROBOT_KEY_OFF_GPIO, 0);
}

static void do_press(bool on)
{
    gpio_num_t pin = (gpio_num_t)(on ? CONFIG_SWROBOT_KEY_ON_GPIO : CONFIG_SWROBOT_KEY_OFF_GPIO);
    ESP_LOGI(TAG, "pulse %s button for %d ms", on ? "ON" : "OFF", CONFIG_SWROBOT_PRESS_HOLD_MS);
    gpio_set_level(pin, 1);
    vTaskDelay(pdMS_TO_TICKS(CONFIG_SWROBOT_PRESS_HOLD_MS));
    gpio_set_level(pin, 0);
    vTaskDelay(pdMS_TO_TICKS(200)); /* gap so the remote sees separate presses */
}

#endif

static void actuator_task(void *)
{
    bool on;
    while (true) {
        if (xQueueReceive(s_queue, &on, portMAX_DELAY) == pdTRUE) {
            /* Collapse a burst of commands into the last one. */
            bool latest;
            while (xQueueReceive(s_queue, &latest, 0) == pdTRUE) {
                on = latest;
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
    if (xTaskCreate(actuator_task, "actuator", 3072, nullptr, 5, nullptr) != pdPASS) {
        return ESP_FAIL;
    }
    return ESP_OK;
}

void actuator_request(bool on)
{
    if (s_queue && xQueueSend(s_queue, &on, 0) != pdTRUE) {
        ESP_LOGW(TAG, "queue full, command dropped");
    }
}
