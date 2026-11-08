import importlib.util
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

HAS_HA = importlib.util.find_spec("pytest_homeassistant_custom_component") is not None
if HAS_HA:
    pytest_plugins = "pytest_homeassistant_custom_component"

    @pytest.fixture(autouse=True)
    def _enable(enable_custom_integrations):
        yield
