"""Importing the API must not load the ML stack: on a 512 MB Render instance torch/transformers
at import time leave no headroom and the process is OOM-killed on the first auth request.
"""

import subprocess
import sys
from pathlib import Path

_CHECK = (
    "import app.api.main, sys; print(any(m.split('.')[0] in "
    "{'torch','transformers','torchvision','peft','timm'} for m in sys.modules))"
)


def test_api_import_does_not_load_ml_libraries():
    result = subprocess.run(
        [sys.executable, "-c", _CHECK],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "False"
