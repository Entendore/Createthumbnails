"""
HTML File Viewer
================

Displays HTML files from the `input/` folder (or any HTML file dropped onto the
window) inside an embedded Chromium web view, with full support for putting
the viewer — or the page itself — into true fullscreen.

Features
--------
* Combo-box picker for every `.html`/`.htm`/`.xhtml` file in `./input`
* Auto-rescan when files are added / removed in the input folder
  (QFileSystemWatcher)
* Drag-and-drop any HTML file from anywhere on the system
* Open-any-file dialog (Ctrl+O)
* Back / Forward navigation history (Alt+Left / Alt+Right)
* Reload (F5 / Ctrl+R), hard reload bypassing cache (Ctrl+Shift+R)
* Zoom in/out/reset (Ctrl+= / Ctrl+- / Ctrl+0)
* Find in page (Ctrl+F, Enter / Shift+Enter, Ctrl+G / Ctrl+Shift+G)
* Print (Ctrl+P)
* True fullscreen toggle (F11) with auto-hiding toolbars and cursor
* Open the current file in the system default browser
* Open / reveal the input folder in the OS file manager
* Persistent settings: window geometry, last viewed file, recent files
* Status bar showing current file path, size, modified date and zoom
* CSS injected so every HTML page fills the viewport

NOTE: the previous version called `document.requestFullscreen()` from inside
`loadFinished`, which produced:

    js: Failed to execute 'requestFullscreen' on 'Element':
        API can only be initiated by a user gesture.
    js: Uncaught (in promise) TypeError: Permissions check failed

Chromium requires a real user-gesture callstack for `requestFullscreen()`, so
that auto-trigger has been removed. We still keep `FullScreenSupportEnabled`
and `fullScreenRequested.connect(...)` so that pages which legitimately request
fullscreen from a click handler inside the page still work.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import (
    Qt, QUrl, QTimer, QByteArray, QFileSystemWatcher, QEvent, QObject
)
from PySide6.QtGui import (
    QAction, QKeySequence, QShortcut, QCursor, QPixmap, QDesktopServices
)
from PySide6.QtWidgets import (
    QApplication, QComboBox, QLabel, QMainWindow, QToolBar, QVBoxLayout,
    QHBoxLayout, QWidget, QFileDialog, QLineEdit, QPushButton, QFrame,
    QMessageBox
)
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import (
    QWebEnginePage, QWebEngineProfile, QWebEngineSettings
)


# --------------------------------------------------------------- paths
if "__file__" in globals():
    BASE_DIR = Path(__file__).resolve().parent
else:
    BASE_DIR = Path.cwd()
INPUT_DIR = BASE_DIR / "input"

# --------------------------------------------------------------- styles
FORCE_FILL_CSS = """
html, body {
    width: 100vw   !important;
    height: 100vh  !important;
    margin: 0      !important;
    padding: 0     !important;
    overflow: hidden !important;
}
"""

# JS that injects (and re-injects on each load) the force-fill CSS.
FORCE_FILL_JS_TEMPLATE = (
    "(function(){{"
    "var old = document.getElementById('__force_fill_css');"
    "if (old) old.parentNode.removeChild(old);"
    "var s = document.createElement('style');"
    "s.id = '__force_fill_css';"
    "s.textContent = {css!r};"
    "document.head.appendChild(s);"
    "}})();"
)

HOME_PAGE_HTML = """
<!DOCTYPE html>
<html><head><meta charset='utf-8'>
<style>
  body {{
    font-family: -apple-system, 'Segoe UI', Roboto, sans-serif;
    background: #fafafa; color: #333; margin: 0; padding: 48px;
    text-align: center;
  }}
  h1 {{ font-weight: 300; color: #444; margin-bottom: 8px; }}
  .hint {{ color: #999; font-size: 14px; margin-top: 24px; line-height: 1.8; }}
  kbd {{
    background: #eee; padding: 2px 6px; border-radius: 4px;
    font-family: 'Menlo', 'Consolas', monospace; border: 1px solid #ddd;
    font-size: 12px;
  }}
</style></head><body>
<h1>HTML Viewer</h1>
<div class='hint'>Pick a file from the dropdown above, or drag &amp; drop an HTML file here.</div>
<div class='hint'>
  <kbd>F11</kbd> fullscreen &middot;
  <kbd>Ctrl+O</kbd> open &middot;
  <kbd>Ctrl+F</kbd> find &middot;
  <kbd>Alt+&larr;/&rarr;</kbd> back/forward &middot;
  <kbd>Ctrl+L</kbd> rescan
</div>
</body></html>
"""


# --------------------------------------------------------- small helpers
def _make_transparent_cursor() -> QCursor:
    pm = QPixmap(1, 1)
    pm.fill(Qt.transparent)
    return QCursor(pm)


def _human_size(num: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024.0:
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} TB"


# ======================================================================
# Custom WebEnginePage
# ======================================================================
class FullScreenWebPage(QWebEnginePage):
    """Automatically accepts every HTML5 fullscreen request coming from the
    page itself (when triggered by a real user gesture inside the page)."""

    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        self.fullScreenRequested.connect(lambda r: r.accept())


# ======================================================================
# Event filter: hide the cursor in fullscreen after a period of inactivity
# ======================================================================
class CursorHideFilter(QObject):
    def __init__(self, viewer: "HTMLViewer"):
        super().__init__(viewer)
        self.viewer = viewer

    def eventFilter(self, obj, event):
        if self.viewer._is_full_screen:
            et = event.type()
            if et in (QEvent.MouseMove, QEvent.MouseButtonPress,
                      QEvent.KeyPress, QEvent.Wheel):
                QApplication.restoreOverrideCursor()
                self.viewer._cursor_hide_timer.start()
        return False


# ======================================================================
# Main window
# ======================================================================
class HTMLViewer(QMainWindow):

    HIDE_CURSOR_MS = 2500
    MAX_RECENT_FILES = 10

    # ------------------------------------------------------------------
    def __init__(self, input_dir: Path = INPUT_DIR):
        super().__init__()
        self.setWindowTitle("HTML Viewer")
        self.resize(1280, 800)

        # State
        self.input_dir = Path(input_dir)
        self._is_full_screen = False
        self._previous_geometry: QByteArray | None = None
        self._previous_state: bytes | None = None
        self._current_path: str | None = None
        self._recent_files: list[str] = []

        # Cursor-hide timer
        self._cursor_hide_timer = QTimer(self)
        self._cursor_hide_timer.setSingleShot(True)
        self._cursor_hide_timer.setInterval(self.HIDE_CURSOR_MS)
        self._cursor_hide_timer.timeout.connect(self._hide_cursor)
        self._transparent_cursor = _make_transparent_cursor()

        # Build everything
        self._build_ui()
        self._wire_shortcuts()
        self._ensure_input_dir()
        self._setup_watcher()
        self._load_settings()
        self._refresh_file_list(initial=True)
        self._populate_recent_menu()

        # Install the cursor-hide event filter on the whole app
        self._cursor_filter = CursorHideFilter(self)
        QApplication.instance().installEventFilter(self._cursor_filter)

        # Show home page
        self._load_home()

    # ============================================================ UI
    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setCentralWidget(central)

        # Web view
        self.web_view = QWebEngineView()
        profile = QWebEngineProfile.defaultProfile()
        self.page = FullScreenWebPage(profile, self.web_view)
        self.web_view.setPage(self.page)

        s = self.web_view.settings()
        s.setAttribute(QWebEngineSettings.FullScreenSupportEnabled, True)
        s.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        s.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        s.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        s.setAttribute(QWebEngineSettings.PluginsEnabled, True)
        s.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
        s.setAttribute(QWebEngineSettings.AutoLoadImages, True)
        s.setAttribute(QWebEngineSettings.ScrollAnimatorEnabled, True)
        s.setAttribute(QWebEngineSettings.SpatialNavigationEnabled, True)
        s.setAttribute(QWebEngineSettings.AllowRunningInsecureContent, False)
        s.setAttribute(
            QWebEngineSettings.AllowWindowActivationFromJavaScript, False
        )

        # Signals
        self.web_view.loadFinished.connect(self._on_load_finished)
        self.web_view.titleChanged.connect(self._on_title_changed)
        self.web_view.urlChanged.connect(self._on_url_changed)
        self.web_view.renderProcessTerminated.connect(self._on_render_crash)

        root.addWidget(self.web_view, 1)

        # Find bar (hidden until invoked)
        self._build_find_bar()
        root.addWidget(self._find_bar)
        self._find_bar.setVisible(False)

        self._build_toolbar()
        self._build_menubar()
        self._build_statusbar()

        self.setAcceptDrops(True)
        self.web_view.setAcceptDrops(False)  # route drags to the window

    # ------------------------------------------------ toolbar
    def _build_toolbar(self):
        tb = QToolBar("Main")
        tb.setMovable(False)
        tb.setObjectName("MainToolBar")
        self.addToolBar(Qt.TopToolBarArea, tb)
        self.toolbar = tb

        self.back_act = QAction("◀ Back", self)
        self.back_act.setToolTip("Back (Alt+Left)")
        self.back_act.triggered.connect(self._back)
        tb.addAction(self.back_act)

        self.fwd_act = QAction("Forward ▶", self)
        self.fwd_act.setToolTip("Forward (Alt+Right)")
        self.fwd_act.triggered.connect(self._forward)
        tb.addAction(self.fwd_act)

        tb.addSeparator()

        tb.addWidget(QLabel(" File:  "))
        self.file_combo = QComboBox()
        self.file_combo.setMinimumWidth(360)
        self.file_combo.currentIndexChanged.connect(self._on_combo_changed)
        tb.addWidget(self.file_combo)

        self.refresh_act = QAction("Refresh list", self)
        self.refresh_act.setToolTip("Rescan input folder (Ctrl+L)")
        self.refresh_act.triggered.connect(self._refresh_file_list)
        tb.addAction(self.refresh_act)

        self.reload_act = QAction("Reload", self)
        self.reload_act.setToolTip("Reload (F5)")
        self.reload_act.triggered.connect(self._reload)
        tb.addAction(self.reload_act)

        tb.addSeparator()

        self.zoom_out_act = QAction("Zoom −", self)
        self.zoom_out_act.setToolTip("Zoom out (Ctrl+-)")
        self.zoom_out_act.triggered.connect(self._zoom_out)
        tb.addAction(self.zoom_out_act)

        self.zoom_pct_lbl = QLabel("100%")
        self.zoom_pct_lbl.setMinimumWidth(48)
        self.zoom_pct_lbl.setAlignment(Qt.AlignCenter)
        tb.addWidget(self.zoom_pct_lbl)

        self.zoom_in_act = QAction("Zoom +", self)
        self.zoom_in_act.setToolTip("Zoom in (Ctrl+=)")
        self.zoom_in_act.triggered.connect(self._zoom_in)
        tb.addAction(self.zoom_in_act)

        tb.addSeparator()

        self.fullscreen_act = QAction("Full Screen", self)
        self.fullscreen_act.setToolTip("Toggle fullscreen (F11)")
        self.fullscreen_act.triggered.connect(self.toggle_full_screen)
        tb.addAction(self.fullscreen_act)

        tb.addSeparator()

        self.find_act_tb = QAction("Find…", self)
        self.find_act_tb.setToolTip("Find in page (Ctrl+F)")
        self.find_act_tb.triggered.connect(self._open_find)
        tb.addAction(self.find_act_tb)

        self.print_act_tb = QAction("Print…", self)
        self.print_act_tb.setToolTip("Print current page (Ctrl+P)")
        self.print_act_tb.triggered.connect(self._print_page)
        tb.addAction(self.print_act_tb)

        tb.addSeparator()

        self.open_browser_act = QAction("Open in Browser", self)
        self.open_browser_act.setToolTip("Open current file in default browser")
        self.open_browser_act.triggered.connect(self._open_in_browser)
        tb.addAction(self.open_browser_act)

        self.open_folder_act = QAction("Open Folder", self)
        self.open_folder_act.setToolTip("Reveal input folder in file manager")
        self.open_folder_act.triggered.connect(self._open_input_folder)
        tb.addAction(self.open_folder_act)

    # ------------------------------------------------ find bar
    def _build_find_bar(self):
        bar = QFrame()
        bar.setFrameShape(QFrame.StyledPanel)
        bar.setStyleSheet(
            "QFrame { background: #f5f5f5; border-top: 1px solid #ddd; }"
            "QLineEdit { padding: 3px 6px; }"
            "QPushButton { padding: 2px 8px; }"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        layout.addWidget(QLabel("Find:"))
        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText("Search in page…")
        self.find_edit.setClearButtonEnabled(True)
        self.find_edit.textChanged.connect(self._find_text_changed)
        self.find_edit.returnPressed.connect(self._find_next)
        layout.addWidget(self.find_edit, 1)

        self.find_prev_btn = QPushButton("◀ Prev")
        self.find_prev_btn.setToolTip("Previous match (Shift+Enter)")
        self.find_prev_btn.clicked.connect(self._find_prev)
        layout.addWidget(self.find_prev_btn)

        self.find_next_btn = QPushButton("Next ▶")
        self.find_next_btn.setToolTip("Next match (Enter)")
        self.find_next_btn.clicked.connect(self._find_next)
        layout.addWidget(self.find_next_btn)

        self.find_close_btn = QPushButton("✕")
        self.find_close_btn.setToolTip("Close (Escape)")
        self.find_close_btn.clicked.connect(self._close_find)
        layout.addWidget(self.find_close_btn)

        self._find_bar = bar

    # ------------------------------------------------ menubar
    def _build_menubar(self):
        mb = self.menuBar()

        file_menu = mb.addMenu("&File")
        file_menu.addAction("Open File…", self._open_file_dialog, "Ctrl+O")
        file_menu.addAction("Open Input Folder", self._open_input_folder)
        file_menu.addAction("Open in Browser", self._open_in_browser)
        file_menu.addSeparator()
        self._recent_menu = file_menu.addMenu("Recent Files")
        file_menu.addSeparator()
        file_menu.addAction("Reload", self._reload, "F5")
        file_menu.addAction(
            "Hard Reload (no cache)", self._hard_reload, "Ctrl+Shift+R"
        )
        file_menu.addSeparator()
        file_menu.addAction("Print…", self._print_page, "Ctrl+P")
        file_menu.addSeparator()
        file_menu.addAction("Quit", self.close, "Ctrl+Q")

        view_menu = mb.addMenu("&View")
        view_menu.addAction("Zoom In", self._zoom_in, "Ctrl+=")
        view_menu.addAction("Zoom Out", self._zoom_out, "Ctrl+-")
        view_menu.addAction("Reset Zoom", self._zoom_reset, "Ctrl+0")
        view_menu.addSeparator()
        view_menu.addAction("Full Screen", self.toggle_full_screen, "F11")
        view_menu.addSeparator()
        view_menu.addAction("Find in Page…", self._open_find, "Ctrl+F")
        view_menu.addAction("Scroll to Top", self._scroll_top, "Home")
        view_menu.addAction("Scroll to Bottom", self._scroll_bottom, "End")

        go_menu = mb.addMenu("&Go")
        go_menu.addAction("Back", self._back, "Alt+Left")
        go_menu.addAction("Forward", self._forward, "Alt+Right")

        help_menu = mb.addMenu("&Help")
        help_menu.addAction("About", self._show_about)

    # ------------------------------------------------ status bar
    def _build_statusbar(self):
        sb = self.statusBar()
        self.path_lbl = QLabel("No file loaded")
        self.path_lbl.setStyleSheet("padding: 0 6px;")
        sb.addWidget(self.path_lbl, 1)

        self.size_lbl = QLabel("")
        self.size_lbl.setStyleSheet("padding: 0 6px; color: #555;")
        sb.addPermanentWidget(self.size_lbl)

        self.zoom_status_lbl = QLabel("100%")
        self.zoom_status_lbl.setStyleSheet("padding: 0 6px; color: #555;")
        sb.addPermanentWidget(self.zoom_status_lbl)

    # ================================================ keyboard shortcuts
    def _wire_shortcuts(self):
        QShortcut(QKeySequence("F11"), self, activated=self.toggle_full_screen)
        QShortcut(QKeySequence("Escape"), self, activated=self._on_escape)
        QShortcut(QKeySequence("Ctrl+R"), self, activated=self._reload)
        QShortcut(QKeySequence("F5"), self, activated=self._reload)
        QShortcut(
            QKeySequence("Ctrl+Shift+R"), self, activated=self._hard_reload
        )
        QShortcut(QKeySequence("Ctrl+L"), self,
                  activated=self._refresh_file_list)
        QShortcut(QKeySequence("Ctrl+Q"), self, activated=self.close)
        QShortcut(QKeySequence("Ctrl+O"), self,
                  activated=self._open_file_dialog)
        QShortcut(QKeySequence("Ctrl+="), self, activated=self._zoom_in)
        QShortcut(QKeySequence("Ctrl++"), self, activated=self._zoom_in)
        QShortcut(QKeySequence("Ctrl+-"), self, activated=self._zoom_out)
        QShortcut(QKeySequence("Ctrl+0"), self, activated=self._zoom_reset)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self._open_find)
        QShortcut(QKeySequence("Ctrl+P"), self, activated=self._print_page)
        QShortcut(QKeySequence("Alt+Left"), self, activated=self._back)
        QShortcut(QKeySequence("Alt+Right"), self, activated=self._forward)
        QShortcut(QKeySequence("Ctrl+G"), self, activated=self._find_next)
        QShortcut(QKeySequence("Ctrl+Shift+G"), self,
                  activated=self._find_prev)

    # ============================================== input dir & files
    def _ensure_input_dir(self):
        if not self.input_dir.exists():
            try:
                self.input_dir.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                self._notify(f"Could not create input folder: {e}")

    def _list_html_files(self) -> list[Path]:
        if not self.input_dir.exists():
            return []
        exts = (".html", ".htm", ".xhtml")
        return sorted(
            (p for p in self.input_dir.iterdir()
             if p.is_file() and p.suffix.lower() in exts),
            key=lambda p: p.name.lower()
        )

    def _refresh_file_list(self, initial: bool = False):
        current = self._current_path
        self.file_combo.blockSignals(True)
        self.file_combo.clear()
        self.file_combo.addItem("— select a file —", userData=None)
        files = self._list_html_files()
        for f in files:
            self.file_combo.addItem(f.name, userData=str(f))
        self.file_combo.blockSignals(False)

        if current:
            idx = self.file_combo.findData(current)
            if idx >= 0:
                self.file_combo.setCurrentIndex(idx)

        self._notify(f"Found {len(files)} HTML file(s) in {self.input_dir}")

    def _setup_watcher(self):
        self._watcher = QFileSystemWatcher(self)
        if self.input_dir.exists():
            self._watcher.addPath(str(self.input_dir))
        self._watcher.directoryChanged.connect(self._on_dir_changed)

    def _on_dir_changed(self, _path: str):
        QTimer.singleShot(50, self._refresh_file_list)

    def _on_combo_changed(self, index: int):
        path = self.file_combo.itemData(index)
        if not path:
            return
        self._load_file(Path(path))

    # ================================================ file loading
    def _load_file(self, path: Path):
        if not path.exists():
            self._notify(f"File not found: {path}")
            return
        self._current_path = str(path.absolute())
        self.web_view.setUrl(QUrl.fromLocalFile(self._current_path))
        self._update_status(path)
        self._add_recent(self._current_path)

    def _load_home(self):
        self.web_view.setHtml(HOME_PAGE_HTML, QUrl("about:blank"))
        self._current_path = None
        self.path_lbl.setText("No file loaded")
        self.size_lbl.setText("")
        self.setWindowTitle("HTML Viewer")

    def _on_load_finished(self, ok: bool):
        if not ok:
            return
        css = FORCE_FILL_CSS.replace("\n", " ")
        js = FORCE_FILL_JS_TEMPLATE.format(css=css)
        self.web_view.page().runJavaScript(js)
        self._update_nav_actions()

    def _on_title_changed(self, title: str):
        if title:
            self.setWindowTitle(f"HTML Viewer — {title}")
        elif self._current_path:
            self.setWindowTitle(
                f"HTML Viewer — {Path(self._current_path).name}"
            )

    def _on_url_changed(self, _url: QUrl):
        self._update_nav_actions()

    def _on_render_crash(self, _status, _code):
        self._notify("Render process crashed — reloading…")
        QTimer.singleShot(500, self._reload)

    # ================================================ navigation
    def _back(self):
        if self.web_view.history().canGoBack():
            self.web_view.back()

    def _forward(self):
        if self.web_view.history().canGoForward():
            self.web_view.forward()

    def _update_nav_actions(self):
        h = self.web_view.history()
        self.back_act.setEnabled(h.canGoBack())
        self.fwd_act.setEnabled(h.canGoForward())

    # ================================================ reload
    def _reload(self):
        self.web_view.reload()

    def _hard_reload(self):
        # Bypass cache by re-setting the URL.
        if self._current_path:
            self.web_view.page().action(
                QWebEnginePage.ReloadAndBypassCache
            ).trigger()
        else:
            self._reload()

    # ================================================ zoom
    def _zoom_in(self):
        z = min(5.0, self.web_view.zoomFactor() + 0.1)
        self.web_view.setZoomFactor(z)
        self._update_zoom_label()

    def _zoom_out(self):
        z = max(0.2, self.web_view.zoomFactor() - 0.1)
        self.web_view.setZoomFactor(z)
        self._update_zoom_label()

    def _zoom_reset(self):
        self.web_view.setZoomFactor(1.0)
        self._update_zoom_label()

    def _update_zoom_label(self):
        pct = int(round(self.web_view.zoomFactor() * 100))
        text = f"{pct}%"
        self.zoom_pct_lbl.setText(text)
        self.zoom_status_lbl.setText(text)

    # ================================================ find in page
    def _open_find(self):
        self._find_bar.setVisible(True)
        self.find_edit.setFocus()
        self.find_edit.selectAll()

    def _close_find(self):
        self._find_bar.setVisible(False)
        self.web_view.page().findText("")
        self.web_view.setFocus()

    def _find_text_changed(self, text: str):
        self.web_view.page().findText(text)

    def _find_next(self):
        self.web_view.page().findText(self.find_edit.text())

    def _find_prev(self):
        self.web_view.page().findText(
            self.find_edit.text(), QWebEnginePage.FindBackward
        )

    # ================================================ scroll
    def _scroll_top(self):
        self.web_view.page().runJavaScript(
            "window.scrollTo(0, 0);"
        )

    def _scroll_bottom(self):
        self.web_view.page().runJavaScript(
            "window.scrollTo(0, document.body.scrollHeight);"
        )

    # ================================================ print
    def _print_page(self):
        printer = QPrinter()
        dlg = QPrintDialog(printer, self)
        dlg.setWindowTitle("Print HTML Document")
        if dlg.exec() == QPrintDialog.Accepted:
            self.web_view.page().print(printer, lambda ok: None)

    # ================================================ fullscreen
    def toggle_full_screen(self):
        if self._is_full_screen:
            self.exit_full_screen()
        else:
            self.enter_full_screen()

    def enter_full_screen(self):
        if self._is_full_screen:
            return
        self._previous_geometry = self.saveGeometry()
        self._previous_state = self.saveState()
        self._is_full_screen = True
        for tb in self.findChildren(QToolBar):
            tb.setVisible(False)
        if self.menuBar():
            self.menuBar().setVisible(False)
        self.statusBar().setVisible(False)
        self._find_bar.setVisible(False)
        self.showFullScreen()
        self._cursor_hide_timer.start()

    def exit_full_screen(self):
        if not self._is_full_screen:
            return
        self._is_full_screen = False
        self._cursor_hide_timer.stop()
        QApplication.restoreOverrideCursor()
        self.showNormal()
        for tb in self.findChildren(QToolBar):
            tb.setVisible(True)
        if self.menuBar():
            self.menuBar().setVisible(True)
        self.statusBar().setVisible(True)
        if self._previous_geometry is not None:
            self.restoreGeometry(self._previous_geometry)
            self._previous_geometry = None
        if self._previous_state is not None:
            self.restoreState(self._previous_state)
            self._previous_state = None

    def _hide_cursor(self):
        if self._is_full_screen:
            QApplication.setOverrideCursor(self._transparent_cursor)

    def _on_escape(self):
        if self._find_bar.isVisible():
            self._close_find()
        elif self._is_full_screen:
            self.exit_full_screen()

    # ================================================ file ops
    def _open_file_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open HTML file", str(self.input_dir),
            "HTML files (*.html *.htm *.xhtml);;All files (*.*)"
        )
        if path:
            self._load_file(Path(path))

    def _open_input_folder(self):
        self._ensure_input_dir()
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(self.input_dir.resolve()))
        )

    def _open_in_browser(self):
        if not self._current_path:
            self._notify("No file is currently loaded.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(self._current_path))

    # ================================================ recent files
    def _add_recent(self, path: str):
        if path in self._recent_files:
            self._recent_files.remove(path)
        self._recent_files.insert(0, path)
        del self._recent_files[self.MAX_RECENT_FILES:]
        self._populate_recent_menu()

    def _populate_recent_menu(self):
        self._recent_menu.clear()
        if not self._recent_files:
            act = self._recent_menu.addAction("(none)")
            act.setEnabled(False)
            return
        for p in self._recent_files:
            label = Path(p).name
            action = self._recent_menu.addAction(label)
            action.setToolTip(p)
            action.triggered.connect(lambda _=False, pp=p: self._load_file(Path(pp)))

    # ================================================ settings
    def _load_settings(self):
        from PySide6.QtCore import QSettings
        self._settings = QSettings(QSettings.IniFormat,
                                   QSettings.UserScope,
                                   "HTMLViewer", "HTMLViewer")
        geom = self._settings.value("geometry")
        if isinstance(geom, (bytes, bytearray)) and not isinstance(geom, str):
            self.restoreGeometry(QByteArray(geom))
        state = self._settings.value("windowState")
        if isinstance(state, (bytes, bytearray)) and not isinstance(state, str):
            self.restoreState(QByteArray(state))
        recent = self._settings.value("recentFiles") or []
        if isinstance(recent, list):
            self._recent_files = [r for r in recent
                                  if isinstance(r, str) and Path(r).exists()]
        last = self._settings.value("lastFile")
        if isinstance(last, str) and Path(last).exists():
            QTimer.singleShot(100, lambda: self._load_file(Path(last)))

    def _save_settings(self):
        from PySide6.QtCore import QSettings
        s = self._settings
        if self._is_full_screen and self._previous_geometry is not None:
            s.setValue("geometry", bytes(self._previous_geometry))
        else:
            s.setValue("geometry", bytes(self.saveGeometry()))
        s.setValue("windowState", bytes(self.saveState()))
        s.setValue("recentFiles", self._recent_files)
        if self._current_path:
            s.setValue("lastFile", self._current_path)

    # ================================================ misc
    def _notify(self, msg: str):
        self.statusBar().showMessage(msg, 4000)

    def _update_status(self, path: Path):
        try:
            stat = path.stat()
            from datetime import datetime
            mtime = datetime.fromtimestamp(stat.st_mtime).strftime(
                "%Y-%m-%d %H:%M"
            )
            self.path_lbl.setText(f"{path.name}  ·  {path.parent}")
            self.size_lbl.setText(
                f"{_human_size(stat.st_size)}  ·  modified {mtime}"
            )
        except OSError:
            self.path_lbl.setText(str(path))
            self.size_lbl.setText("")

    def _show_about(self):
        QMessageBox.about(
            self, "About HTML Viewer",
            "<h3>HTML Viewer</h3>"
            "<p>A simple PySide6 / QtWebEngine-based viewer for local HTML "
            "files, with fullscreen support, file-list monitoring, "
            "drag-and-drop, find-in-page, printing and more.</p>"
            "<p>Drop your HTML files into the <code>input/</code> folder "
            "next to this script, or drag-and-drop them onto the window.</p>"
        )

    # ================================================ drag & drop
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and any(
            u.toLocalFile().lower().endswith((".html", ".htm", ".xhtml"))
            for u in event.mimeData().urls()
        ):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        for u in event.mimeData().urls():
            local = u.toLocalFile()
            if local.lower().endswith((".html", ".htm", ".xhtml")):
                self._load_file(Path(local))
                event.acceptProposedAction()
                return
        event.ignore()

    # ================================================ keys
    def keyPressEvent(self, event):
        # Allow Shift+Enter inside the find bar to go backwards.
        if self._find_bar.isVisible() and self.find_edit.hasFocus():
            if event.key() in (Qt.Key_Return, Qt.Key_Enter) \
                    and (event.modifiers() & Qt.ShiftModifier):
                self._find_prev()
                event.accept()
                return
            if event.key() == Qt.Key_Escape:
                self._close_find()
                event.accept()
                return
        super().keyPressEvent(event)

    # ================================================ close
    def closeEvent(self, event):
        self._save_settings()
        super().closeEvent(event)


# ======================================================================
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("HTML Viewer")
    app.setOrganizationName("HTMLViewer")
    viewer = HTMLViewer(input_dir=INPUT_DIR)
    viewer.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()