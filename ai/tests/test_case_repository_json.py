from datetime import date, datetime, timezone
from decimal import Decimal

from ai.app.case.repository import _decode_json_value, _encode_json_value


def test_case_facts_json_preserves_decimal_and_dates():
    facts = {
        "charged_amount": Decimal("2000.00"),
        "transaction_date": date(2026, 10, 3),
        "observed_at": datetime(2026, 10, 3, 12, tzinfo=timezone.utc),
    }

    restored = _decode_json_value(_encode_json_value(facts))

    assert restored == facts
    assert isinstance(restored["charged_amount"], Decimal)
