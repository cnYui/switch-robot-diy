#pragma once

#include <stdbool.h>

/* Wi-Fi + MQTT link to the home hub on the computer, discovery of the hub on the LAN,
 * and over-the-air updates the hub pushes. */
void net_start(void);
bool net_wifi_up(void);
bool net_mqtt_up(void);
const char *net_ip(void);
void net_publish_state(const char *source);   /* after every press */

/* Implemented in app_main.c: apply a command from any source (MQTT, button, console). */
void switch_set(bool on, const char *source);
extern volatile unsigned g_presses;
