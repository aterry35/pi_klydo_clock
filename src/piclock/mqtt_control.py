"""MQTT transport: callbacks queue commands; the render thread selects faces."""
from __future__ import annotations

import json
import os
import socket
import threading
from pathlib import Path

from .config import MqttConfig


def parse_face_id(payload: bytes) -> str:
    if not payload or len(payload) > 1024:
        raise ValueError("payload must contain 1 to 1024 bytes")
    text = payload.decode("utf-8").strip()
    if text.startswith("{"):
        data = json.loads(text)
        text = data.get("face_id")
    if not isinstance(text, str) or not text or len(text) > 128:
        raise ValueError("face_id must be a nonempty string of at most 128 characters")
    if text in (".", "..") or any(c in text for c in ("/", "\\", "\x00")):
        raise ValueError("face_id must be a design folder name")
    return text


class MqttControl:
    def __init__(self, config: MqttConfig):
        self.config = config
        self.client = None
        self._lock = threading.Lock()
        self._pending = None
        self._refresh = False
        self._last_state = None

    def start(self):
        if not self.config.enabled:
            return
        try:
            import paho.mqtt.client as mqtt
            client = mqtt.Client(
                mqtt.CallbackAPIVersion.VERSION2,
                client_id=self.config.client_id or f"piclock-{socket.gethostname()}",
                protocol=mqtt.MQTTv311,
            )
            client.connect_timeout = 5
            client.max_queued_messages_set(20)
            client.reconnect_delay_set(1, 60)
            client.on_connect = self._on_connect
            client.on_disconnect = self._on_disconnect
            client.on_message = self._on_message
            if self.config.username:
                client.username_pw_set(self.config.username, os.getenv(self.config.password_env))
            if self.config.tls:
                client.tls_set()
            client.will_set(self.topic("availability"), "offline", qos=1, retain=True)
            self.client = client
            client.connect_async(self.config.host, self.config.port, keepalive=30)
            client.loop_start()
            print(f"MQTT connecting to {self.config.host}:{self.config.port}", flush=True)
        except Exception as exc:
            self.client = None
            print(f"MQTT unavailable; clock continues offline: {exc}", flush=True)

    def topic(self, suffix):
        return f"{self.config.topic_prefix}/{suffix}"

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code != 0:
            print(f"MQTT connection rejected: {reason_code}", flush=True)
            return
        client.subscribe(self.topic("face/set"), qos=1)
        client.publish(self.topic("availability"), "online", qos=1, retain=True)
        with self._lock:
            self._refresh = True
        print(f"MQTT connected; subscribed to {self.topic('face/set')}", flush=True)

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        print(f"MQTT disconnected: {reason_code}; automatic reconnect enabled", flush=True)

    def _on_message(self, client, userdata, message):
        if message.topic != self.topic("face/set") or message.retain:
            return
        try:
            face_id = parse_face_id(message.payload)
        except (ValueError, UnicodeError, TypeError) as exc:
            self._result({"ok": False, "error": str(exc)})
            return
        # Coalesce bursts so remote input cannot build an unbounded render backlog.
        with self._lock:
            self._pending = face_id

    def service(self, designs, load_current):
        if self.client is None:
            return
        with self._lock:
            face_id, refresh = self._pending, self._refresh
            self._pending = None
            self._refresh = False
        if face_id is not None:
            current_id = Path(designs.current.path).name if designs.current else None
            if designs.select_id(face_id):
                if current_id is None or current_id.casefold() != face_id.casefold():
                    load_current()
                self._result({"ok": True, "face_id": Path(designs.current.path).name})
                print(f"MQTT selected face: {face_id}", flush=True)
            else:
                self._result({"ok": False, "face_id": face_id, "error": "unknown face_id"})
        current = designs.current
        state = {
            "face_id": Path(current.path).name if current else None,
            "name": current.name if current else None,
            "mode": designs.mode,
        }
        if self.client.is_connected() and (refresh or state != self._last_state):
            self.client.publish(self.topic("face/state"), json.dumps(state), qos=1, retain=True)
            self._last_state = state
        if refresh:
            catalogue = [{"face_id": Path(d.path).name, "name": d.name} for d in designs.designs]
            self.client.publish(self.topic("faces"), json.dumps(catalogue), qos=1, retain=True)

    def _result(self, result):
        if self.client and self.client.is_connected():
            self.client.publish(self.topic("face/result"), json.dumps(result), qos=1)

    def close(self):
        if self.client is not None:
            if self.client.is_connected():
                info = self.client.publish(self.topic("availability"), "offline", qos=1, retain=True)
                info.wait_for_publish(timeout=1)
            self.client.disconnect()
            self.client.loop_stop()
