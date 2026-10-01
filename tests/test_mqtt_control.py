import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from piclock.config import Config, MqttConfig
from piclock.designs import DesignSet
from piclock.mqtt_control import MqttControl, parse_face_id


class MqttTests(unittest.TestCase):
    def test_payload_formats(self):
        self.assertEqual(parse_face_id(b'paper-cut'), 'paper-cut')
        self.assertEqual(parse_face_id(b'{"face_id":"Night"}'), 'Night')
        for payload in (b'', b'../Night', b'{"face_id":2}', b'\xff', b'x' * 1025, b'{oops'):
            with self.assertRaises((ValueError, UnicodeError)):
                parse_face_id(payload)

    def test_config_validation(self):
        self.assertFalse(Config.from_dict({}).mqtt.enabled)
        for data in ({'enabled': True}, {'topic_prefix': 'clock/+'}, {'port': 0}):
            with self.assertRaises(ValueError):
                Config.from_dict({'mqtt': data})

    def test_selection_persistence_invalid_id_and_retained_command(self):
        with tempfile.TemporaryDirectory() as root:
            for slug in ('Night', 'paper-cut'):
                folder = Path(root, slug)
                folder.mkdir()
                (folder / 'theme.json').write_text(json.dumps({'name': 'Shared Name'}))
            state_path = str(Path(root, 'state.json'))
            designs = DesignSet.scan(root, state_path=state_path)
            control = MqttControl(MqttConfig())
            control.client = Mock()
            control.client.is_connected.return_value = True
            load = Mock()
            control._on_message(None, None, SimpleNamespace(
                topic=control.topic('face/set'), payload=b'paper-cut', retain=False))
            control.service(designs, load)
            self.assertEqual(Path(designs.current.path).name, 'paper-cut')
            self.assertEqual(designs.mode, 'manual')
            self.assertEqual(DesignSet.scan(root, state_path=state_path).current.path, designs.current.path)
            control._on_message(None, None, SimpleNamespace(
                topic=control.topic('face/set'), payload=b'Night', retain=True))
            control.service(designs, load)
            self.assertEqual(Path(designs.current.path).name, 'paper-cut')
            self.assertFalse(designs.select_id('missing'))
            self.assertTrue(designs.select_id('night'))
            self.assertEqual(Path(designs.current.path).name, 'Night')

    def test_reconnect_refreshes_state_and_catalogue(self):
        control = MqttControl(MqttConfig())
        control.client = Mock()
        control.client.is_connected.return_value = True
        control._on_connect(control.client, None, None, 0, None)
        control.service(DesignSet(), Mock())
        topics = [call.args[0] for call in control.client.publish.call_args_list]
        self.assertIn(control.topic('faces'), topics)
        self.assertIn(control.topic('face/state'), topics)
        control.client.subscribe.assert_called_once_with(control.topic('face/set'), qos=1)


if __name__ == '__main__':
    unittest.main()
