"""Gate integration tests so a plain `pytest` run never needs a live network.

Pass `--network localnet` (the documented command) to enable them.
"""

import pytest


def pytest_collection_modifyitems(config, items):
    if config.getoption("--network", default=None) is not None:
        return
    skip = pytest.mark.skip(
        reason="integration test: run with `gltest tests/integration -v -s --network localnet`"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)
