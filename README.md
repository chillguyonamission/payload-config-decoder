# Payload Config Decoder

Open a Gremsy `payload_config.payload` file and read the settings inside it: camera, IR, gimbal, video streams and more.

The file is an SQLite database hidden behind a 32-byte XOR key. The decoder finds the key in the file itself, checks the result, and shows every table. Known camera values also get a readable label (for example Iris `25` → `F2.0`).

- **Values** come from the file.
- **Labels** come from Gremsy PayloadSDK headers. `VIO` labels match ViO payloads. `OrusL` and `MB1` labels come from headers for other payloads that use the same field, so treat them as likely, not confirmed. A blank label means no header defines that value.

It only reads files. It never changes the `.payload` file.

## Install

You need Python 3.8 or newer with Tkinter. Nothing else.

### Ubuntu / Debian

1. Install Python and Tkinter:
   ```
   sudo apt update
   sudo apt install python3 python3-tk git
   ```
2. Get the code:
   ```
   git clone https://github.com/chillguyonamission/payload-config-decoder.git
   cd payload-config-decoder
   ```

### Windows

1. Install Python from <https://www.python.org/downloads/>. In the installer, tick **Add python.exe to PATH**. Tkinter is included.
2. Get the code: either install Git from <https://git-scm.com/> and run
   ```
   git clone https://github.com/chillguyonamission/payload-config-decoder.git
   cd payload-config-decoder
   ```
   or on GitHub click **Code → Download ZIP**, unzip it, and open a terminal in that folder.

On Windows, type `python` wherever this README says `python3`.

### Check it works (optional)

```
python3 -m unittest -v test_payload_decode
```

All tests should say `ok`.

## Run

### Window

```
python3 payload_decode_gui.py
```

1. Click **Open...** (or Ctrl+O) and choose a `.payload` file.
2. Pick a table on the left. Settings tables show **Field / Value / Label / Source**.
3. Click **Save Markdown...** (or Ctrl+S) to save all tables as a readable `.md` file.
4. Click **Save decoded database...** to save the plain SQLite file, which any SQLite viewer can open.

You can also open a file straight away:

```
python3 payload_decode_gui.py path/to/payload_config.payload
```

### Command line

```
python3 payload_decode.py payload_config.payload                  # print all tables
python3 payload_decode.py payload_config.payload -o settings.md   # save them as Markdown
python3 payload_decode.py payload_config.payload --db decoded.db  # also save the decoded database
```

## Troubleshooting

| Message | Fix |
|---|---|
| `No module named 'tkinter'` | Ubuntu: `sudo apt install python3-tk`. Windows: re-run the Python installer and keep **tcl/tk and IDLE** ticked. |
| `not a payload_config file` | The file is not a payload config, or it is damaged. |
| `python3: command not found` (Windows) | Use `python` instead. |

## Files

| File | What it is |
|---|---|
| `payload_decode.py` | Decoder, labels and command line |
| `payload_decode_gui.py` | The window |
| `test_payload_decode.py` | Tests |
