#!/usr/bin/env python3
"""Decode a Gremsy payload_config.payload file (an XOR-obfuscated SQLite database) and print every table."""
import argparse
import collections
import os
import sqlite3
import sys
import tempfile

MAGIC = b"SQLite format 3\x00"
KEY_LEN = 32


def seq(start, names):
    return {str(start + i): n for i, n in enumerate(names)}


ON_OFF = {"2": "On", "3": "Off"}
OFF_ON = {"0": "Off", "1": "On"}
LEVELS = {"0": "Off", **{str(i): f"Level {i}" for i in range(1, 6)}}
SHUTTERS = ["1/1", "2/3", "1/2", "1/3", "1/4", "1/6", "1/8", "1/10", "1/15", "1/20", "1/30", "1/50", "1/60", "1/90", "1/100",
            "1/125", "1/180", "1/250", "1/350", "1/500", "1/725", "1/1000", "1/1500", "1/2000", "1/3000", "1/4000", "1/6000",
            "1/10000"]
PALETTES = ["WhiteHot (F1) / WhiteHot (G1)", "BlackHot (F1) / Fulgurite (G1)", "Rainbow (F1) / IronRed (G1)",
            "RainbowHC (F1) / HotIron (G1)", "Ironbow (F1) / Medical (G1)", "Lava (F1) / Arctic (G1)",
            "Arctic (F1) / Rainbow1 (G1)", "Globow (F1) / Rainbow2 (G1)", "Gradedfire (F1) / Tint (G1)",
            "Hottest (F1) / BlackHot (G1)"]

# (table, field) -> (source header, {stored value: label}). Values from PayloadSDK payload-define/*.h only, no guesses.
# VIO = vio_sdk.h (this payload type); OrusL / MB1 = headers for other Gremsy payloads that share the field.
LABELS = {
    "Camera_Settings": {
        "CamVideoSource": ("VIO", {"0": "EO / IR (PiP)", "1": "EO only", "2": "IR only", "3": "IR / EO (PiP)", "4": "Sync",
                                   "6": "Side by side"}),
        "CamVideoRecord": ("VIO", {"0": "EO + IR", "1": "EO", "2": "IR", "5": "With OSD"}),
        "SettingTarget": ("VIO", {"0": "EO", "1": "IR", "2": "Gimbal"}),
        "TrackingMode": ("VIO", {"0": "Object tracking", "1": "Object detection"}),
        "RCMode": ("VIO", {"0": "Gremsy", "1": "Standard"}),
        "GimbalMode": ("VIO", {"0": "OFF", "1": "LOCK", "2": "FOLLOW", "3": "MAPPING", "4": "RESET"}),
        "LRFMode": ("VIO", {"0": "1 Hz", "1": "4 Hz", "2": "10 Hz", "3": "Off"}),
        "CamEO_OsdMode": ("VIO", {"0": "Off", "1": "Debug", "2": "Status", "3": "Custom"}),
        "CamEO_ImageFlip": ("VIO", ON_OFF),
        "CamEO_Freeze": ("VIO", ON_OFF),
        "CamEO_HS": ("VIO", ON_OFF),
        "CamEO_DefogMode": ("VIO", ON_OFF),
        "CamEO_DefogLevel": ("VIO", {"0": "Lowest", "1": "Low", "2": "Mid", "3": "High"}),
        "CamEO_AE": ("VIO", {"0": "Auto", "3": "Manual", "10": "Shutter priority", "11": "Iris priority", "13": "Bright",
                             "14": "Gain priority"}),
        "CamEO_ShutterValue": ("VIO", seq(6, SHUTTERS)),
        "CamEO_MinShutterLimit": ("VIO", seq(13, SHUTTERS[7:24])),
        "CamEO_IrisValue": ("VIO", {"25": "F2.0", "24": "F2.2", "23": "F2.4", "22": "F2.6", "21": "F2.8", "20": "F3.1",
                                    "19": "F3.4", "17": "F4.0", "14": "F5.2", "11": "F6.8", "10": "F7.3", "8": "F8.7",
                                    "7": "F9.6", "6": "F10", "5": "F11", "0": "Closed"}),
        "CamEO_GainValue": ("VIO", {str(i): f"{(i - 1) * 3} dB" for i in range(1, 18)}),
        "CamEO_WB": ("VIO", {"0": "Auto", "1": "Indoor", "2": "Outdoor", "3": "One push", "4": "ATW", "5": "Manual"}),
        "CamEO_ICR_Mode": ("VIO", {"2": "Auto", "3": "Manual"}),
        "CamEO_FocusMode": ("VIO", {"0": "Manual", "1": "Auto", "2": "One-push auto"}),
        "CamEO_ZoomMode": ("VIO", {"0": "Combine", "2": "Super resolution"}),
        "CamEO_ZoomCB_Factor": ("VIO", seq(0, ["1x", "2x", "4x", "6x", "8x", "10x", "12x", "14x", "16x", "18x", "20x", "40x",
                                               "60x", "80x", "100x", "120x", "140x", "160x", "180x", "200x", "220x",
                                               "240x"])),
        "CamEO_ZoomSR_Factor": ("VIO", seq(0, ["1x", "2x", "4x", "6x", "8x", "10x", "12x", "14x", "16x", "18x", "20x",
                                               "30x"])),
        "CamIR_Palette": ("VIO", seq(0, PALETTES)),
        "CamIR_Zoom": ("VIO", seq(0, [f"{i}x" for i in range(1, 9)])),
        "CamEO_EISMode": ("OrusL", {"0": "Hold", "2": "On", "3": "Off"}),
        "CamEO_EISLevel": ("OrusL", {"2": "Super", "3": "Super+"}),
        "CamEO_StableZoom": ("OrusL", OFF_ON),
        "CamEO_SpotAvoidance": ("OrusL", OFF_ON),
        "CamEO_FlickReduction": ("OrusL", ON_OFF),
        "CamEO_NoiseReduction": ("OrusL", {**LEVELS, "127": "Manual"}),
        "CamEO_Noise2D": ("OrusL", LEVELS),
        "CamEO_Noise3D": ("OrusL", LEVELS),
    },
    "Camera_IR_Settings": {
        "CamIR_ContrastMode": ("MB1", {"0": "Default", "1": "Custom"}),
        "CamIR_AGCMode": ("MB1", {"0": "Normal", "1": "Hold", "2": "Threshold", "3": "Bright", "4": "Linear", "5": "Manual"}),
    },
}


def label(table, field, value):
    source, names = LABELS.get(table, {}).get(field, ("", {}))
    name = names.get(str(value), "")
    return name, source if name else ""


def find_key(data):
    # SQLite pages hold long runs of zero bytes, and XOR leaves the key itself there, so the commonest block is the key.
    blocks = collections.Counter(data[i:i + KEY_LEN] for i in range(0, len(data) - KEY_LEN + 1, KEY_LEN))
    return blocks.most_common(1)[0][0]


def decode(data):
    if len(data) < 512:
        raise ValueError("file too small to be a payload_config file")
    key = find_key(data)
    out = bytes(b ^ key[i % KEY_LEN] for i, b in enumerate(data))
    if not out.startswith(MAGIC):
        raise ValueError("not a payload_config file (no SQLite header after decoding)")
    return out


def cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def read_tables(decoded):
    """Return [(table, columns, rows)] from decoded database bytes."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "decoded.db")
        with open(db_path, "wb") as f:
            f.write(decoded)
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            names = [r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name <> 'sqlite_sequence' ORDER BY name")]
            tables = []
            for name in names:
                cur = con.execute(f'SELECT * FROM "{name}"')
                tables.append((name, [d[0] for d in cur.description], cur.fetchall()))
            return tables
        finally:
            con.close()


def to_markdown(tables, source_name):
    lines = [f"# {source_name}", "",
             "Values come from the file. Labels come from PayloadSDK headers: VIO = vio_sdk.h, OrusL / MB1 = headers for "
             "other payloads (likely, not confirmed). A blank label means no header defines that value.", ""]
    for table, cols, rows in tables:
        lines += [f"## {table}", ""]
        if len(rows) == 1:  # wide one-row settings tables read better vertically
            lines += ["| Field | Value | Label | Source |", "|---|---|---|---|"]
            lines += [f"| {c} | {cell(v)} | {' | '.join(label(table, c, v))} |" for c, v in zip(cols, rows[0])]
        elif rows:
            lines += ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
            lines += ["| " + " | ".join(cell(v) for v in r) + " |" for r in rows]
        else:
            lines.append("(empty)")
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Decode a payload_config.payload file and print its tables as Markdown.")
    ap.add_argument("file", help="the .payload file")
    ap.add_argument("-o", "--output", help="write the Markdown here instead of printing it")
    ap.add_argument("--db", help="also save the decoded SQLite database to this path")
    args = ap.parse_args()

    with open(args.file, "rb") as f:
        try:
            decoded = decode(f.read())
        except ValueError as e:
            sys.exit(f"error: {e}")

    if args.db:
        with open(args.db, "wb") as f:
            f.write(decoded)

    md = to_markdown(read_tables(decoded), os.path.basename(args.file))

    if args.output:
        with open(args.output, "w") as f:
            f.write(md)
    else:
        print(md)


if __name__ == "__main__":
    main()
