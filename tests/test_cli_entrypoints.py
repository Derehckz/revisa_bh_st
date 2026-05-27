"""Garantía CLI-first: cada script de etapa es invocable sin API ni frontend."""
from __future__ import annotations

import os
import subprocess
import sys
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_ETAPAS = os.path.join(_REPO, "etapas")
_LIB = os.path.join(_REPO, "lib")


def _stage_scripts() -> list[str]:
    names = sorted(
        f
        for f in os.listdir(_ETAPAS)
        if f.endswith(".py") and f[0].isdigit() and not f.startswith("_")
    )
    return [os.path.join(_ETAPAS, n) for n in names]


class TestCliEntrypoints(unittest.TestCase):
    def test_all_stage_scripts_expose_help(self):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8:replace"
        env["PYTHONUTF8"] = "1"
        py_path = os.pathsep.join([_LIB, _REPO, env.get("PYTHONPATH", "")])
        env["PYTHONPATH"] = py_path

        for script in _stage_scripts():
            with self.subTest(script=os.path.basename(script)):
                proc = subprocess.run(
                    [sys.executable, script, "--help"],
                    cwd=_REPO,
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=60,
                )
                self.assertEqual(
                    proc.returncode,
                    0,
                    msg=(
                        f"{os.path.basename(script)} --help failed "
                        f"(code={proc.returncode})\nstderr:\n{proc.stderr}"
                    ),
                )
                self.assertIn("usage:", proc.stdout.lower())

    def test_main_py_exposes_help(self):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8:replace"
        main_py = os.path.join(_REPO, "main.py")
        proc = subprocess.run(
            [sys.executable, main_py, "--help"],
            cwd=_REPO,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertTrue(proc.stdout.strip() or proc.stderr.strip())


if __name__ == "__main__":
    unittest.main()
