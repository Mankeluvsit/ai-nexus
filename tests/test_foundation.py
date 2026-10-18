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

    def test_catalog_documentation(self):
        self.assertGreaterEqual(len(app.PROVIDERS), 5)
        self.assertTrue(all(url.startswith("https://") for _, _, url in app.PROVIDERS))


if __name__ == "__main__":
    unittest.main()
