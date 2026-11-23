import unittest

import helpers  # noqa: F401  (다른 import 보다 먼저)
from redact import redact


class RedactTest(unittest.TestCase):
    def test_known_tokens(self):
        for secret in ["ghp_abcdefghijklmnopqrstuvwxyz0123456789", "github_pat_11ABCDEFG0abcdefghijklmnop",
                       "sk-ant-api03-abcdefghijklmnopqrstu", "AKIAIOSFODNN7EXAMPLE", "xoxb-1234567890-abcdefghij",
                       "eyJhbGciOiJIUzI1.eyJzdWIiOiIxMjM0.SflKxwRJSMeKKF2QT4fw"]:
            out = redact(f"값은 {secret} 입니다")
            self.assertNotIn(secret, out, secret)
            self.assertIn("***", out)

    def test_pem_block_multiline(self):
        text = "앞\n-----BEGIN RSA PRIVATE KEY-----\nMIIEabc\ndef\n-----END RSA PRIVATE KEY-----\n뒤"
        out = redact(text)
        self.assertNotIn("MIIEabc", out)
        self.assertTrue(out.startswith("앞") and out.endswith("뒤"))

    def test_truncated_pem_is_masked_to_end(self):
        self.assertNotIn("MIIE", redact("-----BEGIN PRIVATE KEY-----\nMIIE..."))

    def test_assignments(self):
        self.assertEqual(redact("export GH_TOKEN=abcd1234efgh"), "export GH_TOKEN=***")
        self.assertEqual(redact("DB_PASSWORD=hunter2hunter2"), "DB_PASSWORD=***")
        self.assertEqual(redact('api_key: "abc123def456"'), 'api_key: "***"')
        self.assertEqual(redact("--password mypass123"), "--password ***")
        self.assertEqual(redact("--token=abcd1234"), "--token=***")

    def test_bearer_and_url_credentials(self):
        self.assertNotIn("abcdefghijklmnop12345", redact("Authorization: Bearer abcdefghijklmnop12345"))
        self.assertEqual(redact("https://bob:s3cret@github.com/x/y.git"), "https://bob:***@github.com/x/y.git")

    def test_no_false_positives(self):
        for ok in ["토큰 발급 방법을 알려줘", "TOKEN=$MY_TOKEN", "max_tokens=1000", "author=kim", "PWD=/home/x",
                   "password=***", "password: <your-password>", "SECRET=${SECRET}", "일반 문장입니다. https://github.com/x/y"]:
            self.assertEqual(redact(ok), ok, ok)

    def test_idempotent_and_non_string(self):
        text = "TOKEN=abcd1234efgh ghp_abcdefghijklmnopqrstuvwxyz0123456789 -----BEGIN PRIVATE KEY-----\nx\n-----END PRIVATE KEY-----"
        once = redact(text)
        self.assertEqual(redact(once), once)
        self.assertIsNone(redact(None))
        self.assertEqual(redact(""), "")


if __name__ == "__main__":
    unittest.main()
