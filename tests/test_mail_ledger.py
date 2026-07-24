"""E12: pruebas básicas de mail_ledger.was_sent/mark_sent con estado aislado."""
from __future__ import annotations

import mail_ledger


def test_was_sent_false_by_default(bh_raiz_tmp):
    assert mail_ledger.was_sent("stage5", "docente-123") is False


def test_mark_sent_then_was_sent_true(bh_raiz_tmp):
    mail_ledger.mark_sent("stage5", "docente-123", details="enviado ok")
    assert mail_ledger.was_sent("stage5", "docente-123") is True


def test_mark_sent_is_scoped_by_stage_and_key(bh_raiz_tmp):
    mail_ledger.mark_sent("stage5", "docente-1", details=None)
    assert mail_ledger.was_sent("stage5", "docente-1") is True
    assert mail_ledger.was_sent("stage7", "docente-1") is False
    assert mail_ledger.was_sent("stage5", "docente-2") is False


def test_clear_sent_resets_flag(bh_raiz_tmp):
    mail_ledger.mark_sent("stage5", "docente-9")
    assert mail_ledger.was_sent("stage5", "docente-9") is True

    mail_ledger.clear_sent("stage5", "docente-9")
    assert mail_ledger.was_sent("stage5", "docente-9") is False


def test_record_pending_and_outbox_stats(bh_raiz_tmp):
    outbox_id = mail_ledger.record_pending("stage5", "docente-42", {"to": "x@y.cl"})
    assert isinstance(outbox_id, int)

    stats_before = mail_ledger.stats_by_status()
    assert stats_before.get("pending", 0) >= 1

    mail_ledger.mark_outbox_sent(outbox_id)
    stats_after = mail_ledger.stats_by_status()
    assert stats_after.get("sent", 0) >= 1
