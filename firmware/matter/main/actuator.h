#pragma once

#include <esp_err.h>

/* Drives the switch: a servo press (J3) or a PhotoMOS button pulse (J4/J5).
 * actuator_request() only queues the job, so it is safe to call from the
 * Matter attribute callback; the motion runs on its own task. */
esp_err_t actuator_init(void);
void actuator_request(bool on);
