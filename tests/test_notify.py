import json
import unittest
from unittest import mock

import helpers
import notify


class NotifyTest(unittest.TestCase):
    def setUp(self):
        helpers.fresh_state()

    def test_off_by_default_and_never_raises(self):
        self.assertEqual(notify.get_url(), "")
        self.assertFalse(notify.send("t", "m"))
        self.assertFalse(notify.needs_you("p", 1))

    def test_set_url_validates(self):
        for bad in ("ntfy.sh/x", "https://ntfy.sh", "ftp://a/b"):
            with self.assertRaises(ValueError):
                notify.set_url(bad)
        notify.set_url("https://ntfy.sh/my-topic")
        self.assertEqual(notify.get_url(), "https://ntfy.sh/my-topic")
        notify.set_url("")
        self.assertEqual(notify.get_url(), "")

    def test_payload_contains_only_minimal_info(self):
        notify.set_url("https://ntfy.sh/my-topic")
        captured = {}

        def fake_urlopen(req, timeout=0):
            captured["url"], captured["body"] = req.full_url, json.loads(req.data.decode("utf-8"))
            return mock.MagicMock(__enter__=lambda s: mock.MagicMock(status=200), __exit__=lambda *a: False)

        with mock.patch("urllib.request.urlopen", fake_urlopen):
            self.assertTrue(notify.needs_you("shop", 12, "https://github.com/o/r/issues/12"))
        self.assertEqual(captured["url"], "https://ntfy.sh")
        self.assertEqual(captured["body"]["topic"], "my-topic")
        self.assertIn("shop", captured["body"]["title"])
        self.assertIn("#12", captured["body"]["message"])
        self.assertEqual(set(captured["body"]), {"topic", "title", "message", "click"})

    def test_network_error_returns_false(self):
        notify.set_url("https://ntfy.sh/my-topic")
        with mock.patch("urllib.request.urlopen", side_effect=OSError("down")):
            self.assertFalse(notify.needs_you("shop", 1))


if __name__ == "__main__":
    unittest.main()
