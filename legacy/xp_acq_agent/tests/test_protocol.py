import json
import struct
import unittest

from elyse_agent.protocol import encode_message


class ProtocolTests(unittest.TestCase):
    def test_encode_message_prefixes_utf8_json_length(self):
        framed = encode_message({"id": "one", "command": "ping", "params": {}})
        size = struct.unpack("!I", framed[:4])[0]
        self.assertEqual(size, len(framed) - 4)
        decoded = json.loads(framed[4:].decode("utf-8"))
        self.assertEqual(decoded["command"], "ping")


if __name__ == "__main__":
    unittest.main()
