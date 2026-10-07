# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Bronya-duck; see skill_package/image-delivery/LICENSE.
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

SCRIPT = Path(__file__).resolve().parents[1] / "skill_package/image-delivery/scripts/image_delivery.py"
spec = importlib.util.spec_from_file_location("image_delivery", SCRIPT)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="image-delivery-test-")
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / "源图 空格.png"
        Image.new("RGB", (17, 11), "red").save(self.source)
        self.original = self.source.read_bytes()
        self.destination = self.root / "项目 中文/images 空格"

    def tearDown(self):
        for path in self.root.rglob("*"):
            if path.is_file() and not path.is_symlink():
                path.chmod(stat.S_IREAD | stat.S_IWRITE)
        self.temp.cleanup()

    def request(self, **extra):
        return dict({"sources": [str(self.source)], "destination_dir": str(self.destination),
                     "names": ["封面"], "usage": "游戏背景", "delivery_confirmed": True}, **extra)

    def test_copy_metadata_hash_query(self):
        before = self.source.stat().st_mtime_ns
        result = tool.deliver(self.request())
        self.assertTrue(result["ok"], result)
        target = self.destination / "封面.png"
        self.assertEqual(target.read_bytes(), self.original)
        self.assertEqual(target.stat().st_mtime_ns, before)
        self.assertEqual(self.source.read_bytes(), self.original)
        found = tool.find(str(self.destination.parent), "游戏背景")
        self.assertEqual(len(found["items"]), 1)
        self.assertEqual(found["items"][0]["integrity"], "valid")
        self.assertEqual(found["items"][0]["target_absolute_path"], str(target))

    def test_collision_replay(self):
        self.destination.mkdir(parents=True)
        existing = self.destination / "封面.png"
        Image.new("RGB", (17, 11), "blue").save(existing)
        previous = existing.read_bytes()
        result = tool.deliver(self.request())
        self.assertTrue(result["ok"], result)
        self.assertEqual(Path(result["items"][0]["target_path"]).name, "封面_001.png")
        self.assertEqual(tool.deliver(self.request())["items"][0]["status"], "reused")
        self.assertEqual(len(tool.read_json(self.destination / tool.MANIFEST)["items"]), 1)
        self.assertEqual(existing.read_bytes(), previous)
        self.assertEqual(len(list(self.destination.glob("*.png"))), 2)

    def test_same_content_reuse(self):
        self.destination.mkdir(parents=True)
        shutil.copy2(self.source, self.destination / "封面.png")
        self.assertEqual(tool.deliver(self.request())["items"][0]["status"], "reused")

    def test_replay_without_usage_preserves_existing_purpose(self):
        tool.deliver(self.request())
        request = self.request()
        request.pop("usage")
        tool.deliver(request)
        self.assertEqual(len(tool.find(str(self.destination), "游戏背景")["items"]), 1)
        tool.deliver(self.request(usage="新用途"))
        self.assertEqual(len(tool.find(str(self.destination), "新用途")["items"]), 1)

    def test_corrupt_manifest_preserved_before_copy(self):
        self.destination.mkdir(parents=True)
        manifest = self.destination / tool.MANIFEST
        manifest.write_text("corrupt manifest", encoding="utf-8")
        with self.assertRaises(ValueError):
            tool.deliver(self.request())
        self.assertEqual(manifest.read_text(), "corrupt manifest")
        self.assertFalse((self.destination / "封面.png").exists())

    def test_launcher_from_another_directory(self):
        launcher = SCRIPT.parent / "run.ps1"
        request = self.root / "inspect.json"
        request.write_text(json.dumps({"sources": [str(self.source)]}), encoding="utf-8")
        shell = shutil.which("pwsh") or shutil.which("powershell")
        process = subprocess.run([shell, "-NoProfile", "-File", str(launcher), "inspect", "--file", str(request)], cwd=self.root, capture_output=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        result = json.loads(process.stdout.decode("utf-8-sig"))
        self.assertEqual(result["items"][0]["source_path"], str(self.source))

    def test_installer_preserves_conflicting_entry(self):
        skills_root = self.root / "user-skills"
        conflict = skills_root / "image-delivery"
        conflict.mkdir(parents=True)
        original = conflict / "keep.txt"
        original.write_text("keep me")
        shell = shutil.which("pwsh") or shutil.which("powershell")
        installer = SCRIPT.parents[1] / "install.ps1"
        process = subprocess.run([shell, "-NoProfile", "-File", str(installer), "-UserSkillsRoot", str(skills_root)], capture_output=True)
        self.assertNotEqual(process.returncode, 0)
        self.assertEqual(original.read_text(), "keep me")
        self.assertFalse(conflict.is_junction())

    def test_batch_prefix_and_names(self):
        second = self.root / "图二.jpg"
        Image.new("RGB", (9, 7), "green").save(second)
        request = self.request(sources=[str(self.source), str(second)], name_prefix="场景")
        request.pop("names")
        result = tool.deliver(request)
        self.assertTrue(result["ok"], result)
        self.assertEqual([Path(i["target_path"]).name for i in result["items"]], ["场景_001.png", "场景_002.jpg"])
        other = self.root / "另一文件夹"
        result = tool.deliver(self.request(sources=[str(self.source), str(second)], names=["甲.png", "乙.jpeg"], destination_dir=str(other)))
        self.assertTrue(result["ok"], result)
        self.assertEqual((other / "乙.jpeg").read_bytes(), second.read_bytes())

    def test_confirmation_and_absolute_paths(self):
        with self.assertRaises(tool.DeliveryError):
            tool.deliver(self.request(delivery_confirmed=False))
        with self.assertRaises(tool.DeliveryError):
            tool.deliver(self.request(destination_dir="relative/path"))
        self.assertFalse(self.destination.exists())

    def test_invalid_names_and_extension(self):
        for name in ("../逃出", "CON.png", "aux.txt", "文件.", "文件 ", "a:b.png", "图.jpg", "LPT1.png", "COM¹.png"):
            with self.subTest(name=name):
                result = tool.deliver(self.request(names=[name]))
                self.assertFalse(result["ok"])
                self.assertEqual(result["items"][0]["status"], "failed")
        self.assertFalse(self.destination.exists())

    def test_missing_and_invalid_image_partial_batch(self):
        bad = self.root / "bad.png"
        bad.write_text("not an image")
        result = tool.deliver(self.request(sources=[str(self.source), str(bad), str(self.root / "missing.png")], names=["成功", "坏图", "缺失"]))
        self.assertFalse(result["ok"])
        self.assertEqual([i["status"] for i in result["items"]], ["copied", "failed", "failed"])
        self.assertTrue((self.destination / "成功.png").is_file())
        self.assertEqual(len(tool.read_json(self.destination / tool.MANIFEST)["items"]), 1)

    def test_manifest_failure_rollback_owned_copy(self):
        with patch.object(tool, "atomic_manifest", side_effect=PermissionError("cannot write manifest")):
            result = tool.deliver(self.request())
        self.assertFalse(result["ok"])
        self.assertFalse((self.destination / "封面.png").exists())
        self.assertEqual(self.source.read_bytes(), self.original)
        self.assertFalse(list(self.destination.glob("*.tmp")))

    def test_manifest_failure_preserves_reused_file(self):
        self.destination.mkdir(parents=True)
        target = self.destination / "封面.png"
        shutil.copy2(self.source, target)
        with patch.object(tool, "atomic_manifest", side_effect=PermissionError("failed")):
            result = tool.deliver(self.request())
        self.assertFalse(result["ok"])
        self.assertEqual(target.read_bytes(), self.original)

    def test_later_failure_keeps_prior_success(self):
        actual = tool.atomic_manifest
        calls = []
        def write(path, data):
            calls.append(1)
            if len(calls) == 2:
                raise PermissionError("second write failed")
            actual(path, data)
        with patch.object(tool, "atomic_manifest", side_effect=write):
            result = tool.deliver(self.request(sources=[str(self.source)] * 2, names=["成功", "失败"]))
        self.assertEqual([i["status"] for i in result["items"]], ["copied", "failed"])
        self.assertTrue((self.destination / "成功.png").exists())
        self.assertFalse((self.destination / "失败.png").exists())
        self.assertEqual(len(tool.read_json(self.destination / tool.MANIFEST)["items"]), 1)

    def test_readonly_source_and_rollback(self):
        self.source.chmod(stat.S_IREAD)
        result = tool.deliver(self.request())
        self.assertTrue(result["ok"], result)
        with patch.object(tool, "atomic_manifest", side_effect=PermissionError("failed")):
            result = tool.deliver(self.request(names=["撤回"]))
        self.assertFalse(result["ok"])
        self.assertFalse((self.destination / "撤回.png").exists())

    def test_unwritable_directory(self):
        actual = Path.mkdir
        def denied(path, *args, **kwargs):
            if path == self.destination:
                raise PermissionError("access denied")
            return actual(path, *args, **kwargs)
        with patch.object(Path, "mkdir", denied):
            result = tool.deliver(self.request())
        self.assertFalse(result["ok"])
        self.assertEqual(result["items"][0]["status"], "failed")
        self.assertFalse(self.destination.exists())

    def test_find_project_move_changed_and_missing(self):
        tool.deliver(self.request())
        moved = self.root / "移动后的项目"
        shutil.move(self.destination.parent, moved)
        found = tool.find(str(moved), "封面")
        self.assertEqual(found["items"][0]["integrity"], "valid")
        target = Path(found["items"][0]["target_absolute_path"])
        target.write_bytes(b"changed")
        self.assertEqual(tool.find(str(moved))["items"][0]["integrity"], "changed")
        target.unlink()
        self.assertEqual(tool.find(str(moved))["items"][0]["integrity"], "missing")

    def test_find_refuses_manifest_traversal(self):
        tool.deliver(self.request())
        manifest = self.destination / tool.MANIFEST
        data = tool.read_json(manifest)
        data["items"][0]["target_path"] = "../../源图 空格.png"
        manifest.write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual(tool.find(str(self.destination))["items"][0]["integrity"], "unsafe")

    def concurrent(self, requests):
        files = []
        for index, request in enumerate(requests):
            path = self.root / f"request-{index}.json"
            path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
            files.append(path)
        processes = [subprocess.Popen([sys.executable, "-B", "-X", "utf8", str(SCRIPT), "deliver", "--file", str(p)], stdout=subprocess.PIPE, stderr=subprocess.PIPE) for p in files]
        results = []
        for process in processes:
            out, err = process.communicate(timeout=30)
            self.assertEqual(process.returncode, 0, (out, err))
            results.append(json.loads(out))
        return results

    def test_concurrent_manifest_updates(self):
        self.concurrent([self.request(names=[f"并发{i}"]) for i in range(4)])
        self.assertEqual(len(tool.read_json(self.destination / tool.MANIFEST)["items"]), 4)
        self.assertEqual(len(list(self.destination.glob("*.png"))), 4)

    def test_concurrent_identical_requests_reuse(self):
        results = self.concurrent([self.request()] * 3)
        self.assertEqual(sorted(r["items"][0]["status"] for r in results), ["copied", "reused", "reused"])
        self.assertEqual(len(tool.read_json(self.destination / tool.MANIFEST)["items"]), 1)

    def comfy_fixture(self):
        folder = self.root / "comfy/data/runs/J-test"
        attempts, reviews = [], []
        for number, color in ((1, "red"), (2, "blue")):
            round_dir = folder / "image_001" / f"round_{number}"
            round_dir.mkdir(parents=True)
            source = round_dir / "result.png"
            Image.new("RGB", (17, 11), color).save(source)
            review = {"accepted": number == 2, "index": 0, "round": number, "viewed_path": str(source),
                      "checks": {"subject": "partial" if number == 1 else "pass", "composition": "pass", "style": "pass", "defects": "pass"}}
            record = {"number": number, "status": "rendered", "folder": str(round_dir), "path": str(source),
                      "output_size": [17, 11], "sha256": tool.sha256(source),
                      "technical_checks": {"execution": "passed", "dimensions": "passed", "png": "passed"}}
            manifest = {"job_id": "J-test", "series_id": "SC-test", "style_key": "S001-v1", "attempt": copy.deepcopy(record), "visual_review": review}
            (round_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            record["visual_review"] = review
            attempts.append(record)
            reviews.append(review)
        job = {"id": "J-test", "series_id": "SC-test", "style_key": "S001-v1", "images": [
            {"index": 0, "review": reviews[-1], "attempts": attempts, "best_path": attempts[-1]["path"]}]}
        job_path = folder / "job.json"
        job_path.write_text(json.dumps(job), encoding="utf-8")
        return job_path, job

    def test_comfy_selected_round_and_originals_unchanged(self):
        job_path, job = self.comfy_fixture()
        snapshots = {p: p.read_bytes() for p in job_path.parent.rglob("*") if p.is_file()}
        request = self.request(comfy_job=str(job_path))
        request.pop("sources")
        result = tool.deliver(request)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["items"][0]["provenance"]["round"], 2)
        self.assertEqual((self.destination / "封面.png").read_bytes(), Path(job["images"][0]["best_path"]).read_bytes())
        for path, data in snapshots.items():
            self.assertEqual(path.read_bytes(), data)
        self.assertEqual(len(tool.find(str(self.destination), "S001-v1")["items"]), 1)

    def test_comfy_mixed_and_none_accepted(self):
        job_path, job = self.comfy_fixture()
        job["images"].append({"index": 1, "review": {"accepted": False}, "attempts": []})
        job_path.write_text(json.dumps(job), encoding="utf-8")
        result = tool.inspect({"comfy_job": str(job_path)})
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["skipped"], [{"image_index": 1, "reason": "not_accepted"}])
        job["images"][0]["review"]["accepted"] = False
        job_path.write_text(json.dumps(job), encoding="utf-8")
        request = self.request(comfy_job=str(job_path))
        request.pop("sources")
        with self.assertRaises(tool.DeliveryError):
            tool.deliver(request)
        self.assertFalse(self.destination.exists())

    def test_comfy_changed_source_and_mismatched_review(self):
        job_path, job = self.comfy_fixture()
        source = Path(job["images"][0]["best_path"])
        Image.new("RGB", (17, 11), "green").save(source)
        result = tool.inspect({"comfy_job": str(job_path)})
        self.assertEqual(result["errors"][0]["code"], "comfy_checksum_mismatch")
        job["images"][0]["review"]["viewed_path"] = job["images"][0]["attempts"][0]["path"]
        job_path.write_text(json.dumps(job), encoding="utf-8")
        result = tool.inspect({"comfy_job": str(job_path)})
        self.assertEqual(result["errors"][0]["code"], "comfy_review_mismatch")

    def test_cli_invalid_request_json(self):
        process = subprocess.run([sys.executable, "-B", "-X", "utf8", str(SCRIPT), "inspect"], capture_output=True)
        self.assertEqual(process.returncode, 1)
        self.assertEqual(json.loads(process.stdout)["errors"][0]["code"], "invalid_arguments")
        self.assertFalse(process.stderr)


if __name__ == "__main__":
    unittest.main()
