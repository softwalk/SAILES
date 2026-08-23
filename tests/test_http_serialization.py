import unittest
from datetime import date
from decimal import Decimal
from uuid import UUID

from atlantis_contracts.http import _json_default


class HttpSerializationTests(unittest.TestCase):
    def test_uuid_serializes_as_string(self):
        value = UUID("00000000-0000-0000-0000-000000000001")
        self.assertEqual(str(value), _json_default(value))

    def test_date_serializes_as_iso8601(self):
        self.assertEqual("2026-08-22", _json_default(date(2026, 8, 22)))

    def test_decimal_serializes_without_binary_float_loss(self):
        self.assertEqual("12.5000", _json_default(Decimal("12.5000")))


if __name__ == "__main__":
    unittest.main()
