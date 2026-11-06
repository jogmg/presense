"""Run glsim with the project's Windows toolchain shims applied.

`gltest.direct.loader` unlinks a temp file while fd 0 still holds it. POSIX
allows this; Windows raises WinError 32. The pytest suite applies a shim in
`tests/conftest.py`, but glsim runs in its own process, so start it through
this launcher instead of calling `glsim` directly:

    python scripts/run_glsim.py --no-browser
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.conftest import (  # noqa: E402
    _patch_runner_bundle_fallback,
    _patch_windows_stdin_cleanup,
)


def _patch_contract_proxy() -> None:
    """Let glsim cache the real contract class, not gltest's calldata proxy.

    `gltest.direct.loader.deploy_contract` returns a proxy whose type has no
    public methods or storage annotations. glsim 0.29.2 expects the raw
    instance, so it caches the proxy and later reports an empty ABI.
    """
    from gltest.direct import loader

    loader._make_contract_proxy = lambda instance: instance


def _patch_transaction_value() -> None:
    """Apply a write transaction's native value to the simulated VM.

    glsim 0.29.2 decodes the value from the raw transaction but never copies
    it into ``vm.value``, so ``gl.message.value`` is always zero inside a
    contract. Payable methods therefore fail even though the receipt is
    reported as finalized. Wrap the RPC handler so the decoded value is set
    for the duration of the call and then restored.
    """
    import glsim.server as server

    original = server._rpc_eth_send_raw_transaction

    def send_with_value(state, engine, params):
        raw_hex = server._positional(params, 0)
        value = 0
        if raw_hex:
            value = server.decode_raw_transaction(raw_hex)["value"]

        previous = engine.vm.value
        engine.vm.value = value
        try:
            return original(state, engine, params)
        finally:
            engine.vm.value = previous

    server._rpc_eth_send_raw_transaction = send_with_value
    server.RPC_METHODS["eth_sendRawTransaction"] = send_with_value


def main() -> int:
    _patch_runner_bundle_fallback()
    if sys.platform == "win32":
        _patch_windows_stdin_cleanup()
    _patch_contract_proxy()
    _patch_transaction_value()

    from glsim.__main__ import main as glsim_main

    return glsim_main() or 0


if __name__ == "__main__":
    raise SystemExit(main())
