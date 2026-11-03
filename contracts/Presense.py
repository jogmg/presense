# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from genlayer import *

import hashlib
import json
import re
import typing


MANIFEST_SCHEMA = "presense.manifest.v1"

MAX_MANIFEST_BYTES = 16_384
MAX_CRITERIA = 20
MAX_ARTIFACTS = 10
MAX_EVIDENCE_URLS = 5
MAX_NOTES_CHARS = 2_000
MAX_REASON_CHARS = 1_000
MIN_DEADLINE_SECONDS = 3_600
MIN_CHALLENGE_WINDOW = 3_600
MAX_CHALLENGE_WINDOW = 604_800
MAX_SOURCE_BYTES = 2_000_000
MAX_TOTAL_BYTES = 10_000_000
MAX_LLM_CHARS = 20_000
MAX_URL_CHARS = 2_048

_TOP_LEVEL_KEYS = (
    "schema",
    "version",
    "title",
    "description",
    "artifact",
    "criteria",
    "decision_policy",
    "evidence_policy",
    "metadata",
)
_CRITERION_KEYS = (
    "id",
    "title",
    "kind",
    "check",
    "weight",
    "mandatory",
    "params",
)
_DECISION_KEYS = (
    "accept_threshold",
    "partial_threshold",
    "mandatory_must_pass",
    "missing_evidence",
    "partial_payout",
    "score_rounding",
)
_EVIDENCE_KEYS = (
    "allowed_domains",
    "require_https",
    "max_bytes_per_source",
    "max_total_bytes",
    "max_sources_per_criterion",
    "allow_redirects",
    "max_redirects",
)
_CHECK_KIND = {
    "http_status": "objective",
    "json_has_keys": "objective",
    "file_hash": "objective",
    "text_contains": "objective",
    "llm_rubric": "subjective",
}
_JSON_TYPES = ("string", "number", "boolean", "object", "array", "null")


def _fail(code: str, message: str) -> typing.NoReturn:
    raise gl.vm.UserError(f"{code}: {message}")


def _reject_constant(value: str) -> typing.NoReturn:
    _fail("E_MANIFEST_INVALID", f"non-finite number '{value}' is not allowed")


def _object_pairs(pairs: list[tuple[str, typing.Any]]) -> dict[str, typing.Any]:
    obj: dict[str, typing.Any] = {}
    for key, value in pairs:
        if key in obj:
            _fail("E_MANIFEST_INVALID", f"duplicate key '{key}'")
        obj[key] = value
    return obj


def parse_manifest(raw: str) -> dict[str, typing.Any]:
    """Strictly parse and canonicalize a manifest.

    Rejects duplicate keys, NaN/Infinity, non-object roots, trailing content,
    invalid UTF-8, and inputs whose raw or canonical form exceeds 16 KiB.
    """
    if not isinstance(raw, str):
        _fail("E_MANIFEST_INVALID", "manifest must be a string")

    try:
        raw_bytes = raw.encode("utf-8")
    except UnicodeEncodeError:
        _fail("E_MANIFEST_INVALID", "manifest is not valid UTF-8")

    if len(raw_bytes) > MAX_MANIFEST_BYTES:
        _fail(
            "E_MANIFEST_TOO_LARGE",
            f"raw manifest is {len(raw_bytes)} bytes; limit is {MAX_MANIFEST_BYTES}",
        )

    try:
        data = json.loads(
            raw,
            object_pairs_hook=_object_pairs,
            parse_constant=_reject_constant,
        )
    except gl.vm.UserError:
        raise
    except (ValueError, TypeError, RecursionError):
        _fail("E_MANIFEST_INVALID", "manifest is not valid JSON")

    if not isinstance(data, dict):
        _fail("E_MANIFEST_INVALID", "manifest root must be an object")

    try:
        canonical = json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError):
        _fail("E_MANIFEST_INVALID", "manifest cannot be canonicalized")

    try:
        canonical_bytes = canonical.encode("utf-8")
    except UnicodeEncodeError:
        _fail("E_MANIFEST_INVALID", "canonical manifest is not valid UTF-8")

    if len(canonical_bytes) > MAX_MANIFEST_BYTES:
        _fail(
            "E_MANIFEST_TOO_LARGE",
            f"canonical manifest is {len(canonical_bytes)} bytes; "
            f"limit is {MAX_MANIFEST_BYTES}",
        )

    return {
        "data": data,
        "canonical": canonical,
        "hash": hashlib.sha256(canonical_bytes).hexdigest(),
    }


def _require_object(value: typing.Any, name: str) -> dict[str, typing.Any]:
    if not isinstance(value, dict):
        _fail("E_MANIFEST_INVALID", f"{name} must be an object")
    return value


def _require_keys(
    obj: dict[str, typing.Any], required: tuple[str, ...], name: str
) -> None:
    for key in required:
        if key not in obj:
            _fail("E_MANIFEST_INVALID", f"{name} is missing '{key}'")


def _reject_unknown_keys(
    obj: dict[str, typing.Any], allowed: tuple[str, ...], name: str
) -> None:
    for key in obj:
        if key not in allowed:
            _fail("E_MANIFEST_INVALID", f"{name} has unknown field '{key}'")


def _require_string(
    obj: dict[str, typing.Any],
    key: str,
    name: str,
    min_len: int = 1,
    max_len: int = 10_000,
) -> str:
    value = obj.get(key)
    if not isinstance(value, str):
        _fail("E_MANIFEST_INVALID", f"{name}.{key} must be a string")
    length = len(value)
    if length < min_len or length > max_len:
        _fail(
            "E_MANIFEST_INVALID",
            f"{name}.{key} must be {min_len}-{max_len} characters",
        )
    return value


def _require_int(
    obj: dict[str, typing.Any],
    key: str,
    name: str,
    min_value: int,
    max_value: int,
) -> int:
    value = obj.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        _fail("E_MANIFEST_INVALID", f"{name}.{key} must be an integer")
    if value < min_value or value > max_value:
        _fail(
            "E_MANIFEST_INVALID",
            f"{name}.{key} must be between {min_value} and {max_value}",
        )
    return value


def _optional_int(
    obj: dict[str, typing.Any],
    key: str,
    name: str,
    min_value: int,
    max_value: int,
    default: int,
) -> int:
    if key not in obj:
        return default
    return _require_int(obj, key, name, min_value, max_value)


def _require_bool(
    obj: dict[str, typing.Any], key: str, name: str, expected: bool
) -> bool:
    value = obj.get(key)
    if not isinstance(value, bool):
        _fail("E_MANIFEST_INVALID", f"{name}.{key} must be a boolean")
    if value is not expected:
        expected_text = "true" if expected else "false"
        _fail(
            "E_MANIFEST_INVALID",
            f"{name}.{key} must be {expected_text} in manifest v1",
        )
    return value


def _require_list(
    obj: dict[str, typing.Any],
    key: str,
    name: str,
    min_len: int,
    max_len: int,
) -> list[typing.Any]:
    value = obj.get(key)
    if not isinstance(value, list):
        _fail("E_MANIFEST_INVALID", f"{name}.{key} must be an array")
    if len(value) < min_len or len(value) > max_len:
        _fail(
            "E_MANIFEST_INVALID",
            f"{name}.{key} must contain {min_len}-{max_len} items",
        )
    return value


def _normalize_domain(value: typing.Any, name: str) -> str:
    if not isinstance(value, str):
        _fail("E_MANIFEST_INVALID", f"{name} must be a string")
    domain = value.lower().rstrip(".")
    if not domain:
        _fail("E_MANIFEST_INVALID", f"{name} must not be empty")
    if len(domain) > 253:
        _fail("E_MANIFEST_INVALID", f"{name} is too long")

    wildcard = domain.startswith("*.")
    base = domain[2:] if wildcard else domain
    if not base or "*" in base:
        _fail("E_MANIFEST_INVALID", f"{name} has an invalid wildcard")
    if "://" in base or "/" in base or " " in base:
        _fail("E_MANIFEST_INVALID", f"{name} must be a bare domain")

    label = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    if re.match(rf"^{label}(?:\.{label})+$", base) is None:
        _fail("E_MANIFEST_INVALID", f"{name} is not a valid domain")

    return ("*." if wildcard else "") + base


def _validate_decision_policy(
    value: typing.Any,
) -> dict[str, typing.Any]:
    policy = _require_object(value, "decision_policy")
    _require_keys(policy, _DECISION_KEYS, "decision_policy")
    _reject_unknown_keys(policy, _DECISION_KEYS, "decision_policy")

    accept = _require_int(policy, "accept_threshold", "decision_policy", 0, 100)
    partial = _require_int(policy, "partial_threshold", "decision_policy", 0, 100)
    if partial > accept:
        _fail(
            "E_MANIFEST_INVALID",
            "decision_policy.partial_threshold must not exceed accept_threshold",
        )

    _require_bool(policy, "mandatory_must_pass", "decision_policy", True)
    missing = _require_string(policy, "missing_evidence", "decision_policy", 1, 32)
    if missing not in ("UNDETERMINED", "REJECT"):
        _fail(
            "E_MANIFEST_INVALID",
            "decision_policy.missing_evidence must be UNDETERMINED or REJECT",
        )
    partial_payout = _require_string(
        policy, "partial_payout", "decision_policy", 1, 32
    )
    if partial_payout != "pro_rata":
        _fail(
            "E_MANIFEST_INVALID",
            "decision_policy.partial_payout must be pro_rata in manifest v1",
        )
    rounding = _require_string(policy, "score_rounding", "decision_policy", 1, 32)
    if rounding != "floor":
        _fail(
            "E_MANIFEST_INVALID",
            "decision_policy.score_rounding must be floor in manifest v1",
        )
    return policy


def _validate_evidence_policy(
    value: typing.Any,
) -> tuple[dict[str, typing.Any], list[str]]:
    policy = _require_object(value, "evidence_policy")
    _require_keys(policy, _EVIDENCE_KEYS, "evidence_policy")
    _reject_unknown_keys(policy, _EVIDENCE_KEYS, "evidence_policy")

    domains_raw = _require_list(policy, "allowed_domains", "evidence_policy", 1, 20)
    domains = []
    for index, domain in enumerate(domains_raw):
        domains.append(
            _normalize_domain(domain, f"evidence_policy.allowed_domains[{index}]")
        )

    _require_bool(policy, "require_https", "evidence_policy", True)
    _require_int(
        policy, "max_bytes_per_source", "evidence_policy", 1_000, 5_000_000
    )
    _require_int(policy, "max_total_bytes", "evidence_policy", 1_000, 20_000_000)
    _require_int(policy, "max_sources_per_criterion", "evidence_policy", 1, 5)
    _require_bool(policy, "allow_redirects", "evidence_policy", True)
    _require_int(policy, "max_redirects", "evidence_policy", 0, 3)
    return policy, domains


def _url_host(url: typing.Any, name: str) -> str:
    if not isinstance(url, str):
        _fail("E_URL_INVALID", f"{name} must be a string")
    if len(url) > MAX_URL_CHARS:
        _fail("E_URL_INVALID", f"{name} exceeds {MAX_URL_CHARS} characters")
    if re.search(r"\s", url) is not None:
        _fail("E_URL_INVALID", f"{name} contains whitespace")
    if not url.lower().startswith("https://"):
        _fail("E_URL_INVALID", f"{name} must use HTTPS")

    authority = re.split(r"[/?#]", url[len("https://") :], maxsplit=1)[0]
    if not authority:
        _fail("E_URL_INVALID", f"{name} has no host")
    if "@" in authority:
        _fail("E_URL_INVALID", f"{name} must not contain credentials")

    if authority.startswith("["):
        end = authority.find("]")
        if end < 0:
            _fail("E_URL_INVALID", f"{name} has an invalid IPv6 host")
        host = authority[1:end]
        tail = authority[end + 1 :]
        if tail and not tail.startswith(":"):
            _fail("E_URL_INVALID", f"{name} has an invalid host")
    else:
        host = authority.split(":", 1)[0]

    host = host.lower().rstrip(".")
    if not host:
        _fail("E_URL_INVALID", f"{name} has no host")
    return host


def _reject_private_host(host: str, name: str) -> None:
    if host in (
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "::1",
        "::",
        "0:0:0:0:0:0:0:1",
    ):
        _fail("E_URL_INVALID", f"{name} points at a loopback or unspecified host")
    if host.endswith(".localhost"):
        _fail("E_URL_INVALID", f"{name} points at localhost")

    ipv4 = re.match(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$", host)
    if ipv4 is not None:
        octets = [int(part) for part in ipv4.groups()]
        if any(octet > 255 for octet in octets):
            _fail("E_URL_INVALID", f"{name} has an invalid IPv4 host")
        first, second = octets[0], octets[1]
        if first == 10:
            _fail("E_URL_INVALID", f"{name} points at a private IPv4 address")
        if first == 127:
            _fail("E_URL_INVALID", f"{name} points at a loopback IPv4 address")
        if first == 172 and 16 <= second <= 31:
            _fail("E_URL_INVALID", f"{name} points at a private IPv4 address")
        if first == 192 and second == 168:
            _fail("E_URL_INVALID", f"{name} points at a private IPv4 address")
        return

    if ":" in host:
        return

    label = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    if re.match(rf"^{label}(?:\.{label})+$", host) is None:
        _fail("E_URL_INVALID", f"{name} has an invalid host")


def _host_matches(host: str, allowed_domains: list[str]) -> bool:
    for domain in allowed_domains:
        if domain.startswith("*."):
            suffix = domain[2:]
            if host.endswith("." + suffix) and host != suffix:
                return True
        elif host == domain or host.endswith("." + domain):
            return True
    return False


def _validate_url(url: typing.Any, allowed_domains: list[str], name: str) -> str:
    host = _url_host(url, name)
    _reject_private_host(host, name)
    if not _host_matches(host, allowed_domains):
        _fail("E_EVIDENCE_DOMAIN", f"{name} host '{host}' is not allowed")
    return url


def _valid_dot_path(value: typing.Any, name: str) -> str:
    if not isinstance(value, str):
        _fail("E_MANIFEST_INVALID", f"{name} must be a string")
    if len(value) < 1 or len(value) > 512:
        _fail("E_MANIFEST_INVALID", f"{name} must be 1-512 characters")
    if re.search(r"\s", value) is not None:
        _fail("E_MANIFEST_INVALID", f"{name} must not contain whitespace")
    if any(part == "" for part in value.split(".")):
        _fail("E_MANIFEST_INVALID", f"{name} has an empty path segment")
    if "[" in value or "]" in value:
        segment = r"[^\[\]]+(?:\[\d+\])?"
        if re.match(rf"^{segment}(?:\.{segment})*$", value) is None:
            _fail("E_MANIFEST_INVALID", f"{name} has an invalid array index")
    return value


def _validate_params(
    check: str,
    params: dict[str, typing.Any],
    allowed_domains: list[str],
    name: str,
) -> None:
    if check == "http_status":
        allowed = ("url", "expected_status", "method")
        _require_keys(params, ("url", "expected_status"), name)
        _reject_unknown_keys(params, allowed, name)
        _validate_url(params.get("url"), allowed_domains, f"{name}.url")

        expected = params.get("expected_status")
        if isinstance(expected, list):
            if len(expected) < 1 or len(expected) > 100:
                _fail(
                    "E_MANIFEST_INVALID",
                    f"{name}.expected_status must contain 1-100 statuses",
                )
            for status in expected:
                if isinstance(status, bool) or not isinstance(status, int):
                    _fail(
                        "E_MANIFEST_INVALID",
                        f"{name}.expected_status must contain integers",
                    )
                if status < 100 or status > 599:
                    _fail(
                        "E_MANIFEST_INVALID",
                        f"{name}.expected_status values must be 100-599",
                    )
        elif isinstance(expected, bool) or not isinstance(expected, int):
            _fail(
                "E_MANIFEST_INVALID",
                f"{name}.expected_status must be an integer or array",
            )
        elif expected < 100 or expected > 599:
            _fail(
                "E_MANIFEST_INVALID",
                f"{name}.expected_status must be 100-599",
            )

        method = params.get("method", "GET")
        if not isinstance(method, str) or method not in ("GET", "HEAD"):
            _fail("E_MANIFEST_INVALID", f"{name}.method must be GET or HEAD")

    elif check == "json_has_keys":
        allowed = ("url", "required_keys", "types")
        _require_keys(params, ("url", "required_keys"), name)
        _reject_unknown_keys(params, allowed, name)
        _validate_url(params.get("url"), allowed_domains, f"{name}.url")

        required_keys = _require_list(params, "required_keys", name, 1, 50)
        for index, key in enumerate(required_keys):
            _valid_dot_path(key, f"{name}.required_keys[{index}]")

        if "types" in params:
            types = _require_object(params["types"], f"{name}.types")
            for key, value in types.items():
                _valid_dot_path(key, f"{name}.types key")
                if not isinstance(value, str) or value not in _JSON_TYPES:
                    _fail(
                        "E_MANIFEST_INVALID",
                        f"{name}.types[{key}] has an unsupported type",
                    )

    elif check == "file_hash":
        allowed = ("url", "sha256")
        _require_keys(params, allowed, name)
        _reject_unknown_keys(params, allowed, name)
        _validate_url(params.get("url"), allowed_domains, f"{name}.url")
        digest = params.get("sha256")
        if not isinstance(digest, str) or re.match(r"^[0-9a-fA-F]{64}$", digest) is None:
            _fail("E_MANIFEST_INVALID", f"{name}.sha256 must be 64 hex characters")

    elif check == "text_contains":
        allowed = ("url", "phrases", "case_sensitive")
        _require_keys(params, ("url", "phrases"), name)
        _reject_unknown_keys(params, allowed, name)
        _validate_url(params.get("url"), allowed_domains, f"{name}.url")

        phrases = _require_list(params, "phrases", name, 1, 20)
        for index, phrase in enumerate(phrases):
            if not isinstance(phrase, str):
                _fail(
                    "E_MANIFEST_INVALID",
                    f"{name}.phrases[{index}] must be a string",
                )
            if not phrase.strip() or len(phrase) > 200:
                _fail(
                    "E_MANIFEST_INVALID",
                    f"{name}.phrases[{index}] must be 1-200 non-empty characters",
                )
        if "case_sensitive" in params and not isinstance(
            params["case_sensitive"], bool
        ):
            _fail("E_MANIFEST_INVALID", f"{name}.case_sensitive must be a boolean")

    elif check == "llm_rubric":
        allowed = ("evidence_url", "rubric", "threshold", "max_chars")
        _require_keys(params, ("evidence_url", "rubric", "threshold"), name)
        _reject_unknown_keys(params, allowed, name)
        _validate_url(
            params.get("evidence_url"), allowed_domains, f"{name}.evidence_url"
        )
        _require_string(params, "rubric", name, 20, 4_000)
        _require_int(params, "threshold", name, 0, 10)
        _optional_int(params, "max_chars", name, 1_000, 50_000, MAX_LLM_CHARS)

    else:
        _fail("E_MANIFEST_INVALID", f"unsupported check '{check}'")


def validate_manifest(parsed: dict[str, typing.Any]) -> None:
    """Validate the schema and semantics of a parsed manifest."""
    data = _require_object(parsed.get("data"), "manifest")
    _require_keys(
        data,
        (
            "schema",
            "version",
            "title",
            "description",
            "criteria",
            "decision_policy",
            "evidence_policy",
        ),
        "manifest",
    )
    _reject_unknown_keys(data, _TOP_LEVEL_KEYS, "manifest")

    schema = _require_string(data, "schema", "manifest", 1, 64)
    if schema != MANIFEST_SCHEMA:
        _fail(
            "E_MANIFEST_INVALID",
            f"manifest.schema must be '{MANIFEST_SCHEMA}'",
        )
    _require_int(data, "version", "manifest", 1, 1)
    _require_string(data, "title", "manifest", 1, 200)
    _require_string(data, "description", "manifest", 1, 2_000)

    if "artifact" in data:
        _require_object(data["artifact"], "manifest.artifact")
    if "metadata" in data:
        _require_object(data["metadata"], "manifest.metadata")

    _validate_decision_policy(data.get("decision_policy"))
    _, allowed_domains = _validate_evidence_policy(data.get("evidence_policy"))

    criteria = _require_list(data, "criteria", "manifest", 1, MAX_CRITERIA)
    seen_ids: list[str] = []
    total_weight = 0

    for index, criterion_value in enumerate(criteria):
        name = f"criteria[{index}]"
        criterion = _require_object(criterion_value, name)
        _require_keys(criterion, _CRITERION_KEYS, name)
        _reject_unknown_keys(criterion, _CRITERION_KEYS, name)

        criterion_id = _require_string(criterion, "id", name, 1, 32)
        if re.match(r"^[A-Za-z0-9_-]+$", criterion_id) is None:
            _fail(
                "E_MANIFEST_INVALID",
                f"{name}.id must match [A-Za-z0-9_-]+",
            )
        if criterion_id in seen_ids:
            _fail("E_MANIFEST_INVALID", f"duplicate criterion id '{criterion_id}'")
        seen_ids.append(criterion_id)

        _require_string(criterion, "title", name, 1, 200)
        kind = _require_string(criterion, "kind", name, 1, 32)
        if kind not in ("objective", "subjective"):
            _fail(
                "E_MANIFEST_INVALID",
                f"{name}.kind must be objective or subjective",
            )

        check = _require_string(criterion, "check", name, 1, 64)
        if check not in _CHECK_KIND:
            _fail("E_MANIFEST_INVALID", f"{name}.check '{check}' is not supported")
        if _CHECK_KIND[check] != kind:
            _fail(
                "E_MANIFEST_INVALID",
                f"{name}.check '{check}' requires kind '{_CHECK_KIND[check]}'",
            )

        weight = _require_int(criterion, "weight", name, 1, 100)
        total_weight += weight

        mandatory = criterion.get("mandatory")
        if not isinstance(mandatory, bool):
            _fail("E_MANIFEST_INVALID", f"{name}.mandatory must be a boolean")

        params = _require_object(criterion.get("params"), f"{name}.params")
        _validate_params(check, params, allowed_domains, f"{name}.params")

    if total_weight != 100:
        _fail(
            "E_MANIFEST_INVALID",
            f"criteria weights must sum to 100, got {total_weight}",
        )


class Presense(gl.Contract):
    """Acceptance adjudication primitive.

    Phase 1: strict manifest parsing, canonicalization, hashing, and schema
    validation. Lifecycle and consensus logic arrive in later phases.
    """

    version: str

    def __init__(self) -> None:
        self.version = "0.1.0"

    @gl.public.view
    def get_version(self) -> str:
        return self.version

    @gl.public.view
    def check_manifest(self, manifest_json: str) -> typing.Any:
        """Validate a manifest and return its canonical form and SHA-256."""
        parsed = parse_manifest(manifest_json)
        validate_manifest(parsed)
        return {
            "canonical": parsed["canonical"],
            "hash": parsed["hash"],
            "criteria": len(parsed["data"]["criteria"]),
        }

    @gl.public.view
    def get_constants(self) -> typing.Any:
        return {
            "version": self.version,
            "manifest_schema": MANIFEST_SCHEMA,
            "MAX_MANIFEST_BYTES": MAX_MANIFEST_BYTES,
            "MAX_CRITERIA": MAX_CRITERIA,
            "MAX_ARTIFACTS": MAX_ARTIFACTS,
            "MAX_EVIDENCE_URLS": MAX_EVIDENCE_URLS,
            "MAX_NOTES_CHARS": MAX_NOTES_CHARS,
            "MAX_REASON_CHARS": MAX_REASON_CHARS,
            "MIN_DEADLINE_SECONDS": MIN_DEADLINE_SECONDS,
            "MIN_CHALLENGE_WINDOW": MIN_CHALLENGE_WINDOW,
            "MAX_CHALLENGE_WINDOW": MAX_CHALLENGE_WINDOW,
            "MAX_SOURCE_BYTES": MAX_SOURCE_BYTES,
            "MAX_TOTAL_BYTES": MAX_TOTAL_BYTES,
            "MAX_LLM_CHARS": MAX_LLM_CHARS,
            "MAX_URL_CHARS": MAX_URL_CHARS,
        }
