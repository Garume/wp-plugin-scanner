import unittest
from pathlib import Path
import tempfile
import shutil
import re

from wp_plugin_scanner.scanner import RuleScanner, ScanRule

class TestRuleScanner(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "plug").mkdir()
        (self.tmp / "plug/file.php").write_text("<?php dangerous_func(); ?>")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_scan(self):
        rule = ScanRule("danger", re.compile(rb"dangerous_func"))
        scanner = RuleScanner([rule])
        result = scanner.scan(self.tmp / "plug")
        self.assertTrue(result["danger"])

if __name__ == '__main__':
    unittest.main()
