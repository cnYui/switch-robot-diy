"""HomeHub: the home's local hub, running on your own computer.

Devices (the switch robot, the ESP32-C6 gateway) talk MQTT to a Mosquitto broker on
this computer. HomeHub listens to every message under home/#, keeps all of it in a
SQLite file on this computer, serves a control page and an HTTP API on the LAN, and
answers devices that broadcast "where is the hub?" so a changed IP never strands them.
Nothing goes to any cloud.
"""

__version__ = "0.1.0"
