from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from packaging_assets import script_assets, RESOURCES


class PackagingTests(unittest.TestCase):
    def test_sensitive_output_and_cache_are_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("scripts/project/main.py", "scripts/project/test_main.py", "scripts/project/.env", "scripts/project/data.csv",
                         "scripts/project/data.json", "scripts/project/private.xlsx",
                         "scripts/project/__pycache__/cache.pyc", "scripts/project/output/report.xlsx",
                         "scripts/project/tests/helper.py", "scripts/project/prove/check.py"):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("test fixture")
            result = script_assets([("scripts/project", "scripts/project")], root)
            self.assertEqual([Path(source).name for source, destination in result], ["main.py"])

    def test_real_resources_kept_and_operational_outputs_excluded(self):
        root = Path(__file__).resolve().parents[1]
        result = script_assets([("scripts", "scripts")], root)
        files = {Path(source).relative_to(root).as_posix() for source, destination in result}
        self.assertTrue(RESOURCES <= files)
        self.assertFalse(any("/output/" in path or "__pycache__" in path or path.endswith(".env") for path in files))
