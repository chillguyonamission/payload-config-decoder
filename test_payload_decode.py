import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "payload_decode.py")


def encode(data, key):
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


class DecodeTest(unittest.TestCase):
    def run_cli(self, path):
        return subprocess.run([sys.executable, SCRIPT, path], capture_output=True, text=True)

    def test_round_trip_prints_table_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "plain.db")
            con = sqlite3.connect(db)
            con.execute("CREATE TABLE Camera_Settings (ID INTEGER, CamEO_WB TEXT, CamEO_IrisValue TEXT, CamEO_AE TEXT)")
            con.execute("INSERT INTO Camera_Settings VALUES (1, '0', '25', '99')")
            con.commit()
            con.close()
            enc = os.path.join(tmp, "x.payload")
            with open(db, "rb") as f, open(enc, "wb") as g:
                g.write(encode(f.read(), os.urandom(32)))

            result = self.run_cli(enc)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("## Camera_Settings", result.stdout)
            self.assertIn("| CamEO_IrisValue | 25 | F2.0 | VIO |", result.stdout)
            self.assertIn("| CamEO_WB | 0 | Auto | VIO |", result.stdout)
            self.assertIn("| CamEO_AE | 99 |  |  |", result.stdout)  # value no header defines stays unlabeled

    def test_rejects_non_payload_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = os.path.join(tmp, "bad.payload")
            with open(bad, "wb") as f:
                f.write(os.urandom(4096))
            result = self.run_cli(bad)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not a payload_config file", result.stderr)


class GuiTest(unittest.TestCase):
    def test_open_shows_labels_and_saves(self):
        import tkinter as tk
        from unittest import mock
        sys.path.insert(0, HERE)
        import payload_decode_gui as gui
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("no display")
        self.addCleanup(root.destroy)
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "plain.db")
            con = sqlite3.connect(db)
            con.execute("CREATE TABLE Camera_Settings (ID INTEGER, CamEO_IrisValue TEXT)")
            con.execute("INSERT INTO Camera_Settings VALUES (1, '25')")
            con.commit()
            con.close()
            enc = os.path.join(tmp, "x.payload")
            with open(db, "rb") as f, open(enc, "wb") as g:
                plain = f.read()
                g.write(encode(plain, os.urandom(32)))

            app = gui.App(root)
            app.open(enc)
            rows = [app.grid.item(i, "values") for i in app.grid.get_children()]
            self.assertIn(("CamEO_IrisValue", "25", "F2.0", "VIO"), rows)

            md_out, db_out = os.path.join(tmp, "out.md"), os.path.join(tmp, "out.db")
            with mock.patch.object(gui.filedialog, "asksaveasfilename", side_effect=[md_out, db_out]):
                app.save_markdown()
                app.save_database()
            with open(md_out) as f:
                self.assertIn("| CamEO_IrisValue | 25 | F2.0 | VIO |", f.read())
            with open(db_out, "rb") as f:
                self.assertEqual(f.read(), plain)


if __name__ == "__main__":
    unittest.main()
