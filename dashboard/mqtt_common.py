"""Shared MQTT settings for the FAHHH? dashboard tools (see contracts/C3_mqtt.md)."""

import os
import ssl

from dotenv import load_dotenv

DEVICE_ID = "unit-01"

# C3 topic names (without prefix)
T_EVENTS = "device/events"
T_STATUS = "device/status"
T_ONLINE = "device/online"


def load_config():
    """Read dashboard/.env if present; defaults are the HiveMQ public broker (C3)."""
    load_dotenv()
    prefix = os.getenv("TOPIC_PREFIX", "sic8/fahhh/")
    if not prefix.endswith("/"):
        prefix += "/"
    return {
        "host": os.getenv("MQTT_HOST", "broker.hivemq.com"),
        "port": int(os.getenv("MQTT_PORT", "8883")),
        "user": os.getenv("MQTT_USER", ""),
        "password": os.getenv("MQTT_PASS", ""),
        "prefix": prefix,
    }


def make_client(cfg, client_id):
    """Create a paho-mqtt 2.x client with TLS on port 8883 and optional login."""
    import paho.mqtt.client as mqtt

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    if cfg["user"]:
        client.username_pw_set(cfg["user"], cfg["password"])
    if cfg["port"] == 8883:
        client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)
    client.reconnect_delay_set(min_delay=1, max_delay=10)
    return client
