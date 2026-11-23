#!/usr/bin/env python3
"""Window for payload_config.payload files: open one, view its tables with labels, save Markdown or the decoded database."""
import os
import sqlite3
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from payload_decode import decode, label, read_tables, to_markdown


class App:
    def __init__(self, root):
        self.root = root
        self.path = None
        self.decoded = None
        self.tables = []

        root.title("Payload Config Decoder")
        root.geometry("950x620")

        bar = ttk.Frame(root, padding=6)
        bar.pack(fill="x")
        ttk.Button(bar, text="Open...", command=self.open).pack(side="left")
        self.save_md_button = ttk.Button(bar, text="Save Markdown...", command=self.save_markdown, state="disabled")
        self.save_md_button.pack(side="left", padx=(6, 0))
        self.save_db_button = ttk.Button(bar, text="Save decoded database...", command=self.save_database, state="disabled")
        self.save_db_button.pack(side="left", padx=(6, 0))
        self.file_label = ttk.Label(bar, text="No file open")
        self.file_label.pack(side="left", padx=12)

        panes = ttk.PanedWindow(root, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=6)
        self.table_list = tk.Listbox(panes, exportselection=False, width=30)
        self.table_list.bind("<<ListboxSelect>>", lambda _e: self.show_table())
        panes.add(self.table_list, weight=0)

        right = ttk.Frame(panes)
        panes.add(right, weight=1)
        self.grid = ttk.Treeview(right, show="headings")
        ys = ttk.Scrollbar(right, orient="vertical", command=self.grid.yview)
        xs = ttk.Scrollbar(right, orient="horizontal", command=self.grid.xview)
        self.grid.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self.grid.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        self.status = ttk.Label(root, text="Open a .payload file to start (Ctrl+O).", padding=6)
        self.status.pack(fill="x")

        root.bind("<Control-o>", lambda _e: self.open())
        root.bind("<Control-s>", lambda _e: self.save_markdown())

    def open(self, path=None):
        path = path or filedialog.askopenfilename(
            title="Open payload config", filetypes=[("Payload config", "*.payload"), ("All files", "*")])
        if not path:
            return
        try:
            with open(path, "rb") as f:
                decoded = decode(f.read())
            tables = read_tables(decoded)
        except (OSError, ValueError, sqlite3.DatabaseError) as e:
            messagebox.showerror("Cannot open file", f"{path}\n\n{e}")
            return

        self.path, self.decoded, self.tables = path, decoded, tables
        self.file_label.config(text=os.path.basename(path))
        self.table_list.delete(0, "end")
        for name, _cols, rows in tables:
            self.table_list.insert("end", f"{name}  ({len(rows)})")
        if tables:
            self.table_list.selection_set(0)
            self.show_table()
        self.save_md_button.config(state="normal")
        self.save_db_button.config(state="normal")
        self.status.config(text=f"Decoded {len(tables)} tables from {path}. Values come from the file; "
                                "labels come from PayloadSDK headers (VIO, OrusL, MB1).")

    def show_table(self):
        selection = self.table_list.curselection()
        if not selection:
            return
        name, cols, rows = self.tables[selection[0]]
        self.grid.delete(*self.grid.get_children())
        if len(rows) == 1:  # one-row settings tables read better vertically, with labels
            headings = {"Field": 220, "Value": 110, "Label": 280, "Source": 70}
            data = [(c, "" if v is None else v, *label(name, c, v)) for c, v in zip(cols, rows[0])]
        else:
            headings = {c: 150 for c in cols}
            data = [["" if v is None else v for v in r] for r in rows]
        self.grid.config(columns=list(headings))
        for heading, width in headings.items():
            self.grid.heading(heading, text=heading)
            self.grid.column(heading, width=width, stretch=True)
        for row in data:
            self.grid.insert("", "end", values=row)

    def save_markdown(self):
        if self.decoded is None:
            return
        stem = os.path.splitext(os.path.basename(self.path))[0]
        target = filedialog.asksaveasfilename(
            title="Save Markdown", defaultextension=".md", initialfile=f"{stem}_settings.md",
            initialdir=os.path.dirname(self.path), filetypes=[("Markdown", "*.md"), ("All files", "*")])
        if target:
            self.write(target, to_markdown(self.tables, os.path.basename(self.path)).encode())

    def save_database(self):
        if self.decoded is None:
            return
        stem = os.path.splitext(os.path.basename(self.path))[0]
        target = filedialog.asksaveasfilename(
            title="Save decoded database", defaultextension=".db", initialfile=f"{stem}_decoded.db",
            initialdir=os.path.dirname(self.path), filetypes=[("SQLite database", "*.db"), ("All files", "*")])
        if target:
            self.write(target, self.decoded)

    def write(self, target, data):
        try:
            with open(target, "wb") as f:
                f.write(data)
        except OSError as e:
            messagebox.showerror("Cannot save file", f"{target}\n\n{e}")
            return
        self.status.config(text=f"Saved {target}")


def main():
    root = tk.Tk()
    app = App(root)
    if len(sys.argv) > 1:
        app.open(sys.argv[1])
    root.mainloop()


if __name__ == "__main__":
    main()
