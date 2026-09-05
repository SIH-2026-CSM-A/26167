import numpy as np
import pytest

from app.tools.fusion.guards import ScaleError, require_db_scale
from app.tools.fusion.sar_scale import SarScale


def test_require_db_scale_passes_through_when_declared_db():
    array = np.array([-12.5, -3.0, -20.1])
    result = require_db_scale(array, SarScale.DB)
    assert result is array


def test_require_db_scale_raises_when_declared_linear():
    array = np.array([0.05, 0.5, 0.001])
    with pytest.raises(ScaleError):
        require_db_scale(array, SarScale.LINEAR)


def test_require_db_scale_does_not_inspect_values():
    positive_looking_dn_values = np.array([500, 12000, 60000], dtype=np.uint16)
    result = require_db_scale(positive_looking_dn_values, SarScale.DB)
    assert result is positive_looking_dn_values
