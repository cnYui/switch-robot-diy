# Switch robot firmware for the home hub on your own computer (ESP-IDF, Wi-Fi + MQTT).
cmake_minimum_required(VERSION 3.16)
set(PROJECT_VER "0.1.0")
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(switch_mqtt)
