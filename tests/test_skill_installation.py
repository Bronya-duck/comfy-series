"""Exercise Windows skill discovery locations, junctions, and conflict handling."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which("powershell.exe")


@unittest.skipUnless(POWERSHELL, "Windows PowerShell is required for junction installation")
class SkillInstallation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="comfy-install-")
        self.base = Path(self.temp.name)
        self.project = self.base / "different project"
        self.project.mkdir()
        (self.project / "comfy_series.json").write_text("{}", encoding="utf-8")
        self.skills = self.base / "different-user" / ".agents" / "skills"
        shutil.copytree(PROJECT / "skill_package", self.project / "skill_package")

    def tearDown(self):
        # Python 3.12 removes Windows junctions without following their contents.
        # Both their targets and every fixture are inside this temporary root.
        self.temp.cleanup()

    def install(self, scope="Both", skills=None):
        selection = ["-Skills", skills] if skills else []
        return subprocess.run(
            [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
             str(PROJECT / "install_codex_skills.ps1"), "-Scope", scope,
             "-ProjectRoot", str(self.project), "-UserSkillsRoot", str(self.skills), *selection],
            cwd=self.base, capture_output=True, text=True, errors="replace", timeout=30,
        )

    def test_default_three_skills_are_visible_and_share_the_project(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["ok"])
        self.assertEqual(len(json.loads(result.stdout)["skills"]), 3)
        for name in ("comfy-series", "config-start", "image-delivery"):
            target = self.project / ".agents" / "skills" / name
            linked = self.skills / name
            self.assertEqual(linked.resolve(), target.resolve())
            self.assertEqual((linked / "SKILL.md").read_bytes(),
                             (self.project / "skill_package" / name / "SKILL.md").read_bytes())
        runner = self.skills / "comfy-series" / "scripts" / "run.py"
        found_project = next(p for p in runner.resolve().parents if (p / "comfy_series.json").is_file())
        self.assertEqual(found_project, self.project.resolve())

    def test_reinstall_updates_source_through_the_same_junction(self):
        self.assertEqual(self.install().returncode, 0)
        source = self.project / "skill_package" / "config-start" / "SKILL.md"
        source.write_text(source.read_text(encoding="utf-8") + "\nUpdated fixture\n", encoding="utf-8")
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.skills / "config-start" / "SKILL.md").read_bytes(), source.read_bytes())

    def test_project_scope_does_not_install_user_entries(self):
        result = self.install("Project")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.skills.exists())
        for name in ("comfy-series", "config-start", "image-delivery"):
            self.assertTrue((self.project / ".agents" / "skills" / name / "SKILL.md").is_file())

    def test_existing_user_skill_is_preserved_before_any_install(self):
        conflict = self.skills / "config-start"
        conflict.mkdir(parents=True)
        marker = conflict / "SKILL.md"
        marker.write_bytes(b"someone else's skill")
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Existing user skill preserved", result.stderr)
        self.assertEqual(marker.read_bytes(), b"someone else's skill")
        self.assertFalse((self.skills / "comfy-series").exists())
        self.assertFalse((self.project / ".agents").exists())

    def test_missing_source_does_not_install_partial_skills(self):
        (self.project / "skill_package" / "config-start" / "SKILL.md").unlink()
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing skill source", result.stderr)
        self.assertFalse(self.skills.exists())
        self.assertFalse((self.project / ".agents").exists())

    def test_image_delivery_only_installation(self):
        result = self.install(skills="image-delivery")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([s["name"] for s in json.loads(result.stdout)["skills"]], ["image-delivery"])
        self.assertTrue((self.skills / "image-delivery" / "scripts" / "run.ps1").is_file())
        self.assertFalse((self.skills / "comfy-series").exists())

    def test_existing_image_delivery_is_preserved_before_any_install(self):
        conflict = self.skills / "image-delivery"
        conflict.mkdir(parents=True)
        marker = conflict / "SKILL.md"
        marker.write_bytes(b"independent delivery install")
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(marker.read_bytes(), b"independent delivery install")
        self.assertFalse((self.skills / "comfy-series").exists())
        self.assertFalse((self.project / ".agents").exists())


if __name__ == "__main__":
    unittest.main()
