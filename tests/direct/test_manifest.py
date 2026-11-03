"""Phase 1: strict manifest parsing, canonicalization, and validation."""

import hashlib
import json

import pytest


def manifest_dict() -> dict:
    return {
        "schema": "presense.manifest.v1",
        "version": 1,
        "title": "Test delivery",
        "description": "A test acceptance manifest.",
        "criteria": [
            {
                "id": "C1",
                "title": "Health endpoint",
                "kind": "objective",
                "check": "http_status",
                "weight": 50,
                "mandatory": True,
                "params": {
                    "url": "https://api.example.com/health",
                    "expected_status": 200,
                },
            },
            {
                "id": "C2",
                "title": "Docs quality",
                "kind": "subjective",
                "check": "llm_rubric",
                "weight": 50,
                "mandatory": True,
                "params": {
                    "evidence_url": "https://docs.example.com",
                    "rubric": "Docs explain authentication and errors.",
                    "threshold": 7,
                },
            },
        ],
        "decision_policy": {
            "accept_threshold": 80,
            "partial_threshold": 50,
            "mandatory_must_pass": True,
            "missing_evidence": "UNDETERMINED",
            "partial_payout": "pro_rata",
            "score_rounding": "floor",
        },
        "evidence_policy": {
            "allowed_domains": ["api.example.com", "docs.example.com"],
            "require_https": True,
            "max_bytes_per_source": 2_000_000,
            "max_total_bytes": 10_000_000,
            "max_sources_per_criterion": 5,
            "allow_redirects": True,
            "max_redirects": 3,
        },
    }


def make_manifest(**overrides) -> str:
    manifest = manifest_dict()
    manifest.update(overrides)
    return json.dumps(manifest)


@pytest.fixture
def presense(direct_deploy):
    return direct_deploy("contracts/Presense.py")


def expect_error(presense, raw: str, code: str) -> None:
    with pytest.raises(Exception) as exc:
        presense.check_manifest(raw)
    message = str(exc.value)
    assert code in message, message


def expect_manifest_error(presense, mutate, code: str) -> None:
    manifest = manifest_dict()
    mutate(manifest)
    expect_error(presense, json.dumps(manifest), code)


def test_manifest_accepts_valid(presense):
    raw = make_manifest()
    result = presense.check_manifest(raw)
    canonical = json.dumps(
        json.loads(raw),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    assert result["canonical"] == canonical
    assert result["hash"] == hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    assert result["criteria"] == 2


def test_manifest_accepts_all_supported_checks(presense):
    manifest = manifest_dict()
    manifest["criteria"] = [
        {
            "id": "C1",
            "title": "HTTP status",
            "kind": "objective",
            "check": "http_status",
            "weight": 20,
            "mandatory": True,
            "params": {
                "url": "https://api.example.com/health",
                "expected_status": [200, 204],
                "method": "HEAD",
            },
        },
        {
            "id": "C2",
            "title": "JSON keys",
            "kind": "objective",
            "check": "json_has_keys",
            "weight": 20,
            "mandatory": True,
            "params": {
                "url": "https://api.example.com/openapi.json",
                "required_keys": ["openapi", "info.title", "paths"],
                "types": {"openapi": "string", "paths": "object"},
            },
        },
        {
            "id": "C3",
            "title": "Pinned file",
            "kind": "objective",
            "check": "file_hash",
            "weight": 20,
            "mandatory": False,
            "params": {
                "url": "https://api.example.com/openapi.json",
                "sha256": "a" * 64,
            },
        },
        {
            "id": "C4",
            "title": "Docs phrases",
            "kind": "objective",
            "check": "text_contains",
            "weight": 20,
            "mandatory": True,
            "params": {
                "url": "https://docs.example.com",
                "phrases": ["authentication", "rate limit"],
                "case_sensitive": False,
            },
        },
        {
            "id": "C5",
            "title": "Docs quality",
            "kind": "subjective",
            "check": "llm_rubric",
            "weight": 20,
            "mandatory": True,
            "params": {
                "evidence_url": "https://docs.example.com",
                "rubric": "Docs explain authentication and errors.",
                "threshold": 7,
                "max_chars": 20_000,
            },
        },
    ]

    assert presense.check_manifest(json.dumps(manifest))["criteria"] == 5


def test_manifest_canonicalization_is_stable(presense):
    manifest = manifest_dict()
    raw_a = json.dumps(manifest, sort_keys=False)
    raw_b = json.dumps(manifest, sort_keys=True)

    result_a = presense.check_manifest(raw_a)
    result_b = presense.check_manifest(raw_b)

    assert raw_a != raw_b
    assert result_a["canonical"] == result_b["canonical"]
    assert result_a["hash"] == result_b["hash"]


def test_manifest_preserves_unicode(presense):
    manifest = manifest_dict()
    manifest["title"] = "Livraison — café ✅"

    result = presense.check_manifest(json.dumps(manifest))

    assert "café" in result["canonical"]
    assert "\\u" not in result["canonical"]


def test_manifest_rejects_duplicate_keys(presense):
    expect_error(presense, '{"a":1,"a":2}', "E_MANIFEST_INVALID")


def test_manifest_rejects_nested_duplicate_keys(presense):
    raw = '{"outer":{"x":1,"x":2}}'
    expect_error(presense, raw, "E_MANIFEST_INVALID")


def test_manifest_rejects_nan(presense):
    expect_error(presense, '{"x": NaN}', "E_MANIFEST_INVALID")


def test_manifest_rejects_infinity(presense):
    expect_error(presense, '{"x": Infinity}', "E_MANIFEST_INVALID")


def test_manifest_rejects_non_object(presense):
    expect_error(presense, "[]", "E_MANIFEST_INVALID")


def test_manifest_rejects_trailing_content(presense):
    expect_error(presense, make_manifest() + " garbage", "E_MANIFEST_INVALID")


def test_manifest_rejects_oversize(presense):
    raw = '{"x":"' + ("a" * 17_000) + '"}'
    expect_error(presense, raw, "E_MANIFEST_TOO_LARGE")


def test_manifest_rejects_bad_schema(presense):
    expect_error(presense, make_manifest(schema="presense.manifest.v2"), "E_MANIFEST_INVALID")


def test_manifest_rejects_unknown_top_level_field(presense):
    expect_error(presense, make_manifest(extra=1), "E_MANIFEST_INVALID")


def test_manifest_rejects_zero_criteria(presense):
    expect_error(presense, make_manifest(criteria=[]), "E_MANIFEST_INVALID")


def test_manifest_rejects_too_many_criteria(presense):
    manifest = manifest_dict()
    template = manifest["criteria"][0]
    manifest["criteria"] = []
    for index in range(21):
        criterion = json.loads(json.dumps(template))
        criterion["id"] = f"C{index}"
        criterion["weight"] = 5
        manifest["criteria"].append(criterion)

    expect_error(presense, json.dumps(manifest), "E_MANIFEST_INVALID")


def test_manifest_rejects_duplicate_ids(presense):
    manifest = manifest_dict()
    manifest["criteria"][1]["id"] = "C1"

    expect_error(presense, json.dumps(manifest), "E_MANIFEST_INVALID")


def test_manifest_rejects_bad_weights(presense):
    manifest = manifest_dict()
    manifest["criteria"][0]["weight"] = 49

    expect_error(presense, json.dumps(manifest), "E_MANIFEST_INVALID")


def test_manifest_rejects_unknown_check(presense):
    manifest = manifest_dict()
    manifest["criteria"][0]["check"] = "magic"

    expect_error(presense, json.dumps(manifest), "E_MANIFEST_INVALID")


def test_manifest_rejects_bad_thresholds(presense):
    manifest = manifest_dict()
    manifest["decision_policy"]["partial_threshold"] = 90

    expect_error(presense, json.dumps(manifest), "E_MANIFEST_INVALID")


def test_manifest_rejects_bad_mandatory_policy(presense):
    manifest = manifest_dict()
    manifest["decision_policy"]["mandatory_must_pass"] = False

    expect_error(presense, json.dumps(manifest), "E_MANIFEST_INVALID")


def test_manifest_rejects_http(presense):
    manifest = manifest_dict()
    manifest["criteria"][0]["params"]["url"] = "http://api.example.com/health"

    expect_error(presense, json.dumps(manifest), "E_URL_INVALID")


def test_manifest_rejects_private_ip(presense):
    manifest = manifest_dict()
    manifest["criteria"][0]["params"]["url"] = "https://127.0.0.1/health"

    expect_error(presense, json.dumps(manifest), "E_URL_INVALID")


def test_manifest_rejects_url_credentials(presense):
    manifest = manifest_dict()
    manifest["criteria"][0]["params"]["url"] = (
        "https://user:pass@api.example.com/health"
    )

    expect_error(presense, json.dumps(manifest), "E_URL_INVALID")


def test_manifest_rejects_disallowed_domain(presense):
    manifest = manifest_dict()
    manifest["criteria"][0]["params"]["url"] = "https://evil.example/health"

    expect_error(presense, json.dumps(manifest), "E_EVIDENCE_DOMAIN")


def test_manifest_accepts_wildcard_domain(presense):
    manifest = manifest_dict()
    manifest["evidence_policy"]["allowed_domains"] = ["*.example.com"]

    assert presense.check_manifest(json.dumps(manifest))["criteria"] == 2


def test_manifest_wildcard_does_not_match_bare_domain(presense):
    manifest = manifest_dict()
    manifest["evidence_policy"]["allowed_domains"] = ["*.example.com"]
    manifest["criteria"][0]["params"]["url"] = "https://example.com/health"

    expect_error(presense, json.dumps(manifest), "E_EVIDENCE_DOMAIN")


def test_manifest_rejects_bad_file_hash(presense):
    manifest = manifest_dict()
    manifest["criteria"][0] = {
        "id": "C1",
        "title": "Pinned file",
        "kind": "objective",
        "check": "file_hash",
        "weight": 50,
        "mandatory": True,
        "params": {
            "url": "https://api.example.com/openapi.json",
            "sha256": "zz",
        },
    }

    expect_error(presense, json.dumps(manifest), "E_MANIFEST_INVALID")


def test_manifest_rejects_bad_text_phrases(presense):
    manifest = manifest_dict()
    manifest["criteria"][0] = {
        "id": "C1",
        "title": "Docs phrases",
        "kind": "objective",
        "check": "text_contains",
        "weight": 50,
        "mandatory": True,
        "params": {
            "url": "https://docs.example.com",
            "phrases": [""],
        },
    }

    expect_error(presense, json.dumps(manifest), "E_MANIFEST_INVALID")


def test_manifest_rejects_short_rubric(presense):
    manifest = manifest_dict()
    manifest["criteria"][1]["params"]["rubric"] = "too short"

    expect_error(presense, json.dumps(manifest), "E_MANIFEST_INVALID")


def test_manifest_rejects_empty_description(presense):
    expect_error(presense, make_manifest(description=""), "E_MANIFEST_INVALID")


def test_manifest_rejects_missing_field(presense):
    manifest = manifest_dict()
    del manifest["decision_policy"]

    expect_error(presense, json.dumps(manifest), "E_MANIFEST_INVALID")


def test_manifest_rejects_kind_check_mismatch(presense):
    manifest = manifest_dict()
    manifest["criteria"][0]["kind"] = "subjective"

    expect_error(presense, json.dumps(manifest), "E_MANIFEST_INVALID")


def test_manifest_rejects_zero_weight(presense):
    manifest = manifest_dict()
    manifest["criteria"][0]["weight"] = 0

    expect_error(presense, json.dumps(manifest), "E_MANIFEST_INVALID")


def test_manifest_rejects_bad_http_method(presense):
    manifest = manifest_dict()
    manifest["criteria"][0]["params"]["method"] = "POST"

    expect_error(presense, json.dumps(manifest), "E_MANIFEST_INVALID")


def test_manifest_rejects_bad_expected_status(presense):
    manifest = manifest_dict()
    manifest["criteria"][0]["params"]["expected_status"] = 700

    expect_error(presense, json.dumps(manifest), "E_MANIFEST_INVALID")


def test_manifest_rejects_bad_json_type(presense):
    manifest = manifest_dict()
    manifest["criteria"][0] = {
        "id": "C1",
        "title": "JSON keys",
        "kind": "objective",
        "check": "json_has_keys",
        "weight": 50,
        "mandatory": True,
        "params": {
            "url": "https://api.example.com/openapi.json",
            "required_keys": ["openapi"],
            "types": {"openapi": "integer"},
        },
    }

    expect_error(presense, json.dumps(manifest), "E_MANIFEST_INVALID")


def test_manifest_rejects_bad_text_case_flag(presense):
    manifest = manifest_dict()
    manifest["criteria"][0] = {
        "id": "C1",
        "title": "Docs phrases",
        "kind": "objective",
        "check": "text_contains",
        "weight": 50,
        "mandatory": True,
        "params": {
            "url": "https://docs.example.com",
            "phrases": ["authentication"],
            "case_sensitive": "no",
        },
    }

    expect_error(presense, json.dumps(manifest), "E_MANIFEST_INVALID")


def test_manifest_rejects_bad_rubric_threshold(presense):
    manifest = manifest_dict()
    manifest["criteria"][1]["params"]["threshold"] = 11

    expect_error(presense, json.dumps(manifest), "E_MANIFEST_INVALID")


def test_manifest_rejects_bad_max_chars(presense):
    manifest = manifest_dict()
    manifest["criteria"][1]["params"]["max_chars"] = 10

    expect_error(presense, json.dumps(manifest), "E_MANIFEST_INVALID")


def test_manifest_rejects_disabled_https(presense):
    manifest = manifest_dict()
    manifest["evidence_policy"]["require_https"] = False

    expect_error(presense, json.dumps(manifest), "E_MANIFEST_INVALID")


def test_manifest_rejects_bad_redirect_limit(presense):
    manifest = manifest_dict()
    manifest["evidence_policy"]["max_redirects"] = 4

    expect_error(presense, json.dumps(manifest), "E_MANIFEST_INVALID")


def test_manifest_rejects_bad_rounding(presense):
    manifest = manifest_dict()
    manifest["decision_policy"]["score_rounding"] = "ceil"

    expect_error(presense, json.dumps(manifest), "E_MANIFEST_INVALID")


def test_manifest_rejects_bad_allowed_domain(presense):
    manifest = manifest_dict()
    manifest["evidence_policy"]["allowed_domains"] = ["https://api.example.com"]

    expect_error(presense, json.dumps(manifest), "E_MANIFEST_INVALID")


@pytest.mark.parametrize(
    "url",
    [
        "https://10.0.0.1/health",
        "https://172.16.0.1/health",
        "https://172.31.255.255/health",
        "https://192.168.1.1/health",
        "https://localhost/health",
        "https://0.0.0.0/health",
    ],
)
def test_manifest_rejects_private_hosts(presense, url):
    manifest = manifest_dict()
    manifest["criteria"][0]["params"]["url"] = url

    expect_error(presense, json.dumps(manifest), "E_URL_INVALID")


def test_manifest_rejects_oversize_url(presense):
    manifest = manifest_dict()
    manifest["criteria"][0]["params"]["url"] = (
        "https://api.example.com/" + ("a" * 2_100)
    )

    expect_error(presense, json.dumps(manifest), "E_URL_INVALID")


def test_manifest_accepts_case_and_trailing_dot(presense):
    manifest = manifest_dict()
    manifest["criteria"][0]["params"]["url"] = "https://API.EXAMPLE.COM./health"

    assert presense.check_manifest(json.dumps(manifest))["criteria"] == 2


def test_get_constants(presense):
    constants = presense.get_constants()

    assert constants["version"] == "0.1.0"
    assert constants["manifest_schema"] == "presense.manifest.v1"
    assert constants["MAX_MANIFEST_BYTES"] == 16_384
    assert constants["MAX_CRITERIA"] == 20


def test_manifest_rejects_lone_surrogate(presense):
    expect_error(presense, '{"x":"\\ud800"}', "E_MANIFEST_INVALID")


def test_manifest_rejects_non_object_artifact(presense):
    expect_manifest_error(
        presense, lambda m: m.__setitem__("artifact", []), "E_MANIFEST_INVALID"
    )


def test_manifest_rejects_non_object_metadata(presense):
    expect_manifest_error(
        presense, lambda m: m.__setitem__("metadata", "x"), "E_MANIFEST_INVALID"
    )


def test_manifest_rejects_non_string_title(presense):
    expect_manifest_error(
        presense, lambda m: m.__setitem__("title", 5), "E_MANIFEST_INVALID"
    )


def test_manifest_rejects_non_integer_version(presense):
    expect_manifest_error(
        presense, lambda m: m.__setitem__("version", "1"), "E_MANIFEST_INVALID"
    )


def test_manifest_rejects_non_array_criteria(presense):
    expect_manifest_error(
        presense, lambda m: m.__setitem__("criteria", "x"), "E_MANIFEST_INVALID"
    )


def test_manifest_rejects_non_boolean_mandatory(presense):
    expect_manifest_error(
        presense,
        lambda m: m["criteria"][0].__setitem__("mandatory", "yes"),
        "E_MANIFEST_INVALID",
    )


def test_manifest_rejects_bad_criterion_id(presense):
    expect_manifest_error(
        presense,
        lambda m: m["criteria"][0].__setitem__("id", "C 1"),
        "E_MANIFEST_INVALID",
    )


def test_manifest_rejects_bad_kind(presense):
    expect_manifest_error(
        presense,
        lambda m: m["criteria"][0].__setitem__("kind", "binary"),
        "E_MANIFEST_INVALID",
    )


def test_manifest_rejects_nonexistent_check(presense):
    expect_manifest_error(
        presense,
        lambda m: m["criteria"][0].__setitem__("check", "magic"),
        "E_MANIFEST_INVALID",
    )


def test_manifest_rejects_bad_missing_evidence_policy(presense):
    expect_manifest_error(
        presense,
        lambda m: m["decision_policy"].__setitem__("missing_evidence", "GUESS"),
        "E_MANIFEST_INVALID",
    )


def test_manifest_rejects_bad_partial_payout(presense):
    expect_manifest_error(
        presense,
        lambda m: m["decision_policy"].__setitem__("partial_payout", "half"),
        "E_MANIFEST_INVALID",
    )


@pytest.mark.parametrize(
    "domain",
    [
        5,
        "",
        "a" * 254,
        "*.",
        "*.*.example.com",
        "https://api.example.com",
        "bad_domain",
    ],
)
def test_manifest_rejects_bad_allowed_domains(presense, domain):
    expect_manifest_error(
        presense,
        lambda m: m["evidence_policy"].__setitem__("allowed_domains", [domain]),
        "E_MANIFEST_INVALID",
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://",
        "https:///path",
        "https://[::1",
        "https://[::1]x",
        "https://api.example.com/with space",
        "ftp://api.example.com",
        "https://api_example.com/health",
    ],
)
def test_manifest_rejects_malformed_urls(presense, url):
    expect_manifest_error(
        presense,
        lambda m: m["criteria"][0]["params"].__setitem__("url", url),
        "E_URL_INVALID",
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://sub.localhost/health",
        "https://256.1.1.1/health",
        "https://127.0.0.2/health",
    ],
)
def test_manifest_rejects_more_private_hosts(presense, url):
    expect_manifest_error(
        presense,
        lambda m: m["criteria"][0]["params"].__setitem__("url", url),
        "E_URL_INVALID",
    )


def test_manifest_accepts_public_ip(presense):
    manifest = manifest_dict()
    manifest["evidence_policy"]["allowed_domains"] = [
        "8.8.8.8",
        "docs.example.com",
    ]
    manifest["criteria"][0]["params"]["url"] = "https://8.8.8.8/health"

    assert presense.check_manifest(json.dumps(manifest))["criteria"] == 2


@pytest.mark.parametrize(
    "keys",
    [
        [5],
        [""],
        ["a b"],
        ["a..b"],
        ["a[bad]"],
        ["a" * 513],
    ],
)
def test_manifest_rejects_bad_dot_paths(presense, keys):
    expect_manifest_error(
        presense,
        lambda m: m["criteria"].__setitem__(
            0,
            {
                "id": "C1",
                "title": "JSON keys",
                "kind": "objective",
                "check": "json_has_keys",
                "weight": 50,
                "mandatory": True,
                "params": {
                    "url": "https://api.example.com/openapi.json",
                    "required_keys": keys,
                },
            },
        ),
        "E_MANIFEST_INVALID",
    )


def test_manifest_rejects_bad_types_key(presense):
    expect_manifest_error(
        presense,
        lambda m: m["criteria"][0]["params"].__setitem__(
            "types", {"a..b": "string"}
        ),
        "E_MANIFEST_INVALID",
    )


@pytest.mark.parametrize(
    "expected",
    [
        [],
        [200, "201"],
        [700],
        "200",
        True,
    ],
)
def test_manifest_rejects_bad_expected_statuses(presense, expected):
    manifest = manifest_dict()
    manifest["criteria"][0] = {
        "id": "C1",
        "title": "HTTP status",
        "kind": "objective",
        "check": "http_status",
        "weight": 50,
        "mandatory": True,
        "params": {
            "url": "https://api.example.com/health",
            "expected_status": expected,
        },
    }

    expect_error(presense, json.dumps(manifest), "E_MANIFEST_INVALID")
