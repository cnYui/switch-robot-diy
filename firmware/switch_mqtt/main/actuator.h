#pragma once

#include <stdbool.h>
#include <esp_err.h>

/* Servo press (J3) or PhotoMOS button pulse (J4/J5). actuator_request() only queues
 * the job; the motion runs on its own task with the current g_settings calibration. */
esp_err_t actuator_init(void);
void actuator_request(bool on);
const char *actuator_mode(void);
