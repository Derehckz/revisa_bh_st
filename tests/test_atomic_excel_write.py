import os
import tempfile

import pandas as pd

import utils


def test_commit_temp_to_target_replaces_file():
    with tempfile.TemporaryDirectory() as td:
        target = os.path.join(td, "libro.xlsx")
        pd.DataFrame({"a": [1]}).to_excel(target, index=False)

        fd, tmp = tempfile.mkstemp(suffix=".xlsx", dir=td)
        os.close(fd)
        pd.DataFrame({"a": [2]}).to_excel(tmp, index=False)

        utils._commit_temp_to_target(tmp, target)
        out = pd.read_excel(target)
        assert int(out.loc[0, "a"]) == 2
