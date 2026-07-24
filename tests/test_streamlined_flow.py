from stages.streamlined import confirm_unless_streamlined, param_streamlined


class _FakeUI:
    def __init__(self):
        self.logs = []
        self.asked = 0

    def log(self, message, level="info"):
        self.logs.append((level, message))

    def confirm_yes_no(self, title, message, default=True):
        self.asked += 1
        return False


def test_param_streamlined_defaults_true():
    assert param_streamlined({}) is True
    assert param_streamlined({"streamlined": False}) is False
    assert param_streamlined({"streamlined": True}) is True


def test_confirm_unless_streamlined_skips_prompt():
    ui = _FakeUI()
    assert confirm_unless_streamlined(ui, True, "Guardar Excel", "¿Guardar?", default=True) is True
    assert ui.asked == 0
    assert any("automático" in m for _, m in ui.logs)


def test_confirm_unless_streamlined_asks_when_not_streamlined():
    ui = _FakeUI()
    assert confirm_unless_streamlined(ui, False, "Guardar Excel", "¿Guardar?", default=True) is False
    assert ui.asked == 1
