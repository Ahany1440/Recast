"""Recast desktop app: converts files and removes metadata.

    gui.pyw                         open the app
    gui.pyw FILE [FILE...]          open the app with these files (Send To / "Open in Recast")
    gui.pyw --convert TARGET FILE   convert one file right away (the right-click menu), small popup only
"""
import multiprocessing as mp
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
import winreg
from pathlib import Path
from tkinter import filedialog, ttk

from converters.tools import ALREADY_SMALL

# Format chips, in the order they're offered. At most MAX_CHIPS show; the rest go under "More".
CHIPS = {"merge-pdf": ("Merge", "one .pdf"), "images-pdf": ("One PDF", ".pdf"),
         "pdf": ("PDF", ".pdf"), "docx": ("Word", ".docx"),
         "pptx": ("PowerPoint", ".pptx"),
         "txt": ("Text", ".txt"), "png": ("Images", ".png"), "jpg": ("JPG", ".jpg"),
         "xlsx": ("Excel", ".xlsx"), "csv": ("CSV", ".csv"), "mp4": ("Video", ".mp4"), "mp3": ("Audio", ".mp3")}
MAX_CHIPS = 4
# Features that keep the file type: their own row under the formats.
TOOLS = {"compress": ("Smaller file", "compress"), "clean": ("Remove metadata", "author, GPS, dates")}
THEMES = {
    "dark": dict(card="#1e1e1e", field="#262626", border="#343434", text="#f2f2f2", muted="#a3a3a3",
                 accent="#4cc2ff", done="#5fd18a", error="#ff6b6b"),
    "light": dict(card="#ffffff", field="#f3f4f6", border="#d6d9de", text="#161616", muted="#5f6670",
                  accent="#0b5cb5", done="#1f9d55", error="#d64545"),
}
BODY, BOLD, SMALL = ("Segoe UI", 11), ("Segoe UI", 11, "bold"), ("Segoe UI", 10)


def mix(a, b, t):
    """Colour a laid over colour b at strength t (both "#rrggbb")."""
    return "#" + "".join(f"{round(int(a[i:i + 2], 16) * t + int(b[i:i + 2], 16) * (1 - t)):02x}" for i in (1, 3, 5))


def system_is_dark():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


class UiQueue:
    """Tkinter isn't thread-safe: worker threads hand UI updates to the main thread through this."""

    def __init__(self, root):
        self.q, self.root = queue.Queue(), root
        self._poll()

    def __call__(self, fn, *args):
        self.q.put((fn, args))

    def _poll(self):
        try:
            while True:
                fn, args = self.q.get_nowait()
                fn(*args)
        except queue.Empty:
            pass
        self.root.after(80, self._poll)


def near_pointer(w, h, offset=16):
    """Top-left corner for a w x h window just below-right of the mouse, kept inside that
    monitor's work area (so it never lands off-screen or under the taskbar)."""
    import ctypes
    from ctypes import wintypes

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

    pt = wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    info = MONITORINFO(cbSize=ctypes.sizeof(MONITORINFO))
    monitor = ctypes.windll.user32.MonitorFromPoint(pt, 2)  # 2 = nearest monitor
    ctypes.windll.user32.GetMonitorInfoW(monitor, ctypes.byref(info))
    work = info.rcWork
    x, y = pt.x + offset, pt.y + offset
    if x + w > work.right:
        x = pt.x - w - offset  # no room on the right: open to the left of the mouse
    if y + h > work.bottom:
        y = pt.y - h - offset  # no room below: open above the mouse
    return max(work.left, min(x, work.right - w)), max(work.top, min(y, work.bottom - h))


def own_taskbar_button(root):
    """Give the window its own taskbar identity so it shows the Recast icon. Store-installed Python is a
    packaged app whose identity wins over the per-process ID, so this sets it on the window itself."""
    import ctypes
    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = [("a", wintypes.DWORD), ("b", wintypes.WORD), ("c", wintypes.WORD), ("d", ctypes.c_ubyte * 8)]

        def __init__(self, a, b, c, *d):
            super().__init__(a, b, c, (ctypes.c_ubyte * 8)(*d))

    class PROPERTYKEY(ctypes.Structure):
        _fields_ = [("fmtid", GUID), ("pid", wintypes.DWORD)]

    class PROPVARIANT(ctypes.Structure):
        _fields_ = [("vt", ctypes.c_ushort), ("r1", ctypes.c_ushort), ("r2", ctypes.c_ushort),
                    ("r3", ctypes.c_ushort), ("val", ctypes.c_wchar_p), ("pad", ctypes.c_void_p)]

    iid = GUID(0x886D8EEB, 0x8CF2, 0x4446, 0x8D, 0x02, 0xCD, 0xBA, 0x1D, 0xBD, 0xCF, 0x99)  # IPropertyStore
    key = PROPERTYKEY(GUID(0x9F4C2855, 0x9F79, 0x4B39, 0xA8, 0xD0, 0xE1, 0xD4, 0x2D, 0xE1, 0xD5, 0xF3), 5)  # AppUserModel.ID
    root.update_idletasks()
    hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
    store = ctypes.c_void_p()
    if ctypes.windll.shell32.SHGetPropertyStoreForWindow(hwnd, ctypes.byref(iid), ctypes.byref(store)):
        return
    vtbl = ctypes.cast(ctypes.cast(store, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.POINTER(ctypes.c_void_p))
    method = lambda i, *types: ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, *types)(vtbl[i])
    try:
        value = PROPVARIANT(vt=31, val="Recast.App")  # 31 = VT_LPWSTR
        method(6, ctypes.POINTER(PROPERTYKEY), ctypes.POINTER(PROPVARIANT))(store, ctypes.byref(key), ctypes.byref(value))
        method(7)(store)  # Commit
    finally:
        ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtbl[2])(store)  # Release


def exact_icons(root, ico):
    """Give the window the icon frames at exactly the sizes this screen's scaling uses (e.g. 40 and 20 px
    at 125%). Tk picks a nearby size and stretches it, which is what made the taskbar icon blurry."""
    import ctypes
    user32 = ctypes.windll.user32
    user32.LoadImageW.restype = ctypes.c_void_p
    user32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
    root.update_idletasks()
    hwnd = user32.GetParent(root.winfo_id())
    for which, metric in ((1, 11), (0, 49)):  # ICON_BIG / SM_CXICON, ICON_SMALL / SM_CXSMICON
        size = user32.GetSystemMetrics(metric)
        icon = user32.LoadImageW(None, str(ico), 1, size, size, 0x10)  # IMAGE_ICON, LR_LOADFROMFILE
        if icon:
            user32.SendMessageW(hwnd, 0x80, which, icon)  # WM_SETICON


def title_bar_theme(root, dark):
    """Windows draws the title bar light unless the window asks for dark."""
    import ctypes
    root.update_idletasks()
    hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
    ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(ctypes.c_int(dark)), 4)  # 20 = DWMWA_USE_IMMERSIVE_DARK_MODE
    # the frame only repaints on a size change, so nudge it
    w, h = root.winfo_width(), root.winfo_height()
    if w > 1:
        root.geometry(f"{w + 1}x{h}")
        root.update_idletasks()
        root.geometry(f"{w}x{h}")


def show_in_folder(path):
    subprocess.Popen(["explorer", "/select,", str(path)])


def setup_window(root, title):
    import sv_ttk
    from core import HERE
    root.title(title)
    try:
        root.iconbitmap(default=str(HERE / "assets" / "icon.ico"))
    except tk.TclError:
        pass
    try:
        exact_icons(root, HERE / "assets" / "icon.ico")
        own_taskbar_button(root)
        title_bar_theme(root, system_is_dark())
    except (OSError, AttributeError):
        pass  # cosmetic only: worst case the taskbar shows the Python icon or a light title bar
    sv_ttk.set_theme("dark" if system_is_dark() else "light")


# ------------------------------------------------------------------ right-click popup
def quick_convert(target, path):
    import converters
    import core
    root = tk.Tk()
    setup_window(root, "Recast")
    root.resizable(False, False)
    root.attributes("-topmost", True)
    src = Path(path)
    conv = converters.MAP.get(converters.ext_of(src.name), {}).get(target)
    label = conv.label if conv else target

    frame = ttk.Frame(root, padding=18)
    frame.pack(fill="both", expand=True)
    title = ttk.Label(frame, text={"clean": f"Removing metadata from {src.name}", "compress": f"Making {src.name} smaller"}.get(target, f"Converting {src.name}"), font=("Segoe UI Variable Display", 13, "bold"),
                      wraplength=360)
    title.pack(anchor="w")
    detail = ttk.Label(frame, text={"clean": "Saving a clean copy next to it", "compress": "Saving a smaller copy next to it"}.get(target, f"to {label}"), wraplength=360)
    detail.pack(anchor="w", pady=(2, 10))
    bar = ttk.Progressbar(frame, mode="indeterminate", length=360)
    bar.pack(fill="x")
    bar.start(12)
    buttons = ttk.Frame(frame)
    buttons.pack(fill="x", pady=(12, 0))

    # Next to the mouse (where you right-clicked), staggered so several conversions don't stack exactly.
    root.update_idletasks()
    w, h = 400, root.winfo_reqheight() + 40
    slot = os.getpid() % 5
    x, y = near_pointer(w, h, offset=16 + slot * 28)
    root.geometry(f"{w}x{h}+{x}+{y}")

    def finished(saved=None, error=None):
        bar.stop()
        bar.pack_forget()
        if error and error.startswith(ALREADY_SMALL):
            title.config(text=f"{src.name} is already small")
            detail.config(text="It couldn't get noticeably smaller, so no copy was made. "
                               "Open it in Recast and choose Strong for a smaller, lower-quality copy.")
            ttk.Button(buttons, text="Close", command=root.destroy).pack(side="right")
            return
        if error:
            title.config(text=f"Couldn't convert {src.name}")
            detail.config(text=error, foreground="#D9534F")
            ttk.Button(buttons, text="Close", command=root.destroy).pack(side="right")
            return
        title.config(text="Done")
        detail.config(text=f"Saved as {Path(saved).name}")
        ttk.Button(buttons, text="Close", command=root.destroy).pack(side="right")
        ttk.Button(buttons, text="Open", command=lambda: (os.startfile(saved), root.destroy())).pack(side="right", padx=6)
        ttk.Button(buttons, text="Show in folder", style="Accent.TButton",
                   command=lambda: (show_in_folder(saved), root.destroy())).pack(side="right")
        root.after(12000, root.destroy)

    ui = UiQueue(root)

    def work():
        try:
            ui(finished, core.convert([src], target))
        except Exception as e:
            ui(finished, None, str(e))

    threading.Thread(target=work, daemon=True).start()
    root.mainloop()


# ------------------------------------------------------------------ main window
class App:
    def __init__(self, files):
        import converters
        import shell
        import sv_ttk
        from converters.tools import status
        from tkinterdnd2 import DND_FILES, TkinterDnD
        self.converters, self.shell = converters, shell
        self.formats = converters.MAP
        self.tools = status()

        self.root = root = TkinterDnD.Tk()
        setup_window(root, "Recast")
        root.geometry("820x800")
        root.minsize(520, 520)
        self.items = {}  # tree row id -> {"path", "ext", "state", "saved"}
        self.dest = None  # None = next to each file
        self.busy = False
        self.sel = None  # chosen output id
        self.last_saved = None
        self.ui = UiQueue(root)

        outer = ttk.Frame(root, padding=(24, 16, 24, 16))
        outer.columnconfigure(0, weight=1)
        self.outer = outer
        # Re-laying out the themed widgets costs ~90 ms, so redoing it on every mouse move while the window
        # edge is dragged makes resizing stutter. The contents keep their size during a drag and catch up
        # once it pauses.
        self._settle = None
        outer.place(x=0, y=0, width=820, height=800)
        root.bind("<Configure>", lambda e: e.widget is root and self.resize_later())
        try:  # and Windows shouldn't repaint the whole window on each step either, only the uncovered strip
            import ctypes
            set_style = ctypes.windll.user32.SetClassLongPtrW
            set_style.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
            get_style = ctypes.windll.user32.GetClassLongPtrW
            get_style.restype = ctypes.c_ssize_t
            root.update_idletasks()
            for hwnd in (root.winfo_id(), ctypes.windll.user32.GetParent(root.winfo_id())):
                set_style(hwnd, -26, get_style(hwnd, -26) & ~0x3)  # GCL_STYLE without CS_VREDRAW | CS_HREDRAW
        except (OSError, AttributeError):
            pass

        # header
        top = ttk.Frame(outer)
        top.grid(row=0, column=0, sticky="ew")
        ttk.Label(top, text="Recast", font=("Segoe UI Variable Display", 16, "bold")).pack(side="left")
        ttk.Button(top, text="Settings", command=self.toggle_settings).pack(side="right")

        # settings, hidden until asked for
        self.settings = ttk.Frame(outer)
        toggles = ttk.Frame(self.settings)
        toggles.pack(anchor="e")
        self.dark_var = tk.BooleanVar(value=sv_ttk.get_theme() == "dark")
        ttk.Checkbutton(toggles, text="Dark mode", style="Switch.TCheckbutton",
                        variable=self.dark_var, command=self.toggle_theme).pack(side="left")
        self.menu_var = tk.BooleanVar(value=shell.is_installed())
        ttk.Checkbutton(toggles, text="Show in right-click menu", style="Switch.TCheckbutton",
                        variable=self.menu_var, command=self.toggle_menu).pack(side="left", padx=(24, 0))
        for t in self.tools.values():  # missing programs, and how to get them
            if not t["found"]:
                row = ttk.Frame(self.settings)
                row.pack(fill="x", pady=(8, 0))
                ttk.Label(row, text=f"{t['name']} isn't installed, so its formats are off. Install with:").pack(side="left")
                e = ttk.Entry(row, width=44)
                e.insert(0, t["install"])
                e.config(state="readonly")
                e.pack(side="left", padx=6)

        # drop zone: big when empty, one row once files are in
        self.drop = tk.Frame(outer, highlightthickness=1)
        self.drop.grid(row=2, column=0, sticky="ew", pady=(14, 14))
        self.drop_title = tk.Label(self.drop, text="Drop files here")
        self.add_btn = ttk.Button(self.drop, text="Add files…", command=self.browse)
        self.drag_over = False
        root.drop_target_register(DND_FILES)
        root.dnd_bind("<<Drop>>", self.on_drop)
        root.dnd_bind("<<DropEnter>>", lambda e: (self.set_drag(True), e.action)[1])
        root.dnd_bind("<<DropLeave>>", lambda e: (self.set_drag(False), e.action)[1])

        # setup: "Convert X to", chips, options, save + Convert
        self.setup = ttk.Frame(outer)
        self.setup.grid(row=3, column=0, sticky="ew")
        lead = ttk.Frame(self.setup)
        lead.pack(anchor="w")
        self.lead = [ttk.Label(lead, font=f) for f in (BODY, BOLD, BODY)]
        for w in self.lead:
            w.pack(side="left")
        self.chips = tk.Frame(self.setup)
        self.chips.pack(fill="x", pady=(8, 0))
        self.hint = ttk.Label(self.setup, wraplength=740)
        self.hint.pack(anchor="w")

        # options, shown only when they apply
        self.opts_frame = ttk.Frame(self.setup)
        self.opts_frame.pack(anchor="w", pady=(6, 0))
        self.vars = {"pages": tk.StringVar(), "quality": tk.IntVar(value=90), "max_size": tk.StringVar(value="Keep original"),
                     "resolution": tk.StringVar(value="Keep original"), "lang": tk.StringVar(value="eng"),
                     "strength": tk.StringVar(value="Light")}
        self.opt_widgets = {}

        def opt(key, label, widget):
            f = ttk.Frame(self.opts_frame)
            ttk.Label(f, text=label).pack(anchor="w")
            w = widget(f)
            w.pack(anchor="w")
            if isinstance(w, ttk.Combobox):  # a readonly dropdown keeps its text highlighted after a pick
                w.bind("<<ComboboxSelected>>", lambda e: (e.widget.selection_clear(), self.root.focus_set()))
            self.opt_widgets[key] = f
        opt("pages", "Pages (e.g. 1-3, 5)", lambda f: ttk.Entry(f, textvariable=self.vars["pages"], width=16))

        def quality(f):
            box = ttk.Frame(f)
            ttk.Scale(box, from_=40, to=100, variable=self.vars["quality"], length=140,
                      command=lambda v: self.vars["quality"].set(round(float(v)))).pack(side="left")
            ttk.Label(box, textvariable=self.vars["quality"], width=4).pack(side="left", padx=6)
            return box
        opt("quality", "Quality", quality)
        opt("max_size", "Longest side (px)", lambda f: ttk.Combobox(
            f, textvariable=self.vars["max_size"], state="readonly", width=14,
            values=["Keep original", "3840", "1920", "1280", "800", "256"]))
        opt("resolution", "Video height", lambda f: ttk.Combobox(
            f, textvariable=self.vars["resolution"], state="readonly", width=14,
            values=["Keep original", "1080", "720", "480", "360"]))
        opt("lang", "Text language", lambda f: ttk.Entry(f, textvariable=self.vars["lang"], width=12))
        opt("strength", "How much smaller", lambda f: ttk.Combobox(
            f, textvariable=self.vars["strength"], state="readonly", width=30,
            values=["Light", "Strong"]))
        self.strength_note = ttk.Label(self.opt_widgets["strength"], font=SMALL)
        self.strength_note.pack(anchor="w")
        self.vars["strength"].trace_add("write", lambda *_: self.strength_note.config(text=(
            "Smallest file, lower quality you can see" if self.vars["strength"].get() == "Strong"
            else "Looks the same, a bit smaller")))
        self.vars["strength"].set("Light")

        go_row = ttk.Frame(self.setup)
        go_row.pack(fill="x", pady=(12, 0))
        self.save_text = ttk.Label(go_row, text="Saved next to each file  ·", font=BODY)
        self.save_text.pack(side="left")
        self.change = tk.Label(go_row, text="Change", cursor="hand2", font=("Segoe UI", 11, "underline"), takefocus=1)
        self.change.pack(side="left", padx=(4, 0))
        for seq in ("<Button-1>", "<Return>", "<space>"):
            self.change.bind(seq, self.change_dest)
        self.go = ttk.Button(go_row, text="Convert", style="Big.Accent.TButton", command=self.go_pressed)
        self.go.pack(side="right")

        # file list
        self.lst = ttk.Frame(outer)
        self.lst.grid(row=4, column=0, sticky="nsew", pady=(16, 0))
        outer.rowconfigure(4, weight=1)
        self.tree = ttk.Treeview(self.lst, columns=("status", "saved", "show"), selectmode="extended")
        self.tree.heading("#0", text="File", anchor="w")
        self.tree.heading("status", text="Status", anchor="w")
        self.tree.heading("saved", text="Saved as", anchor="w")
        self.tree.column("#0", width=260, stretch=True)
        self.tree.column("status", width=200, stretch=True)
        self.tree.column("saved", width=200, stretch=True)
        self.tree.column("show", width=60, stretch=False)
        sb = ttk.Scrollbar(self.lst, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<Button-1>", self.on_row_click)
        self.tree.bind("<Delete>", lambda e: self.remove_selected())
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.update_remove())

        self.bottom = ttk.Frame(outer)
        self.bottom.grid(row=5, column=0, sticky="ew", pady=(10, 0))
        self.remove_btn = ttk.Button(self.bottom, text="Remove selected", command=self.remove_selected)
        self.remove_btn.pack(side="left")
        ttk.Button(self.bottom, text="Clear list", command=self.clear).pack(side="left", padx=8)

        self.footer = ttk.Label(outer, font=SMALL, text="Runs on this computer only. Nothing is uploaded, "
                                                        "and your original files are never changed.")
        self.footer.grid(row=6, column=0, sticky="w", pady=(12, 0))

        self.apply_theme_colors()
        self.add_files(files)
        self.refresh()

    # ---------- files
    def add_files(self, paths):
        for p in paths:
            p = Path(p)
            if p.is_dir():
                self.add_files(sorted(x for x in p.iterdir() if x.is_file()))
                continue
            ext = self.converters.ext_of(p.name)
            ok = ext in self.formats
            iid = self.tree.insert("", "end", text=p.name,
                                   values=("Waiting" if ok else f"Failed: .{ext or '?'} files aren't supported", "", ""),
                                   tags=("waiting",) if ok else ("failed",))
            self.items[iid] = {"path": p, "ext": ext, "state": "waiting" if ok else "unsupported", "saved": None}
        self.refresh()

    def browse(self):
        self.add_files(filedialog.askopenfilenames(title="Add files to convert"))

    def on_drop(self, event):
        self.set_drag(False)
        self.add_files(self.root.tk.splitlist(event.data))
        return event.action

    def set_drag(self, on):
        self.drag_over = on
        self.color_drop()

    def remove_selected(self):
        for iid in self.tree.selection():
            if self.items[iid]["state"] != "working":
                self.tree.delete(iid)
                del self.items[iid]
        self.refresh()

    def clear(self):
        for iid in list(self.items):
            if self.items[iid]["state"] != "working":
                self.tree.delete(iid)
                del self.items[iid]
        self.refresh()

    def on_row_click(self, event):
        """A click selects or unselects a row; "Show" on a finished row opens its folder."""
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        if self.tree.identify_column(event.x) == "#3" and self.items[iid]["saved"]:
            show_in_folder(self.items[iid]["saved"])
        else:
            self.tree.selection_toggle(iid)
        return "break"

    def update_remove(self):
        self.remove_btn.config(state="normal" if self.tree.selection() else "disabled")

    def change_dest(self, event):
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label="Next to each file", command=lambda: self.set_dest(None))
        m.add_command(label="Choose folder…", command=lambda: self.set_dest(
            filedialog.askdirectory(title="Save converted files in") or self.dest))
        m.tk_popup(self.change.winfo_rootx(), self.change.winfo_rooty() + self.change.winfo_height())

    def set_dest(self, folder):
        self.dest = Path(folder) if folder else None
        self.save_text.config(text=f"Saved in {self.dest}  ·" if self.dest else "Saved next to each file  ·")

    # ---------- what the files can become
    def pending(self):
        return [i for i in self.items.values() if i["state"] in ("waiting", "failed")]

    def choices(self):
        """[(id, label, usable)] that every pending file can become, in chip order."""
        exts = list(dict.fromkeys(i["ext"] for i in self.pending()))
        if not exts:
            return []
        common = list(self.formats[exts[0]].items())
        for e in exts[1:]:
            common = [(k, c) for k, c in common if k in self.formats[e]]
        multi = []
        if len(self.pending()) > 1:
            multi = [(k, c) for k, c in self.converters.MULTI.items()
                     if all(e in self.converters.MULTI_ACCEPTS[k] for e in exts)]
        out = []
        for k, c in multi + common:
            missing = [self.tools[t]["name"] for t in c.needs if not self.tools[t]["found"]]
            out.append((k, c.label + (f"  (needs {', '.join(missing)})" if missing else ""), not missing))
        order = list(CHIPS)
        return sorted(out, key=lambda o: order.index(o[0]) if o[0] in order else len(order))

    def pick(self, target):
        if not self.busy:
            self.sel = target
            self.refresh()

    def chip(self, col, title, sub, selected, on_click, parent=None):
        c = self.colors
        bg = c["tint"] if selected else c["field"]
        line = c["accent"] if selected else c["border"]
        parent = parent or self.chips
        f = tk.Frame(parent, bg=bg, cursor="hand2", takefocus=1, highlightthickness=1,
                     highlightbackground=line, highlightcolor=c["accent"])
        f.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 8, 0))
        parent.columnconfigure(col, weight=1, uniform="chip")
        a = tk.Label(f, text=title, font=("Segoe UI", 11, "bold"), bg=bg, fg=c["text"])
        b = tk.Label(f, text=sub, font=SMALL, bg=bg, fg=c["accent"] if selected else c["muted"])
        a.pack(pady=(10, 0))
        b.pack(pady=(0, 10))
        for w in (f, a, b):
            w.bind("<Button-1>", on_click)
        for seq in ("<Return>", "<space>"):
            f.bind(seq, on_click)

    def more_menu(self, event, more):
        m = tk.Menu(self.root, tearoff=0)
        for k, label, ok in more:
            m.add_command(label=label, state="normal" if ok else "disabled", command=lambda k=k: self.pick(k))
        m.tk_popup(event.widget.winfo_rootx(), event.widget.winfo_rooty() + event.widget.winfo_height())

    def refresh(self):
        opts = self.choices()
        usable = [k for k, _, ok in opts if ok]
        if usable and self.sel not in usable:  # no files waiting (e.g. mid-batch): keep the choice
            self.sel = usable[0]
        target = self.sel
        pend = self.pending()
        has = bool(self.items)
        done = has and not pend and any(i["state"] == "done" for i in self.items.values())

        for w in (self.setup, self.lst, self.bottom):
            w.grid() if has else w.grid_remove()
        self.layout_drop(not has)

        # "Convert Lab 4.pdf to" / "Converting…" / "All done"
        names = [i["path"].name for i in pend]
        text = (("Converting…", "", "") if self.busy else ("All done", "", "") if done else
                ("Convert ", names[0] if len(names) == 1 else f"{len(names)} files", " to") if names else ("", "", ""))
        for w, t in zip(self.lead, text):
            w.config(text=t)

        # chips: the first few usable formats, everything else under "More"
        for w in self.chips.winfo_children():
            w.destroy()
        for col in range(MAX_CHIPS + 1):
            self.chips.columnconfigure(col, weight=0, uniform="")
        primary = [k for k in usable if k in CHIPS][:MAX_CHIPS]
        tools = [k for k in TOOLS if k in usable]
        more = [o for o in opts if o[0] not in primary and o[0] not in tools]
        if pend and not self.busy:
            for col, k in enumerate(primary):
                self.chip(col, *CHIPS[k], k == target, lambda e, k=k: self.pick(k))
            if more:
                picked = next((label for k, label, _ in more if k == target), None)
                self.chip(len(primary), picked or "More", "▾", bool(picked), lambda e: self.more_menu(e, more))
            if tools:
                ttk.Label(self.chips, text="Or keep the same type", font=BODY).grid(
                    row=1, column=0, columnspan=MAX_CHIPS + 1, sticky="w", pady=(14, 6))
                row = tk.Frame(self.chips, bg=self.chips.cget("bg"))  # two equal halves, whatever the formats above
                row.grid(row=2, column=0, columnspan=MAX_CHIPS + 1, sticky="ew")
                for col, k in enumerate(tools):
                    self.chip(col, *TOOLS[k], k == target, lambda e, k=k: self.pick(k), parent=row)
        # an emptied Tk frame keeps its old size, so take it out of the layout instead
        if self.chips.winfo_children():
            self.chips.pack(fill="x", pady=(8, 0), before=self.hint)
        else:
            self.chips.pack_forget()

        c = self.colors
        if pend and not opts:
            self.hint.config(text="These files can't be turned into the same format. Convert them one type at a time.",
                             foreground=c["error"])
        elif target in self.converters.MULTI and not self.busy:
            self.hint.config(text=f"All {len(pend)} files go into one PDF, in the order listed.", foreground=c["muted"])
        else:
            self.hint.config(text="")
        self.hint.pack_configure(pady=(6, 0) if self.hint.cget("text") else 0)

        if self.busy:
            self.go.config(text="Converting…", state="disabled")
        elif done:
            self.go.config(text="Show in folder", state="normal")
        else:
            self.go.config(text="Convert", state="normal" if (target and pend) else "disabled")
        self.update_remove()

        exts = list(dict.fromkeys(i["ext"] for i in pend))
        images = set(self.converters.IMAGES)
        show = {
            "pages": bool(target) and "pdf" in exts and target not in (*self.converters.MULTI, "compress", "clean"),
            "strength": target == "compress",
            "quality": target in ("jpg", "webp", "heic"),
            "max_size": bool(images & set(exts)) and (target in images or target in ("pdf", "images-pdf")),
            "resolution": target in ("mp4", "webm", "gif"),
            "lang": bool(target and target.startswith("ocr")),
        }
        for key, frame in self.opt_widgets.items():
            frame.pack_forget()
            if show[key] and not self.busy:
                frame.pack(side="left", padx=(0, 18))
        if any(f.winfo_manager() for f in self.opt_widgets.values()):
            self.opts_frame.pack(anchor="w", pady=(6, 0), after=self.hint)
        else:
            self.opts_frame.pack_forget()

    def layout_drop(self, empty):
        if getattr(self, "_drop_empty", None) == empty:
            return
        self._drop_empty = empty
        for w in (self.drop_title, self.add_btn):
            w.pack_forget()
        if empty:
            self.drop_title.config(font=("Segoe UI Variable Display", 18, "bold"))
            self.drop_title.pack(pady=(64, 12))
            self.add_btn.pack(pady=(0, 64))
        else:
            self.drop_title.config(font=("Segoe UI Variable Display", 13, "bold"))
            self.drop_title.pack(side="left", padx=20, pady=14)
            self.add_btn.pack(side="right", padx=16)

    def options(self):
        o = {}
        for key, frame in self.opt_widgets.items():
            if frame.winfo_manager():
                v = str(self.vars[key].get()).strip()
                if v and v != "Keep original":
                    o[key] = v
        return o

    # ---------- converting
    def set_row(self, iid, status, tag=None, saved=""):
        if self.tree.exists(iid):
            self.tree.item(iid, values=(status, saved, "Show" if tag == "done" else ""), tags=(tag,) if tag else ())

    def go_pressed(self):
        if self.go.cget("text") == "Show in folder":
            show_in_folder(self.last_saved)
        else:
            self.start()

    def start(self):
        import core
        target, opts, dest = self.sel, self.options(), self.dest
        batch = [iid for iid, i in self.items.items() if i["state"] in ("waiting", "failed")]
        if not target or not batch:
            return
        groups = [batch] if target in self.converters.MULTI else [[iid] for iid in batch]
        self.busy = True
        for iid in batch:
            self.items[iid]["state"] = "working"
            self.set_row(iid, "Waiting", "waiting")
        self.refresh()

        def work():
            for group in groups:
                for iid in group:
                    self.ui(self.set_row, iid, "Converting…", "working")
                try:
                    saved = core.convert([self.items[i]["path"] for i in group], target, opts, dest)
                    self.last_saved = saved
                    for n, iid in enumerate(group):
                        self.items[iid].update(state="done", saved=saved)
                        self.ui(self.set_row, iid, "Done" if n == 0 else "Done (included)",
                                "done", Path(saved).name)
                except Exception as e:
                    for iid in group:
                        self.items[iid]["state"] = "failed"  # stays in the batch, e.g. to retry on Strong
                        if str(e).startswith(ALREADY_SMALL):
                            self.ui(self.set_row, iid, "Already small"
                                    + ("" if opts.get("strength") == "Strong" else ", try Strong"), "waiting")
                        else:
                            self.ui(self.set_row, iid, f"Failed: {e}", "failed")
            self.busy = False
            self.ui(self.refresh)

        threading.Thread(target=work, daemon=True).start()

    # ---------- settings
    def toggle_settings(self):
        if self.settings.winfo_manager():
            self.settings.grid_remove()
        else:
            self.settings.grid(row=1, column=0, sticky="ew", pady=(10, 0))

    def toggle_menu(self):
        try:
            self.shell.install() if self.menu_var.get() else self.shell.uninstall()
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Recast", f"Couldn't change the right-click menu: {e}")
        self.menu_var.set(self.shell.is_installed())

    def toggle_theme(self):
        import sv_ttk
        sv_ttk.set_theme("dark" if self.dark_var.get() else "light")
        try:
            title_bar_theme(self.root, self.dark_var.get())
        except (OSError, AttributeError):
            pass
        self.apply_theme_colors()
        self.refresh()

    def color_drop(self):
        c = self.colors
        bg = mix(c["accent"], c["card"], 0.12) if self.drag_over else c["card"]
        line = c["accent"] if self.drag_over else c["border"]
        self.drop.config(bg=bg, highlightbackground=line, highlightcolor=line)
        self.drop_title.config(bg=bg, fg=c["text"])

    def resize_later(self):
        if self._settle:
            self.root.after_cancel(self._settle)
        self._settle = self.root.after(120, lambda: self.outer.place_configure(
            width=self.root.winfo_width(), height=self.root.winfo_height()))

    def apply_theme_colors(self):
        import sv_ttk
        theme = sv_ttk.get_theme()
        c = self.colors = dict(THEMES[theme])
        c["tint"] = mix(c["accent"], c["field"], 0.16)
        style = ttk.Style()
        bg = style.lookup("TFrame", "background") or self.root.cget("bg")
        self.root.config(bg=bg)  # what shows in the gap while a resize catches up
        self.chips.config(bg=bg)
        self.change.config(bg=bg, fg=c["accent"])
        self.footer.config(foreground=c["muted"])
        self.strength_note.config(foreground=c["muted"])
        self.color_drop()
        style.configure("Big.Accent.TButton", font=("Segoe UI", 12, "bold"), padding=(34, 8))
        style.map("Treeview", background=[("selected", c["tint"])], foreground=[("selected", c["text"])])
        self.tree.tag_configure("waiting", foreground=c["muted"])
        self.tree.tag_configure("working", foreground=c["accent"])
        self.tree.tag_configure("done", foreground=c["done"])
        self.tree.tag_configure("failed", foreground=c["error"])


def main():
    try:  # sharp text on high-DPI screens; must happen before the first window
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        # own taskbar identity, or Windows groups the window under pythonw.exe and shows the Python icon
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Recast.App")
    except Exception:
        pass
    args = sys.argv[1:]
    if len(args) >= 3 and args[0] == "--convert":
        quick_convert(args[1], args[2])
    else:
        App(args).root.mainloop()


if __name__ == "__main__":
    mp.freeze_support()  # lets the .exe start its own conversion worker processes
    sys.path.insert(0, str(Path(__file__).parent))
    main()
