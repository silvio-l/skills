#!/usr/bin/env python3
"""Prepare or publish independently validated audit findings. Python 3.9+, stdlib; git only for credential lookup."""
import argparse
import base64
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

LIMIT = 100
MAX_PAGES = 100
MAX_RESPONSE = 4 * 1024 * 1024


class IssueError(ValueError):
    pass


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise IssueError("duplicate JSON key")
        result[key] = value
    return result


def read(path):
    if Path(path).stat().st_size > 32 * 1024 * 1024:
        raise IssueError("input exceeds 32 MiB; pass issue-export.json from audit.py report, not result.json")
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique)


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".issues-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(value, out, indent=2, ensure_ascii=False)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


# Explicit list: ipaddress.is_private also covers documentation and other special-purpose ranges.
PRIVATE_NETWORKS = tuple(ipaddress.ip_network(n) for n in (
    "10.0.0.0/8", "172.16.0.0/12", "192.0.2.10/16", "127.0.0.0/8", "169.254.0.0/16",
    "fc00::/7", "fe80::/10", "::1/128"))


def private_host(host):
    """True for RFC 1918, loopback, link-local and IPv6 ULA addresses and mDNS `.local` names."""
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return host.lower().rstrip(".").endswith(".local") or host.lower() == "localhost"
    if getattr(address, "ipv4_mapped", None):
        address = address.ipv4_mapped
    return any(address in network for network in PRIVATE_NETWORKS)


def lan_http(config):
    url = urllib.parse.urlsplit(config["base_url"])
    return url.scheme == "http" and config.get("allow_http") == "private-lan" and private_host(url.hostname or "")


def config_check(config, require_transport=True):
    required = {"provider", "base_url", "repository", "visibility"}
    if not isinstance(config, dict) or not required <= set(config):
        raise IssueError("tracker config missing required fields")
    if set(config) - required - {"public_details", "token_env", "credential", "allow_http"}:
        raise IssueError("unknown tracker config field")
    if ("token_env" in config) == ("credential" in config):
        raise IssueError("tracker config needs exactly one of token_env or credential")
    if "credential" in config and config["credential"] != "git-credential":
        raise IssueError("credential must be git-credential")
    if "allow_http" in config and config["allow_http"] != "private-lan":
        raise IssueError("allow_http must be private-lan")
    if config["provider"] not in ("internal forge", "gitea", "github", "gitlab"):
        raise IssueError("unsupported provider")
    if not isinstance(config["base_url"], str):
        raise IssueError("invalid base_url")
    url = urllib.parse.urlsplit(config["base_url"])
    if (url.scheme not in ("http", "https") or not url.hostname or url.username or url.password
            or url.query or url.fragment or ".." in url.path.split("/")
            or any(ord(c) <= 32 or ord(c) == 127 for c in config["base_url"]) or "\\" in config["base_url"]):
        raise IssueError("base_url must be a reviewed HTTP(S) API endpoint without credentials")
    try:
        url.port
    except ValueError:
        raise IssueError("invalid API endpoint port") from None
    if "allow_http" in config and (url.scheme != "http" or not private_host(url.hostname)):
        raise IssueError("allow_http private-lan needs an http base_url on a private address or .local name")
    if require_transport and url.scheme != "https" and not lan_http(config):
        raise IssueError("live transport blocked: HTTPS required; offline outbox remains available")
    repo = config["repository"]
    if not isinstance(repo, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+", repo):
        raise IssueError("invalid repository path")
    if any(x in (".", "..") for x in repo.split("/")):
        raise IssueError("invalid repository segment")
    if config["provider"] != "gitlab" and len(repo.split("/")) != 2:
        raise IssueError("provider requires owner/repository")
    if "token_env" in config and (not isinstance(config["token_env"], str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", config["token_env"])):
        raise IssueError("invalid token environment variable name")
    if config["visibility"] not in ("public", "private"):
        raise IssueError("visibility must be public or private")
    if type(config.get("public_details", False)) is not bool:
        raise IssueError("public_details must be boolean")
    return config


def skip_reason(finding):
    """Name the actual gate, so a blocked confirmed finding is not mistaken for a missing review."""
    if finding.get("status") != "confirmed":
        return "status " + str(finding.get("status")) + ", not confirmed"
    blockers = finding.get("publication_blockers")
    if blockers:
        return "confirmed, but blocked by unresolved review " + ", ".join(map(str, blockers))
    if finding.get("independent_confirmation") is False:
        return "confirmed without a current independent finding review"
    if finding.get("independent_validated") is not True:
        return "not independently validated (integrity or review gate failed)"
    return ""


def fingerprint(config, finding):
    # Deliberately excludes run ID, priority, title and line numbers: these change on repeat audits.
    key = [config["base_url"].rstrip("/"), config["repository"], finding["criterion"], finding["root_cause"]]
    return hashlib.sha256(json.dumps(key, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def prepare(export, config):
    config_check(config, require_transport=False)
    if not isinstance(export, dict) or not isinstance(export.get("findings"), list):
        raise IssueError("export must contain findings array")
    if export.get("integrity_valid") is False or export.get("integrity_errors"):
        raise IssueError("audit integrity validation failed; regenerate valid evidence and export")
    if export.get("repository") != config["repository"]:
        raise IssueError("export repository does not match reviewed tracker configuration")
    if not isinstance(export.get("run_id"), str) or not export["run_id"].strip():
        raise IssueError("export run_id missing")
    if urllib.parse.urlsplit(config["base_url"]).scheme == "https":
        transport = {"status": "eligible", "reason": "HTTPS endpoint; credentials and remote checks still required"}
    elif lan_http(config):
        transport = {"status": "eligible", "reason": "explicit private-LAN HTTP opt-in: credentials and issue text travel "
                     "unencrypted inside the local network; no redirects, resolved addresses must be private"}
    else:
        transport = {"status": "blocked", "reason": "HTTP endpoint: offline preparation only; live transport requires reviewed HTTPS access "
                     "or the allow_http private-lan opt-in for a private address"}
    notices = export.get("coverage_notices") or []
    if not isinstance(notices, list) or any(not isinstance(n, str) for n in notices):
        raise IssueError("coverage_notices must be a list of review IDs")
    result = {"run_id": export["run_id"], "repository": config["repository"],
              "provider": config["provider"], "base_url": config["base_url"], "issues": [], "skipped": [],
              "coverage_notices": notices, "transport": transport}
    seen_ids, by_marker = set(), {}
    for finding in export["findings"]:
        if isinstance(finding, dict) and isinstance(finding.get("steps"), list):
            if not finding["steps"] or any(not isinstance(s, str) or not s.strip() for s in finding["steps"]):
                raise IssueError("invalid reproduction steps")
            finding = {**finding, "steps": "\n".join(str(i + 1) + ". " + s for i, s in enumerate(finding["steps"]))}
        if not isinstance(finding, dict) or not isinstance(finding.get("id"), str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,120}", finding["id"]):
            raise IssueError("invalid finding identifier")
        if finding["id"] in seen_ids:
            raise IssueError("duplicate finding identifier")
        seen_ids.add(finding["id"])
        reason = skip_reason(finding)
        if reason:
            result["skipped"].append({"id": finding["id"], "reason": reason})
            continue
        for field in ("title", "criterion", "root_cause", "impact", "priority", "steps", "expected", "actual", "recommendation"):
            if not isinstance(finding.get(field), str) or not finding[field].strip():
                raise IssueError("confirmed finding missing " + field)
        if "\n" in finding["title"] or len(finding["title"]) > 240:
            raise IssueError("finding title must be one line, at most 240 characters")
        if not isinstance(finding.get("evidence"), list) or not finding["evidence"] or any(not isinstance(x, str) or not x.strip() for x in finding["evidence"]):
            raise IssueError("confirmed finding requires evidence references")
        key = fingerprint(config, finding)
        marker = "<!-- ui-ux-audit:" + key + " -->"
        if key in by_marker:
            by_marker[key]["finding_ids"].append(finding["id"])
            continue
        title = finding["title"]
        if config["visibility"] == "public" and not config.get("public_details", False):
            title = "UI/UX audit finding " + key[:12]
            body = "An independently validated UI/UX finding is recorded in the private audit ledger.\n\n" + marker
        else:
            sections = [("Criterion", finding["criterion"]), ("User impact and priority", finding["impact"] + "\n\n" + finding["priority"]),
                        ("Reproduction", finding["steps"]), ("Expected", finding["expected"]), ("Actual", finding["actual"]),
                        ("Root cause", finding["root_cause"]), ("Recommended change and acceptance checks", finding["recommendation"]),
                        ("Evidence references", "\n".join("- " + x for x in finding["evidence"]))]
            if notices:
                sections.append(("Audit coverage", "Audit coverage is incomplete (open inventory review " + ", ".join(notices)
                                 + "). This finding was confirmed independently on its own evidence."))
            body = "\n\n".join("## " + head + "\n\n" + text for head, text in sections) + "\n\n" + marker
        row = {"key": key, "marker": marker, "finding_ids": [finding["id"]], "title": title, "body": body}
        by_marker[key] = row
        result["issues"].append(row)
    return result


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise IssueError("tracker redirect refused")


def resolved_private(host, port):
    """Refuse a .local or private-looking name that resolves outside the private network."""
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError):
        raise IssueError("tracker host does not resolve") from None
    addresses = {info[4][0].split("%")[0] for info in infos}
    # private_host on a resolved address checks the IP itself; a name never passes here.
    if not addresses or any(not private_host(a) or not _is_ip(a) for a in addresses):
        raise IssueError("tracker host resolves outside the private network; HTTP refused")


def _is_ip(value):
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def git_credential(base_url):
    """Read username/password for the endpoint from git's credential helpers (e.g. the keychain)."""
    git = shutil.which("git")
    if not git:
        raise IssueError("git not found for credential lookup")
    url = urllib.parse.urlsplit(base_url)
    request = "protocol=" + url.scheme + "\nhost=" + url.netloc + "\n\n"
    # Stored credentials only: no terminal prompt, no askpass dialog, no interactive credential manager.
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_ASKPASS", "SSH_ASKPASS")}
    env.update(GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never")
    try:
        done = subprocess.run([git, "-c", "core.askPass=", "-c", "credential.interactive=false", "credential", "fill"],
                              input=request, capture_output=True, text=True, timeout=15, env=env)
    except (OSError, subprocess.TimeoutExpired):
        raise IssueError("git credential lookup failed") from None
    fields = dict(line.split("=", 1) for line in done.stdout.splitlines() if "=" in line)
    if done.returncode or not fields.get("password"):
        raise IssueError("no stored git credential for the tracker host")
    return fields.get("username", ""), fields["password"]


class Client:
    def __init__(self, config):
        self.config = config_check(config)
        self.base = config["base_url"].rstrip("/")
        url = urllib.parse.urlsplit(self.base)
        if url.scheme == "http":
            resolved_private(url.hostname, url.port or 80)
        if "credential" in config:
            user, token = git_credential(config["base_url"])
        else:
            user, token = "", os.environ.get(config["token_env"], "")
        if not token or "\n" in token or "\r" in token:
            raise IssueError("tracker credential missing or invalid")
        self.headers = {"Accept": "application/json", "Content-Type": "application/json", "User-Agent": "ui-ux-audit/1"}
        if config["provider"] == "gitlab":
            self.headers["PRIVATE-TOKEN"] = token
        elif user:
            self.headers["Authorization"] = "Basic " + base64.b64encode((user + ":" + token).encode()).decode()
        else:
            self.headers["Authorization"] = "Bearer " + token
        # Do not inherit proxy routing that might expose an audit token to a proxy.
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def request(self, method, path, data=None):
        if not path.startswith("/") or path.startswith("//"):
            raise IssueError("invalid API path")
        body = None if data is None else json.dumps(data).encode()
        req = urllib.request.Request(self.base + path, data=body, headers=self.headers, method=method)
        try:
            with self.opener.open(req, timeout=20) as response:
                raw = response.read(MAX_RESPONSE + 1)
                if len(raw) > MAX_RESPONSE:
                    raise IssueError("tracker response too large")
                return json.loads(raw, object_pairs_hook=unique)
        except urllib.error.HTTPError as exc:
            raise IssueError("tracker HTTP error " + str(exc.code)) from None
        except (urllib.error.URLError, TimeoutError, OSError, UnicodeError, json.JSONDecodeError):
            raise IssueError("tracker request failed or returned invalid JSON") from None


def paths(config):
    if config["provider"] == "gitlab":
        repo = "/projects/" + urllib.parse.quote(config["repository"], safe="")
    else:
        repo = "/repos/" + config["repository"]
    return repo, repo + "/issues"


def verify_visibility(client, config):
    metadata = client.request("GET", paths(config)[0])
    if not isinstance(metadata, dict):
        raise IssueError("invalid repository metadata")
    if config["provider"] == "gitlab":
        visibility = metadata.get("visibility")
        if visibility not in ("private", "public", "internal"):
            raise IssueError("repository visibility unavailable")
        actual = "public" if visibility != "private" else "private"
    else:
        if type(metadata.get("private")) is not bool:
            raise IssueError("repository visibility unavailable")
        actual = "private" if metadata["private"] else "public"
    if actual != config["visibility"]:
        raise IssueError("repository visibility differs from reviewed configuration")


def list_issues(client, config):
    existing, ids = [], set()
    for page in range(1, MAX_PAGES + 1):
        query = {"state": "all", "page": page}
        query["limit" if config["provider"] in ("internal forge", "gitea") else "per_page"] = LIMIT
        if config["provider"] == "gitlab":
            query.update({"scope": "all", "order_by": "created_at", "sort": "asc"})
        elif config["provider"] == "github":
            query.update({"sort": "created", "direction": "asc"})
        rows = client.request("GET", paths(config)[1] + "?" + urllib.parse.urlencode(query))
        if not isinstance(rows, list):
            raise IssueError("invalid issues listing")
        if not rows:
            return existing
        for row in rows:
            if not isinstance(row, dict) or type(row.get("id")) is not int:
                raise IssueError("invalid issue record")
            body = row.get("description" if config["provider"] == "gitlab" else "body")
            if body is not None and not isinstance(body, str):
                raise IssueError("invalid issue body")
            if row["id"] in ids:
                raise IssueError("unstable or repeated pagination; retry reconciliation")
            ids.add(row["id"])
            if "pull_request" not in row:
                existing.append(row)
        # Continue even on short pages: servers may cap page size below the requested limit.
    raise IssueError("issue pagination limit reached; no issues published")


def record_link(row, config):
    key = "iid" if config["provider"] == "gitlab" else "number"
    number = row.get(key)
    url = row.get("web_url" if config["provider"] == "gitlab" else "html_url")
    schemes = ("https://", "http://") if lan_http(config) else ("https://",)
    if type(number) is not int or number < 1 or not isinstance(url, str) or not url.startswith(schemes):
        raise IssueError("tracker issue reference missing or invalid")
    return {"number": number, "url": url, "state": row.get("state", "unknown")}


def publish(outbox, config, receipt_path, client=None):
    """Single coordinator only; lock prevents concurrent local writers, not remote writers."""
    config_check(config)  # Enforce before credential access, client injection or local receipt writes.
    if any(outbox.get(k) != config[k] for k in ("provider", "base_url", "repository")):
        raise IssueError("outbox destination differs from reviewed tracker; prepare again")
    receipt_path = Path(receipt_path)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    lock = receipt_path.with_suffix(receipt_path.suffix + ".lock")
    try:
        lock.mkdir()
    except FileExistsError:
        raise IssueError("publication lock exists; check prior process before removing it") from None
    try:
        client = client or Client(config)
        identity = {"provider": config["provider"], "base_url": config["base_url"], "repository": config["repository"]}
        receipt = read(receipt_path) if receipt_path.exists() else {**identity, "deliveries": {}}
        if any(receipt.get(k) != v for k, v in identity.items()) or not isinstance(receipt.get("deliveries"), dict):
            raise IssueError("receipt belongs to a different tracker or is invalid")
        verify_visibility(client, config)
        existing = list_issues(client, config)
        plans = []
        for item in outbox["issues"]:
            matches = [r for r in existing if item["marker"] in ((r.get("description") if config["provider"] == "gitlab" else r.get("body")) or "")]
            if len(matches) > 1:
                raise IssueError("multiple remote issues share the audit marker; reconcile manually")
            old = receipt["deliveries"].get(item["key"], {})
            if matches:
                link = record_link(matches[0], config)
                plans.append((item, link))
            elif old:
                raise IssueError("previous delivery absent remotely or outcome unknown; manual reconciliation required")
            else:
                plans.append((item, None))
        # Reconciliation of every candidate succeeds before the first mutation.
        for item, link in plans:
            record = {"finding_ids": item["finding_ids"], "payload_sha256": hashlib.sha256((item["title"] + "\n" + item["body"]).encode()).hexdigest()}
            if link:
                receipt["deliveries"][item["key"]] = {**record, "status": "existing", **link}
                atomic(receipt_path, receipt)
                continue
            receipt["deliveries"][item["key"]] = {**record, "status": "outcome_unknown"}
            atomic(receipt_path, receipt)
            payload = {"title": item["title"], "description" if config["provider"] == "gitlab" else "body": item["body"]}
            row = client.request("POST", paths(config)[1], payload)
            link = record_link(row, config)
            receipt["deliveries"][item["key"]] = {**record, "status": "created", **link}
            atomic(receipt_path, receipt)
        return receipt
    finally:
        lock.rmdir()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export")
    parser.add_argument("config")
    parser.add_argument("outbox")
    parser.add_argument("--execute", action="store_true", help="publish after reviewing destination and prepared issue content")
    parser.add_argument("--receipts", help="persistent receipt JSON; required with --execute")
    args = parser.parse_args(argv)
    try:
        if args.execute and not args.receipts:
            raise IssueError("--execute requires --receipts")
        paths_used = [Path(p).resolve() for p in (args.export, args.config, args.outbox, args.receipts) if p]
        if len(set(paths_used)) != len(paths_used):
            raise IssueError("input, outbox and receipt paths must be distinct")
        config = config_check(read(args.config), require_transport=False)
        outbox = prepare(read(args.export), config)
        atomic(args.outbox, outbox)
        if args.execute:
            result = publish(outbox, config, args.receipts)
            print(json.dumps({"status": "published", "receipt": str(args.receipts), "deliveries": result["deliveries"]}))
        else:
            print(json.dumps({"status": "prepared", "outbox": str(args.outbox), "eligible": len(outbox["issues"]), "skipped": outbox["skipped"], "transport": outbox["transport"]}))
        return 0
    except (IssueError, OSError, json.JSONDecodeError, TypeError, KeyError) as exc:
        # Unexpected content must not surface tokens, remote bodies or exception URL strings.
        message = str(exc) if isinstance(exc, IssueError) else "invalid input or local I/O failure"
        print(json.dumps({"status": "blocked", "reason": message}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
