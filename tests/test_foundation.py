import os
import tempfile
import unittest
from unittest.mock import patch
from contextlib import closing

from ainexus import __version__
from ainexus import __main__ as app


class FoundationTests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(__version__, "0.1.0")

    def test_persistence(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(app, "DB", os.path.join(folder, "test.sqlite")):
                with closing(app.database()) as con:
                    con.execute("INSERT INTO models (id,discovered_at) VALUES (?,?)", ("local-test", 123))
                    con.commit()
                with closing(app.database()) as con:
                    row = con.execute("SELECT id FROM models").fetchone()
                    self.assertEqual(row["id"], "local-test")

    def test_dashboard_views_and_accessibility(self):
        from html.parser import HTMLParser

        class Inspector(HTMLParser):
            def __init__(self):
                super().__init__()
                self.views = set()
                self.ids = set()
                self.buttons = []
            def handle_starttag(self, tag, attrs):
                a = dict(attrs)
                if "data-view" in a:
                    self.views.add(a["data-view"])
                if "id" in a:
                    self.ids.add(a["id"])
                if tag == "button":
                    self.buttons.append(a)

        parsed = Inspector()
        parsed.feed(app.HTML)
        self.assertEqual(parsed.views, {"overview", "providers", "models", "execute", "activity", "settings"})
        self.assertIn("main", parsed.ids)
        self.assertIn("message", parsed.ids)
        self.assertIn("aria-live", app.HTML)
        self.assertIn("prefers-reduced-motion", app.HTML)
        self.assertIn("data-theme", app.HTML)
        self.assertIn("data-density", app.HTML)
        self.assertIn('rel="noopener noreferrer"', app.HTML.replace('link.rel="noopener noreferrer"', 'rel="noopener noreferrer"'))

    def test_static_ui_is_packaged(self):
        from pathlib import Path
        path = Path(app.__file__).with_name("ui.html")
        self.assertTrue(path.is_file())
        self.assertEqual(path.read_text(encoding="utf-8"), app.HTML)

    def test_catalog_documentation(self):
        self.assertGreaterEqual(len(app.PROVIDERS), 5)
        self.assertTrue(all(url.startswith("https://") for _, _, url in app.PROVIDERS))


if __name__ == "__main__":
    unittest.main()
