"""Root-owned NetworkManager/Comitup control service for the clock renderer."""
from __future__ import annotations

import argparse
import json
import os
import socket
import stat
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


def run_command(args: list[str], timeout: float) -> CommandResult:
    completed = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def split_nmcli(line: str) -> list[str]:
    """Split terse nmcli output while preserving escaped colons and backslashes."""
    fields: list[str] = []
    current: list[str] = []
    escaped = False
    for char in line.rstrip("\n"):
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == ":":
            fields.append("".join(current))
            current = []
        else:
            current.append(char)
    if escaped:
        current.append("\\")
    fields.append("".join(current))
    return fields


class NetworkBackend:
    def __init__(
        self,
        interface: str = "wlan0",
        runner: Callable[[list[str], float], CommandResult] = run_command,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        if (
            not interface
            or any(char.isspace() for char in interface)
            or any(not (char.isalnum() or char in "._-") for char in interface)
        ):
            raise ValueError("invalid network interface")
        self.interface = interface
        self.runner = runner
        self.sleeper = sleeper

    def _run(self, args: list[str], timeout: float = 8.0) -> str:
        result = self.runner(args, timeout)
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "command failed"
            raise RuntimeError(detail)
        return result.stdout

    def _optional(self, args: list[str], timeout: float = 5.0) -> str:
        try:
            return self._run(args, timeout)
        except (OSError, RuntimeError, subprocess.TimeoutExpired):
            return ""

    def snapshot(self, rescan: bool = False) -> dict:
        comitup_state, comitup_connection = self._comitup_status()
        nm_state, nm_connection = self._networkmanager_status()
        state = comitup_state or nm_state or "unknown"
        connection = comitup_connection or nm_connection
        return {
            "state": state,
            "connection": connection,
            "ip_address": self._ip_address(),
            "hotspot": state.upper() == "HOTSPOT",
            "access_points": self._access_points(rescan),
        }

    def _comitup_status(self) -> tuple[str, str]:
        output = self._optional(["comitup-cli", "i"], timeout=2.0)
        state = ""
        connection = ""
        for line in output.splitlines():
            stripped = line.strip()
            if stripped.upper().endswith(" STATE"):
                candidate = stripped[:-6].strip().upper()
                if candidate in {"HOTSPOT", "CONNECTING", "CONNECTED"}:
                    state = candidate
                    continue
            key, separator, value = line.partition(":")
            if not separator:
                continue
            if key.strip().lower() == "state":
                state = value.strip().upper()
            elif key.strip().lower() == "connection":
                connection = value.strip()
        return state, connection

    def _networkmanager_status(self) -> tuple[str, str]:
        output = self._optional([
            "nmcli", "--terse", "--escape", "yes",
            "--fields", "GENERAL.STATE,GENERAL.CONNECTION",
            "device", "show", self.interface,
        ])
        values: dict[str, str] = {}
        for line in output.splitlines():
            fields = split_nmcli(line)
            if len(fields) >= 2:
                values[fields[0]] = ":".join(fields[1:])
        raw_state = values.get("GENERAL.STATE", "").lower()
        if "disconnected" in raw_state or "unavailable" in raw_state:
            state = "DISCONNECTED"
        elif "connecting" in raw_state:
            state = "CONNECTING"
        elif "connected" in raw_state:
            state = "CONNECTED"
        elif raw_state:
            state = "DISCONNECTED"
        else:
            state = ""
        connection = values.get("GENERAL.CONNECTION", "")
        if connection == "--":
            connection = ""
        return state, connection

    def _ip_address(self) -> str:
        output = self._optional([
            "ip", "-json", "-4", "address", "show", "dev", self.interface,
        ])
        if not output:
            return ""
        try:
            interfaces = json.loads(output)
        except json.JSONDecodeError:
            return ""
        for interface in interfaces:
            for address in interface.get("addr_info", []):
                if address.get("family") == "inet" and address.get("scope") == "global":
                    return str(address.get("local", ""))
        return ""

    def _access_points(self, rescan: bool) -> list[dict]:
        output = self._optional([
            "nmcli", "--terse", "--escape", "yes",
            "--fields", "IN-USE,SSID,SIGNAL,SECURITY",
            "device", "wifi", "list", "ifname", self.interface,
            "--rescan", "yes" if rescan else "no",
        ], timeout=15.0 if rescan else 5.0)
        by_ssid: dict[str, dict] = {}
        for line in output.splitlines():
            fields = split_nmcli(line)
            if len(fields) != 4:
                continue
            in_use, ssid, signal, security = fields
            if not ssid.strip():
                continue
            try:
                strength = max(0, min(100, int(signal)))
            except ValueError:
                strength = 0
            point = {
                "ssid": ssid,
                "signal": strength,
                "security": security,
                "in_use": in_use.strip() == "*",
            }
            existing = by_ssid.get(ssid)
            if (
                existing is None
                or (point["in_use"] and not existing["in_use"])
                or (point["in_use"] == existing["in_use"] and strength > existing["signal"])
            ):
                by_ssid[ssid] = point
        return sorted(
            by_ssid.values(),
            key=lambda item: (not item["in_use"], -item["signal"], item["ssid"].lower()),
        )[:12]

    def start_hotspot(self) -> dict:
        self._run(["comitup-cli", "x"], timeout=15.0)
        for _ in range(20):
            state, _ = self._comitup_status()
            if state == "HOTSPOT":
                return self.snapshot(rescan=False)
            self.sleeper(0.5)
        raise RuntimeError("Comitup did not enter hotspot mode")


class NetworkControlServer:
    ALLOWED_ACTIONS = {"status", "scan", "start_hotspot"}

    def __init__(self, socket_path: str, backend: NetworkBackend):
        self.socket_path = Path(socket_path).resolve()
        allowed_dir = Path("/run/piclock-network").resolve()
        if self.socket_path.parent != allowed_dir:
            raise ValueError("network control socket must be under /run/piclock-network")
        self.backend = backend

    def serve_forever(self) -> None:
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        if self.socket_path.exists():
            if not stat.S_ISSOCK(self.socket_path.stat().st_mode):
                raise RuntimeError("refusing to replace a non-socket control path")
            self.socket_path.unlink()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            server.bind(str(self.socket_path))
            os.chmod(self.socket_path, 0o660)
            server.listen(4)
            while True:
                connection, _ = server.accept()
                with connection:
                    connection.settimeout(2.0)
                    try:
                        request = _receive_request(connection)
                        response = self.handle(request)
                    except Exception as exc:
                        response = {"ok": False, "error": str(exc)}
                    try:
                        connection.sendall(
                            json.dumps(response, separators=(",", ":")).encode() + b"\n"
                        )
                    except OSError:
                        pass

    def handle(self, request: dict) -> dict:
        try:
            action = request.get("action")
            if action not in self.ALLOWED_ACTIONS:
                raise ValueError("unsupported network action")
            if action == "start_hotspot":
                snapshot = self.backend.start_hotspot()
            else:
                snapshot = self.backend.snapshot(rescan=action == "scan")
            return {"ok": True, "snapshot": snapshot}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


def _receive_request(connection: socket.socket, maximum: int = 4096) -> dict:
    data = bytearray()
    while len(data) < maximum:
        chunk = connection.recv(min(1024, maximum - len(data)))
        if not chunk:
            break
        data.extend(chunk)
        if b"\n" in chunk:
            break
    if not data or (len(data) >= maximum and b"\n" not in data):
        raise ValueError("invalid network request")
    payload = json.loads(bytes(data).split(b"\n", 1)[0].decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("network request must be a JSON object")
    return payload


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Pi clock network control helper")
    parser.add_argument("--socket")
    parser.add_argument("--interface")
    args = parser.parse_args(argv)
    from .config import load_clock_config

    config = load_clock_config()
    socket_path = args.socket or config.network.control_socket
    interface = args.interface or config.network.interface
    NetworkControlServer(socket_path, NetworkBackend(interface)).serve_forever()


if __name__ == "__main__":
    main()
