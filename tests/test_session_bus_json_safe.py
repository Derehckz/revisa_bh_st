import json

import numpy as np

from interaction.session_bus import SessionBus, json_safe


def test_json_safe_numpy_scalars():
    assert json_safe(np.int64(9)) == 9
    assert json_safe({"revis_ini": np.int64(0), "total": np.int64(99)}) == {
        "revis_ini": 0,
        "total": 99,
    }


def test_publish_events_are_json_serializable():
    bus = SessionBus("abc123")
    bus.publish(
        "analysis.complete",
        {"revis_ini": np.int64(0), "revis_fin": np.int64(9), "total": np.int64(99)},
    )
    events = bus.events_since(0)
    assert len(events) == 1
    json.dumps(events[0])
