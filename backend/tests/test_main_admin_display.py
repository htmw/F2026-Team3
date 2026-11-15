"""Connection-state and rounding regressions; never sends mail or changes settings."""
from types import SimpleNamespace
from unittest.mock import Mock, patch
import pytest
from risk_mvp.admin_display import email_health, workload_percent
from services import integrations, mailer


@pytest.mark.parametrize("row,health,expected", [
    (None, ("Healthy", "unused"), "Off"),
    (SimpleNamespace(id="mail", enabled=False, last_error=None), ("Healthy", "unused"), "Off"),
    (SimpleNamespace(id="mail", enabled=True, last_error="failed"), ("Healthy", "unused"), "Down"),
    (SimpleNamespace(id="mail", enabled=True, last_error=None), ("Degraded", "Delivery delayed"), "Degraded"),
    (SimpleNamespace(id="mail", enabled=True, last_error=None), ("Healthy", "unused"), "Healthy"),
])
def test_email_connection_state(row, health, expected):
    db = Mock()
    db.get.return_value = row
    with patch.object(mailer, "health", return_value=health), patch.object(mailer, "_smtp_send", side_effect=AssertionError("No network")):
        status, detail = email_health(db)
        assert status == expected
        if row is not None:
            assert {"Error": "Down", "Connected": "Healthy"}.get(integrations.status(row), integrations.status(row)) == status
        if status == "Healthy":
            assert "not verified" in detail
        elif status == "Off":
            assert "not connected" in detail
        db.commit.assert_not_called()
        db.add.assert_not_called()


@pytest.mark.parametrize("count,capacity,expected", [(25,40,63),(2,3,67),(0,40,0),(45,40,100),(1,0,100)])
def test_workload_rounding(count, capacity, expected):
    assert workload_percent(count, capacity) == expected
