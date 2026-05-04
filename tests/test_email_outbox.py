import email_outbox


def test_outbox_pending_sent_failed(bh_raiz_tmp):
    oid = email_outbox.record_pending("t", "k1", {"a": 1})
    assert oid > 0
    email_outbox.mark_sent(oid)
    oid2 = email_outbox.record_pending("t", "k2", None)
    email_outbox.mark_failed(oid2, "boom")
    # No exception = journal escribió en SQLite


def test_outbox_fetch_pending_and_status(bh_raiz_tmp):
    oid = email_outbox.record_pending("script5.recepcion_send", "k3", None)
    assert email_outbox.get_row_status(oid) == "pending"
    rows = email_outbox.fetch_pending_rows(limit=10)
    ids = [r["id"] for r in rows]
    assert oid in ids
    email_outbox.mark_sent(oid)
    assert email_outbox.get_row_status(oid) == "sent"
