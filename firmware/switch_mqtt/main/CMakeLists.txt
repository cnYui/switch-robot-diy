idf_component_register(SRCS "app_main.c" "actuator.c" "settings.c" "net.c" "console.c"
                       INCLUDE_DIRS "."
                       PRIV_REQUIRES nvs_flash esp_wifi esp_netif esp_event mqtt json esp_https_ota
                                     esp_http_client app_update esp_timer esp_driver_ledc esp_driver_gpio
                                     esp_driver_usb_serial_jtag console esp_app_format)
