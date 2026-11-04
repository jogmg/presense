# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from genlayer import *

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
import typing
from urllib.parse import urljoin


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


@gl.evm.contract_interface
class _Recipient:
    class View:
        pass

    class Write:
        pass


@allow_storage
@dataclass
class Agreement:
    id: str
    buyer: Address
    seller: Address
    manifest_json: str
    manifest_hash: str
    manifest_url: str
    metadata_url: str
    escrow: u256
    deadline: u256
    challenge_window: u256
    created_at: u256
    status: str
    submission_id: str
    verdict_id: str
    challenge_id: str
    challenge_count: u8
    evaluated_at: u256


@allow_storage
@dataclass
class Submission:
    id: str
    agreement_id: str
    artifact_urls: DynArray[str]
    artifact_hashes: DynArray[str]
    notes: str
    submitted_at: u256
    submitter: Address


def _fail(code: str, message: str) -> typing.NoReturn:
    raise gl.vm.UserError(f"{code}: {message}")


def _as_address(value: typing.Any) -> Address:
    if isinstance(value, Address):
        return value
    return Address(value)


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


def _response_header(headers: dict[str, typing.Any], name: str) -> typing.Any:
    target = name.lower()
    for key, value in headers.items():
        if isinstance(key, str) and key.lower() == target:
            if isinstance(value, bytes):
                try:
                    return value.decode("ascii")
                except UnicodeDecodeError:
                    return None
            return value
    return None


def _missing_fetch(
    reason: str,
    url: str,
    bytes_fetched: int = 0,
    budget: dict[str, int] | None = None,
    bytes_used: int = 0,
    additional_bytes: int = 0,
) -> dict[str, typing.Any]:
    if budget is not None:
        budget["bytes_used"] = bytes_used + bytes_fetched + additional_bytes
    return {
        "status": "MISSING",
        "http_status": 0,
        "body": b"",
        "url": url,
        "bytes_fetched": bytes_fetched,
        "reason": reason,
    }


def _fetch(
    url: str,
    policy: dict[str, typing.Any],
    budget: dict[str, int] | None = None,
    method: str = "GET",
) -> dict[str, typing.Any]:
    """Fetch one source within policy caps; caller may share a budget across checks."""
    domains = [
        _normalize_domain(domain, "evidence_policy.allowed_domains")
        for domain in policy["allowed_domains"]
    ]
    source_limit = min(policy["max_bytes_per_source"], MAX_SOURCE_BYTES)
    total_limit = min(policy["max_total_bytes"], MAX_TOTAL_BYTES)
    bytes_used = budget.get("bytes_used", 0) if budget is not None else 0
    current_url = url
    redirects = 0
    source_bytes = 0

    while True:
        try:
            _validate_url(current_url, domains, "evidence URL")
            response = gl.nondet.web.request(current_url, method=method)
            status = int(response.status)
            headers = response.headers
            body = response.body if response.body is not None else b""
            if not isinstance(body, bytes):
                return _missing_fetch("invalid response body", current_url, source_bytes)
        except Exception:
            return _missing_fetch(
                "network request failed", current_url, source_bytes, budget, bytes_used
            )

        body_size = len(body)
        length_header = _response_header(headers, "content-length")
        if length_header is not None:
            try:
                content_length = int(length_header)
            except (TypeError, ValueError):
                return _missing_fetch(
                    "invalid content-length",
                    current_url,
                    source_bytes,
                    budget,
                    bytes_used,
                    body_size,
                )
            if content_length < 0 or content_length > source_limit - source_bytes:
                return _missing_fetch(
                    "source exceeds byte limit",
                    current_url,
                    source_bytes,
                    budget,
                    bytes_used,
                    body_size,
                )
            if content_length > total_limit - bytes_used - source_bytes:
                return _missing_fetch(
                    "total evidence exceeds byte limit",
                    current_url,
                    source_bytes,
                    budget,
                    bytes_used,
                    body_size,
                )

        if body_size > source_limit - source_bytes:
            return _missing_fetch(
                "source exceeds byte limit",
                current_url,
                source_bytes,
                budget,
                bytes_used,
                body_size,
            )
        if body_size > total_limit - bytes_used - source_bytes:
            return _missing_fetch(
                "total evidence exceeds byte limit",
                current_url,
                source_bytes,
                budget,
                bytes_used,
                body_size,
            )

        source_bytes += body_size
        if status in (301, 302, 303, 307, 308):
            if not policy["allow_redirects"]:
                return _missing_fetch(
                    "redirects are disabled", current_url, source_bytes, budget, bytes_used
                )
            if redirects >= policy["max_redirects"]:
                return _missing_fetch(
                    "redirect limit exceeded", current_url, source_bytes, budget, bytes_used
                )
            location = _response_header(headers, "location")
            if not isinstance(location, str) or not location:
                return _missing_fetch(
                    "redirect has no location", current_url, source_bytes, budget, bytes_used
                )
            current_url = urljoin(current_url, location)
            if status == 303:
                method = "GET"
            redirects += 1
            continue

        if budget is not None:
            budget["bytes_used"] = bytes_used + source_bytes
        return {
            "status": "OK",
            "http_status": status,
            "body": body,
            "url": current_url,
            "bytes_fetched": source_bytes,
            "reason": "",
        }


def _json_path_value(data: typing.Any, path: str) -> tuple[bool, typing.Any]:
    value = data
    for segment in path.split("."):
        match = re.match(r"^([^\[\]]+)(?:\[(\d+)\])?$", segment)
        if match is None or not isinstance(value, dict) or match.group(1) not in value:
            return False, None
        value = value[match.group(1)]
        if match.group(2) is not None:
            if not isinstance(value, list):
                return False, None
            index = int(match.group(2))
            if index >= len(value):
                return False, None
            value = value[index]
    return True, value


def _json_type_matches(value: typing.Any, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "string":
        return isinstance(value, str)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    return False


def _objective_result(
    criterion: dict[str, typing.Any],
    passed: bool,
    status: str,
    reason: str,
    evidence_url: str,
) -> dict[str, typing.Any]:
    return {
        "criterion_id": criterion["id"],
        "kind": "objective",
        "check": criterion["check"],
        "passed": passed,
        "score": 10 if passed else 0,
        "weight": criterion["weight"],
        "reason": reason[:MAX_REASON_CHARS],
        "evidence_url": evidence_url,
        "evidence_quote": "",
        "status": status,
    }


def _run_objective(
    criterion: dict[str, typing.Any],
    evidence_policy: dict[str, typing.Any],
    budget: dict[str, int] | None = None,
) -> dict[str, typing.Any]:
    """Run one manifest-validated objective criterion against independently fetched bytes."""
    check = criterion["check"]
    params = criterion["params"]
    evidence_url = params["url"]
    if check not in ("http_status", "json_has_keys", "file_hash", "text_contains"):
        _fail("E_CHECK_UNSUPPORTED", f"unsupported objective check '{check}'")

    method = params.get("method", "GET") if check == "http_status" else "GET"
    fetched = _fetch(evidence_url, evidence_policy, budget, method)
    if fetched["status"] == "MISSING":
        return _objective_result(
            criterion,
            False,
            "MISSING",
            fetched["reason"],
            evidence_url,
        )

    body = fetched["body"]
    if check == "http_status":
        expected = params["expected_status"]
        expected_statuses = expected if isinstance(expected, list) else [expected]
        passed = fetched["http_status"] in expected_statuses
        reason = f"HTTP {fetched['http_status']}"
    elif check == "file_hash":
        actual_hash = hashlib.sha256(body).hexdigest()
        passed = actual_hash.lower() == params["sha256"].lower()
        reason = "SHA-256 matches" if passed else "SHA-256 does not match"
    elif check == "json_has_keys":
        try:
            document = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError, TypeError, RecursionError):
            return _objective_result(
                criterion, False, "FAIL", "response is not valid JSON", evidence_url
            )
        passed = True
        for path in params["required_keys"]:
            found, _ = _json_path_value(document, path)
            if not found:
                passed = False
                break
        if passed:
            for path, expected_type in params.get("types", {}).items():
                found, value = _json_path_value(document, path)
                if not found or not _json_type_matches(value, expected_type):
                    passed = False
                    break
        reason = "required JSON paths and types are present" if passed else "required JSON path or type is missing"
    else:
        text = " ".join(body.decode("utf-8", errors="replace").split())
        phrases = [" ".join(phrase.split()) for phrase in params["phrases"]]
        case_sensitive = params.get("case_sensitive", False)
        if not case_sensitive:
            text = text.lower()
            phrases = [phrase.lower() for phrase in phrases]
        passed = all(phrase in text for phrase in phrases)
        reason = "all required phrases are present" if passed else "one or more required phrases are missing"

    return _objective_result(
        criterion,
        passed,
        "PASS" if passed else "FAIL",
        reason,
        evidence_url,
    )


class Presense(gl.Contract):
    """Acceptance adjudication primitive with manifest and escrow lifecycle."""

    version: str
    agreements: TreeMap[str, Agreement]
    submissions: TreeMap[str, Submission]
    claims: TreeMap[Address, u256]
    total_locked: u256

    def __init__(self) -> None:
        self.version = "0.1.0"
        self.total_locked = u256(0)

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

    @gl.public.write.payable
    def create_agreement(
        self,
        agreement_id: str,
        seller: Address,
        manifest_json: str,
        manifest_url: str,
        deadline: u256,
        challenge_window: u256,
        metadata_url: str,
    ) -> str:
        """Create and fund a new agreement with a validated manifest."""
        if (
            not isinstance(agreement_id, str)
            or re.match(r"^[A-Za-z0-9_-]{1,64}$", agreement_id) is None
        ):
            _fail("E_BAD_ID", "agreement ID must be 1-64 letters, digits, '_' or '-'")
        if agreement_id in self.agreements:
            _fail("E_AGREEMENT_EXISTS", "agreement ID already exists")

        buyer = _as_address(gl.message.sender_address)
        seller = _as_address(seller)
        zero_address = Address("0x" + "0" * 40)
        if seller == buyer:
            _fail("E_SELF_AGREEMENT", "buyer and seller must be different")
        if seller == zero_address or seller == gl.message.contract_address:
            _fail("E_ZERO_ADDRESS", "seller must be a non-zero external address")
        if gl.message.value == u256(0):
            _fail("E_ESCROW_ZERO", "escrow must be greater than zero")

        now = self._now()
        if int(deadline) < int(now) + MIN_DEADLINE_SECONDS:
            _fail("E_DEADLINE_INVALID", "deadline must be at least one hour in the future")
        if (
            int(challenge_window) < MIN_CHALLENGE_WINDOW
            or int(challenge_window) > MAX_CHALLENGE_WINDOW
        ):
            _fail("E_WINDOW_INVALID", "challenge window must be between 1 hour and 7 days")

        parsed = parse_manifest(manifest_json)
        validate_manifest(parsed)
        _, allowed_domains = _validate_evidence_policy(
            parsed["data"]["evidence_policy"]
        )
        self._validate_optional_url(manifest_url, "manifest_url")
        self._validate_optional_url(metadata_url, "metadata_url")
        self._validate_manifest_urls(parsed["data"], allowed_domains)

        agreement = Agreement(
            id=agreement_id,
            buyer=buyer,
            seller=seller,
            manifest_json=parsed["canonical"],
            manifest_hash=parsed["hash"],
            manifest_url=manifest_url,
            metadata_url=metadata_url,
            escrow=gl.message.value,
            deadline=u256(deadline),
            challenge_window=u256(challenge_window),
            created_at=now,
            status="CREATED",
            submission_id="",
            verdict_id="",
            challenge_id="",
            challenge_count=u8(0),
            evaluated_at=u256(0),
        )
        self.agreements[agreement_id] = agreement
        self.total_locked = self.total_locked + gl.message.value
        return agreement_id

    @gl.public.write
    def accept_agreement(self, agreement_id: str) -> None:
        """Accept an agreement as its named seller."""
        agreement = self._require_agreement(agreement_id)
        if _as_address(gl.message.sender_address) != agreement.seller:
            _fail("E_UNAUTHORIZED", "only the seller can accept")
        if agreement.status != "CREATED":
            _fail("E_INVALID_STATE", "agreement is not awaiting acceptance")
        if self._now() > agreement.deadline:
            _fail("E_DEADLINE_PASSED", "acceptance deadline has passed")

        agreement.status = "ACTIVE"
        self.agreements[agreement_id] = agreement

    @gl.public.write
    def cancel_agreement(self, agreement_id: str) -> None:
        """Cancel an unaccepted agreement and credit the buyer's refund."""
        agreement = self._require_agreement(agreement_id)
        if _as_address(gl.message.sender_address) != agreement.buyer:
            _fail("E_UNAUTHORIZED", "only the buyer can cancel")
        if agreement.status != "CREATED":
            _fail("E_INVALID_STATE", "only an unaccepted agreement can be cancelled")

        agreement.status = "CANCELLED"
        self.agreements[agreement_id] = agreement
        self._credit_claim(agreement.buyer, agreement.escrow)

    @gl.public.write
    def submit_delivery(
        self,
        agreement_id: str,
        artifact_urls: DynArray[str],
        artifact_hashes: DynArray[str],
        notes: str,
    ) -> str:
        """Record the seller's artifact references before the deadline."""
        agreement = self._require_agreement(agreement_id)
        if _as_address(gl.message.sender_address) != agreement.seller:
            _fail("E_UNAUTHORIZED", "only the seller can submit delivery")
        if agreement.status != "ACTIVE":
            _fail("E_INVALID_STATE", "agreement is not active")
        if self._now() > agreement.deadline:
            _fail("E_DEADLINE_PASSED", "delivery deadline has passed")
        if len(artifact_urls) < 1 or len(artifact_urls) > MAX_ARTIFACTS:
            _fail("E_ARTIFACT_COUNT", "delivery must contain 1-10 artifact URLs")
        if len(artifact_urls) != len(artifact_hashes):
            _fail("E_ARTIFACT_MISMATCH", "artifact URL and hash counts differ")
        if not isinstance(notes, str) or len(notes) > MAX_NOTES_CHARS:
            _fail("E_MANIFEST_INVALID", "notes must be at most 2,000 characters")

        manifest = json.loads(agreement.manifest_json)
        _, allowed_domains = _validate_evidence_policy(manifest["evidence_policy"])
        for index in range(len(artifact_urls)):
            url = artifact_urls[index]
            digest = artifact_hashes[index]
            _validate_url(url, allowed_domains, f"artifact_urls[{index}]")
            if digest != "" and re.match(r"^[0-9a-fA-F]{64}$", digest) is None:
                _fail("E_BAD_HASH", f"artifact_hashes[{index}] must be empty or 64 hex characters")

        submission_id = f"{agreement_id}:submission"
        submission = Submission(
            id=submission_id,
            agreement_id=agreement_id,
            artifact_urls=artifact_urls,
            artifact_hashes=artifact_hashes,
            notes=notes,
            submitted_at=self._now(),
            submitter=_as_address(gl.message.sender_address),
        )
        self.submissions[submission_id] = submission
        agreement.submission_id = submission_id
        agreement.status = "SUBMITTED"
        self.agreements[agreement_id] = agreement
        return submission_id

    @gl.public.write
    def preview_objective_checks(self, agreement_id: str) -> typing.Any:
        """Run and return objective results without storing a verdict or changing state."""
        agreement = self._require_agreement(agreement_id)
        if agreement.status not in ("SUBMITTED", "DISPUTED"):
            _fail("E_INVALID_STATE", "agreement has no submitted delivery to check")
        manifest = json.loads(agreement.manifest_json)
        criteria = manifest["criteria"]
        evidence_policy = manifest["evidence_policy"]

        def run_checks() -> list[dict[str, typing.Any]]:
            budget = {"bytes_used": 0}
            results = []
            for criterion in criteria:
                if criterion["kind"] == "objective":
                    results.append(
                        _run_objective(criterion, evidence_policy, budget)
                    )
            return results

        return gl.eq_principle.strict_eq(run_checks)

    @gl.public.write
    def claim_expired(self, agreement_id: str) -> None:
        """Refund the buyer after an active agreement misses its deadline."""
        agreement = self._require_agreement(agreement_id)
        if agreement.status != "ACTIVE":
            _fail("E_INVALID_STATE", "only an active agreement can expire")
        if agreement.submission_id:
            _fail("E_ALREADY_SUBMITTED", "delivery has already been submitted")
        if self._now() <= agreement.deadline:
            _fail("E_DEADLINE_NOT_PASSED", "delivery deadline has not passed")

        agreement.status = "EXPIRED"
        self.agreements[agreement_id] = agreement
        self._credit_claim(agreement.buyer, agreement.escrow)

    @gl.public.write
    def withdraw(self, kind: str) -> None:
        """Withdraw the caller's full claim to an EVM address or IC."""
        if kind not in ("evm", "ic"):
            _fail("E_BAD_RECIPIENT_KIND", "kind must be 'evm' or 'ic'")
        sender = _as_address(gl.message.sender_address)
        amount = self.claims.get(sender, u256(0))
        if amount == u256(0):
            _fail("E_CLAIM_ZERO", "caller has no claim to withdraw")

        self.claims[sender] = u256(0)
        self.total_locked = self.total_locked - amount
        if kind == "ic":
            gl.get_contract_at(sender).emit_transfer(value=amount, on="finalized")
        else:
            _Recipient(sender).emit_transfer(value=amount)

    @gl.public.view
    def get_agreement(self, agreement_id: str) -> typing.Any:
        """Return the public agreement fields as a structured object."""
        return self._agreement_dict(self._require_agreement(agreement_id))

    @gl.public.view
    def get_agreement_json(self, agreement_id: str) -> str:
        """Return the agreement fields as compact JSON."""
        return json.dumps(
            self._agreement_dict(self._require_agreement(agreement_id)),
            sort_keys=True,
            separators=(",", ":"),
        )

    @gl.public.view
    def get_status(self, agreement_id: str) -> str:
        """Return the current lifecycle status for an agreement."""
        return self._require_agreement(agreement_id).status

    @gl.public.view
    def get_claim(self, address: Address) -> u256:
        """Return an address's unwithdrawn claim."""
        return self.claims.get(_as_address(address), u256(0))

    @gl.public.view
    def get_totals(self) -> typing.Any:
        """Return tracked escrow/claims and the contract's native balance."""
        return {"total_locked": self.total_locked, "balance": self.balance}

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

    def _now(self) -> u256:
        return u256(int(datetime.now(timezone.utc).timestamp()))

    def _require_agreement(self, agreement_id: str) -> Agreement:
        if agreement_id not in self.agreements:
            _fail("E_NOT_FOUND", "agreement does not exist")
        return self.agreements[agreement_id]

    def _credit_claim(self, address: Address, amount: u256) -> None:
        self.claims[address] = self.claims.get(address, u256(0)) + amount

    def _validate_optional_url(self, url: str, name: str) -> None:
        if not isinstance(url, str):
            _fail("E_URL_INVALID", f"{name} must be a string")
        if url:
            host = _url_host(url, name)
            _reject_private_host(host, name)

    def _validate_manifest_urls(
        self, manifest: dict[str, typing.Any], allowed_domains: list[str]
    ) -> None:
        for index, criterion in enumerate(manifest["criteria"]):
            params = criterion["params"]
            key = "evidence_url" if criterion["check"] == "llm_rubric" else "url"
            _validate_url(params[key], allowed_domains, f"criteria[{index}].params.{key}")

    def _agreement_dict(self, agreement: Agreement) -> dict[str, typing.Any]:
        return {
            "id": agreement.id,
            "buyer": str(agreement.buyer),
            "seller": str(agreement.seller),
            "manifest_json": agreement.manifest_json,
            "manifest_hash": agreement.manifest_hash,
            "manifest_url": agreement.manifest_url,
            "metadata_url": agreement.metadata_url,
            "escrow": int(agreement.escrow),
            "deadline": int(agreement.deadline),
            "challenge_window": int(agreement.challenge_window),
            "created_at": int(agreement.created_at),
            "status": agreement.status,
            "submission_id": agreement.submission_id,
            "verdict_id": agreement.verdict_id,
            "challenge_id": agreement.challenge_id,
            "challenge_count": int(agreement.challenge_count),
            "evaluated_at": int(agreement.evaluated_at),
        }
