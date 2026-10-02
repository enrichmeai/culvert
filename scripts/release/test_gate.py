"""Table tests for scripts/release/gate.py: python3 -m unittest scripts/release/test_gate.py"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import gate  # noqa: E402

POM = """<project xmlns="http://maven.apache.org/POM/4.0.0"><version>{v}</version></project>"""
CHILD = """<project xmlns="http://maven.apache.org/POM/4.0.0"><parent><version>{v}</version></parent></project>"""
PYPROJECT = '[project]\nname = "x"\nversion = "{v}"\n'


def registry(pypi=404, maven_versions=("0.1.0",)):
    def get(url):
        if "pypi.org" in url:
            return pypi, ""
        if maven_versions is None:
            return 503, ""
        return 200, "".join(f"<version>{v}</version>" for v in maven_versions)
    return get


class GateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.git("init", "-q")
        self.write("0.1.0", changelog="## [0.1.0] — 2026-01-01\n")
        self.before = self.commit()

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def commit(self):
        self.git("add", "-A")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "c")
        return self.git("rev-parse", "HEAD")

    def write(self, v, changelog=None, java=None, core=None, child=None):
        files = {
            "python-culvert/pyproject.toml": PYPROJECT.format(v=v),
            "data-pipeline-libraries/data-pipeline-core/pyproject.toml": PYPROJECT.format(v=core or v),
            "data-pipeline-libraries-java/pom.xml": POM.format(v=java or v),
            "data-pipeline-libraries-java/data-pipeline-core-java/pom.xml": CHILD.format(v=child or java or v),
        }
        if changelog is not None:
            files["CHANGELOG.md"] = changelog
        for name, text in files.items():
            (self.root / name).parent.mkdir(parents=True, exist_ok=True)
            (self.root / name).write_text(text)

    def release_pr(self, **kw):
        kw.setdefault("changelog", "## [Unreleased]\n\n## [0.2.0] — 2026-02-01\n- x\n\n## [0.1.0]\n")
        self.write("0.2.0", **kw)
        self.commit()

    def decide(self, target, get, event="push", confirm="", ref="refs/heads/main"):
        return gate.decide(target, event, self.root, confirm=confirm, before=self.before,
                           ref=ref, get=get, log=lambda *_: None)

    def test_release_pr_releases_on_both(self):
        self.release_pr()
        self.assertEqual(self.decide("pypi", registry()), ("0.2.0", True, True))
        self.assertEqual(self.decide("maven", registry()), ("0.2.0", True, False))

    def test_unchanged_version_is_a_noop_even_while_central_awaits_publish(self):
        self.release_pr()
        self.before = self.commit_dependency_bump()
        # 0.2.0 sits in Central's validation stage: not yet in maven-metadata.xml.
        self.assertEqual(self.decide("maven", registry()), ("0.2.0", False, False))
        self.assertEqual(self.decide("pypi", registry(pypi=200)), ("0.2.0", False, False))

    def commit_dependency_bump(self):
        head = self.git("rev-parse", "HEAD")
        p = self.root / "python-culvert/pyproject.toml"
        p.write_text(p.read_text() + 'dependencies = ["y"]\n')
        self.commit()
        return head

    def test_already_on_pypi_skips_publish_but_still_tags(self):
        self.release_pr()
        self.assertEqual(self.decide("pypi", registry(pypi=200)), ("0.2.0", False, True))

    def test_already_on_central_skips(self):
        self.release_pr()
        self.assertEqual(self.decide("maven", registry(maven_versions=("0.2.0",))), ("0.2.0", False, False))

    def test_dev_version_is_not_a_release(self):
        self.write("0.3.0.dev0")
        self.commit()
        self.assertEqual(self.decide("pypi", registry()), ("0.3.0.dev0", False, False))

    def test_missing_changelog_section_fails(self):
        self.release_pr(changelog="## [Unreleased]\n## [0.1.0]\n")
        with self.assertRaisesRegex(gate.GateError, "CHANGELOG"):
            self.decide("pypi", registry())

    def test_changelog_heading_is_matched_literally(self):
        self.release_pr(changelog="## [0x2y0]\n")
        with self.assertRaisesRegex(gate.GateError, "CHANGELOG"):
            self.decide("maven", registry())

    def test_java_python_mismatch_fails(self):
        self.release_pr(java="0.1.0")
        with self.assertRaisesRegex(gate.GateError, "data-pipeline-libraries-java/pom.xml=0.1.0"):
            self.decide("pypi", registry())

    def test_python_package_left_behind_fails(self):
        self.release_pr(core="0.1.0")
        with self.assertRaisesRegex(gate.GateError, "data-pipeline-core/pyproject.toml=0.1.0"):
            self.decide("maven", registry())

    def test_java_child_left_behind_fails(self):
        self.release_pr(child="0.1.0")
        with self.assertRaisesRegex(gate.GateError, "data-pipeline-core-java/pom.xml=0.1.0"):
            self.decide("pypi", registry())

    def test_registry_errors_fail_loudly(self):
        self.release_pr()
        for status in (500, 429, None):
            with self.subTest(status=status):
                with self.assertRaisesRegex(gate.GateError, "PyPI answered"):
                    self.decide("pypi", registry(pypi=status))
        with self.assertRaisesRegex(gate.GateError, "Maven Central metadata"):
            self.decide("maven", registry(maven_versions=None))

    def test_dispatch_needs_the_confirm_phrase(self):
        self.assertEqual(self.decide("pypi", registry(), event="workflow_dispatch", confirm="yes"),
                         ("0.1.0", False, False))
        self.assertEqual(self.decide("pypi", registry(), event="workflow_dispatch", confirm="publish-culvert"),
                         ("0.1.0", True, True))
        self.assertEqual(self.decide("maven", registry(maven_versions=("0.0.9",)), event="workflow_dispatch",
                                     confirm="publish-maven"), ("0.1.0", True, False))

    def test_dispatch_after_a_failed_tag_job_only_tags(self):
        self.assertEqual(self.decide("pypi", registry(pypi=200), event="workflow_dispatch",
                                     confirm="publish-culvert"), ("0.1.0", False, True))

    def test_unknown_before_sha_counts_as_changed(self):
        self.release_pr()
        self.before = "0" * 40
        self.assertEqual(self.decide("pypi", registry()), ("0.2.0", True, True))


    def test_dispatch_from_another_branch_fails(self):
        with self.assertRaisesRegex(gate.GateError, "main only"):
            self.decide("pypi", registry(), event="workflow_dispatch",
                        confirm="publish-culvert", ref="refs/heads/feature")

    def test_unreadable_version_file_fails_with_a_message(self):
        (self.root / "data-pipeline-libraries-java/data-pipeline-core-java/pom.xml").write_text(
            '<project xmlns="http://maven.apache.org/POM/4.0.0"/>')
        with self.assertRaisesRegex(gate.GateError, "data-pipeline-core-java/pom.xml: no readable parent/version"):
            self.decide("maven", registry())

    def test_unreadable_before_version_fails_with_a_message(self):
        (self.root / "python-culvert/pyproject.toml").write_text("[project]\nname = 'x'\n")
        self.before = self.commit()
        self.release_pr()
        with self.assertRaisesRegex(gate.GateError, "at [0-9a-f]{12}: no readable"):
            self.decide("pypi", registry())


class RealRepoTest(unittest.TestCase):
    def test_repo_versions_agree(self):
        found = gate.versions(Path(__file__).resolve().parents[2])
        self.assertEqual(len(set(found.values())), 1, found)


if __name__ == "__main__":
    unittest.main()
