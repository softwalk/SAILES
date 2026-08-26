import unittest
from datetime import UTC, datetime

from _load import load
from atlantis_contracts import Channel, ContactabilityRequest, Decision, DecisionOutcome

repository_module = load(
    "atlantis_decision_repository",
    "services/policy_gateway/app/decision_repository.py",
)


class FakeCursor:
    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params):
        self.calls.append((" ".join(sql.split()), params))


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self._cursor


class PolicyPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.cursor = FakeCursor()
        self.repository = repository_module.PostgresDecisionRepository(
            lambda: FakeConnection(self.cursor)
        )
        self.request = ContactabilityRequest(
            tenant_id="00000000-0000-0000-0000-000000000001",
            contact_id="00000000-0000-0000-0000-000000000002",
            campaign_version_id="00000000-0000-0000-0000-000000000003",
            purpose="SALES",
            channel=Channel.VOICE,
            content_hash="a" * 64,
            requested_at=datetime(2026, 8, 22, tzinfo=UTC),
        )

    def decision(self, outcome):
        return Decision(
            decision_id="00000000-0000-0000-0000-000000000004",
            outcome=outcome,
            reason_codes=("POLICY_ALLOW",),
            policy_version="mx-contactability@1",
            decided_at=datetime(2026, 8, 22, tzinfo=UTC),
        )

    def test_retry_uses_stable_action_intent_id(self):
        first = self.repository.persist(self.decision(DecisionOutcome.ALLOW), self.request)
        second = self.repository.persist(self.decision(DecisionOutcome.ALLOW), self.request)
        self.assertEqual(first, second)
        self.assertEqual(first, self.cursor.calls[1][1][0])
        self.assertEqual(first, self.cursor.calls[2][1][-1])
        self.assertEqual(first, self.cursor.calls[5][1][0])
        self.assertEqual(first, self.cursor.calls[6][1][-1])
        self.assertIn("append_audit_event", self.cursor.calls[3][0])

    def test_denied_decision_is_not_marked_allowed(self):
        self.repository.persist(self.decision(DecisionOutcome.DENY), self.request)
        self.assertEqual("DENIED", self.cursor.calls[1][1][8])
        self.assertEqual("DENY", self.cursor.calls[2][1][6])


if __name__ == "__main__":
    unittest.main()
