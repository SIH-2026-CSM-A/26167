"""Importing the API must not load the ML stack: on a 512 MB Render instance torch/transformers
at import time leave no headroom and the process is OOM-killed on the first auth request.
"""

import subprocess
import sys
from pathlib import Path

import pytest

_CHECK = (
    "import {module}, sys; print(any(m.split('.')[0] in "
    "{{'torch','transformers','torchvision','peft','timm'}} for m in sys.modules))"
)


# app.pipeline is imported on the first /query; fusion and vetoed queries must stay torch-free.
@pytest.mark.parametrize("module", ["app.api.main", "app.pipeline"])
def test_import_does_not_load_ml_libraries(module):
    result = subprocess.run(
        [sys.executable, "-c", _CHECK.format(module=module)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "False"
