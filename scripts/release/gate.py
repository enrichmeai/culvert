"""Decide whether a push to main (or a manual run) releases Culvert.

Used by .github/workflows/publish-pypi.yml and publish-maven.yml (RELEASE.md
§ "Automatic release"). Prints its reasoning and writes `version`, `release`
and `tag` to $GITHUB_OUTPUT. Exits 1 when a release PR is malformed or a
registry cannot be read, so a release never fails silently.

  python3 scripts/release/gate.py pypi|maven --event push --before <sha>
  python3 scripts/release/gate.py pypi|maven --event workflow_dispatch --confirm <phrase> --ref <ref>
"""
import argparse
import os
import re
import subprocess
import sys
import tomllib
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

POM_NS = {"m": "http://maven.apache.org/POM/4.0.0"}
PYTHON_META = "python-culvert/pyproject.toml"
JAVA_PARENT = "data-pipeline-libraries-java/pom.xml"
CONFIRM = {"pypi": "publish-culvert", "maven": "publish-maven"}
VERSION_FILE = {"pypi": PYTHON_META, "maven": JAVA_PARENT}
PLAIN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


class GateError(Exception):
    pass


def pyproject_version(text, where):
    try:
        return tomllib.loads(text)["project"]["version"]
    except (tomllib.TOMLDecodeError, KeyError) as e:
        raise GateError(f"{where}: no readable [project] version ({e})") from e


def _pom_text(text, path, where):
    try:
        return ET.fromstring(text).find(path, POM_NS).text
    except (ET.ParseError, AttributeError) as e:
        raise GateError(f"{where}: no readable {path.replace('m:', '')} ({e})") from e


def pom_version(text, where):
    return _pom_text(text, "m:version", where)


def pom_parent_version(text, where):
    return _pom_text(text, "m:parent/m:version", where)


def versions(root):
    """Every version a release must set, keyed by file."""
    found = {PYTHON_META: pyproject_version((root / PYTHON_META).read_text(), PYTHON_META)}
    for p in sorted(root.glob("data-pipeline-libraries/*/pyproject.toml")):
        name = str(p.relative_to(root))
        found[name] = pyproject_version(p.read_text(), name)
    found[JAVA_PARENT] = pom_version((root / JAVA_PARENT).read_text(), JAVA_PARENT)
    for p in sorted(root.glob("data-pipeline-libraries-java/*/pom.xml")):
        name = str(p.relative_to(root))
        found[name] = pom_parent_version(p.read_text(), name)
    return found


def changelog_has(root, version):
    heading = f"## [{version}]"
    return any(line.startswith(heading)
               for line in (root / "CHANGELOG.md").read_text().splitlines())


def http_get(url):
    """(status, body). Retries transient failures."""
    last = None
    for _ in range(3):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return r.status, r.read().decode()
        except urllib.error.HTTPError as e:
            if e.code < 500 and e.code != 429:
                return e.code, ""
            last = e.code
        except OSError as e:
            last = e
    return last, ""


def published(target, version, get=http_get):
    if target == "pypi":
        status, _ = get(f"https://pypi.org/pypi/culvert/{version}/json")
        if status == 200:
            return True
        if status == 404:
            return False
        raise GateError(f"PyPI answered {status!r} for culvert {version}; not deciding blind")
    status, body = get("https://repo1.maven.org/maven2/com/enrichmeai/culvert/"
                       "data-pipeline-core/maven-metadata.xml")
    if status != 200 or not body:
        raise GateError(f"Maven Central metadata answered {status!r}; not deciding blind")
    return f"<version>{version}</version>" in body


def version_before(root, target, before):
    """The version file's version at `before`, or None if it cannot be read."""
    if not before or set(before) == {"0"}:
        return None
    path = VERSION_FILE[target]
    try:
        text = subprocess.run(["git", "-C", str(root), "show", f"{before}:{path}"],
                              check=True, capture_output=True, text=True).stdout
    except subprocess.CalledProcessError:
        return None
    where = f"{path} at {before[:12]}"
    return pyproject_version(text, where) if target == "pypi" else pom_version(text, where)


def decide(target, event, root, confirm="", before="", ref="refs/heads/main",
           get=http_get, log=print):
    """Return (version, release, tag)."""
    if ref != "refs/heads/main":
        raise GateError(f"releases run from main only, not {ref}")
    found = versions(root)
    version = found[VERSION_FILE[target]]
    log(f"{target}: version {version}")

    if event == "workflow_dispatch":
        if confirm != CONFIRM[target]:
            log(f"confirm phrase is not {CONFIRM[target]!r}: nothing to do")
            return version, False, False
    else:
        if not PLAIN.match(version):
            log(f"not a release version: {version}")
            return version, False, False
        previous = version_before(root, target, before)
        if previous == version:
            log(f"{VERSION_FILE[target]} changed but its version is still {version}: not a release")
            return version, False, False
        log(f"version changed: {previous} -> {version}")

    if published(target, version, get):
        log(f"{version} is already published on {target}")
        # PyPI: the GitHub Release may still be missing (a failed tag job).
        return version, False, target == "pypi"

    if event != "workflow_dispatch":
        if not changelog_has(root, version):
            raise GateError(f"CHANGELOG.md has no '## [{version}]' section; the release PR must write it")
        odd = {f: v for f, v in found.items() if v != version}
        if odd:
            raise GateError("a release carries one version, but these differ from "
                            f"{version}: " + ", ".join(f"{f}={v}" for f, v in odd.items()))
    return version, True, target == "pypi"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("target", choices=["pypi", "maven"])
    ap.add_argument("--event", required=True)
    ap.add_argument("--confirm", default="")
    ap.add_argument("--before", default="")
    ap.add_argument("--ref", default="refs/heads/main")
    ap.add_argument("--root", default=".")
    a = ap.parse_args(argv)
    try:
        version, release, tag = decide(a.target, a.event, Path(a.root), a.confirm, a.before, a.ref)
    except GateError as e:
        print(f"::error::{e}")
        return 1
    out = f"version={version}\nrelease={str(release).lower()}\ntag={str(tag).lower()}\n"
    print(out, end="")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
