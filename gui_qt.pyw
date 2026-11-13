"""The Recast window, in Qt (PySide6): files on the left, what to make of them on the right.

    gui_qt.pyw [FILE...]               open the window
    gui_qt.pyw --convert TARGET FILE   the right-click popup: handed to gui.pyw's small Tk one, which starts faster

Everything that isn't drawing (formats, colours, engine, Windows tweaks) comes from gui.pyw and core.py.
Without PySide6 installed, it opens gui.pyw's Tkinter window instead.
"""
import multiprocessing as mp
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gui as G  # noqa: E402  (gui.pyw; Windows imports .pyw like .py)
from core import HERE  # noqa: E402  (the app folder, also inside the .exe)

# Create an empty file with this name next to the app to hide the "runs on this computer" line.
SHOW_PRIVACY_NOTE = not (HERE / "hide-privacy-note").exists()
BG = {"dark": "#121212", "light": "#eef0f3"}  # window background
ON_ACCENT = {"dark": "#06202e", "light": "#ffffff"}


def palette(theme):
    c = dict(G.THEMES[theme], bg=BG[theme], on_accent=ON_ACCENT[theme])
    c["side"] = G.mix(c["card"], c["bg"], 0.55) if theme == "dark" else c["card"]
    c["tint"] = G.mix(c["accent"], c["field"], 0.16)
    c["drop_tint"] = G.mix(c["accent"], c["bg"], 0.10)
    c["go_off"] = G.mix(c["accent"], c["side"], 0.35)  # the disabled Convert button: accent at 35%
    return c


def human(n):
    """1536 -> '1.5 KB'."""
    for unit in ("B", "KB", "MB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit != "MB" else f"{n:.1f} MB"
        n /= 1024
    return f"{n:.1f} GB"


def stylesheet(c):
    return f"""
    QWidget {{ color: {c['text']}; font-family: "Segoe UI"; font-size: 10.5pt; }}
    QWidget#window, QDialog, QMessageBox {{ background: {c['bg']}; }}
    QLabel {{ background: transparent; }}
    QLabel#appName {{ font-size: 11pt; font-weight: 600; }}
    QLabel#heading {{ font-size: 15pt; font-weight: 600; }}
    QLabel#muted, QLabel#meta {{ color: {c['muted']}; font-size: 9.5pt; }}
    QLabel#section {{ color: {c['muted']}; font-size: 9.5pt; font-weight: 600; }}
    QLabel#meta[tag="working"] {{ color: {c['accent']}; }}
    QLabel#meta[tag="done"] {{ color: {c['done']}; }}
    QLabel#meta[tag="failed"], QLabel#error {{ color: {c['error']}; }}
    QLabel#dropTitle {{ font-size: 17pt; font-weight: 600; }}
    QFrame#row {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 10px; }}
    QFrame#row[picked="true"] {{ background: {c['tint']}; border: 1px solid {c['accent']}; }}
    QLabel#badge {{ background: {c['field']}; color: {c['muted']}; border-radius: 6px; font-size: 7.5pt;
                    font-weight: 700; }}
    QLabel#rowName {{ font-weight: 500; }}
    QFrame#side {{ background: {c['side']}; border: none; border-left: 1px solid {c['border']}; }}
    QFrame#drop {{ background: transparent; border: 1px dashed {c['border']}; border-radius: 12px; }}
    QFrame#drop[over="true"] {{ background: {c['drop_tint']}; border: 1px solid {c['accent']}; }}
    QScrollArea, QWidget#listInner {{ background: transparent; border: none; }}
    QPushButton {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 7px; padding: 6px 14px; }}
    QPushButton:hover {{ border-color: {c['muted']}; }}
    QPushButton:disabled {{ color: {c['muted']}; border-color: {c['border']}; }}
    QPushButton:focus {{ border-color: {c['accent']}; }}
    QPushButton#flat {{ background: transparent; border: 1px solid transparent; color: {c['muted']}; }}
    QPushButton#flat:hover {{ color: {c['text']}; border-color: {c['border']}; }}
    QPushButton#x {{ background: transparent; border: none; color: {c['muted']}; padding: 0; border-radius: 6px; }}
    QPushButton#x:hover {{ background: {c['field']}; color: {c['text']}; }}
    QPushButton#x:disabled {{ color: transparent; }}
    QPushButton#go {{ background: {c['accent']}; color: {c['on_accent']}; border: none; border-radius: 10px;
                      font-size: 11.5pt; font-weight: 700; min-height: 46px; }}
    QPushButton#go:disabled {{ background: {c['go_off']}; color: {c['on_accent']}; }}
    QPushButton#chip {{ background: {c['field']}; border-radius: 9px; padding: 0; }}
    QPushButton#chip[selected="true"] {{ background: {c['tint']}; border: 1px solid {c['accent']}; }}
    QPushButton#chip:disabled {{ border-color: {c['border']}; }}
    QLabel#chipTitle {{ font-weight: 600; }}
    QLabel#chipSub {{ color: {c['muted']}; font-size: 9pt; }}
    QLabel#chipSubOn {{ color: {c['accent']}; font-size: 9pt; }}
    QPushButton#link {{ background: transparent; border: none; color: {c['accent']}; padding: 0; }}
    QPushButton#link:hover {{ text-decoration: underline; }}
    QComboBox, QLineEdit {{ background: {c['field']}; border: 1px solid {c['border']}; border-radius: 7px;
                            padding: 5px 8px; }}
    QComboBox:focus, QLineEdit:focus {{ border-color: {c['accent']}; }}
    QComboBox::drop-down {{ border: none; width: 22px; }}
    QComboBox QAbstractItemView {{ background: {c['card']}; border: 1px solid {c['border']};
                                   selection-background-color: {c['tint']}; selection-color: {c['text']}; }}
    QMenu {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 6px; padding: 4px; }}
    QMenu::item {{ padding: 6px 18px; border-radius: 4px; }}
    QMenu::item:selected {{ background: {c['tint']}; }}
    QMenu::item:disabled {{ color: {c['muted']}; }}
    QProgressBar {{ background: {c['field']}; border: none; border-radius: 1px; }}
    QProgressBar::chunk {{ background: {c['accent']}; border-radius: 1px; }}
    QSlider::groove:horizontal {{ background: {c['field']}; height: 4px; border-radius: 2px; }}
    QSlider::handle:horizontal {{ background: {c['accent']}; width: 14px; margin: -5px 0; border-radius: 7px; }}
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {c['border']}; border-radius: 3px; min-height: 24px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
    """


def main():
    args = sys.argv[1:]
    try:
        import PySide6  # noqa: F401
    except ImportError:
        args = ["--convert"]  # falls through to gui.pyw, which opens its own window
    if args[:1] == ["--convert"]:
        G.main()  # the light Tk popup (or, without PySide6, the Tk window); it reads the same sys.argv
        return

    from PySide6.QtCore import QObject, QSize, Qt, Signal
    from PySide6.QtGui import QColor, QIcon, QPainter
    from PySide6.QtWidgets import (QAbstractButton, QApplication, QComboBox, QFileDialog, QFrame, QGraphicsOpacityEffect, QGridLayout,
                                   QHBoxLayout, QLabel, QLineEdit, QMenu, QMessageBox, QProgressBar, QPushButton,
                                   QScrollArea, QSizePolicy, QSlider, QVBoxLayout, QWidget)
    import converters
    import shell
    from converters.tools import ALREADY_SMALL, status

    def repolish(w):
        w.style().unpolish(w)
        w.style().polish(w)

    def clear_layout(lay):
        while lay.count():
            w = lay.takeAt(0).widget()
            if w:
                w.setParent(None)  # deleteLater alone leaves it painted until the next event loop pass
                w.deleteLater()

    def shrinkable(label):
        """A label that gets cut off in a narrow window instead of forcing the window wider."""
        label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        label.setMinimumWidth(0)
        return label

    class Switch(QAbstractButton):
        """The 38x22 pill toggle."""

        def __init__(self, text, window):
            super().__init__()
            self.setCheckable(True)
            self.setText(text)
            self.setCursor(Qt.PointingHandCursor)
            self.w = window

        def sizeHint(self):
            return QSize(46 + self.fontMetrics().horizontalAdvance(self.text()), 26)

        def paintEvent(self, event):
            c = self.w.colors
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            on = self.isChecked()
            p.setPen(QColor(c["accent"] if on else c["border"]))
            p.setBrush(QColor(c["accent"] if on else c["field"]))
            p.drawRoundedRect(0, 2, 38, 22, 11, 11)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(c["on_accent"] if on else c["muted"]))
            p.drawEllipse(21 if on else 5, 7, 12, 12)
            p.setPen(QColor(c["text"]))
            p.drawText(self.rect().adjusted(46, 0, 0, 0), Qt.AlignVCenter | Qt.AlignLeft, self.text())

    class Bus(QObject):
        """Worker thread -> window: Qt signals cross threads safely."""
        row = Signal(object, str, str, str)
        finished = Signal()

    class FileRow(QFrame):
        """One file: type badge, name, size and status, a progress line while it converts."""

        def __init__(self, window, path, ext):
            super().__init__()
            self.setObjectName("row")
            self.window_ = window
            self.setCursor(Qt.PointingHandCursor)
            try:
                self.bytes = path.stat().st_size
            except OSError:
                self.bytes = 0
            lay = QHBoxLayout(self)
            lay.setContentsMargins(12, 10, 8, 10)
            lay.setSpacing(12)
            badge = QLabel((ext or "?").upper()[:4])
            badge.setObjectName("badge")
            badge.setFixedSize(38, 42)
            badge.setAlignment(Qt.AlignHCenter | Qt.AlignBottom)
            badge.setContentsMargins(0, 0, 0, 6)
            lay.addWidget(badge)
            mid = QVBoxLayout()
            mid.setSpacing(3)
            self.name = shrinkable(QLabel(path.name))
            self.name.setObjectName("rowName")
            self.name.setToolTip(str(path))
            self.meta = shrinkable(QLabel())
            self.meta.setObjectName("meta")
            self.bar = QProgressBar()
            self.bar.setRange(0, 0)  # keeps moving while this file converts
            self.bar.setTextVisible(False)
            self.bar.setFixedHeight(3)
            self.bar.hide()
            mid.addWidget(self.name)
            mid.addWidget(self.meta)
            mid.addWidget(self.bar)
            lay.addLayout(mid, 1)
            self.show_btn = QPushButton("Show in folder")
            self.show_btn.setObjectName("link")
            self.show_btn.setCursor(Qt.PointingHandCursor)
            self.show_btn.clicked.connect(lambda: G.show_in_folder(window.items[self]["saved"]))
            self.show_btn.hide()
            lay.addWidget(self.show_btn)
            self.x = QPushButton("✕")
            self.x.setObjectName("x")
            self.x.setFixedSize(30, 30)
            self.x.setToolTip("Remove from the list")
            self.x.setAccessibleName(f"Remove {path.name}")
            self.x.setCursor(Qt.PointingHandCursor)
            self.x.clicked.connect(lambda: window.remove_rows([self]))
            lay.addWidget(self.x)

        def mousePressEvent(self, event):  # clicking a file picks it (the buttons on it handle their own clicks)
            if event.button() == Qt.LeftButton:
                self.window_.toggle_pick(self)

        def show_state(self, text, tag, busy):
            size = human(self.bytes) if self.bytes else ""
            self.meta.setText(" · ".join(t for t in (size, text) if t))
            self.meta.setToolTip(text if len(text) > 40 else "")
            self.meta.setProperty("tag", tag)
            repolish(self.meta)
            self.bar.setVisible(tag == "working")
            self.show_btn.setVisible(tag == "done")
            self.x.setEnabled(tag != "working" and not busy)

    class Window(QWidget):
        def __init__(self, files):
            super().__init__()
            self.setObjectName("window")
            self.setAttribute(Qt.WA_StyledBackground)
            self.formats, self.tools = converters.MAP, status()
            self.items = {}  # FileRow -> {"path", "ext", "state", "saved", "tag", "text"}
            self.dest, self.busy, self.sel, self.last_saved = None, False, None, None
            self.picked = set()  # rows clicked to convert only those; empty = all of them
            self.theme = "dark" if G.system_is_dark() else "light"
            self.colors = palette(self.theme)
            self.bus = Bus()
            self.bus.row.connect(self.set_row)
            self.bus.finished.connect(self.batch_done)

            self.setWindowTitle("Recast")
            icon = QIcon(str(HERE / "assets" / "icon.ico"))
            self.setWindowIcon(icon)
            self.resize(980, 680)
            self.setMinimumSize(720, 520)
            self.setAcceptDrops(True)
            root = QVBoxLayout(self)
            root.setContentsMargins(0, 0, 0, 0)
            root.setSpacing(0)

            # header: logo, name, settings
            top = QHBoxLayout()
            top.setContentsMargins(20, 12, 16, 12)
            top.setSpacing(10)
            logo = QLabel()
            logo.setPixmap(icon.pixmap(QSize(22, 22), QApplication.primaryScreen().devicePixelRatio()))
            top.addWidget(logo)
            name = QLabel("Recast")
            name.setObjectName("appName")
            top.addWidget(name)
            top.addStretch()
            settings_btn = QPushButton("Settings")
            settings_btn.setObjectName("flat")
            settings_btn.setCursor(Qt.PointingHandCursor)
            settings_btn.clicked.connect(lambda: self.settings.setVisible(not self.settings.isVisible()))
            top.addWidget(settings_btn)
            root.addLayout(top)

            # settings, hidden until asked for
            self.settings = QWidget()
            s = QVBoxLayout(self.settings)
            s.setContentsMargins(24, 0, 24, 12)
            toggles = QHBoxLayout()
            toggles.addStretch()
            self.dark_switch = Switch("Dark mode", self)
            self.dark_switch.setChecked(self.theme == "dark")
            self.dark_switch.toggled.connect(lambda on: self.apply_theme("dark" if on else "light"))
            self.menu_switch = Switch("Show in right-click menu", self)
            self.menu_switch.setChecked(shell.is_installed())
            self.menu_switch.toggled.connect(self.toggle_menu)
            toggles.addWidget(self.dark_switch)
            toggles.addSpacing(24)
            toggles.addWidget(self.menu_switch)
            s.addLayout(toggles)
            for t in self.tools.values():  # missing programs, and how to get them
                if not t["found"]:
                    row = QHBoxLayout()
                    row.addWidget(QLabel(f"{t['name']} isn't installed, so its formats are off. Install with:"))
                    cmd = QLineEdit(t["install"])
                    cmd.setReadOnly(True)
                    row.addWidget(cmd, 1)
                    s.addLayout(row)
            self.settings.hide()
            root.addWidget(self.settings)

            body = QHBoxLayout()
            body.setSpacing(0)
            root.addLayout(body, 1)

            # left: the files
            left_w = QWidget()
            self.left = QVBoxLayout(left_w)
            self.left.setContentsMargins(24, 8, 24, 24)
            self.left.setSpacing(12)
            head = QHBoxLayout()
            self.heading = QLabel("Your files")
            self.heading.setObjectName("heading")
            head.addWidget(self.heading)
            head.addSpacing(6)
            self.summary = QLabel()
            self.summary.setObjectName("muted")
            head.addWidget(self.summary, 0, Qt.AlignBottom)
            head.addStretch()
            self.clear_btn = QPushButton("Clear list")
            self.clear_btn.setObjectName("flat")
            self.clear_btn.setCursor(Qt.PointingHandCursor)
            self.clear_btn.clicked.connect(lambda: self.unpick() if self.picked else self.clear())
            head.addWidget(self.clear_btn)
            self.head_w = QWidget()
            self.head_w.setLayout(head)
            head.setContentsMargins(0, 0, 0, 0)
            self.left.addWidget(self.head_w)

            self.scroll = QScrollArea()
            self.scroll.setWidgetResizable(True)
            self.scroll.setFrameShape(QFrame.NoFrame)
            inner = QWidget()
            inner.setObjectName("listInner")
            self.list = QVBoxLayout(inner)
            self.list.setContentsMargins(0, 0, 4, 0)
            self.list.setSpacing(8)
            self.list.addStretch()
            self.scroll.setWidget(inner)
            self.scroll.viewport().setAutoFillBackground(False)
            self.left.addWidget(self.scroll, 1)

            # drop zone: the whole window when empty, a slim strip under the list after
            self.drop = QFrame()
            self.drop.setObjectName("drop")
            d = QVBoxLayout(self.drop)
            d.setContentsMargins(16, 10, 12, 10)
            self.drop_big = QWidget()
            big = QVBoxLayout(self.drop_big)
            big.setSpacing(10)
            big.addStretch()
            t = QLabel("Drop files here")
            t.setObjectName("dropTitle")
            big.addWidget(t, 0, Qt.AlignHCenter)
            sub = QLabel("PDF, Word, PowerPoint, Excel, images, audio and video")
            sub.setObjectName("muted")
            big.addWidget(sub, 0, Qt.AlignHCenter)
            big.addSpacing(6)
            add_btn = QPushButton("Add files…")
            add_btn.setCursor(Qt.PointingHandCursor)
            add_btn.clicked.connect(self.browse)
            big.addWidget(add_btn, 0, Qt.AlignHCenter)
            big.addStretch()
            if SHOW_PRIVACY_NOTE:
                note = QLabel("Runs on this computer only. Nothing is uploaded, and your original files are never changed.")
                note.setObjectName("muted")
                note.setWordWrap(True)
                note.setAlignment(Qt.AlignHCenter)
                big.addWidget(note)
            self.drop_small = QWidget()
            small = QHBoxLayout(self.drop_small)
            small.setContentsMargins(0, 0, 0, 0)
            more_text = QLabel("Drop more files here, or")
            more_text.setObjectName("muted")
            small.addStretch()
            small.addWidget(more_text)
            browse = QPushButton("browse")
            browse.setObjectName("link")
            browse.setCursor(Qt.PointingHandCursor)
            browse.clicked.connect(self.browse)
            small.addWidget(browse)
            small.addStretch()
            d.addWidget(self.drop_big)
            d.addWidget(self.drop_small)
            self.left.addWidget(self.drop)
            body.addWidget(left_w, 1)

            # right: what to make of them
            self.side = QFrame()
            self.side.setObjectName("side")
            self.side.setFixedWidth(330)
            side_lay = QVBoxLayout(self.side)
            side_lay.setContentsMargins(0, 0, 0, 20)
            side_lay.setSpacing(8)
            # the choices scroll when the window is short; save + Convert stay pinned below them
            choices = QScrollArea()
            choices.setWidgetResizable(True)
            choices.setFrameShape(QFrame.NoFrame)
            choices.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            choices_inner = QWidget()
            choices_inner.setObjectName("listInner")
            sl = QVBoxLayout(choices_inner)
            sl.setContentsMargins(20, 20, 20, 4)
            sl.setSpacing(8)
            choices.setWidget(choices_inner)
            choices.viewport().setAutoFillBackground(False)
            side_lay.addWidget(choices, 1)
            self.to_label = QLabel("Convert to")
            self.to_label.setObjectName("section")
            sl.addWidget(self.to_label)
            self.chip_box = QWidget()
            self.chip_grid = QGridLayout(self.chip_box)
            self.chip_grid.setContentsMargins(0, 0, 0, 0)
            self.chip_grid.setSpacing(8)
            sl.addWidget(self.chip_box)
            self.more_btn = QPushButton()
            self.more_btn.setObjectName("flat")
            self.more_btn.setCursor(Qt.PointingHandCursor)
            self._more = []
            self.more_btn.clicked.connect(lambda: self.more_menu(self._more))
            sl.addWidget(self.more_btn)
            self.tools_label = QLabel("Keep the same type")
            self.tools_label.setObjectName("section")
            sl.addSpacing(8)
            sl.addWidget(self.tools_label)
            self.tool_box = QWidget()
            self.tool_col = QVBoxLayout(self.tool_box)
            self.tool_col.setContentsMargins(0, 0, 0, 0)
            self.tool_col.setSpacing(8)
            sl.addWidget(self.tool_box)
            self.hint = QLabel()
            self.hint.setWordWrap(True)
            sl.addWidget(self.hint)

            # options, shown only when they apply
            sl.addSpacing(6)
            self.opt_widgets, self.opt_values = {}, {}

            def opt(key, label, widget, value, note=None):
                box = QWidget()
                v = QVBoxLayout(box)
                v.setContentsMargins(0, 4, 0, 0)
                v.setSpacing(4)
                cap = QLabel(label)
                cap.setObjectName("muted")
                v.addWidget(cap)
                v.addWidget(widget)
                if note:
                    v.addWidget(note)
                sl.addWidget(box)
                self.opt_widgets[key], self.opt_values[key] = box, value

            pages = QLineEdit()
            pages.setPlaceholderText("All pages")
            opt("pages", "Pages (e.g. 1-3, 5)", pages, pages.text)
            quality = QWidget()
            q = QHBoxLayout(quality)
            q.setContentsMargins(0, 0, 0, 0)
            slider = QSlider(Qt.Horizontal)
            slider.setRange(40, 100)
            slider.setValue(90)
            shown = QLabel("90")
            slider.valueChanged.connect(lambda v: shown.setText(str(v)))
            q.addWidget(slider, 1)
            q.addWidget(shown)
            opt("quality", "Quality", quality, lambda: str(slider.value()))

            def combo(values):
                b = QComboBox()
                b.addItems(values)
                return b
            max_size = combo(["Keep original", "3840", "1920", "1280", "800", "256"])
            opt("max_size", "Longest side (px)", max_size, max_size.currentText)
            resolution = combo(["Keep original", "1080", "720", "480", "360"])
            opt("resolution", "Video height", resolution, resolution.currentText)
            lang = QLineEdit("eng")
            opt("lang", "Text language", lang, lang.text)
            strength = combo(["Light", "Strong"])
            note = QLabel("Looks the same, a bit smaller")
            note.setObjectName("muted")
            strength.currentTextChanged.connect(lambda v: note.setText(
                "Smallest file, lower quality you can see" if v == "Strong" else "Looks the same, a bit smaller"))
            opt("strength", "How much smaller", strength, strength.currentText, note)

            sl.addStretch()
            # the new file's name, when the result is one file (one file in, or a merge)
            self.name_box = QWidget()
            nb = QVBoxLayout(self.name_box)
            nb.setContentsMargins(20, 0, 20, 4)
            nb.setSpacing(4)
            name_cap = QLabel("Name")
            name_cap.setObjectName("muted")
            nb.addWidget(name_cap)
            self.name_edit = QLineEdit()
            self.name_edit.setAccessibleName("Name of the new file")
            nb.addWidget(self.name_edit)
            side_lay.addWidget(self.name_box)
            save_row = QHBoxLayout()
            self.save_text = shrinkable(QLabel("Saved next to each file"))
            self.save_text.setObjectName("muted")
            save_row.addWidget(self.save_text, 1)
            self.change = QPushButton("Change")
            self.change.setObjectName("link")
            self.change.setCursor(Qt.PointingHandCursor)
            self.change.clicked.connect(self.change_dest)
            save_row.addWidget(self.change)
            save_row.setContentsMargins(20, 0, 20, 0)
            side_lay.addLayout(save_row)
            self.go = QPushButton("Convert")
            self.go.setObjectName("go")
            self.go.setCursor(Qt.PointingHandCursor)
            self.go.clicked.connect(self.go_pressed)
            go_wrap = QHBoxLayout()
            go_wrap.setContentsMargins(20, 0, 20, 0)
            go_wrap.addWidget(self.go)
            side_lay.addLayout(go_wrap)
            body.addWidget(self.side)

            self.apply_theme(self.theme)
            self.add_files(files)
            self.refresh()

        # ---------- window chrome
        def showEvent(self, event):
            super().showEvent(event)
            hwnd = int(self.winId())
            try:
                G.own_taskbar_button(hwnd)
                G.dark_title_bar(hwnd, self.theme == "dark")
            except (OSError, AttributeError):
                pass  # cosmetic only

        def apply_theme(self, theme):
            self.theme, self.colors = theme, palette(theme)
            QApplication.instance().setStyleSheet(stylesheet(self.colors))
            if self.isVisible():
                try:
                    G.dark_title_bar(int(self.winId()), theme == "dark")
                    self.resize(self.width() + 1, self.height())  # the frame repaints only on a size change
                    self.resize(self.width() - 1, self.height())
                except (OSError, AttributeError):
                    pass

        # ---------- files
        def add_files(self, paths):
            for p in paths:
                p = Path(p)
                if p.is_dir():
                    self.add_files(sorted(x for x in p.iterdir() if x.is_file()))
                    continue
                ext = converters.ext_of(p.name)
                ok = ext in self.formats
                row = FileRow(self, p, ext)
                self.list.insertWidget(self.list.count() - 1, row)  # above the stretch
                self.items[row] = {"path": p, "ext": ext, "state": "waiting" if ok else "unsupported",
                                   "saved": None, "tag": "waiting" if ok else "failed",
                                   "text": "" if ok else f".{ext or '?'} files aren't supported"}
                row.show_state(self.items[row]["text"], self.items[row]["tag"], self.busy)
            self.refresh()

        def browse(self):
            files, _ = QFileDialog.getOpenFileNames(self, "Add files to convert")
            self.add_files(files)

        def dragEnterEvent(self, event):
            if event.mimeData().hasUrls():
                event.acceptProposedAction()
                self.set_drag(True)

        def dragLeaveEvent(self, event):
            self.set_drag(False)

        def dropEvent(self, event):
            self.set_drag(False)
            self.add_files([u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()])

        def set_drag(self, on):
            self.drop.setProperty("over", on)
            repolish(self.drop)

        def remove_rows(self, rows):
            for row in rows:
                if row in self.items and self.items[row]["state"] != "working":
                    self.list.removeWidget(row)
                    row.setParent(None)
                    row.deleteLater()
                    del self.items[row]
            self.refresh()

        def clear(self):
            self.remove_rows(list(self.items))

        def toggle_pick(self, row):
            if self.busy or self.items[row]["state"] not in ("waiting", "failed"):
                return
            self.picked ^= {row}
            self.refresh()

        def unpick(self):
            self.picked.clear()
            self.refresh()

        def change_dest(self):
            m = QMenu(self)
            m.addAction("Next to each file", lambda: self.set_dest(None))
            m.addAction("Choose folder…", lambda: self.set_dest(
                QFileDialog.getExistingDirectory(self, "Save converted files in") or self.dest))
            m.exec(self.change.mapToGlobal(self.change.rect().bottomLeft()))

        def set_dest(self, folder):
            self.dest = Path(folder) if folder else None
            self.save_text.setText(f"Saved in {self.dest}" if self.dest else "Saved next to each file")
            self.save_text.setToolTip(str(self.dest or ""))

        # ---------- what the files can become (same rules as gui.pyw)
        def pending_rows(self):
            """The files the next Convert works on: the picked ones, or else every one not done yet."""
            rows = [r for r, i in self.items.items() if i["state"] in ("waiting", "failed")]
            return [r for r in rows if r in self.picked] or rows

        def pending(self):
            return [self.items[r] for r in self.pending_rows()]

        def choices(self):
            exts = list(dict.fromkeys(i["ext"] for i in self.pending()))
            if not exts:
                return []
            common = list(self.formats[exts[0]].items())
            for e in exts[1:]:
                common = [(k, c) for k, c in common if k in self.formats[e]]
            multi = []
            if len(self.pending()) > 1:
                multi = [(k, c) for k, c in converters.MULTI.items()
                         if all(e in converters.MULTI_ACCEPTS[k] for e in exts)]
            out = []
            for k, c in multi + common:
                missing = [self.tools[t]["name"] for t in c.needs if not self.tools[t]["found"]]
                out.append((k, c.label + (f"  (needs {', '.join(missing)})" if missing else ""), not missing))
            order = list(G.CHIPS)
            return sorted(out, key=lambda o: order.index(o[0]) if o[0] in order else len(order))

        def pick(self, target):
            if not self.busy:
                self.sel = target
                self.refresh()

        def chip(self, title, sub, selected, on_click):
            b = QPushButton()
            b.setObjectName("chip")
            b.setProperty("selected", selected)
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedHeight(56)  # fixed, so a short window scrolls the panel instead of squashing chips
            b.setAccessibleName(f"{title} {sub}")
            lay = QVBoxLayout(b)
            lay.setContentsMargins(12, 8, 10, 8)
            lay.setSpacing(1)
            for text, name in ((title, "chipTitle"), (sub, "chipSubOn" if selected else "chipSub")):
                label = shrinkable(QLabel(text))
                label.setObjectName(name)
                label.setAttribute(Qt.WA_TransparentForMouseEvents)
                lay.addWidget(label)
            b.clicked.connect(on_click)
            b.setEnabled(not self.busy)
            return b

        def more_menu(self, more):
            m = QMenu(self)
            for k, label, ok in more:
                action = m.addAction(label, lambda k=k: self.pick(k))
                action.setEnabled(ok)
            m.exec(self.more_btn.mapToGlobal(self.more_btn.rect().bottomLeft()))

        def refresh(self):
            opts = self.choices()
            usable = [k for k, _, ok in opts if ok]
            if usable and self.sel not in usable:  # no files waiting (e.g. mid-batch): keep the choice
                self.sel = usable[0]
            target, pend = self.sel, self.pending()
            has = bool(self.items)
            done = has and not pend and any(i["state"] == "done" for i in self.items.values())

            for w in (self.head_w, self.scroll, self.side):
                w.setVisible(has)
            self.drop_big.setVisible(not has)
            self.drop_small.setVisible(has)
            self.left.setStretchFactor(self.drop, 0 if has else 1)
            self.picked &= {r for r, i in self.items.items() if i["state"] in ("waiting", "failed")}
            self.clear_btn.setVisible(has and not self.busy)
            self.clear_btn.setText("Unselect" if self.picked else "Clear list")
            total = sum(r.bytes for r in self.items)
            n = len(self.items)
            waiting = sum(i["state"] in ("waiting", "failed") for i in self.items.values())
            self.heading.setText("Converting…" if self.busy else "All done" if done else "Your files")
            extra = (f" · {len(self.picked)} picked" if self.picked else
                     " · click files to pick some" if waiting > 1 and not self.busy else "")
            self.summary.setText(f"{n} file{'s' * (n != 1)}" + (f" · {human(total)}" if total else "") + extra)
            for row, i in self.items.items():
                row.show_state(i["text"], i["tag"], self.busy)
                row.setProperty("picked", row in self.picked)
                repolish(row)
            one_out = bool(pend) and not self.busy and (len(pend) == 1 or target in converters.MULTI)
            self.name_box.setVisible(one_out)
            if one_out:
                self.name_edit.setPlaceholderText(
                    {"merge-pdf": "merged", "images-pdf": "images"}.get(target, pend[0]["path"].stem))

            # the choices stay put while converting, just greyed out
            if not self.busy:
                clear_layout(self.chip_grid)
                clear_layout(self.tool_col)
                primary = [k for k in usable if k in G.CHIPS][:G.MAX_CHIPS]
                tools = [k for k in G.TOOLS if k in usable]
                more = [o for o in opts if o[0] not in primary and o[0] not in tools]
                for n_, k in enumerate(primary):
                    self.chip_grid.addWidget(self.chip(*G.CHIPS[k], k == target, lambda _=0, k=k: self.pick(k)),
                                             n_ // 2, n_ % 2)
                for k in tools:
                    self.tool_col.addWidget(self.chip(*G.TOOLS[k], k == target, lambda _=0, k=k: self.pick(k)))
                picked = next((label for k, label, _ in more if k == target), None)
                self.more_btn.setText(f"{picked}  ▾" if picked else f"{len(more)} more format{'s' * (len(more) != 1)}  ▾")
                self._more = more
                self.more_btn.setVisible(bool(more))
                self.to_label.setVisible(bool(primary or more))
                self.tools_label.setVisible(bool(tools))
                self.tool_box.setVisible(bool(tools))
            for w in (self.chip_box, self.tool_box, self.more_btn):
                w.setEnabled(not self.busy)
                fade = None
                if self.busy:  # QSS can't grey a button's child labels, so fade the whole group
                    fade = QGraphicsOpacityEffect(w)
                    fade.setOpacity(0.45)
                w.setGraphicsEffect(fade)
                for b in w.findChildren(QPushButton):
                    b.setEnabled(not self.busy)

            if pend and not opts:
                self.hint.setObjectName("error")
                self.hint.setText("These files can't be turned into the same format. Convert them one type at a time.")
            elif target in converters.MULTI and not self.busy and pend:
                self.hint.setObjectName("muted")
                self.hint.setText(f"All {len(pend)} files go into one PDF, in the order listed.")
            else:
                self.hint.setText("")
            repolish(self.hint)
            self.hint.setVisible(bool(self.hint.text()))

            if self.busy:
                self.go.setText("Converting…")
                self.go.setEnabled(False)
            elif done:
                self.go.setText("Show in folder")
                self.go.setEnabled(True)
            else:
                self.go.setText(f"Convert {len(pend)} files" if len(pend) > 1 and target not in converters.MULTI
                                else "Convert")
                self.go.setEnabled(bool(target and pend))

            exts = list(dict.fromkeys(i["ext"] for i in pend))
            images = set(converters.IMAGES)
            show = {
                "pages": bool(target) and "pdf" in exts and target not in (*converters.MULTI, "compress", "clean"),
                "strength": target == "compress",
                "quality": target in ("jpg", "webp", "heic"),
                "max_size": bool(images & set(exts)) and (target in images or target in ("pdf", "images-pdf")),
                "resolution": target in ("mp4", "webm", "gif"),
                "lang": bool(target and target.startswith("ocr")),
            }
            for key, box in self.opt_widgets.items():
                box.setVisible(show[key] and bool(pend) and not self.busy)

        def options(self):
            o = {}
            for key, box in self.opt_widgets.items():
                if box.isVisible():
                    v = str(self.opt_values[key]()).strip()
                    if v and v != "Keep original":
                        o[key] = v
            return o

        # ---------- converting
        def set_row(self, row, text, tag, saved):
            if row not in self.items:
                return
            if tag == "done" and saved:
                text = f"Included in {saved}" if "included" in text else f"Saved as {saved}"
            self.items[row].update(tag=tag, text=text)
            row.show_state(text, tag, self.busy)

        def go_pressed(self):
            if self.go.text() == "Show in folder":
                G.show_in_folder(self.last_saved)
            else:
                self.start()

        def start(self):
            import core
            target, opts, dest = self.sel, self.options(), self.dest
            name = self.name_edit.text() if self.name_box.isVisible() else None
            batch = self.pending_rows()
            if not target or not batch:
                return
            groups = [batch] if target in converters.MULTI else [[row] for row in batch]
            self.busy = True
            for row in batch:
                self.items[row]["state"] = "working"
                self.set_row(row, "Waiting", "waiting", "")
            self.refresh()
            paths = {row: self.items[row]["path"] for row in batch}

            def work():
                for group in groups:
                    for row in group:
                        self.bus.row.emit(row, "Converting…", "working", "")
                    try:
                        saved = core.convert([paths[r] for r in group], target, opts, dest, name)
                        self.last_saved = saved
                        for n, row in enumerate(group):
                            self.items[row].update(state="done", saved=saved)
                            self.bus.row.emit(row, "Done" if n == 0 else "Done (included)", "done", Path(saved).name)
                    except Exception as e:
                        for row in group:
                            self.items[row]["state"] = "failed"  # stays in the batch, e.g. to retry on Strong
                            if str(e).startswith(ALREADY_SMALL):
                                self.bus.row.emit(row, "Already small" + (
                                    "" if opts.get("strength") == "Strong" else ", try Strong"), "waiting", "")
                            else:
                                self.bus.row.emit(row, f"Failed: {e}", "failed", "")
                self.bus.finished.emit()

            threading.Thread(target=work, daemon=True).start()

        def batch_done(self):
            self.busy = False
            self.picked.clear()
            self.name_edit.clear()
            self.refresh()

        # ---------- settings
        def toggle_menu(self, on):
            try:
                shell.install() if on else shell.uninstall()
            except Exception as e:
                QMessageBox.critical(self, "Recast", f"Couldn't change the right-click menu: {e}")
            self.menu_switch.blockSignals(True)
            self.menu_switch.setChecked(shell.is_installed())
            self.menu_switch.blockSignals(False)

    app = QApplication(sys.argv[:1])
    window = Window(args)
    window.show()
    app.exec()


if __name__ == "__main__":
    mp.freeze_support()  # conversions run in worker processes started from here
    main()
