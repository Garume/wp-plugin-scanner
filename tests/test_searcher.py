import unittest
from unittest import mock
from pathlib import Path
import tempfile
import shutil

import requests

from wp_plugin_scanner.searcher import PluginSearcher
from wp_plugin_scanner.manager import AuditManager
from wp_plugin_scanner.scanner import UploadScanner
from wp_plugin_scanner.reporter import ExcelReporter
from wp_plugin_scanner.config import SAVE_ROOT


class TestSearcher(unittest.TestCase):
    def test_parse(self):
        html_snippet = "<a href=\"https://wordpress.org/plugins/foo/\">Foo</a>"
        with mock.patch.object(requests.Session, "get") as mget:
            mget.return_value.status_code = 200
            mget.return_value.text = html_snippet
            mget.return_value.raise_for_status = lambda: None
            s = PluginSearcher()
            result = s.search("foo", limit=1)
            self.assertEqual(result, ["foo"])


class TestArchive(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "plug").mkdir()
        (self.tmp / "plug/a.php").write_text("<?php wp_handle_upload(); ?>")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        shutil.rmtree(SAVE_ROOT, ignore_errors=True)

    def test_archive(self):
        class DummyReporter(ExcelReporter):
            def add_result(self, result):
                pass

        mgr = AuditManager(
            downloader=mock.Mock(download=lambda slug: self.tmp / "plug"),
            scanner=UploadScanner(),
            reporter=DummyReporter(Path(self.tmp / "out.xlsx")),
            save_sources=True,
        )
        mgr.run(["demo"])
        self.assertTrue((SAVE_ROOT / "demo/a.php").exists())

    def test_progress_callback(self):
        class DummyReporter(ExcelReporter):
            def add_result(self, result):
                pass

        events = []
        mgr = AuditManager(
            downloader=mock.Mock(download=lambda slug: self.tmp / "plug"),
            scanner=UploadScanner(),
            reporter=DummyReporter(Path(self.tmp / "out.xlsx")),
            save_sources=False,
        )
        mgr.run(["demo"], progress_cb=lambda m: events.append(m))
        self.assertTrue(any("Checking demo" in e for e in events))


if __name__ == "__main__":
    unittest.main()
