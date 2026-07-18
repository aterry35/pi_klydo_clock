"""Renderer-side client and asynchronous state for network recovery."""
from __future__ import annotations

import json
import queue
import socket
import threading
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AccessPoint:
    ssid: str
    signal: int = 0
    security: str = ""
    in_use: bool = False


@dataclass(frozen=True)
class NetworkSnapshot:
    state: str = "unknown"
    connection: str = ""
    ip_address: str = ""
    hotspot: bool = False
    access_points: tuple[AccessPoint, ...] = field(default_factory=tuple)

    @staticmethod
    def from_payload(payload: dict) -> "NetworkSnapshot":
        points = tuple(
            AccessPoint(
                ssid=str(item.get("ssid", "")),
                signal=_signal_strength(item.get("signal", 0)),
                security=str(item.get("security", "")),
                in_use=bool(item.get("in_use", False)),
            )
            for item in payload.get("access_points", [])
            if isinstance(item, dict) and str(item.get("ssid", "")).strip()
        )
        return NetworkSnapshot(
            state=str(payload.get("state", "unknown")),
            connection=str(payload.get("connection", "")),
            ip_address=str(payload.get("ip_address", "")),
            hotspot=bool(payload.get("hotspot", False)),
            access_points=points,
        )


class NetworkClient:
    def __init__(self, socket_path: str, timeout: float = 40.0):
        self.socket_path = socket_path
        self.timeout = timeout

    def request(self, action: str) -> dict:
        request = json.dumps({"action": action}, separators=(",", ":")).encode() + b"\n"
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(self.timeout)
            client.connect(self.socket_path)
            client.sendall(request)
            response = _receive_line(client)
        payload = json.loads(response.decode("utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeError("network helper returned an invalid response")
        if not payload.get("ok"):
            raise RuntimeError(str(payload.get("error", "network operation failed")))
        return payload


def _receive_line(sock: socket.socket, maximum: int = 65536) -> bytes:
    data = bytearray()
    while len(data) < maximum:
        chunk = sock.recv(min(4096, maximum - len(data)))
        if not chunk:
            break
        data.extend(chunk)
        if b"\n" in chunk:
            break
    line = bytes(data).split(b"\n", 1)[0]
    if not line:
        raise RuntimeError("network helper closed without a response")
    if len(data) >= maximum and b"\n" not in data:
        raise RuntimeError("network helper response was too large")
    return line


class NetworkController:
    """Run helper calls away from the frame loop and expose polled UI state."""

    def __init__(self, client: NetworkClient):
        self.client = client
        self.snapshot = NetworkSnapshot()
        self.busy = False
        self.message = ""
        self.error = ""
        self._requests: queue.Queue[str | None] = queue.Queue()
        self._results: queue.Queue[tuple[str, dict | None, Exception | None]] = queue.Queue()
        self._thread = threading.Thread(
            target=self._worker,
            name="piclock-network",
            daemon=True,
        )
        self._thread.start()

    def refresh(self) -> bool:
        submitted = self._submit("scan")
        if submitted:
            self.message = ""
        return submitted

    def start_hotspot(self) -> bool:
        submitted = self._submit("start_hotspot")
        if submitted:
            self.message = "Starting setup hotspot..."
        return submitted

    def _submit(self, action: str) -> bool:
        if self.busy:
            return False
        self.busy = True
        self.error = ""
        self._requests.put(action)
        return True

    def _worker(self) -> None:
        while True:
            action = self._requests.get()
            if action is None:
                return
            try:
                result = self.client.request(action)
            except Exception as exc:  # surfaced in the on-screen recovery panel
                self._results.put((action, None, exc))
            else:
                self._results.put((action, result, None))

    def poll(self) -> None:
        while True:
            try:
                action, result, error = self._results.get_nowait()
            except queue.Empty:
                return
            self.busy = False
            if error is not None:
                self.error = str(error)
                self.message = ""
                continue
            assert result is not None
            snapshot = result.get("snapshot", {})
            if isinstance(snapshot, dict):
                self.snapshot = NetworkSnapshot.from_payload(snapshot)
            self.error = ""
            if action == "start_hotspot":
                self.message = "Setup hotspot is ready"
            else:
                self.message = ""

    def close(self) -> None:
        self._requests.put(None)


def _signal_strength(value) -> int:
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return 0
