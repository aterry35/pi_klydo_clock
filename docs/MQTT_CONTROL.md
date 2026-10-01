# MQTT face selection

MQTT is optional and disabled by default. Install the updated requirements and
merge the `mqtt` section from `config/mqtt.example.json` into the device's
`/etc/piclock/clock.json`. Preserve its existing layout calibration.
Restart `piclock-renderer` after changing settings.

Use a unique `topic_prefix` and `client_id` for each clock. Credentials are
device-local: `username` comes from configuration, while the password is read
from the environment variable named by `password_env`. Set `tls` to true for
a broker with a trusted TLS certificate and configure its TLS port.

## Topics

| Topic suffix | Behavior |
| --- | --- |
| `/face/set` | Send a folder ID as plain text or `{"face_id":"paper-cut"}` |
| `/face/state` | Retained JSON: selected `face_id`, display `name`, and `mode` |
| `/faces` | Retained array of available `{face_id,name}` entries |
| `/face/result` | Non-retained acknowledgement or validation error |
| `/availability` | Retained `online`/`offline`, including an offline last will |

IDs are the folder names, case-insensitive, not display names or numeric indexes.
Invalid IDs leave selection unchanged. Successful selection enters manual mode
and is saved using the existing state file. Local taps and daily-mode changes
also update the MQTT state topic. A tap or the existing daily command can still
change the face after a remote command.

Publish commands without retain. Retained commands are deliberately ignored so
an old broker message cannot override the locally saved selection on reconnect.
New folders are discovered after a renderer restart as before. MQTT reconnects
automatically; unavailable network/broker does not prevent the clock rendering.

```bash
mosquitto_sub -h BROKER -p PORT -t 'piclock/my-clock/#' -v
mosquitto_pub -h BROKER -p PORT -q 1 \
  -t 'piclock/my-clock/face/set' -m 'paper-cut'
```

The existing EC2 broker was inspected on September 30, 2026: Mosquitto uses an
anonymous TCP listener on port 1884. This does not authenticate publishers or
encrypt traffic. Its address is configured on the deployed device rather than
embedded in the public source.
