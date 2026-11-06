"""Example manifests must stay valid against the deployed contract schema."""

import hashlib
import json
from pathlib import Path

import pytest


EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def read_example(name: str) -> str:
    return (EXAMPLES / name).read_text(encoding="utf-8")


@pytest.fixture
def contract(direct_deploy):
    return direct_deploy("contracts/Presense.py")


@pytest.mark.parametrize(
    ("name", "criteria"),
    [
        ("manifest.weather-api.json", 5),
        ("manifest.docs-delivery.json", 4),
    ],
)
def test_valid_examples_canonicalize_and_hash(contract, name, criteria):
    raw = read_example(name)

    result = contract.check_manifest(raw)

    assert result["criteria"] == criteria
    assert result["canonical"] == json.dumps(
        json.loads(raw),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    assert result["hash"] == hashlib.sha256(
        result["canonical"].encode("utf-8")
    ).hexdigest()


def test_bad_example_is_rejected_with_manifest_error(contract):
    with pytest.raises(Exception) as exc:
        contract.check_manifest(read_example("manifest.bad-example.json"))

    assert "E_MANIFEST_INVALID" in str(exc.value)
    assert "weights must sum to 100" in str(exc.value)
