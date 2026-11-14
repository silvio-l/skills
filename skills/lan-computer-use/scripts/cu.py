#!/usr/bin/env python3
"""lan-computer-use client: drive the GUI of the local Mac or of macOS/Windows machines in the LAN over SSH.

A small agent runs in the target's desktop session and listens on 127.0.0.1 only. This client keeps an SSH
control master with a port forward open, so after the first call every command is one local TCP round trip.

    cu.py [-t TARGET] [--json] <command> [args]      (cu.py <command> -h for details)

Targets: built-in `local` (this Mac) plus ~/.config/lan-computer-use/targets.json, see REFERENCE.md.
"""
import argparse
import base64
import hashlib
import json
import os
import re
import shlex
import signal
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
AGENT_DIR = os.path.join(HERE, "agent")
CONFIG = os.path.expanduser(os.environ.get("LCU_CONFIG", "~/.config/lan-computer-use/targets.json"))
CACHE = os.path.expanduser(os.environ.get("LCU_CACHE", "~/.cache/lan-computer-use"))
LOCAL_DIR = os.path.expanduser("~/Library/Application Support/lan-computer-use")
REMOTE_WIN_DIR = "AppData/Local/Temp/lan-computer-use"   # relative to the SSH user's home (sftp + ssh cwd)
REMOTE_MAC_DIR = "Library/Caches/lan-computer-use"
INPUT_CMDS = {"click", "move", "drag", "scroll", "press", "set-value", "focus", "type", "key", "activate", "launch"}
PROTOCOL = "1"


class CuError(Exception):
    pass


# ---------------------------------------------------------------- targets

def load_targets():
    targets = {"local": {"os": "macos", "local": True, "announce": True, "idle_minutes": 3}}
    default = "local"
    if os.path.exists(CONFIG):
        try:
            with open(CONFIG, encoding="utf-8") as f:
                cfg = json.load(f)
        except (OSError, ValueError) as e:
            raise CuError(f"cannot read {CONFIG}: {e}")
        default = cfg.get("default", default)
        for name, t in (cfg.get("targets") or {}).items():
            if not isinstance(t, dict):
                raise CuError(f"target '{name}' must be an object")
            targets[name] = t
    return targets, default


ALIASES = os.path.join(CACHE, "ssh-aliases.json")


def detect_os(rc, out):
    """OS of an SSH host from `uname -s`: Darwin is a Mac; Windows has no uname (cmd/PowerShell fail)."""
    if rc == 255:
        return None
    first = out.strip().splitlines()[0].strip() if out.strip() else ""
    if rc == 0 and first == "Darwin":
        return "macos"
    if rc == 0 and (first in ("Linux", "FreeBSD", "OpenBSD", "NetBSD", "SunOS") or first.startswith(("CYGWIN", "MINGW", "MSYS"))):
        return "unsupported"
    return "windows"


def alias_target(name):
    """A target name that is no targets.json entry but an SSH host (alias): detect its OS once and cache it."""
    hint = (f"unknown target '{name}'. Add it to {CONFIG}, e.g. "
            f'"{name}": {{"os": "windows", "host": "{name}", "user": "me"}} (see REFERENCE.md, cu.py targets)')
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or name.startswith("-"):
        raise CuError(hint)
    try:
        with open(ALIASES, encoding="utf-8") as f:
            known = json.load(f)
    except (OSError, ValueError):
        known = {}
    if known.get(name) in ("windows", "macos"):
        return {"os": known[name], "host": name}
    try:
        p = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", name, "uname -s"],
                           stdin=subprocess.DEVNULL, capture_output=True, text=True, errors="replace", timeout=20)
        osname = detect_os(p.returncode, p.stdout)
    except (OSError, subprocess.TimeoutExpired):
        osname = None
    if osname is None:
        raise CuError(hint + f"; no SSH connection to '{name}' either")
    if osname == "unsupported":
        raise CuError(f"target '{name}' answers over SSH but is neither macOS nor Windows")
    os.makedirs(CACHE, mode=0o700, exist_ok=True)
    known[name] = osname
    with open(ALIASES, "w", encoding="utf-8") as f:
        json.dump(known, f)
    print(f"target '{name}': SSH host, detected {osname} (pin it in {CONFIG} to skip detection)", file=sys.stderr)
    return {"os": osname, "host": name}


def validate_target(name, t):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
        raise CuError(f"invalid target name '{name}'")
    if t.get("local"):
        if sys.platform != "darwin":
            raise CuError("the local target needs macOS")
        return
    osname = t.get("os")
    if osname not in ("windows", "macos"):
        raise CuError(f"target '{name}': os must be 'windows' or 'macos'")
    if not t.get("host"):
        raise CuError(f"target '{name}' has no host")


def agent_sources(osname):
    if osname == "windows":
        d = os.path.join(AGENT_DIR, "windows")
        return [os.path.join(d, "agent.cs"), os.path.join(d, "setup.ps1")]
    d = os.path.join(AGENT_DIR, "macos")
    return [os.path.join(d, "agent.swift"), os.path.join(d, "setup.sh")]


def build_hash(osname):
    h = hashlib.sha256()
    for p in agent_sources(osname):
        with open(p, "rb") as f:
            h.update(f.read())
        h.update(b"\0")
    return h.hexdigest()[:12]


# ---------------------------------------------------------------- session state (client side)

def state_path(name):
    return os.path.join(CACHE, f"{name}.json")


def load_state(name):
    try:
        with open(state_path(name), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(name, st):
    os.makedirs(CACHE, mode=0o700, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=CACHE, prefix=".state-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(st, f)
    os.replace(tmp, state_path(name))


def drop_state(name):
    try:
        os.unlink(state_path(name))
    except OSError:
        pass


# ---------------------------------------------------------------- wire protocol

class Conn:
    def __init__(self, port, token, timeout=120):
        self.token = token
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=5)
        self.sock.settimeout(timeout)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.buf = b""

    def call(self, cmd, **args):
        if cmd == "task" and not args.get("done"):
            args.setdefault("operator", operator_name())
        req = {k: v for k, v in args.items() if v is not None and v is not False}
        req["cmd"] = cmd
        req["token"] = self.token
        self.sock.sendall(json.dumps(req).encode() + b"\n")
        while b"\n" not in self.buf:
            chunk = self.sock.recv(1 << 20)
            if not chunk:
                raise ConnectionResetError("agent closed the connection")
            self.buf += chunk
        line, self.buf = self.buf.split(b"\n", 1)
        return json.loads(line)

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


# ---------------------------------------------------------------- SSH plumbing

def ssh_base(name, t):
    cm = os.path.join(CACHE, f"cm-{name}")
    args = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "-o", "ServerAliveInterval=15",
            "-o", f"ControlPath={cm}"]
    if t.get("port"):
        args += ["-p", str(t["port"])]
    if t.get("identity"):
        args += ["-i", os.path.expanduser(t["identity"]), "-o", "IdentitiesOnly=yes"]
    if t.get("host_key"):
        kh = os.path.join(CACHE, "known_hosts")
        line = f"lcu-{name} {t['host_key'].strip()}\n"
        try:
            with open(kh, encoding="utf-8") as f:
                lines = [ln for ln in f if not ln.startswith(f"lcu-{name} ")]
        except OSError:
            lines = []
        if line not in lines:
            lines.append(line)
            with open(kh, "w", encoding="utf-8") as f:
                f.writelines(lines)
        args += ["-o", f"UserKnownHostsFile={kh}", "-o", f"HostKeyAlias=lcu-{name}", "-o", "StrictHostKeyChecking=yes"]
    for o in t.get("ssh_options") or []:
        args += ["-o", o]
    dest = t["host"] if not t.get("user") else f"{t['user']}@{t['host']}"
    return args, dest


def ensure_master(name, t):
    os.makedirs(CACHE, mode=0o700, exist_ok=True)
    base, dest = ssh_base(name, t)
    if subprocess.run(base + ["-O", "check", dest], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
        return
    r = subprocess.run(base + ["-f", "-N", "-M", "-o", "ControlPersist=30m", "-o", "ExitOnForwardFailure=yes", dest],
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=30)
    if r.returncode != 0:
        raise CuError(f"ssh to {dest} failed: {r.stderr.strip()[-400:]}")


def ssh_run(name, t, command, timeout=120, input_text=None):
    base, dest = ssh_base(name, t)
    r = subprocess.run(base + [dest, command], input=input_text, capture_output=True, text=True, timeout=timeout,
                       encoding="utf-8", errors="replace")
    return r.returncode, r.stdout, r.stderr


def sftp_put(name, t, remote_dir, files):
    base, dest = ssh_base(name, t)
    sftp = ["sftp", "-b", "-"] + [a for a in base[1:] if a not in ()]  # same -o/-i options
    # sftp takes -P for the port instead of -p
    fixed = []
    it = iter(sftp)
    for a in it:
        if a == "-p":
            fixed += ["-P", next(it)]
        else:
            fixed.append(a)
    parts = remote_dir.split("/")
    batch = [f"-mkdir {'/'.join(parts[:i + 1])}" for i in range(len(parts))]
    batch += [f'put "{local}" "{remote_dir}/{rname}"' for local, rname in files]
    r = subprocess.run(fixed + [dest], input="\n".join(batch) + "\n", capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise CuError(f"upload to {dest} failed: {r.stderr.strip()[-400:]}")


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def forward(name, t, rport):
    base, dest = ssh_base(name, t)
    for _ in range(3):
        lport = free_port()
        r = subprocess.run(base + ["-O", "forward", "-L", f"127.0.0.1:{lport}:127.0.0.1:{rport}", dest],
                           capture_output=True, text=True)
        if r.returncode == 0:
            return lport
    raise CuError(f"cannot forward the agent port: {r.stderr.strip()}")


# bump together with VERSION in both agents on every behaviour change; setup never replaces a newer agent
AGENT_VERSION = 4
LEASE_MAX = 300   # seconds one control lease may span; renew with cu task --eta
LEASE_GRACE = 60  # the agents keep control this long after a lease ran out


def idle_minutes(t):
    """Idle exit of an agent without a lease: default 3, never more than 5 minutes."""
    try:
        v = int(t.get("idle_minutes", 3))
    except (TypeError, ValueError):
        v = 3
    return max(1, min(v, 5))


UPDATE_HINT = "update this skill copy (npx skills@latest update -g -y, or update <skill> -y in the project)"


def parse_setup(out, err, rc):
    for line in out.splitlines():
        if line.startswith("STATE "):
            return json.loads(line[6:])
    if "OUTDATED" in out:
        raise CuError(out.strip()[-500:] + ": " + UPDATE_HINT)
    for marker in ("COMPILE-ERROR", "NO-DESKTOP", "START-TIMEOUT", "NO-GUI"):
        if marker in out:
            raise CuError(out.strip()[-1500:])
    return None


# ---------------------------------------------------------------- starting the agent

def remote_setup(name, t, h):
    osname = t["os"]
    idle = idle_minutes(t)
    src, setup = agent_sources(osname)
    if osname == "windows":
        files = [(src, f"agent-{h}.cs"), (setup, f"setup-{h}.ps1")]
        rdir = REMOTE_WIN_DIR
        cmd = (f"powershell -NoProfile -ExecutionPolicy Bypass -File {rdir.replace('/', chr(92))}\\setup-{h}.ps1"
               f" -Hash {h} -Idle {idle} -Version {AGENT_VERSION}")
    else:
        files = [(src, f"agent-{h}.swift"), (setup, f"setup-{h}.sh")]
        rdir = REMOTE_MAC_DIR
        cmd = f"/bin/bash {rdir}/setup-{h}.sh {h} {idle} {AGENT_VERSION}"
    rc, out, err = ssh_run(name, t, cmd, timeout=240)
    st = parse_setup(out, err, rc)
    if st is None:   # first run on this machine or sources changed: upload and retry
        sftp_put(name, t, rdir, files)
        rc, out, err = ssh_run(name, t, cmd, timeout=240)
        st = parse_setup(out, err, rc)
    if st is None:
        raise CuError(f"agent setup failed (rc {rc}): {(out + err).strip()[-1500:]}")
    return st


def local_setup(t, h):
    os.makedirs(LOCAL_DIR, mode=0o700, exist_ok=True)
    statef = os.path.join(LOCAL_DIR, "state.json")
    st = read_json(statef)
    if st and st.get("build") == h and pid_alive(st.get("pid")):
        return st
    if st and pid_alive(st.get("pid")):
        if newer_agent(st):
            raise CuError(f"OUTDATED: agent version {st.get('version')} runs here, this skill copy brings "
                          f"{AGENT_VERSION}: {UPDATE_HINT}")
        try:
            c = Conn(st["port"], st["token"], timeout=5)
            c.call("quit")
            c.close()
        except (OSError, ValueError):
            try:
                os.kill(int(st["pid"]), signal.SIGTERM)
            except (OSError, ValueError):
                pass
        time.sleep(0.3)
    binp = os.path.join(LOCAL_DIR, f"lcu-agent-{h}")
    if not os.path.exists(binp):
        for f in os.listdir(LOCAL_DIR):
            if f.startswith("lcu-agent-"):
                try:
                    os.unlink(os.path.join(LOCAL_DIR, f))
                except OSError:
                    pass
        src = agent_sources("macos")[0]
        tmp = binp + ".tmp"
        r = subprocess.run(["swiftc", "-O", "-swift-version", "5", "-o", tmp, src], capture_output=True, text=True,
                           timeout=600)
        if r.returncode != 0:
            raise CuError("COMPILE-ERROR\n" + "\n".join(ln for ln in r.stderr.splitlines() if "error" in ln)[:2000])
        os.replace(tmp, binp)
    try:
        os.unlink(statef)
    except OSError:
        pass
    # child of this terminal: inherits its Accessibility / Screen Recording permissions
    subprocess.Popen([binp, "--idle", str(idle_minutes(t)), "--build", h, "--dir", LOCAL_DIR],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True, close_fds=True)
    deadline = time.time() + 10
    while time.time() < deadline:
        st = read_json(statef)
        if st and st.get("build") == h:
            return st
        time.sleep(0.05)
    raise CuError("START-TIMEOUT: local agent did not report within 10 s")


def newer_agent(st):
    """True if the running agent is newer than this skill copy (must not be replaced by it)."""
    try:
        return int(st.get("version", 0)) > AGENT_VERSION
    except (TypeError, ValueError):
        return False


def read_json(p):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def pid_alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, TypeError, ValueError):
        return False


def connect(name, t, fresh=False):
    """Return an open Conn to the target's agent, starting it (and the tunnel) when needed."""
    h = build_hash(t["os"] if not t.get("local") else "macos")
    st = {} if fresh else load_state(name)
    if st.get("lport") and st.get("token") and st.get("build") == h:
        try:
            c = Conn(st["lport"], st["token"])
            r = c.call("hello") if not st.get("checked") else None
            if r is None or r.get("ok"):
                if r is not None:
                    st["checked"] = True
                    save_state(name, st)
                return c, st
            c.close()
        except (OSError, ValueError):
            pass
    if t.get("local"):
        ast = local_setup(t, h)
        lport = ast["port"]
    else:
        ensure_master(name, t)
        ast = remote_setup(name, t, h)
        lport = forward(name, t, ast["port"])
    old = load_state(name)
    st = {"lport": lport, "token": ast["token"], "build": ast.get("build"), "rport": ast["port"], "pid": ast.get("pid"),
          "announced": old.get("announced") if old.get("token") == ast["token"] else False}
    c = Conn(lport, st["token"])
    r = c.call("hello")
    if not r.get("ok"):
        c.close()
        raise CuError(f"agent rejected hello: {r.get('error')}")
    st["checked"] = True
    save_state(name, st)
    return c, st


class Session:
    """One target: lazy connection, transparent reconnect once when the agent or tunnel went away."""

    def __init__(self, name, t):
        self.name, self.t = name, t
        self.conn = None
        self.st = {}

    def call(self, cmd, **args):
        if cmd in INPUT_CMDS:
            self.announce()
        for attempt in (0, 1):
            try:
                if self.conn is None:
                    self.conn, self.st = connect(self.name, self.t, fresh=attempt == 1)
                r = self.conn.call(cmd, **args)
                if not r.get("ok") and r.get("error") == "bad token" and attempt == 0:
                    raise ConnectionResetError("bad token")
                return r
            except (OSError, ValueError) as e:
                if self.conn:
                    self.conn.close()
                self.conn = None
                if attempt == 1:
                    raise CuError(f"agent unreachable: {e}")
        raise CuError("unreachable")

    def announce(self):
        if not self.t.get("announce", False):
            return
        st = load_state(self.name)
        identity = operator_name()
        if st.get("announced") == identity:
            return
        where = "auf diesem Mac" if self.t.get("local") else f"auf {self.name}"
        msg = f"{identity} steuert jetzt Maus und Tastatur {where}."
        print(f"[lan-computer-use] {msg}", file=sys.stderr)
        try:
            subprocess.Popen(["say", msg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError:
            pass
        if st:
            st["announced"] = identity
            save_state(self.name, st)
        else:
            self._announce_pending = True

    def close(self):
        if self.conn:
            if getattr(self, "_announce_pending", False):
                st = load_state(self.name)
                if st:
                    st["announced"] = operator_name()
                    save_state(self.name, st)
            self.conn.close()


def down(name, t):
    st = load_state(name)
    if t.get("local"):
        ast = read_json(os.path.join(LOCAL_DIR, "state.json"))
        if ast and pid_alive(ast.get("pid")):
            try:
                c = Conn(ast["port"], ast["token"], timeout=5)
                c.call("quit")
                c.close()
            except (OSError, ValueError):
                os.kill(int(ast["pid"]), signal.SIGTERM)
        drop_state(name)
        return "stopped"
    base, dest = ssh_base(name, t)
    if t["os"] == "windows":
        cmd = ("powershell -NoProfile -Command \"Get-Process lcu-agent* -EA 0 | Stop-Process -Force; "
               "Start-Sleep -m 300; Remove-Item $env:TEMP\\lan-computer-use -Recurse -Force -EA 0; 'STOPPED'\"")
    else:
        cmd = f"/bin/bash -c 'pkill -f lcu-agent- ; sleep 0.3; rm -rf ~/{REMOTE_MAC_DIR}; echo STOPPED'"
    try:
        ensure_master(name, t)
        rc, out, err = ssh_run(name, t, cmd, timeout=60)
    except (CuError, subprocess.TimeoutExpired) as e:
        out, err = "", str(e)
    subprocess.run(base + ["-O", "exit", dest], capture_output=True)
    drop_state(name)
    if "STOPPED" not in out:
        raise CuError(f"remote cleanup unconfirmed: {(out + err).strip()[-400:]}")
    return "stopped, agent removed, tunnel closed"


# ---------------------------------------------------------------- keys

KEY_ALIASES = {
    "control": "ctrl", "ctl": "ctrl", "^": "ctrl", "option": "alt", "opt": "alt", "⌥": "alt", "command": "cmd",
    "⌘": "cmd", "super": "cmd", "meta": "cmd", "windows": "win", "return": "enter", "↵": "enter", "escape": "esc",
    "del": "delete", "bksp": "backspace", "pgup": "pageup", "pgdn": "pagedown", "page_up": "pageup",
    "page_down": "pagedown", "arrowleft": "left", "arrowright": "right", "arrowup": "up", "arrowdown": "down",
    "spacebar": "space", "⇧": "shift", "ins": "insert",
}


def parse_combo(combo):
    s = combo.strip()
    if not s:
        raise CuError("empty key combo")
    parts = s.split("+")
    keys = []
    i = 0
    while i < len(parts):
        p = parts[i]
        if p == "" and i + 1 < len(parts) and parts[i + 1] == "":   # "cmd++" -> plus key
            keys.append("plus")
            i += 2
            continue
        if p == "":
            if i == len(parts) - 1 and keys:
                keys.append("plus")
            i += 1
            continue
        k = p.strip()
        kl = k.lower()
        keys.append(KEY_ALIASES.get(kl, kl))
        i += 1
    return keys


# ---------------------------------------------------------------- output

def q(s):
    return json.dumps(s, ensure_ascii=False)


def fmt_post(p):
    if not p:
        return "ok"
    out = f"ok · fg {q(p.get('window', ''))} ({p.get('app', '?')})"
    if p.get("focus_role"):
        out += f" · focus {p['focus_role']} {q(p.get('focus_name', ''))}"
    if p.get("desktop") not in (None, "normal", "Default"):
        out += f" · desktop {p['desktop']}"
    return out


def fmt_node(n, indent=True):
    pad = "  " * n.get("depth", 0) if indent else ""
    s = f"{pad}[{n['ref']}] {n.get('role', '?')} {q(n.get('name', ''))}"
    if "value" in n:
        s += f" ={q(n['value'])}"
    if n.get("id") and n["id"] != n.get("name"):
        s += f" #{n['id']}"
    if n.get("flags"):
        s += " " + " ".join(n["flags"])
    if n.get("rect"):
        s += " @" + ",".join(str(v) for v in n["rect"])
    return s


def fmt_win(w):
    s = f"window {q(w.get('title', ''))} ({w.get('app', '?')}) [{','.join(str(v) for v in w.get('rect', []))}]"
    s += f" handle={w.get('handle')}"
    if w.get("foreground"):
        s += " foreground"
    if w.get("minimized"):
        s += " minimized"
    return s


def save_png(r, out_path):
    data = base64.b64decode(r.pop("png"))
    if not out_path:
        d = os.path.join(CACHE, "shots")
        os.makedirs(d, mode=0o700, exist_ok=True)
        out_path = os.path.join(d, time.strftime("%Y%m%d-%H%M%S-") + f"{int(time.time() * 1000) % 1000:03d}.png")
    with open(out_path, "wb") as f:
        f.write(data)
    r["path"] = os.path.abspath(out_path)
    return r


def render(cmd, r, as_json):
    if as_json:
        return json.dumps(r, ensure_ascii=False)
    if not r.get("ok"):
        return f"error: {r.get('error')}"
    if cmd == "hello":
        perms = ", ".join(f"{k}={'yes' if v else 'NO'}" for k, v in (r.get("permissions") or {}).items())
        return (f"{r.get('os')} {r.get('os_version')} · user {r.get('user')} on {r.get('host')} · desktop "
                f"{r.get('desktop')} · screen {r.get('screen')} {r.get('units')} · agent build {r.get('build')} "
                f"pid {r.get('pid')}" + (f" · permissions {perms}" if perms else ""))
    if cmd == "task":
        if r.get("overlay") == "hidden":
            return "overlay hidden · now run cu down to release the machine"
        return f"overlay {r.get('overlay')}"
    if cmd == "hide":
        if r.get("hidden_for"):
            return f"overlay hidden for {r['hidden_for']} s (announced in the overlay first) · cu hide 0 shows it again"
        return "overlay shown again"
    if cmd == "windows":
        return "\n".join(fmt_win(w) for w in r.get("windows", [])) or "(no windows)"
    if cmd == "snapshot":
        lines = [fmt_win(r["window"])] + [fmt_node(n) for n in r.get("nodes", [])]
        if r.get("truncated"):
            lines.append("… truncated (raise --max or snapshot a narrower window)")
        return "\n".join(lines)
    if cmd in ("find", "wait"):
        lines = [fmt_node(n, indent=False) for n in r.get("nodes", [])]
        if cmd == "wait":
            lines.append(f"waited {r.get('waited')} s")
        return "\n".join(lines) or "(no match)"
    if cmd == "shot":
        return (f"{r['path']} · {r['width']}x{r['height']} px · 1 px = {r['scale']} {'pt' if r.get('units') != 'px' else 'px'}"
                f" · origin {r['origin']} (click --img X Y uses these pixels)")
    if cmd == "ocr":
        lines = [f"{q(i['text'])} @{','.join(map(str, i['rect']))} center {i['center'][0]},{i['center'][1]}"
                 for i in r.get("items", [])]
        return "\n".join(lines) or "(no text found)"
    s = fmt_post(r.get("post"))
    if r.get("at"):
        s += f" · at {r['at'][0]},{r['at'][1]}"
    if r.get("how"):
        s += f" · via {r['how']}"
    if r.get("window"):
        s += "\n" + fmt_win(r["window"])
    if r.get("note"):
        s += f"\nnote: {r['note']}"
    return s


# ---------------------------------------------------------------- commands

def sel_args(ns):
    a = {}
    if getattr(ns, "window", None):
        a["window"] = ns.window
    if getattr(ns, "app", None):
        a["app"] = ns.app
    if getattr(ns, "handle", None) is not None:
        a["handle"] = ns.handle
    return a


def settle(ns):
    return {"settle": ns.settle} if getattr(ns, "settle", None) is not None else {}


def operator_name():
    """Explicit identity wins; only session markers identify an automatic caller."""
    explicit = os.environ.get("LCU_AGENT", "").strip()
    if explicit:
        return " ".join(explicit.split())[:40]
    if os.environ.get("CODEX_THREAD_ID") or os.environ.get("CODEX_SESSION_ID"):
        return "Codex"
    if os.environ.get("CLAUDE_PID") or os.environ.get("CLAUDE_CODE_SESSION_ID"):
        return "Claude Code"
    return "AI agent"


def owner_pid():
    """An explicit long-lived local owner, or Claude's session process; never the transient CLI parent."""
    value = os.environ.get("LCU_OWNER_PID", "")
    if not value and operator_name() == "Claude Code":
        value = os.environ.get("CLAUDE_PID", "")
    return value if value.isdigit() and int(value) > 0 else ""


def session_label():
    """Overlay session label: explicit name, caller metadata, then the working directory."""
    v = os.environ.get("LCU_SESSION", "").strip()
    if v:
        return v[:40]
    if operator_name() == "Codex":
        sid = os.environ.get("CODEX_THREAD_ID") or os.environ.get("CODEX_SESSION_ID", "")
        return ("Codex " + sid[:8]) if sid else os.path.basename(os.getcwd())[:40]
    pid = os.environ.get("CLAUDE_PID", "")
    if pid.isdigit():
        meta = read_json(os.path.join(claude_home(), "sessions", f"{pid}.json")) or {}
        if isinstance(meta.get("name"), str) and meta["name"].strip():
            return meta["name"].strip()[:40]
    return os.path.basename(os.getcwd())[:40]


# ---------------------------------------------------------------- activity feed (what the controlling session does)
#
# The controlled window usually hides the agent chat that drives it. A small detached worker tails that
# session's transcript and shows its last one or two steps (chat text or tool step) below the overlay.

FEED_EVERY = 1.5     # seconds between transcript polls
FEED_RESEND = 15     # resend unchanged lines this often, so a restarted agent shows them again
FEED_CLIP = 140


def claude_home():
    return os.path.expanduser(os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude")


def transcript_path():
    """Resolve only this caller's transcript, never the newest unrelated conversation."""
    explicit = os.environ.get("LCU_TRANSCRIPT", "")
    if explicit:
        path = os.path.abspath(os.path.expanduser(explicit))
        return path if os.path.isfile(path) else None
    if operator_name() == "Codex":
        import glob
        sid = os.environ.get("CODEX_THREAD_ID") or os.environ.get("CODEX_SESSION_ID", "")
        if not re.fullmatch(r"[0-9A-Fa-f-]{8,64}", sid):
            return None
        home = os.path.expanduser(os.environ.get("CODEX_HOME") or "~/.codex")
        hits = glob.glob(os.path.join(glob.escape(home), "sessions", "*", "*", "*", f"rollout-*-{sid}.jsonl"))
        return max(hits, key=os.path.getmtime) if hits else None
    home = claude_home()
    sid = ""
    pid = os.environ.get("CLAUDE_PID", "")
    if pid.isdigit():
        meta = read_json(os.path.join(home, "sessions", f"{pid}.json")) or {}
        sid = meta.get("sessionId") if isinstance(meta.get("sessionId"), str) else ""
    sid = sid or os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    if not re.fullmatch(r"[0-9A-Fa-f-]{8,64}", sid or ""):
        return None
    import glob
    hits = glob.glob(os.path.join(glob.escape(os.path.join(home, "projects")), "*", f"{sid}.jsonl"))
    return max(hits, key=os.path.getmtime) if hits else None


def _clip_line(s, n=FEED_CLIP):
    s = re.sub(r"```.*?(```|$)", " ", s, flags=re.S)        # code blocks say nothing at a glance
    s = re.sub(r"[`*_#>|]+", "", s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)            # [text](link) -> text
    s = " ".join(s.split())
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


def entry_items(e):
    """Feed lines from one transcript entry: public chat text and tool steps, in order."""
    if isinstance(e, dict) and e.get("type") == "response_item":
        payload = e.get("payload") or {}
        if not isinstance(payload, dict):
            return []
        if payload.get("type") in ("function_call", "custom_tool_call"):
            return ["▸ " + _clip_line(str(payload.get("name") or "tool"))]
        if payload.get("type") == "message" and payload.get("role") == "assistant" and payload.get("phase") in (None, "commentary", "final", "final_answer"):
            content = payload.get("content")
            if not isinstance(content, list):
                return []
            return [_clip_line(b["text"]) for b in content
                    if isinstance(b, dict) and b.get("type") == "output_text" and isinstance(b.get("text"), str)
                    and b["text"].strip()]
        return []
    if not isinstance(e, dict) or e.get("type") != "assistant" or e.get("isSidechain"):
        return []
    content = (e.get("message") or {}).get("content")
    if not isinstance(content, list):
        return []
    out = []
    for b in content:
        if not isinstance(b, dict):
            continue
        kind = b.get("type")
        if kind == "text":
            v = _clip_line(str(b.get(kind) or ""))
            if v:
                out.append(v)
        elif kind == "tool_use":
            inp = b.get("input") if isinstance(b.get("input"), dict) else {}
            tool = str(b.get("name") or "tool")
            if isinstance(inp.get("description"), str) and inp["description"].strip():
                v = inp["description"]
            elif isinstance(inp.get("file_path"), str):
                v = f"{tool} {os.path.basename(inp['file_path'])}"
            elif isinstance(inp.get("command"), str) and inp["command"].strip():
                v = f"{tool}: {inp['command'].strip().splitlines()[0][:80]}"
            elif isinstance(inp.get("pattern"), str):
                v = f"{tool} {inp['pattern']}"
            else:
                v = tool
            out.append("▸ " + _clip_line(v))
    return out


def recent_activity(path, n=2, tail=512 * 1024):
    """The last n feed lines of a transcript, oldest first."""
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - tail))
            data = f.read()
    except OSError:
        return []
    lines = data.split(b"\n")
    if size > tail:
        lines = lines[1:]   # the first line is cut
    found = []
    for raw in reversed(lines):
        if not raw.strip():
            continue
        try:
            items = entry_items(json.loads(raw))
        except ValueError:
            continue
        for v in reversed(items):
            found.append(v)
            if len(found) >= n:
                return found[::-1]
    return found[::-1]


class ActivityCache:
    """Avoid reading and parsing an unchanged transcript on every feed tick."""

    def __init__(self):
        self.signature = None
        self.lines = []

    def read(self, path):
        try:
            st = os.stat(path)
            signature = (path, st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)
        except OSError:
            self.signature, self.lines = None, []
            return []
        if signature != self.signature:
            self.lines = recent_activity(path)
            self.signature = signature
        return self.lines


def feed_worker(name, owner, path):
    """Detached: push the session's latest activity to the overlay until the lease ends or the session is gone."""
    me, last, sent_at, fails = os.getpid(), None, 0.0, 0
    activity = ActivityCache()
    time.sleep(0.5)
    while True:
        st = load_state(name)
        end = st.get("eta_end")
        if st.get("feed_pid") != me or not end or time.time() > end + LEASE_GRACE or (owner and not pid_alive(owner)):
            return 0
        lines = activity.read(path)
        if lines and (lines != last or time.time() - sent_at > FEED_RESEND):
            try:
                c = Conn(st["lport"], st["token"], timeout=5)
                try:
                    c.call("note", lines=lines)
                finally:
                    c.close()
                last, sent_at, fails = lines, time.time(), 0
            except (OSError, ValueError, KeyError):
                fails += 1
                if fails >= 5:
                    return 1
        time.sleep(FEED_EVERY)


def start_feed(name):
    """Start (or keep) the activity feed worker for this target; LCU_FEED=0 turns it off."""
    if os.environ.get("LCU_FEED", "1") == "0":
        return
    owner = owner_pid()
    path = transcript_path()
    if not path:
        return
    st = load_state(name)
    if st.get("feed_pid") and pid_alive(st["feed_pid"]) and st.get("feed_path") == path:
        return
    p = subprocess.Popen([sys.executable, os.path.abspath(__file__), "_feed", name, owner, path],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    st = load_state(name)
    st["feed_pid"], st["feed_path"] = p.pid, path
    save_state(name, st)


def eta_hint(name, cmd, now=None):
    """Nudge the controlling session to keep the overlay's ETA honest (stderr, one line), or None."""
    if cmd not in INPUT_CMDS:
        return None
    st = load_state(name)
    end = st.get("eta_end")
    if not end:
        return ('no control lease: run cu task "WHAT" --eta DURATION (at most 5m) before any input')
    left = end - (now or time.time())
    if left > 45:
        return None
    if left > 0:
        return (f"control lease ends in {int(left)} s: if more work is left, renew now with cu task --eta DURATION "
                "(at most 5m), otherwise finish with cu task --done and cu down")
    over = -left
    return (f"control lease expired {int(over) // 60}:{int(over) % 60:02d} ago: input is refused, renew with "
            "cu task --eta DURATION (at most 5m) or finish with cu task --done and cu down")


def parse_duration(v):
    """'90', '90s', '5m', '1h' -> seconds."""
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([smh]?)\s*", str(v))
    if not m:
        raise CuError(f"bad duration '{v}' (use e.g. 90s, 5m, 1h)")
    return int(float(m.group(1)) * {"": 1, "s": 1, "m": 60, "h": 3600}[m.group(2)])


REF_RE = re.compile(r"@?e\d+")


def coord_or_ref(v):
    """First positional of click/move/scroll: a number, or a snapshot ref (e3, @e3) as in agent-browser."""
    if REF_RE.fullmatch(v):
        return v.lstrip("@")
    return float(v)


def normalize_refs(ns):
    if isinstance(getattr(ns, "x", None), str):
        if getattr(ns, "y", None) is not None:
            raise CuError("give either a ref or X Y")
        ns.ref, ns.x = ns.x, None
    elif getattr(ns, "x", None) is not None and getattr(ns, "y", None) is None and ns.cmd != "drag":
        raise CuError("X needs Y")
    if isinstance(getattr(ns, "ref", None), str):
        ns.ref = ns.ref.lstrip("@")
    return ns


def coord_args(ns, xs=("x", "y")):
    a = {}
    for k in xs:
        a[k] = getattr(ns, k)
    if ns.img:
        a["img"] = True
    elif ns.window or ns.app or ns.handle is not None:
        a["local"] = True
    return a


def click_text(sess, ns, osname, extra):
    sel = sel_args(ns)
    r = sess.call("find", text=ns.text, max=20, **sel)
    if not r.get("ok"):
        return r
    nodes = [n for n in r.get("nodes", []) if n.get("rect") and "disabled" not in n.get("flags", [])]
    exact = [n for n in nodes if n.get("name", "").strip().lower() == ns.text.strip().lower()]
    actionable = {"button", "link", "checkbox", "radio", "tab", "menuitem", "listitem", "treeitem", "textfield",
                  "searchfield", "popup", "combobox", "menubutton", "splitbutton", "cell", "row"}
    pool = exact or nodes
    pool.sort(key=lambda n: (n.get("role") not in actionable, n["rect"][2] * n["rect"][3]))
    if pool:
        res = sess.call("click", ref=pool[0]["ref"], **extra)
        res["matched"] = {"via": "accessibility", "node": pool[0]}
        return res
    if osname != "macos":
        return {"ok": False, "error": f"no accessible element with text {q(ns.text)} (no OCR fallback on Windows: "
                                      f"shot + click --img)"}
    r = sess.call("ocr", text=ns.text, **sel)
    if not r.get("ok"):
        return r
    items = r.get("items", [])
    if not items:
        return {"ok": False, "error": f"text {q(ns.text)} found neither in the accessibility tree nor by OCR"}
    items.sort(key=lambda i: (i["text"].strip().lower() != ns.text.strip().lower(), -i.get("conf", 0)))
    x, y = items[0]["center"]
    res = sess.call("click", x=x, y=y, **extra)
    res["matched"] = {"via": "ocr", "item": items[0]}
    return res


def run_cmd(sess, ns, osname):
    c = ns.cmd
    if c == "hello":
        return sess.call("hello")
    if c == "windows":
        return sess.call("windows", all=ns.all)
    if c == "snapshot":
        r = sess.call("snapshot", max=ns.max, depth=ns.depth, all=ns.all,
                      interactive=ns.interactive, **sel_args(ns))
        if ns.interactive and not ns.rects:  # refs are enough to act on; rects cost ~30 % of the tokens
            for n in r.get("nodes", []):
                n.pop("rect", None)
        return r
    if c == "task":
        if ns.done:
            r = sess.call("task", done=True)
            st = load_state(sess.name)
            if st.pop("eta_end", None) is not None:
                save_state(sess.name, st)
            return r
        if not ns.eta:
            raise CuError("task needs --eta: estimate realistically how long the whole remaining work takes "
                          "(e.g. --eta 4m), the person at the machine plans around it")
        eta = parse_duration(ns.eta)
        if eta <= 0:
            raise CuError("--eta must be greater than zero")
        if eta > LEASE_MAX:
            raise CuError(f"--eta {ns.eta} is over the {LEASE_MAX // 60}m limit of one control lease: plan the work in "
                          "chunks of at most 5 minutes and renew with cu task --eta before the lease ends")
        a = dict(text=ns.text, eta=eta, session=session_label(), operator=operator_name())
        owner = owner_pid()
        if sess.t.get("local"):
            a["owner_pid"] = int(owner or "0")  # clear a previous caller's owner when none is known
        r = sess.call("task", **a)
        st = load_state(sess.name)
        if st and r.get("ok"):
            st["eta_end"] = time.time() + eta
            save_state(sess.name, st)
            start_feed(sess.name)
        return r
    if c == "hide":
        secs = 0 if ns.duration in ("0", "off") else parse_duration(ns.duration)
        r = sess.call("hide", secs=secs)
        if r.get("ok") and r.get("notice"):
            time.sleep(float(r["notice"]) + 0.1)   # return once the announcement ran and the overlay is gone
        return r
    if c in ("find", "wait"):
        a = dict(text=ns.text, role=ns.role, id=ns.id, exact=ns.exact, max=ns.max, **sel_args(ns))
        if c == "wait":
            a.update(timeout=ns.timeout, gone=ns.gone)
        if not (ns.text or ns.role or ns.id):
            raise CuError(f"{c} needs TEXT, --role or --id")
        return sess.call(c, **a)
    if c == "shot":
        a = dict(max=ns.max, ref=ns.ref, **sel_args(ns))
        if ns.region:
            a["region"] = [int(v) for v in ns.region.split(",")]
        r = sess.call("shot", **a)
        return save_png(r, ns.output) if r.get("ok") else r
    if c == "ocr":
        if osname != "macos":
            raise CuError("ocr is available on macOS targets only (Vision framework)")
        a = dict(text=ns.text, fast=ns.fast, **sel_args(ns))
        if ns.region:
            a["region"] = [int(v) for v in ns.region.split(",")]
        return sess.call("ocr", **a)
    if c == "click":
        extra = dict(button=ns.button if ns.button != "left" else None, double=ns.double, **settle(ns))
        if ns.text:
            return click_text(sess, ns, osname, extra)
        if ns.ref:
            return sess.call("click", ref=ns.ref, **extra)
        if ns.x is None or ns.y is None:
            raise CuError("click needs X Y, --ref or --text")
        return sess.call("click", **coord_args(ns), **sel_args(ns), **extra)
    if c == "move":
        if ns.ref:
            return sess.call("move", ref=ns.ref, **settle(ns))
        return sess.call("move", **coord_args(ns), **sel_args(ns), **settle(ns))
    if c == "drag":
        return sess.call("drag", **coord_args(ns, ("x", "y", "x2", "y2")), **sel_args(ns), **settle(ns))
    if c == "scroll":
        a = dict(dy=ns.dy, dx=ns.dx, **settle(ns))
        if ns.ref:
            a["ref"] = ns.ref
        elif ns.x is not None:
            a.update(coord_args(ns), **sel_args(ns))
        return sess.call("scroll", **a)
    if c == "press":
        return sess.call("press", ref=ns.ref, **settle(ns))
    if c == "focus":
        return sess.call("focus", ref=ns.ref, **settle(ns))
    if c == "set-value":
        return sess.call("set-value", ref=ns.ref, text=read_text(ns.text), password_ok=ns.password_ok, **settle(ns))
    if c == "type":
        return sess.call("type", text=read_text(ns.text), ref=ns.ref, password_ok=ns.password_ok, **settle(ns))
    if c == "key":
        r = None
        for combo in ns.combos:
            r = sess.call("key", keys=parse_combo(combo), times=ns.times if ns.times > 1 else None, **settle(ns))
            if not r.get("ok"):
                return r
        return r
    if c == "activate":
        if not (ns.window or ns.app or ns.handle is not None):
            raise CuError("activate needs --window, --app or --handle")
        return sess.call("activate", **sel_args(ns), **settle(ns))
    if c == "launch":
        return sess.call("launch", target=ns.app, args=ns.args, wait=ns.wait, timeout=ns.timeout, **settle(ns))
    raise CuError(f"unknown command {c}")


def read_text(t):
    return sys.stdin.read() if t == "-" else t


def batch(sess, as_json):
    """Raw JSON request lines on stdin ({"cmd": ..., args}), one response line each; stops at the first error."""
    rc = 0
    for line in sys.stdin:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        req = json.loads(line)
        cmd = req.pop("cmd")
        out = req.pop("out", None)
        r = sess.call(cmd, **req)
        if cmd == "shot" and r.get("ok"):
            save_png(r, out)
        print(render(cmd, r, as_json), flush=True)
        if not r.get("ok"):
            rc = 1
            break
    return rc


# ---------------------------------------------------------------- CLI

def build_parser():
    p = argparse.ArgumentParser(prog="cu.py", description="GUI control of the local Mac or LAN machines over SSH.")
    p.add_argument("-t", "--target", help="target name (default: config 'default' or 'local')")
    p.add_argument("--json", action="store_true", help="print the raw agent response as JSON")
    sub = p.add_subparsers(dest="cmd", required=True)

    def sel(sp, coords=False):
        sp.add_argument("--window", "-w", help="window title substring (default: foreground window)")
        sp.add_argument("--app", "-a", help="app: process name, macOS app name or bundle id")
        sp.add_argument("--handle", type=int, help="window handle from `windows`")
        if coords:
            sp.add_argument("--img", action="store_true", help="X Y are pixels of the last `shot`")

    def st(sp):
        sp.add_argument("--settle", type=int, help="ms to wait after the action before reading the state")

    sub.add_parser("up", help="start agent + tunnel (all other commands do this on demand)")
    sub.add_parser("down", help="stop the agent, remove it from the target, close the tunnel")
    sub.add_parser("status", help="client-side session state (no secrets)")
    sub.add_parser("targets", help="list configured targets")
    sub.add_parser("hello", help="OS, user, desktop state, screen, permissions")
    sp = sub.add_parser("windows", help="list top-level windows")
    sp.add_argument("--all", action="store_true")
    sp = sub.add_parser("snapshot", help="accessibility tree of a window with refs [eN]")
    sel(sp)
    sp.add_argument("--max", type=int, default=250)
    sp.add_argument("--depth", type=int)
    sp.add_argument("--all", action="store_true", help="include elements scrolled out of the window")
    sp.add_argument("-i", "--interactive", action="store_true", help="only clickable/editable elements, flat")
    sp.add_argument("--rects", action="store_true", help="with -i: keep the @x,y,w,h rectangles")
    sp = sub.add_parser("task", help="overlay on the target: what the agent is doing and for how long")
    sp.add_argument("text", nargs="?", help="short task description shown in the overlay")
    sp.add_argument("--eta", help="required: realistic estimate of the whole remaining work, e.g. 90s, 5m, 1h "
                    "(countdown); repeat with a new estimate when it runs out")
    sp.add_argument("--done", action="store_true", help="task finished: hide the overlay")
    sp = sub.add_parser("hide", help="hide the overlay for a while (announced in it first, max 60s, not in the first "
                        "5s of a task); 0 shows it again")
    sp.add_argument("duration", help="e.g. 15s; 0 or off shows the overlay again")
    for name in ("find", "wait"):
        sp = sub.add_parser(name, help="search elements" if name == "find" else "wait until an element (dis)appears")
        sel(sp)
        sp.add_argument("text", nargs="?", help="substring of name or value")
        sp.add_argument("--role")
        sp.add_argument("--id", help="automation id / DOM id / testID")
        sp.add_argument("--exact", action="store_true")
        sp.add_argument("--max", type=int, default=20)
        if name == "wait":
            sp.add_argument("--timeout", type=float, default=10)
            sp.add_argument("--gone", action="store_true")
    sp = sub.add_parser("shot", help="screenshot (screen, window, element or region) to PNG")
    sel(sp)
    sp.add_argument("--ref")
    sp.add_argument("--region", help="x,y,w,h in screen units")
    sp.add_argument("--max", type=int, default=1280, help="longest side in px (0 = native)")
    sp.add_argument("-o", "--output")
    sp = sub.add_parser("ocr", help="(macOS) recognized text with screen coordinates")
    sel(sp)
    sp.add_argument("text", nargs="?", help="only lines containing this text")
    sp.add_argument("--region")
    sp.add_argument("--fast", action="store_true")
    sp = sub.add_parser("click", help="click X Y | --ref eN | --text T")
    sel(sp, coords=True)
    st(sp)
    sp.add_argument("x", type=coord_or_ref, nargs="?", help="X, or a ref like e3 / @e3")
    sp.add_argument("y", type=float, nargs="?")
    sp.add_argument("--ref")
    sp.add_argument("--text", help="accessible name, falls back to OCR on macOS")
    sp.add_argument("--button", choices=["left", "right", "middle"], default="left")
    sp.add_argument("--right", dest="button", action="store_const", const="right")
    sp.add_argument("--double", action="store_true")
    sp = sub.add_parser("move", help="move the pointer (hover)")
    sel(sp, coords=True)
    st(sp)
    sp.add_argument("x", type=coord_or_ref, nargs="?", help="X, or a ref like e3 / @e3")
    sp.add_argument("y", type=float, nargs="?")
    sp.add_argument("--ref")
    sp = sub.add_parser("drag", help="drag X Y X2 Y2 with the left button")
    sel(sp, coords=True)
    st(sp)
    for k in ("x", "y", "x2", "y2"):
        sp.add_argument(k, type=float)
    sp = sub.add_parser("scroll", help="scroll --dy N (down) / --dx N (right) notches")
    sel(sp, coords=True)
    st(sp)
    sp.add_argument("x", type=coord_or_ref, nargs="?", help="X, or a ref like e3 / @e3")
    sp.add_argument("y", type=float, nargs="?")
    sp.add_argument("--ref")
    sp.add_argument("--dy", type=int, default=0)
    sp.add_argument("--dx", type=int, default=0)
    for name, hlp in (("press", "invoke an element (button press) without the mouse"),
                      ("focus", "focus an element")):
        sp = sub.add_parser(name, help=hlp)
        st(sp)
        sp.add_argument("ref")
    sp = sub.add_parser("set-value", help="replace a field's text (ref from snapshot/find)")
    st(sp)
    sp.add_argument("ref")
    sp.add_argument("text", help="'-' reads stdin")
    sp.add_argument("--password-ok", action="store_true", help="only with the user's explicit consent")
    sp = sub.add_parser("type", help="type text into the focused element (or --ref)")
    st(sp)
    sp.add_argument("text", help="'-' reads stdin")
    sp.add_argument("--ref")
    sp.add_argument("--password-ok", action="store_true", help="only with the user's explicit consent")
    sp = sub.add_parser("key", help="key combos in sequence, e.g. cmd+shift+t enter")
    st(sp)
    sp.add_argument("combos", nargs="+")
    sp.add_argument("--times", type=int, default=1)
    sp = sub.add_parser("activate", help="bring a window/app to the front (restores minimized)")
    sel(sp)
    st(sp)
    sp = sub.add_parser("launch", help="start an app (path, app name, bundle id; Windows: exe/AUMID)")
    st(sp)
    sp.add_argument("app", help="what to start")
    sp.add_argument("--args")
    sp.add_argument("--wait", help="window title to wait for")
    sp.add_argument("--timeout", type=float, default=15)
    sub.add_parser("batch", help="raw JSON request lines from stdin, one connection")
    return p


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["_feed"] and len(argv) == 4 and argv[2].isdigit():
        return feed_worker(argv[1], int(argv[2]), argv[3])
    ns = build_parser().parse_args(argv)
    try:
        normalize_refs(ns)
        targets, default = load_targets()
        if ns.cmd == "targets":
            for n, t in targets.items():
                mark = " (default)" if n == default else ""
                where = "this Mac" if t.get("local") else f"{t.get('user', '')}@{t.get('host')}"
                print(f"{n}{mark}: {t.get('os')} · {where}")
            return 0
        name = ns.target or os.environ.get("LCU_TARGET") or default
        t = targets[name] if name in targets else alias_target(name)
        validate_target(name, t)
        osname = "macos" if t.get("local") else t["os"]
        if ns.cmd == "down":
            print(down(name, t))
            return 0
        if ns.cmd == "status":
            st = load_state(name)
            if not st:
                print(f"{name}: no session")
            else:
                print(f"{name}: session on local port {st.get('lport')} · agent build {st.get('build')} pid {st.get('pid')}"
                      f" · announced {'yes' if st.get('announced') else 'no'}")
            return 0
        sess = Session(name, t)
        try:
            if ns.cmd == "up":
                r = sess.call("hello")
                print(render("hello", r, ns.json))
                return 0 if r.get("ok") else 1
            if ns.cmd == "batch":
                return batch(sess, ns.json)
            t0 = time.time()
            r = run_cmd(sess, ns, osname)
            hint = eta_hint(name, ns.cmd) if r.get("ok") else None
            if hint:
                print(f"[lan-computer-use] {hint}", file=sys.stderr)
            if os.environ.get("LCU_TIMING"):
                print(f"[{(time.time() - t0) * 1000:.0f} ms]", file=sys.stderr)
            if ns.json:
                print(json.dumps(r, ensure_ascii=False))
            else:
                print(render(ns.cmd, r, False))
                if r.get("matched"):
                    m = r["matched"]
                    print(f"matched via {m['via']}: " + (fmt_node(m["node"], False) if "node" in m else q(m["item"]["text"])))
            return 0 if r.get("ok") else 1
        finally:
            sess.close()
    except CuError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except subprocess.TimeoutExpired as e:
        print(f"error: timeout: {shlex.join(e.cmd) if isinstance(e.cmd, list) else e.cmd}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
