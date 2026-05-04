import idempotency_store


def test_was_success_mark_success_roundtrip(bh_raiz_tmp):
    assert not idempotency_store.was_success("test.stage", "k1")
    idempotency_store.mark_success("test.stage", "k1", details="x")
    assert idempotency_store.was_success("test.stage", "k1")
    idempotency_store.clear_success("test.stage", "k1")
    assert not idempotency_store.was_success("test.stage", "k1")


def test_report_duplicate(bh_raiz_tmp):
    assert not idempotency_store.report_duplicate("test.stage", "d1")
    assert idempotency_store.report_duplicate("test.stage", "d1")
