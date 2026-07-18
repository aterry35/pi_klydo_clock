import json
import unittest

from piclock.network_service import (
    CommandResult,
    NetworkBackend,
    NetworkControlServer,
    split_nmcli,
)


class FakeRunner:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def __call__(self, args, timeout):
        self.calls.append((args, timeout))
        for predicate, result in self.responses:
            if predicate(args):
                return result
        return CommandResult(1, stderr=f"unexpected command: {args}")


class NetworkServiceTests(unittest.TestCase):
    def test_nmcli_parser_preserves_escaped_ssid_characters(self):
        self.assertEqual(
            split_nmcli(r"*:Cafe\: Guest\\5G:82:WPA2"),
            ["*", "Cafe: Guest\\5G", "82", "WPA2"],
        )

    def test_snapshot_combines_comitup_networkmanager_and_ip_data(self):
        runner = FakeRunner([
            (
                lambda args: args[:2] == ["comitup-cli", "i"],
                CommandResult(
                    0,
                    "Host PiClock-1234.local on comitup version 1.43\n"
                    "'single' mode\nCONNECTED state\n",
                ),
            ),
            (
                lambda args: "GENERAL.STATE,GENERAL.CONNECTION" in args,
                CommandResult(
                    0,
                    "GENERAL.STATE:100 (connected)\nGENERAL.CONNECTION:Home WiFi\n",
                ),
            ),
            (
                lambda args: args[:3] == ["ip", "-json", "-4"],
                CommandResult(0, json.dumps([{
                    "addr_info": [{
                        "family": "inet",
                        "scope": "global",
                        "local": "192.168.1.217",
                    }],
                }])),
            ),
            (
                lambda args: "IN-USE,SSID,SIGNAL,SECURITY" in args,
                CommandResult(
                    0,
                    ":Home WiFi:95:WPA2\n*:Home WiFi:78:WPA2\n"
                    ":Guest\\: IoT:64:WPA2\n",
                ),
            ),
        ])
        snapshot = NetworkBackend(runner=runner).snapshot(rescan=True)

        self.assertEqual(snapshot["state"], "CONNECTED")
        self.assertEqual(snapshot["connection"], "Home WiFi")
        self.assertEqual(snapshot["ip_address"], "192.168.1.217")
        self.assertFalse(snapshot["hotspot"])
        self.assertEqual(
            [(point["ssid"], point["signal"], point["in_use"])
             for point in snapshot["access_points"]],
            [("Home WiFi", 78, True), ("Guest: IoT", 64, False)],
        )

    def test_server_rejects_actions_outside_the_allowlist(self):
        server = NetworkControlServer(
            "/run/piclock-network/test.sock",
            NetworkBackend(runner=FakeRunner([])),
        )

        response = server.handle({"action": "run_command"})

        self.assertFalse(response["ok"])
        self.assertIn("unsupported", response["error"])

    def test_disconnected_networkmanager_state_is_not_reported_as_connected(self):
        runner = FakeRunner([
            (
                lambda args: "GENERAL.STATE,GENERAL.CONNECTION" in args,
                CommandResult(
                    0,
                    "GENERAL.STATE:30 (disconnected)\nGENERAL.CONNECTION:--\n",
                ),
            ),
        ])

        state, connection = NetworkBackend(runner=runner)._networkmanager_status()

        self.assertEqual(state, "DISCONNECTED")
        self.assertEqual(connection, "")

    def test_server_rejects_socket_paths_outside_runtime_directory(self):
        with self.assertRaisesRegex(ValueError, "must be under"):
            NetworkControlServer(
                "/tmp/piclock-network.sock",
                NetworkBackend(runner=FakeRunner([])),
            )

    def test_hotspot_reset_uses_comitup_nuke_then_waits_for_hotspot(self):
        status_calls = 0

        def runner(args, timeout):
            nonlocal status_calls
            if args[:2] == ["comitup-cli", "x"]:
                return CommandResult(0)
            if args[:2] == ["comitup-cli", "i"]:
                status_calls += 1
                state = "CONNECTED" if status_calls == 1 else "HOTSPOT"
                return CommandResult(0, f"{state} state\n")
            if "GENERAL.STATE,GENERAL.CONNECTION" in args:
                connection = "Home WiFi" if status_calls == 1 else "PiClock-1234"
                return CommandResult(
                    0,
                    f"GENERAL.STATE:100 (connected)\nGENERAL.CONNECTION:{connection}\n",
                )
            return CommandResult(1, stderr="not available")

        backend = NetworkBackend(runner=runner, sleeper=lambda _: None)
        snapshot = backend.start_hotspot()

        self.assertTrue(snapshot["hotspot"])
        self.assertEqual(snapshot["connection"], "PiClock-1234")


if __name__ == "__main__":
    unittest.main()
