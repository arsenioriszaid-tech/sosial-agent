"""Shared helpers for sosial-agent V0 dry-run scripts (stdlib only)."""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# V0 never performs these: scripts refuse flags/commands matching them,
# and validate.py scans all outputs for them.
FORBIDDEN_ACTION_PATTERNS = [
    "auto-publish", "autopublish", "auto publish",
    "auto-reply", "auto reply", "mass like", "mass follow",
    "rate-limit bypass", "rate limit bypass", "captcha",
    "paid promotion", "purchased engagement",
]
CREDENTIAL_PATTERNS = [
    "api_key", "apikey", "api-secret", "password", "session token",
    "session_token", "auth header", "authorization: bearer",
    "private key", "private_key", "cookie:",
]
# Generic-hype markers per CONTENT-RULES.md (specific observation > generic opinion).
HYPE_PATTERNS = [
    "will change everything", "revolutionary", "game-changer", "game changer",
    "mind-blowing", "mindblowing", "10x", "100x", "the future is here",
    "you won't believe", "secret trick", "viral",
    "akan mengubah segalanya", "mengubah segalanya",
]
# Engagement/controversy-bait markers. Heuristic only: they trigger SKIP
# solely when combined with thin substance (depth != analysis), never alone.
BAIT_PATTERNS = [
    "everyone is wrong", "unpopular opinion", "hot take",
    "nobody is talking about", "nobody talks about",
    "you're doing it wrong", "stop doing", "will shock you",
    "semua orang salah", "pendapat kontroversial",
    "tidak ada yang membicarakan",
]

CANDIDATE_STATES_V0 = {"DISCOVERED", "QUALIFIED", "NEEDS_REVIEW", "IRRELEVANT"}
# CONTACTED and beyond are post-human states; a V0 dry-run must never emit them.
POST_HUMAN_STATES = {"CONTACTED", "RESPONDED", "TEST_SCHEDULED", "TESTED", "NOT_INTERESTED"}


def refuse_forbidden_flags(argv):
    bad = [a for a in argv if a.strip("--").replace("-", " ").replace("_", " ") in
           {"publish", "send", "reply", "follow", "like", "dm", "delete", "promote"}]
    if bad:
        print(f"REFUSED: V0 is research/draft/qualify only (human-review boundary). "
              f"Flag(s) not allowed: {bad}", file=sys.stderr)
        sys.exit(2)


def utc_today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def sha_short(path):
    h = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return h[:12], h


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


# --- Minimal YAML subset parser (covers current config/ shapes; no dependency) ---
def _scalar(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def parse_simple_yaml(text):
    """Parse indent-based YAML subset: nested maps, lists of scalars,
    lists of maps (one key on the '-' line, rest on deeper lines)."""
    return _repair_lists(text)


def _repair_lists(text):
    """Line-oriented re-parse that correctly builds lists under keys."""
    root = {}
    stack: list = [(-1, root)]  # (indent, node: dict | list)
    pending = {}               # id(dict) -> [key, key_indent] for last empty 'k:'
    placeholders = set()       # ids of empty-dict placeholders (may become lists)

    raw_lines = [l for l in text.splitlines()
                 if l.strip() and not l.strip().startswith("#")]
    i = 0
    while i < len(raw_lines):
        raw = raw_lines[i]
        indent = len(raw) - len(raw.lstrip(" "))
        content = raw.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        node = stack[-1][1]
        if content.startswith("- "):
            rest = content[2:].strip()
            if isinstance(node, dict):
                if id(node) in placeholders and not node:
                    # empty placeholder -> it was a list child after all
                    placeholders.discard(id(node))
                    parent = stack[-2][1]
                    key, kindent = pending.pop(id(parent))
                    lst: list = []
                    parent[key] = lst
                    stack.pop()
                    stack.append((kindent, lst))
                    node = lst
                else:
                    key, kindent = pending.pop(id(node))
                    lst = []
                    node[key] = lst
                    stack.append((kindent, lst))
                    node = lst
            if ":" in rest:
                k, v = rest.split(":", 1)
                item = {_scalar(k): _scalar(v) if v.strip() else None}
                node.append(item)
                # deeper continuation lines belong to item
                j = i + 1
                while j < len(raw_lines):
                    nraw = raw_lines[j]
                    nindent = len(nraw) - len(nraw.lstrip(" "))
                    ncontent = nraw.strip()
                    if nindent <= indent or ncontent.startswith("- "):
                        break
                    if ":" in ncontent:
                        nk, nv = ncontent.split(":", 1)
                        item[_scalar(nk)] = _scalar(nv) if nv.strip() else None
                    j += 1
                i = j
                continue
            node.append(_scalar(rest))
        elif ":" in content:
            k, v = content.split(":", 1)
            key, val = _scalar(k), v.strip()
            if isinstance(node, list):
                # continuation of '- k: v' item
                node[-1][key] = _scalar(val) if val else None
            else:
                placeholders.discard(id(node))
                if val == "":
                    node[key] = {}
                    pending[id(node)] = [key, indent]
                    placeholders.add(id(node[key]))
                    stack.append((indent, node[key]))
                else:
                    node[key] = _scalar(val)
        i += 1
    return root


def load_yaml(path):
    return parse_simple_yaml(Path(path).read_text(encoding="utf-8"))


def write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
