import hashlib
import hmac
import unittest

from _load import load

webhooks = load("atlantis_webhooks", "shared/atlantis_contracts/webhook.py")


class WebhookTests(unittest.TestCase):
    def setUp(self):
        self.events = set()
        self.remember = lambda provider, event_id, body_hash: False if (provider, event_id) in self.events else not self.events.add((provider, event_id))
        self.secret = b"w" * 32

    def test_meta_signature_and_duplicate(self):
        body = b'{"entry":[]}'
        signature = "sha256=" + hmac.new(self.secret, body, hashlib.sha256).hexdigest()
        verifier = webhooks.WebhookVerifier({"meta": self.secret}, self.remember)
        receipt = verifier.verify_meta(body, signature, "meta-1", now=1000)
        self.assertEqual(receipt.event_id, "meta-1")
        with self.assertRaisesRegex(webhooks.WebhookError, "DUPLICATE"):
            verifier.verify_meta(body, signature, "meta-1", now=1001)

    def test_invalid_meta_signature(self):
        verifier = webhooks.WebhookVerifier({"meta": self.secret}, self.remember)
        with self.assertRaisesRegex(webhooks.WebhookError, "INVALID_META_SIGNATURE"):
            verifier.verify_meta(b"{}", "sha256=" + "0" * 64, "meta-2")

    def test_generic_webhook_rejects_stale_timestamp(self):
        verifier = webhooks.WebhookVerifier({"marketia": self.secret}, self.remember)
        with self.assertRaisesRegex(webhooks.WebhookError, "STALE_WEBHOOK"):
            verifier.verify_generic("marketia", b"{}", "none", "100", "m-1", now=1000)


if __name__ == "__main__": unittest.main()
