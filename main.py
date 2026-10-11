"""
HTML File Viewer & Editor (v9 — Complete)
=========================================

An advanced IDE-like HTML/CSS/JS viewer and editor built with PySide6.

All features:
- Viewer with Chromium DevTools (Ctrl+Shift+I)
- Code editor: syntax highlighting, line numbers, autocomplete (Ctrl+Space)
- Emmet abbreviation expansion (Tab key)
- HTML Beautify (Ctrl+Shift+B)
- Auto-pair HTML tags
- Indentation guides, bracket matching, color swatches
- TODO/FIXME highlight, selection occurrence highlight, trailing whitespace
- HTML entities quick-insert, Lorem ipsum, timestamp, base64 image encoder
- Line operations: sort, dedupe, remove blank lines
- Regex Find/Replace with match counter
- Auto-reload on external file change
- Quick Open (Ctrl+P)
- Responsive preview buttons
- Session restore (cursor + scroll)
- Save as JPG via Playwright Chromium (QThread worker, cancellable, persistent browser pool)
- Comprehensive logging with subsystem loggers, timing decorator, exception hook
- LogViewerDock with level filter, text search, auto-scroll
- TaskManager for background task tracking
- Async file loading for large files
- All previous bug-fixes
"""

from __future__ import annotations

import os
import re
import sys
import base64
import time
import logging
import threading
import functools
import traceback
import uuid
import html as html_module
from pathlib import Path
from datetime import datetime

from PySide6.QtCore import (
    Qt, QUrl, QTimer, QByteArray, QFileSystemWatcher, QEvent, QObject, Signal,
    QStringListModel, QSortFilterProxyModel, QSettings, QRegularExpression,
    QThread, QThreadPool, QRunnable, QMutex, QMutexLocker
)
from PySide6.QtGui import (
    QAction, QKeySequence, QShortcut, QCursor, QPixmap, QDesktopServices,
    QSyntaxHighlighter, QTextCharFormat, QTextCursor, QFont, QColor, QPainter,
    QFontDatabase, QTextFormat, QImage
)
from PySide6.QtWidgets import (
    QApplication, QComboBox, QLabel, QMainWindow, QToolBar, QVBoxLayout,
    QHBoxLayout, QWidget, QFileDialog, QLineEdit, QPushButton, QFrame,
    QMessageBox, QTabWidget, QPlainTextEdit, QSplitter, QMenu, QDockWidget,
    QInputDialog, QTextEdit, QTreeView, QFileSystemModel, QCompleter,
    QAbstractItemView, QProgressDialog, QListWidget, QDialog, QCheckBox
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

# --------------------------------------------------------------- autocomplete
AUTOCOMPLETE_KEYWORDS = [
    "html","head","body","div","span","a","img","ul","li","ol","script","style","link","meta",
    "header","footer","main","section","article","nav","aside","figure","figcaption","table","tr","td","th",
    "class","id","href","src","alt","style","onclick","onload","type","placeholder","value",
    "display","position","top","left","right","bottom","width","height","color","background","background-color",
    "margin","padding","border","border-radius","font-size","font-weight","text-align","flex","grid","gap",
    "justify-content","align-items","transform","transition","animation","opacity","z-index","box-shadow",
    "function","return","const","let","var","if","else","for","while","class","import","export","default",
    "try","catch","finally","throw","typeof","instanceof","in","of","break","continue","switch","case",
    "async","await","new","delete","void","this","true","false","null","undefined",
    "document","window","console","addEventListener","querySelector","getElementById","createElement","appendChild",
    "Math","Date","Array","Object","String","Number","Boolean","Promise","JSON","localStorage"
]

HTML_ENTITIES = {
    "&nbsp;":"Non-breaking space","&lt;":"Less than (<)","&gt;":"Greater than (>)",
    "&amp;":"Ampersand (&)","&quot;":'Quotation ("',"&apos;":"Apostrophe (')",
    "&copy;":"Copyright (©)","&reg;":"Registered (®)","&trade;":"Trademark (™)",
    "&mdash;":"Em dash (—)","&ndash;":"En dash (–)","&hellip;":"Ellipsis (…)",
    "&laquo;":"«","&raquo;":"»","&euro;":"Euro (€)","&pound;":"Pound (£)",
    "&cent;":"Cent (¢)","&yen;":"Yen (¥)","&deg;":"Degree (°)","&plusmn;":"±",
    "&times;":"×","&divide;":"÷","&larr;":"←","&rarr;":"→","&uarr;":"↑","&darr;":"↓",
    "&hearts;":"♥","&star;":"★","&check;":"✓",
}

LOREM_IPSUM = (
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
    "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. "
    "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris "
    "nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in "
    "reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla "
    "pariatur. Excepteur sint occaecat cupidatat non proident, sunt in "
    "culpa qui officia deserunt mollit anim id est laborum."
)

APP_STYLESHEET = """
QMainWindow,QWidget{background-color:#1e1e1e;color:#d4d4d4;}
QToolBar{background-color:#2d2d2d;border:none;border-bottom:1px solid #1e1e1e;padding:4px;spacing:4px;}
QToolBar QLabel{color:#888;}
QTabWidget::pane{border:1px solid #1e1e1e;}
QTabBar::tab{background:#252526;color:#888;padding:8px 16px;border:1px solid #1e1e1e;border-bottom:none;}
QTabBar::tab:selected{background:#1e1e1e;color:#fff;border-bottom:2px solid #007acc;margin-bottom:-1px;}
QStatusBar{background-color:#007acc;color:white;}QStatusBar QLabel{color:white;}
QPushButton{background-color:#3a3d41;color:white;border:1px solid #1e1e1e;padding:4px 10px;border-radius:3px;}
QPushButton:hover{background-color:#4e5256;}QPushButton:pressed{background-color:#2d2d2d;}
QPushButton:checked{background-color:#007acc;border-color:#007acc;}
QComboBox{background-color:#3a3d41;color:white;border:1px solid #1e1e1e;padding:3px 8px;border-radius:3px;}
QComboBox:hover{border-color:#007acc;}
QComboBox QAbstractItemView{background-color:#2d2d2d;color:white;selection-background-color:#094771;border:1px solid #1e1e1e;}
QLineEdit{background-color:#252526;color:#d4d4d4;border:1px solid #1e1e1e;padding:4px 6px;border-radius:3px;}
QLineEdit:focus{border:1px solid #007acc;}
QMenu{background-color:#2d2d2d;color:#d4d4d4;border:1px solid #1e1e1e;}
QMenu::item:selected{background-color:#094771;}QMenu::separator{height:1px;background:#1e1e1e;margin:4px 0px;}
QSplitter::handle{background-color:#1e1e1e;}
QPlainTextEdit{border:none;}QTextEdit{border:none;}
QTreeView{background-color:#252526;color:#d4d4d4;border:none;}
QTreeView::item:selected{background-color:#094771;}QTreeView::branch{background:#252526;}
QDockWidget{border:none;color:#d4d4d4;}
QDockWidget::title{background:#2d2d2d;padding:6px;border-bottom:1px solid #1e1e1e;}
QFrame#FindBar{background:#252526;border-top:1px solid #1e1e1e;}
QDialog{background-color:#2d2d2d;color:#d4d4d4;}
QCompleter QListView{background-color:#252526;color:#d4d4d4;selection-background-color:#094771;border:1px solid #1e1e1e;}
QListWidget{background-color:#252526;color:#d4d4d4;border:1px solid #1e1e1e;}
QListWidget::item:selected{background-color:#094771;}
QCheckBox{color:#d4d4d4;}
"""

FORCE_FILL_CSS = "html,body{width:100vw!important;height:100vh!important;margin:0!important;padding:0!important;overflow:hidden!important;}"
FORCE_FILL_JS_TEMPLATE = "(function(){{var o=document.getElementById('__ff');if(o)o.parentNode.removeChild(o);var s=document.createElement('style');s.id='__ff';s.textContent={css!r};document.head.appendChild(s);}})();"

HOME_PAGE_HTML = """<!DOCTYPE html><html><head><meta charset='utf-8'><style>
body{font-family:-apple-system,'Segoe UI',Roboto,sans-serif;background:#1e1e1e;color:#d4d4d4;margin:0;padding:48px;text-align:center;}
h1{font-weight:300;color:#fff;margin-bottom:8px;}.hint{color:#888;font-size:14px;margin-top:24px;line-height:1.8;}
kbd{background:#333;padding:2px 6px;border-radius:4px;font-family:'Menlo','Consolas',monospace;border:1px solid #444;font-size:12px;color:#d4d4d4;}</style></head><body>
<h1>HTML Viewer & Editor</h1>
<div class='hint'>Pick a file from the Explorer on the left, or drag &amp; drop an HTML file here.</div>
<div class='hint'><kbd>Alt+1</kbd> Viewer · <kbd>Alt+2</kbd> Editor · <kbd>F11</kbd> Fullscreen · <kbd>Ctrl+Shift+I</kbd> DevTools · <kbd>Ctrl+Space</kbd> Autocomplete · <kbd>Ctrl+P</kbd> Quick Open · <kbd>Ctrl+Shift+B</kbd> Beautify · <kbd>Ctrl+Shift+J</kbd> Save JPG</div>
</body></html>"""

HTML5_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>My Page</title>
<style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:-apple-system,'Segoe UI',Roboto,sans-serif;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);min-height:100vh;display:flex;justify-content:center;align-items:center}.card{background:#fff;padding:48px;border-radius:16px;box-shadow:0 20px 60px rgba(0,0,0,.3);text-align:center;max-width:400px}h1{color:#333;margin-bottom:12px}p{color:#666;line-height:1.6}</style>
</head><body><div class="card"><h1>Hello, World!</h1><p>Edit this template to create your page.</p></div></body></html>"""

CSS_KEYFRAME_ANIMATION = """<div class="pulse-box">Pulsing Animation</div>
<style>@keyframes pulse{0%,100%{transform:scale(1);box-shadow:0 0 0 0 rgba(231,76,60,.7)}50%{transform:scale(1.1);box-shadow:0 0 0 20px rgba(231,76,60,0)}}.pulse-box{padding:24px 48px;background:#e74c3c;color:#fff;border-radius:12px;display:inline-block;font-family:sans-serif;font-size:18px;animation:pulse 2s infinite}</style>"""

JS_CONSOLE_TEST = """<button onclick="logMessage()">Click Me</button>
<style>button{padding:15px 30px;font-size:18px;cursor:pointer;background:#007acc;color:#fff;border:none;border-radius:8px}</style>
<script>function logMessage(){console.log("Clicked: "+new Date().toLocaleTimeString());console.warn("Warning message.")}</script>"""

# --------------------------------------------------------------- logging
LOG_FILE = BASE_DIR / "html_viewer.log"
SESSION_ID = uuid.uuid4().hex[:8]

def _lg(name): return logging.getLogger(f"HTMLViewer.{name}")
log_app=_lg("App"); log_viewer=_lg("Viewer"); log_editor=_lg("Editor")
log_preview=_lg("Preview"); log_fileops=_lg("FileOps"); log_jpg=_lg("JPG")
log_settings=_lg("Settings"); log_keys=_lg("Keys"); log_playw=_lg("Playwright")

def _setup_logging():
    class _Fmt(logging.Formatter):
        _main=threading.main_thread().name
        def format(self,r):
            m=super().format(r)
            if r.threadName!=self._main: m=m.replace(f"{r.name} |",f"{r.name} [{r.threadName}] |",1)
            return m
    fh=logging.FileHandler(str(LOG_FILE),mode='w',encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(_Fmt('%(asctime)s.%(msecs)03d [%(levelname)-7s] %(name)-14s | %(message)s','%Y-%m-%d %H:%M:%S'))
    ch=logging.StreamHandler(); ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter('[%(levelname)-7s] %(message)s'))
    root=logging.getLogger(); root.setLevel(logging.DEBUG); root.handlers.clear()
    root.addHandler(fh); root.addHandler(ch)
    log_app.info("="*72); log_app.info("Session ID: %s",SESSION_ID)
    log_app.info("HTML Viewer & Editor v9 — log started (mode='w')")
    log_app.info("Python %s",sys.version.replace('\n',' '))
    log_app.info("Platform: %s",sys.platform)
    log_app.info("BASE_DIR=%s",BASE_DIR); log_app.info("INPUT_DIR=%s",INPUT_DIR)
    log_app.info("LOG_FILE=%s",LOG_FILE); log_app.info("="*72)

def timed(sub=None,level=logging.DEBUG):
    def deco(fn):
        log=_lg(sub or fn.__qualname__.split('.')[0] or "Misc")
        @functools.wraps(fn)
        def wrap(*a,**kw):
            log.log(level,"→ %s()",fn.__qualname__)
            t0=time.perf_counter()
            try:
                r=fn(*a,**kw); dt=(time.perf_counter()-t0)*1000
                if dt>100: log.info("← %s() done in %.1fms",fn.__qualname__,dt)
                else: log.log(level,"← %s() done in %.1fms",fn.__qualname__,dt)
                return r
            except Exception as e:
                dt=(time.perf_counter()-t0)*1000
                log.error("✗ %s() FAILED in %.1fms — %s",fn.__qualname__,dt,e); raise
        return wrap
    return deco

def install_excepthook():
    def h(et,ev,tb):
        if issubclass(et,KeyboardInterrupt): sys.__excepthook__(et,ev,tb); return
        log_app.critical("─"*60)
        log_app.critical("UNCAUGHT: %s: %s",et.__name__,ev)
        log_app.critical("Traceback:\n%s",''.join(traceback.format_tb(tb)))
        log_app.critical("─"*60)
        sys.__excepthook__(et,ev,tb)
    sys.excepthook=h; log_app.info("Global exception hook installed")

# --------------------------------------------------------------- helpers
def _make_transparent_cursor():
    pm=QPixmap(1,1); pm.fill(Qt.transparent); return QCursor(pm)

def _human_size(n):
    for u in("B","KB","MB","GB"):
        if n<1024: return f"{n:.0f} {u}" if u=="B" else f"{n:.1f} {u}"
        n/=1024
    return f"{n:.1f} TB"

def _get_monospace_font(size=10):
    for p in["Cascadia Code","Fira Code","JetBrains Mono","Consolas","Menlo","Monaco"]:
        if p in QFontDatabase.families():
            f=QFont(p,size); f.setStyleHint(QFont.Monospace); f.setFixedPitch(True); return f
    f=QFont("Courier New",size); f.setStyleHint(QFont.Monospace); f.setFixedPitch(True); return f

def _find_ancestor(w,t):
    p=w.parent()
    while p:
        if isinstance(p,t): return p
        p=p.parent()
    return None

# --------------------------------------------------------------- Emmet
class _EmmetExpander:
    VOID=frozenset({'br','hr','img','input','meta','link','area','base','col','embed','source','track','wbr'})
    def __init__(self,t): self.t=t; self.p=0
    def _pk(self): return self.t[self.p] if self.p<len(self.t) else ''
    def parse(self):
        n=self._sib(); l=[]; self._r(n,0,l); return '\n'.join(l)
    def _sib(self):
        n=[self._node()]
        while self._pk()=='+': self.p+=1; n.append(self._node())
        return [x for x in n if x]
    def _node(self):
        tag=''
        while self._pk().isalnum() or self._pk()=='-': tag+=self.t[self.p]; self.p+=1
        if not tag: tag='div'
        cl=[]; eid=None
        while self._pk() in'.#':
            m=self.t[self.p]; self.p+=1; nm=''
            while self._pk().isalnum() or self._pk() in'-_': nm+=self.t[self.p]; self.p+=1
            if not nm: return None
            if m=='.': cl.append(nm)
            else: eid=nm
        txt=None
        if self._pk()=='{':
            self.p+=1; txt=''
            while self._pk() and self._pk()!='}': txt+=self.t[self.p]; self.p+=1
            if self._pk()=='}': self.p+=1
        cnt=1
        if self._pk()=='*':
            self.p+=1; num=''
            while self._pk().isdigit(): num+=self.t[self.p]; self.p+=1
            if num: cnt=int(num)
        ch=[]
        if self._pk()=='>': self.p+=1; ch=self._sib()
        return{'tag':tag,'classes':cl,'id':eid,'text':txt,'count':cnt,'children':ch}
    def _r(self,nodes,ind,lines):
        pf='    '*ind
        for nd in nodes:
            a=''
            if nd['id']: a+=f' id="{nd["id"]}"'
            if nd['classes']: a+=f' class="{" ".join(nd["classes"])}"'
            for _ in range(nd['count']):
                if nd['tag'] in self.VOID: lines.append(f'{pf}<{nd["tag"]}{a}>')
                elif nd['children']:
                    lines.append(f'{pf}<{nd["tag"]}{a}>'); self._r(nd['children'],ind+1,lines)
                    lines.append(f'{pf}</{nd["tag"]}>')
                elif nd['text'] is not None: lines.append(f'{pf}<{nd["tag"]}{a}>{nd["text"]}</{nd["tag"]}>')
                else: lines.append(f'{pf}<{nd["tag"]}{a}></{nd["tag"]}>')

def _expand_emmet(abbr):
    if not abbr or not re.match(r'^[a-zA-Z]',abbr): return None
    try:
        r=_EmmetExpander(abbr).parse(); return r if r.strip() else None
    except: return None

# --------------------------------------------------------------- beautify
def _beautify_html(raw):
    vt=frozenset({'br','hr','img','input','meta','link','area','base','col','embed','source','track','wbr'})
    it=frozenset({'a','span','strong','em','b','i','u','code','small','sub','sup','label','abbr','cite','q','mark'})
    pt=frozenset({'pre','textarea','code'})
    toks=re.split(r'(<!--.*?-->|<[^>]+>)',raw,flags=re.DOTALL)
    res=[]; ind=0; pre=False
    for tk in toks:
        ts=tk.strip()
        if not ts: continue
        if ts.startswith('<!--'): res.append('    '*ind+ts)
        elif ts.startswith('</'):
            m=re.match(r'</(\w+)',ts)
            if m:
                tg=m.group(1).lower()
                if tg in pt: pre=False
                if tg not in it and not pre: ind=max(0,ind-1)
            res.append('    '*ind+ts)
        elif ts.startswith('<'):
            m=re.match(r'<(\w+)',ts)
            if m:
                tg=m.group(1).lower()
                if tg in pt: pre=True
                res.append('    '*ind+ts)
                if tg not in vt and tg not in it and not pre: ind+=1
            else: res.append('    '*ind+ts)
        else:
            res.append(tk if pre else '    '*ind+ts)
    return '\n'.join(res)

# ======================================================================
class FullScreenWebPage(QWebEnginePage):
    def __init__(self,profile,parent=None):
        super().__init__(profile,parent)
        self.fullScreenRequested.connect(lambda r:r.accept())

class PreviewWebPage(QWebEnginePage):
    consoleMessage=Signal(str,int,str,str)
    def javaScriptConsoleMessage(self,level,msg,ln,sid):
        lm={QWebEnginePage.InfoMessageLevel:("INFO","#d4d4d4"),QWebEnginePage.WarningMessageLevel:("WARN","#ffd700"),QWebEnginePage.ErrorMessageLevel:("ERROR","#f44747")}
        n,c=lm.get(level,("LOG","#d4d4d4")); self.consoleMessage.emit(msg,ln,n,c)

class FileTreeProxyModel(QSortFilterProxyModel):
    def lessThan(self,l,r):
        ld=self.sourceModel().isDir(l); rd=self.sourceModel().isDir(r)
        if ld!=rd: return ld
        return self.sourceModel().data(l).lower()<self.sourceModel().data(r).lower()

class CursorHideFilter(QObject):
    def __init__(self,viewer):
        super().__init__(viewer); self.viewer=viewer
    def eventFilter(self,obj,ev):
        if self.viewer._is_full_screen:
            et=ev.type()
            if et in(QEvent.MouseMove,QEvent.MouseButtonPress,QEvent.KeyPress,QEvent.Wheel):
                QApplication.restoreOverrideCursor(); self.viewer._cursor_hide_timer.start()
        return False

# ======================================================================
class HTMLSyntaxHighlighter(QSyntaxHighlighter):
    COLOR_PAT=re.compile(r'#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b|rgba?\([^)]*\)|hsla?\([^)]*\)')
    def __init__(self,parent=None):
        super().__init__(parent); self.rules=[]
        c=QTextCharFormat(); c.setForeground(QColor("#6a9955")); c.setFontItalic(True)
        self.rules.append((re.compile(r"<!--.*?-->",re.DOTALL),c))
        self.rules.append((re.compile(r"/\*.*?\*/",re.DOTALL),c))
        self.rules.append((re.compile(r"//.*$",re.MULTILINE),c))
        td=QTextCharFormat(); td.setForeground(QColor("#ffd700")); td.setFontWeight(QFont.Bold)
        self.rules.append((re.compile(r"\b(TODO|FIXME|HACK|XXX|BUG)\b",re.IGNORECASE),td))
        dt=QTextCharFormat(); dt.setForeground(QColor("#c586c0")); dt.setFontWeight(QFont.Bold)
        self.rules.append((re.compile(r"<!DOCTYPE[^>]*>",re.IGNORECASE),dt))
        tg=QTextCharFormat(); tg.setForeground(QColor("#569cd6")); tg.setFontWeight(QFont.Bold)
        self.rules.append((re.compile(r"</?\w+"),tg)); self.rules.append((re.compile(r"/?>"),tg))
        at=QTextCharFormat(); at.setForeground(QColor("#9cdcfe"))
        self.rules.append((re.compile(r"\b[\w-]+(?=\s*=)"),at))
        st=QTextCharFormat(); st.setForeground(QColor("#ce9178"))
        self.rules.append((re.compile(r'"[^"]*"'),st)); self.rules.append((re.compile(r"'[^']*'"),st))
        cp=QTextCharFormat(); cp.setForeground(QColor("#9cdcfe"))
        self.rules.append((re.compile(r"[\w-]+(?=\s*:)"),cp))
        ar=QTextCharFormat(); ar.setForeground(QColor("#c586c0")); ar.setFontWeight(QFont.Bold)
        self.rules.append((re.compile(r"@\w+"),ar))
        nm=QTextCharFormat(); nm.setForeground(QColor("#b5cea8"))
        self.rules.append((re.compile(r"\b\d+(?:\.\d+)?(?:px|em|rem|%|vh|vw|s|ms|deg|fr)?\b"),nm))
        kw=QTextCharFormat(); kw.setForeground(QColor("#c586c0")); kw.setFontWeight(QFont.Bold)
        self.rules.append((re.compile(r"\b(?:function|return|if|else|for|while|var|let|const|true|false|null|undefined|new|this|class|extends|import|export|default|from|async|await|try|catch|throw|typeof|instanceof|in|of|break|continue|switch|case|do|delete|void|with|yield)\b"),kw))
        ws=QTextCharFormat(); ws.setBackground(QColor("#3a1f1f"))
        self.rules.append((re.compile(r"[ \t]+$"),ws))
    def highlightBlock(self,text):
        for pat,fmt in self.rules:
            for m in pat.finditer(text): self.setFormat(m.start(),m.end()-m.start(),fmt)
        for m in self.COLOR_PAT.finditer(text):
            cs=m.group(); col=QColor(cs.strip())
            if col.isValid():
                lum=(0.299*col.red()+0.587*col.green()+0.114*col.blue())/255
                fmt=QTextCharFormat()
                fmt.setForeground(QColor("#000") if lum>0.55 else QColor("#fff"))
                fmt.setBackground(col)
                self.setFormat(m.start(),m.end()-m.start(),fmt)
        self.setCurrentBlockState(0)

class LineNumberArea(QWidget):
    def __init__(self,editor): super().__init__(editor); self.editor=editor
    def paintEvent(self,ev):
        p=QPainter(self); p.fillRect(ev.rect(),QColor("#1e1e1e"))
        b=self.editor.firstVisibleBlock(); bn=b.blockNumber()
        top=round(self.editor.blockBoundingGeometry(b).translated(self.editor.contentOffset()).top())
        bot=top+round(self.editor.blockBoundingRect(b).height())
        p.setFont(self.editor.font()); p.setPen(QColor("#858585"))
        while b.isValid() and top<=ev.rect().bottom():
            if b.isVisible() and bot>=ev.rect().top():
                p.drawText(0,top,self.width()-8,self.editor.fontMetrics().height(),Qt.AlignRight,str(bn+1))
            b=b.next(); top=bot; bot=top+round(self.editor.blockBoundingRect(b).height()); bn+=1

# ======================================================================
class QuickOpenDialog(QDialog):
    def __init__(self,viewer,parent=None):
        super().__init__(parent); self.viewer=viewer
        self.setWindowTitle("Quick Open"); self.setModal(True); self.resize(600,400)
        self.setStyleSheet("background:#2d2d2d;")
        lay=QVBoxLayout(self); lay.setContentsMargins(8,8,8,8); lay.setSpacing(4)
        self.se=QLineEdit(); self.se.setPlaceholderText("Type to search files…")
        self.se.setStyleSheet("QLineEdit{background:#252526;color:#d4d4d4;border:1px solid #1e1e1e;padding:6px;border-radius:3px;}QLineEdit:focus{border:1px solid #007acc;}")
        self.se.textChanged.connect(self._filter); lay.addWidget(self.se)
        self.lw=QListWidget(); self.lw.setUniformItemSizes(True)
        self.lw.setStyleSheet("QListWidget{background:#1e1e1e;color:#d4d4d4;border:none;}QListWidget::item:selected{background:#094771;}")
        self.lw.itemDoubleClicked.connect(self._open); lay.addWidget(self.lw)
        self._files=[]; self._populate(); self.se.setFocus()
    def _populate(self):
        self._files=self.viewer._list_html_files()
        for f in self._files: self.lw.addItem(f.name)
        if self.lw.count()>0: self.lw.setCurrentRow(0)
    def _filter(self,t):
        tl=t.lower(); self.lw.clear()
        for f in self._files:
            if tl in f.name.lower(): self.lw.addItem(f.name)
        if self.lw.count()>0: self.lw.setCurrentRow(0)
    def _open(self,item):
        for f in self._files:
            if f.name==item.text(): self.viewer._load_file(f); break
        self.accept()
    def keyPressEvent(self,ev):
        if ev.key() in(Qt.Key_Return,Qt.Key_Enter):
            if self.lw.currentItem(): self._open(self.lw.currentItem())
            return
        elif ev.key()==Qt.Key_Escape: self.reject(); return
        super().keyPressEvent(ev)

# ======================================================================
# Threading infrastructure
# ======================================================================
class TaskManager(QObject):
    task_started=Signal(str); task_progress=Signal(str,int,str)
    task_result=Signal(str,object); task_error=Signal(str,str); task_finished=Signal(str)
    def __init__(self,parent=None):
        super().__init__(parent); self._tasks={}; self._mutex=QMutex()
    def is_running(self,tid):
        with QMutexLocker(self._mutex): return tid in self._tasks
    def get_worker(self,tid):
        with QMutexLocker(self._mutex): return self._tasks.get(tid)
    def cancel(self,tid):
        with QMutexLocker(self._mutex): w=self._tasks.get(tid)
        if w and hasattr(w,'cancel'): w.cancel(); return True
        return False
    def cancel_all(self):
        with QMutexLocker(self._mutex): ids=list(self._tasks.keys())
        for i in ids: self.cancel(i)
    def register(self,tid,worker):
        with QMutexLocker(self._mutex):
            if tid in self._tasks: return False
            self._tasks[tid]=worker
        worker.finished.connect(lambda: self._unreg(tid)); return True
    def _unreg(self,tid):
        with QMutexLocker(self._mutex): self._tasks.pop(tid,None)
        self.task_finished.emit(tid)

class PlaywrightPool:
    def __init__(self):
        self._lock=threading.Lock(); self._pw=None; self._br=None
        self._args=['--disable-gpu','--no-sandbox','--disable-dev-shm-usage','--disable-extensions','--disable-background-networking','--disable-background-timer-throttling']
    def get_browser(self):
        with self._lock:
            if self._br and self._br.is_connected(): return self._br
            from playwright.sync_api import sync_playwright
            if self._pw is None: self._pw=sync_playwright().start(); log_playw.info("Playwright runtime started")
            self._br=self._pw.chromium.launch(headless=True,args=self._args)
            log_playw.info("Chromium launched (persistent pool)"); return self._br
    def new_page(self,w=1920,h=1080):
        br=self.get_browser(); ctx=br.new_context(viewport={'width':w,'height':h},device_scale_factor=1)
        return ctx,ctx.new_page()
    def cleanup(self):
        with self._lock:
            if self._br:
                try: self._br.close(); log_playw.info("Chromium closed (pool)")
                except Exception as e: log_playw.warning("Browser close error: %s",e)
                self._br=None
            if self._pw:
                try: self._pw.stop(); log_playw.info("Playwright stopped")
                except Exception as e: log_playw.warning("Playwright stop error: %s",e)
                self._pw=None

class JPGExportWorker(QThread):
    progress=Signal(int,str); finished_result=Signal(bool,str)
    def __init__(self,source_path,html_content,save_path,full_page,quality,vp_width,pool,temp_dir,source_name,parent=None):
        super().__init__(parent)
        self.source_path=source_path; self.html_content=html_content; self.save_path=save_path
        self.full_page=full_page; self.quality=quality; self.vp_width=vp_width
        self.pool=pool; self.temp_dir=temp_dir; self.source_name=source_name; self._cancelled=False
    def cancel(self): self._cancelled=True
    @property
    def is_cancelled(self): return self._cancelled
    def run(self):
        tf=None; t0=time.perf_counter()
        try:
            self.progress.emit(5,"Connecting to Chromium…")
            try: ctx,page=self.pool.new_page(self.vp_width)
            except ImportError: self.finished_result.emit(False,"IMPORT_ERROR"); return
            except Exception as e: log_jpg.exception("Pool error: %s",e); self.finished_result.emit(False,str(e)); return
            if self.is_cancelled: ctx.close(); self.finished_result.emit(False,"CANCELLED"); return
            self.progress.emit(20,"Loading page…"); t1=time.perf_counter()
            if self.source_path and os.path.exists(self.source_path):
                fu=Path(self.source_path).resolve().as_uri()
                log_playw.info("Navigating: %s",fu)
                page.goto(fu,wait_until='domcontentloaded',timeout=10000)
            else:
                tf=str(self.temp_dir/f"__jpg_temp_{self.source_name}.html")
                with open(tf,'w',encoding='utf-8') as f: f.write(self.html_content or "")
                fu=Path(tf).resolve().as_uri(); log_playw.info("Navigating (temp): %s",fu)
                page.goto(fu,wait_until='domcontentloaded',timeout=10000)
            log_playw.info("Page loaded in %.0fms",(time.perf_counter()-t1)*1000)
            if self.is_cancelled: ctx.close(); self._cleanup_temp(tf); self.finished_result.emit(False,"CANCELLED"); return
            self.progress.emit(50,"Waiting for content…"); t2=time.perf_counter()
            try: page.wait_for_load_state('networkidle',timeout=2000); log_playw.debug("networkidle in %.0fms",(time.perf_counter()-t2)*1000)
            except: log_playw.debug("networkidle timed out")
            page.wait_for_timeout(200)
            if self.is_cancelled: ctx.close(); self._cleanup_temp(tf); self.finished_result.emit(False,"CANCELLED"); return
            self.progress.emit(75,"Capturing screenshot…"); t3=time.perf_counter()
            page.screenshot(path=self.save_path,type='jpeg',quality=self.quality,full_page=self.full_page)
            log_playw.info("Screenshot in %.0fms",(time.perf_counter()-t3)*1000)
            try: ctx.close()
            except: pass
            self._cleanup_temp(tf)
            log_jpg.info("JPG saved: %s (%.0fms total)",self.save_path,(time.perf_counter()-t0)*1000)
            self.progress.emit(100,"Done!"); self.finished_result.emit(True,self.save_path)
        except Exception as e:
            log_jpg.exception("JPG worker FAILED: %s",e); self._cleanup_temp(tf)
            self.finished_result.emit(False,str(e))
    def _cleanup_temp(self,tf):
        if tf and os.path.exists(tf):
            try: os.unlink(tf)
            except: pass

class PlaywrightInstallerWorker(QThread):
    progress=Signal(int,str); finished_result=Signal(bool,str)
    def __init__(self,browser_only=False,parent=None):
        super().__init__(parent); self._bo=browser_only
    def run(self):
        import subprocess; errs=[]
        if not self._bo:
            self.progress.emit(10,"Installing playwright package…")
            try:
                r=subprocess.run([sys.executable,'-m','pip','install','playwright'],capture_output=True,text=True,timeout=180)
                if r.returncode!=0: errs.append(f"pip install:\n{r.stderr.strip()}")
            except Exception as e: errs.append(f"pip error:\n{str(e)}")
        if not errs:
            self.progress.emit(50,"Installing Chromium browser…")
            try:
                r=subprocess.run([sys.executable,'-m','playwright','install','chromium'],capture_output=True,text=True,timeout=600)
                if r.returncode!=0: errs.append(f"playwright install:\n{r.stderr.strip()}")
            except Exception as e: errs.append(f"playwright error:\n{str(e)}")
        self.progress.emit(90,"Finishing…")
        if errs: self.finished_result.emit(False,"\n\n".join(errs))
        else: self.finished_result.emit(True,"")

class FileLoadWorker(QThread):
    loaded=Signal(Path,str); failed=Signal(Path,str)
    def __init__(self,path,parent=None): super().__init__(parent); self.path=path
    def run(self):
        try:
            c=self.path.read_text(encoding='utf-8'); self.loaded.emit(self.path,c)
            log_fileops.info("File loaded async: %s (%d chars)",self.path.name,len(c))
        except OSError as e: self.failed.emit(self.path,str(e)); log_fileops.exception("Async load failed: %s",self.path)

# ======================================================================
class LogViewerDock(QDockWidget):
    def __init__(self,parent=None):
        super().__init__("Log Viewer",parent); self.setObjectName("LogViewerDock")
        self.setAllowedAreas(Qt.AllDockWidgetAreas); self._autoscroll=True
        cw=QWidget(); lay=QVBoxLayout(cw); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)
        bar=QToolBar(); bar.setMovable(False); bar.setObjectName("LogViewerToolBar")
        bar.addWidget(QLabel(" Level: "))
        self.lc=QComboBox(); self.lc.addItems(["DEBUG","INFO","WARNING","ERROR"])
        self.lc.setCurrentText("INFO"); self.lc.currentTextChanged.connect(self._refresh); bar.addWidget(self.lc)
        bar.addSeparator()
        aa=QAction("Auto-scroll",self); aa.setCheckable(True); aa.setChecked(True)
        aa.toggled.connect(self._toggle_as); bar.addAction(aa)
        bar.addAction("🔄 Refresh",self._refresh)
        bar.addAction("Clear",lambda:self.lt.clear())
        bar.addSeparator()
        bar.addAction("📂 Open log file",self._open_log)
        lay.addWidget(bar)
        sr=QHBoxLayout(); sr.setContentsMargins(6,4,6,4); sr.setSpacing(4)
        sr.addWidget(QLabel("Filter:")); self.se=QLineEdit(); self.se.setPlaceholderText("Case-insensitive filter…")
        self.se.setClearButtonEnabled(True); self.se.textChanged.connect(self._refresh); sr.addWidget(self.se,1)
        lay.addLayout(sr)
        self.lt=QPlainTextEdit(); self.lt.setReadOnly(True); self.lt.setMaximumBlockCount(2000)
        self.lt.setStyleSheet("QPlainTextEdit{background:#1a1a1a;color:#d4d4d4;font-family:'Cascadia Code','Consolas',monospace;font-size:11px;border:none;}")
        lay.addWidget(self.lt); self.setWidget(cw)
        self._tmr=QTimer(self); self._tmr.setInterval(400); self._tmr.timeout.connect(self._refresh); self._tmr.start()
        self._refresh()
    def _toggle_as(self,c): self._autoscroll=c
    def _open_log(self): QDesktopServices.openUrl(QUrl.fromLocalFile(str(LOG_FILE)))
    def _refresh(self):
        try:
            if not LOG_FILE.exists(): return
            with open(LOG_FILE,'r',encoding='utf-8') as f: lines=f.readlines()
        except OSError: return
        lv=self.lc.currentText(); levels=["DEBUG","INFO","WARNING","ERROR"]
        mi=levels.index(lv) if lv in levels else 0; allowed=levels[mi:]
        filt=[]
        for l in lines:
            ok=False
            for al in allowed:
                if f"[{al}   ]" in l or f"[{al}  ]" in l or f"[{al} ]" in l: ok=True; break
            if not ok and lv!="DEBUG" and not any(f"[{x}" in l for x in levels): ok=True
            if ok: filt.append(l)
        s=self.se.text().strip().lower()
        if s: filt=[l for l in filt if s in l.lower()]
        self.lt.setPlainText(''.join(filt[-500:]))
        if self._autoscroll:
            sb=self.lt.verticalScrollBar(); sb.setValue(sb.maximum())

# ======================================================================
class CodeEditor(QPlainTextEdit):
    PAIRS={'(':')','[':']','{':'}'}
    VOID=frozenset({'br','hr','img','input','meta','link','area','base','col','embed','source','track','wbr'})
    def __init__(self,parent=None):
        super().__init__(parent)
        self.lna=LineNumberArea(self)
        self.blockCountChanged.connect(self._ulnw); self.updateRequest.connect(self._ulna); self._ulnw()
        self.cursorPositionChanged.connect(self._ues); self._ues()
        self.completer=QCompleter(self); self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setWrapAround(False); self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.setWidget(self); self.completer.activated.connect(self._insertCompletion)
        self.cm=QStringListModel(); self.completer.setModel(self.cm)
    def _insertCompletion(self,comp):
        if self.completer.widget() is not self: return
        c=self.textCursor(); extra=len(comp)-len(self.completer.completionPrefix())
        c.movePosition(QTextCursor.Left); c.movePosition(QTextCursor.EndOfWord)
        c.insertText(comp[-extra:]); self.setTextCursor(c)
    def textUnderCursor(self):
        c=self.textCursor(); c.select(QTextCursor.WordUnderCursor); return c.selectedText()
    def contextMenuEvent(self,ev):
        m=self.createStandardContextMenu(); m.addSeparator()
        ew=_find_ancestor(self,HTMLEditor)
        m.addAction("Toggle Comment",self.toggle_comment,QKeySequence("Ctrl+/"))
        if ew: m.addAction("Find/Replace",ew._open_find_replace,QKeySequence("Ctrl+F"))
        m.addSeparator()
        if ew:
            m.addAction("Beautify HTML",ew._beautify,QKeySequence("Ctrl+Shift+B"))
            m.addAction("Sort Lines",ew._sort_lines)
            m.addAction("Remove Duplicates",ew._dedupe_lines)
            m.addAction("Remove Blank Lines",ew._remove_blank_lines)
            m.addAction("Insert Lorem Ipsum",lambda:ew._insert_lorem(1))
            m.addAction("Insert Timestamp",ew._insert_timestamp)
            m.addAction("Encode Image as Base64",ew._encode_image_base64)
            em=m.addMenu("Insert HTML Entity")
            for ent,desc in HTML_ENTITIES.items():
                em.addAction(f"{ent}  ({desc})",lambda _=False,e=ent:ew._insert_text(e))
        m.exec(ev.globalPos())
    def keyPressEvent(self,ev):
        isSC=(ev.modifiers()==Qt.ControlModifier and ev.key()==Qt.Key_Space)
        if self.completer.popup().isVisible():
            if ev.key() in(Qt.Key_Enter,Qt.Key_Return,Qt.Key_Escape,Qt.Key_Tab,Qt.Key_Backtab): ev.ignore(); return
            if ev.text() and not re.match(r'\w',ev.text()): self.completer.popup().hide()
        if isSC:
            text=self.toPlainText(); dw=set(re.findall(r'\b[A-Za-z0-9_-]+\b',text))
            aw=sorted(list(dw.union(AUTOCOMPLETE_KEYWORDS))); self.cm.setStringList(aw)
            pf=self.textUnderCursor()
            if pf!=self.completer.completionPrefix(): self.completer.setCompletionPrefix(pf)
            cr=self.cursorRect(); cr.setWidth(self.completer.popup().sizeHintForColumn(0)+self.completer.popup().verticalScrollBar().sizeHint().width())
            self.completer.complete(cr); return
        c=self.textCursor()
        if ev.key()==Qt.Key_Tab and ev.modifiers()==Qt.NoModifier:
            if c.hasSelection(): self._indent_sel(c); return
            else:
                lt=c.block().text(); col=c.columnNumber()
                wm=re.search(r'([a-zA-Z][\w.#*>+\-{}*]*)$',lt[:col])
                if wm:
                    abbr=wm.group(1); exp=_expand_emmet(abbr)
                    if exp:
                        c.movePosition(QTextCursor.Left,QTextCursor.KeepAnchor,len(abbr))
                        c.removeSelectedText(); c.insertText(exp)
                        if '>' in exp: c.movePosition(QTextCursor.Left,QTextCursor.MoveAnchor,len(exp)-exp.find('>')-1)
                        self.setTextCursor(c); return
                c.insertText('    '); return
        elif ev.key()==Qt.Key_Backtab:
            if c.hasSelection(): self._unindent_sel(c); return
        if ev.text() in self.PAIRS and not c.hasSelection():
            cl=self.PAIRS[ev.text()]; c.insertText(ev.text()+cl)
            c.movePosition(QTextCursor.Left); self.setTextCursor(c); return
        if ev.text()=='>' and not c.hasSelection():
            tb=self.toPlainText()[:c.position()]
            tm=re.search(r'<(\w+)(?:\s[^<>]*)?$',tb)
            if tm:
                tg=tm.group(1)
                if tg.lower() not in self.VOID:
                    c.insertText('>'); ct=f'</{tg}>'
                    c.insertText(ct); c.movePosition(QTextCursor.Left,QTextCursor.MoveAnchor,len(ct))
                    self.setTextCursor(c); return
        if ev.key()==Qt.Key_Backspace and not c.hasSelection():
            pos=c.position()
            if pos>0:
                c.movePosition(QTextCursor.Left,QTextCursor.KeepAnchor); lc=c.selectedText()
                c.movePosition(QTextCursor.Right); c.movePosition(QTextCursor.Right,QTextCursor.KeepAnchor)
                rc=c.selectedText(); c.movePosition(QTextCursor.Left)
                if self.PAIRS.get(lc)==rc: c.deleteChar(); c.deletePreviousChar(); return
        elif ev.key()==Qt.Key_D and ev.modifiers()==Qt.ControlModifier: self.duplicate_line(); return
        elif ev.key()==Qt.Key_Up and ev.modifiers()==Qt.AltModifier: self.move_line(-1); return
        elif ev.key()==Qt.Key_Down and ev.modifiers()==Qt.AltModifier: self.move_line(1); return
        elif ev.key()==Qt.Key_Slash and ev.modifiers()==Qt.ControlModifier: self.toggle_comment(); return
        elif ev.key()==Qt.Key_K and ev.modifiers()==(Qt.ControlModifier|Qt.ShiftModifier): self.delete_line(); return
        elif ev.key() in(Qt.Key_Return,Qt.Key_Enter):
            text=c.block().text(); ind=len(text)-len(text.lstrip())
            if text.strip().endswith('{'): ind+=4
            super().keyPressEvent(ev)
            if ind>0: self.textCursor().insertText(' '*ind)
            return
        super().keyPressEvent(ev)
    def _ues(self):
        extra=[]
        sel=QTextEdit.ExtraSelection(); sel.format.setBackground(QColor("#2a2a2a"))
        sel.format.setProperty(QTextFormat.FullWidthSelection,True)
        sel.cursor=self.textCursor(); sel.cursor.clearSelection(); extra.append(sel)
        for pos in self._find_bracket():
            s=QTextEdit.ExtraSelection(); s.format.setBackground(QColor("#3d3d3d"))
            s.cursor=QTextCursor(self.document()); s.cursor.setPosition(pos)
            s.cursor.movePosition(QTextCursor.Right,QTextCursor.KeepAnchor); extra.append(s)
        c=self.textCursor()
        if c.hasSelection():
            word=c.selectedText()
            if len(word)>=2 and '\n' not in word:
                sc=QTextCursor(self.document())
                while True:
                    sc=self.document().find(word,sc)
                    if sc.isNull(): break
                    if sc.selectionStart()!=c.selectionStart():
                        s=QTextEdit.ExtraSelection(); s.format.setBackground(QColor("#264f78"))
                        s.cursor=sc; extra.append(s)
        self.setExtraSelections(extra)
    def _find_bracket(self):
        c=self.textCursor(); pos=c.position(); text=self.toPlainText()
        if pos>=len(text): return []
        ch=text[pos]
        if ch not in'()[]{}':
            if pos>0: ch=text[pos-1]
            if ch not in'()[]{}': return []
            pos-=1
        op='([{'; cl=')]}'
        if ch in op:
            tg=cl[op.index(ch)]; d=1; i=pos+1
            while i<len(text) and d>0:
                if text[i]==ch: d+=1
                elif text[i]==tg: d-=1
                i+=1
            if d==0: return[pos,i-1]
        elif ch in cl:
            tg=op[cl.index(ch)]; d=1; i=pos-1
            while i>=0 and d>0:
                if text[i]==ch: d+=1
                elif text[i]==tg: d-=1
                i-=1
            if d==0: return[i+1,pos]
        return[]
    def paintEvent(self,ev):
        super().paintEvent(ev)
        p=QPainter(self.viewport()); p.setPen(QColor("#2a2a2a"))
        b=self.firstVisibleBlock(); sw=self.fontMetrics().horizontalAdvance(' ')
        off=self.contentOffset()
        while b.isValid():
            text=b.text()
            top=round(self.blockBoundingGeometry(b).translated(off).top())
            bot=top+round(self.blockBoundingRect(b).height())
            if bot<0: b=b.next(); continue
            if top>self.height(): break
            ind=len(text)-len(text.lstrip(' '))
            if ind>=4:
                for lv in range(1,ind//4+1):
                    x=lv*4*sw; p.drawLine(x,top,x,bot)
            b=b.next()
    def _ulnw(self):
        d=max(1,len(str(self.blockCount())))
        w=self.fontMetrics().horizontalAdvance('9')*d+16
        self.lna.setFixedWidth(w); self.setViewportMargins(w,0,0,0)
    def _ulna(self,rect,dy):
        if dy: self.lna.scroll(0,dy)
        else: self.lna.update(0,rect.y(),self.lna.width(),rect.height())
        if rect.contains(self.viewport().rect()): self._ulnw()
    def resizeEvent(self,ev):
        super().resizeEvent(ev)
        cr=self.contentsRect()
        self.lna.setGeometry(cr.left(),cr.top(),self.lna.width(),cr.height())
    def _indent_sel(self,c):
        s=c.selectionStart(); e=c.selectionEnd()
        c.setPosition(s); c.setPosition(e,QTextCursor.KeepAnchor)
        t=c.selectedText(); lines=t.split('\u2029')
        c.beginEditBlock(); c.removeSelectedText()
        c.insertText('\n'.join('    '+l for l in lines)); c.endEditBlock()
    def _unindent_sel(self,c):
        s=c.selectionStart(); e=c.selectionEnd()
        c.setPosition(s); c.setPosition(e,QTextCursor.KeepAnchor)
        t=c.selectedText(); lines=t.split('\u2029'); ui=[]
        for l in lines:
            if l.startswith('    '): ui.append(l[4:])
            elif l.startswith(' '): ui.append(l.lstrip(' '))
            else: ui.append(l)
        c.beginEditBlock(); c.removeSelectedText(); c.insertText('\n'.join(ui)); c.endEditBlock()
    def duplicate_line(self):
        c=self.textCursor(); c.beginEditBlock()
        c.select(QTextCursor.BlockUnderCursor); t=c.selectedText()
        c.movePosition(QTextCursor.EndOfBlock); c.insertText('\n'+t); c.endEditBlock()
    def move_line(self,d):
        c=self.textCursor(); c.beginEditBlock()
        c.movePosition(QTextCursor.StartOfBlock); c.movePosition(QTextCursor.EndOfBlock,QTextCursor.KeepAnchor)
        if not c.atEnd(): c.movePosition(QTextCursor.NextCharacter,QTextCursor.KeepAnchor)
        t=c.selectedText(); c.removeSelectedText()
        if d>0:
            if c.movePosition(QTextCursor.NextBlock): c.insertText(t); c.movePosition(QTextCursor.PreviousBlock)
            else:
                c.movePosition(QTextCursor.EndOfBlock)
                if not t.endswith('\n'): t='\n'+t
                c.insertText(t)
        else:
            if c.movePosition(QTextCursor.PreviousBlock):
                if not t.endswith('\n'): t+='\n'
                c.insertText(t); c.movePosition(QTextCursor.PreviousBlock)
            else:
                c.movePosition(QTextCursor.StartOfBlock)
                if not t.endswith('\n'): t+='\n'
                c.insertText(t)
        c.endEditBlock()
    def delete_line(self):
        c=self.textCursor(); c.select(QTextCursor.BlockUnderCursor)
        c.removeSelectedText(); c.deletePreviousChar()
    def toggle_comment(self):
        c=self.textCursor()
        if c.hasSelection():
            s=c.selectionStart(); e=c.selectionEnd()
            c.setPosition(s); c.beginEditBlock(); c.insertText('<!-- ')
            c.setPosition(e+5); c.insertText(' -->'); c.endEditBlock()
        else:
            c.select(QTextCursor.BlockUnderCursor)
            t=c.selectedText().replace('\u2029',''); st=t.strip()
            if st.startswith('<!--') and st.endswith('-->'):
                nt=t.replace('<!--','',1); i=nt.rfind('-->')
                if i!=-1: nt=nt[:i]+nt[i+3:]
                c.beginEditBlock(); c.removeSelectedText(); c.insertText(nt); c.endEditBlock()
            else:
                c.movePosition(QTextCursor.StartOfBlock); c.beginEditBlock()
                c.insertText('<!-- '); c.movePosition(QTextCursor.EndOfBlock)
                c.insertText(' -->'); c.endEditBlock()

# ======================================================================
class HTMLEditor(QWidget):
    TEMPLATES={"HTML5 Boilerplate":HTML5_TEMPLATE,"Keyframe Pulse Animation":CSS_KEYFRAME_ANIMATION,"JS Console Test":JS_CONSOLE_TEST}
    def __init__(self,viewer,parent=None):
        super().__init__(parent); self.viewer=viewer
        self.current_file=None; self._modified=False; self._auto_preview=True; self._preview_scroll=0
        self._preview_timer=QTimer(self); self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(400); self._preview_timer.timeout.connect(self._prepare_update_preview)
        self._auto_save_timer=QTimer(self); self._auto_save_timer.setSingleShot(True)
        self._auto_save_timer.setInterval(1000); self._auto_save_timer.timeout.connect(self._save_file)
        self._file_watcher=QFileSystemWatcher(self); self._file_watcher.fileChanged.connect(self._on_file_changed)
        self._suppress_reload=False; self._file_load_worker=None
        self._build_ui()
        self.preview=QWebEngineView(); self.preview_page=PreviewWebPage(self.preview)
        self.preview.setPage(self.preview_page); self.preview_page.consoleMessage.connect(self._on_console_message)
        ps=self.preview.settings()
        ps.setAttribute(QWebEngineSettings.JavascriptEnabled,True)
        ps.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls,True)
        ps.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls,True)
        ps.setAttribute(QWebEngineSettings.AutoLoadImages,True)
        self.preview.setHtml("<html><body style='font-family:sans-serif;padding:40px;background:#1e1e1e;color:#888;text-align:center;'><h3>Preview will appear here</h3><p>Start typing or load a file…</p></body></html>")
        self.console=QTextEdit(); self.console.setReadOnly(True)
        self.console.setStyleSheet("background:#1e1e1e;color:#d4d4d4;border:none;")
    def _build_ui(self):
        lay=QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)
        self.etb=QToolBar("Editor"); self.etb.setObjectName("EditorToolBar"); self.etb.setMovable(False)
        def _a(icon,tip,slot,sep=False):
            a=QAction(icon,self); a.setToolTip(tip); a.triggered.connect(slot); self.etb.addAction(a)
            if sep: self.etb.addSeparator()
        _a("📄 New","New file (Ctrl+N)",self._new_file); _a("📂 Open","",self._open_file); _a("💾 Save","",self._save_file)
        _a("Save As…","",self._save_as,True)
        self.auto_save_act=QAction("⚡ Auto-Save",self); self.auto_save_act.setCheckable(True); self.auto_save_act.setChecked(False)
        self.etb.addAction(self.auto_save_act); self.etb.addSeparator()
        _a("⬆ Load Viewer File","",self._load_from_viewer); _a("👁 Save & View","",self._save_and_view,True)
        _a("▶ Apply","",self._prepare_update_preview)
        self.auto_preview_act=QAction("🔄 Auto-Preview",self); self.auto_preview_act.setCheckable(True)
        self.auto_preview_act.setChecked(True); self.auto_preview_act.toggled.connect(self._toggle_auto_preview)
        self.etb.addAction(self.auto_preview_act); self.etb.addSeparator()
        self.word_wrap_act=QAction("↩ Word Wrap",self); self.word_wrap_act.setCheckable(True)
        self.word_wrap_act.setChecked(False); self.word_wrap_act.toggled.connect(self._toggle_word_wrap)
        self.etb.addAction(self.word_wrap_act)
        tm=QMenu("Templates",self)
        for n in self.TEMPLATES: tm.addAction(n,lambda _=False,n2=n:self._insert_template(n2))
        tb=QAction("📋 Templates",self); tb.setMenu(tm); self.etb.addAction(tb)
        em=QMenu("Entities",self)
        for ent,desc in HTML_ENTITIES.items(): em.addAction(f"{ent}  ({desc})",lambda _=False,e=ent:self._insert_text(e))
        eb=QAction("&",self); eb.setMenu(em); self.etb.addAction(eb)
        im=QMenu("Insert",self)
        im.addAction("Lorem Ipsum (1)",lambda:self._insert_lorem(1))
        im.addAction("Lorem Ipsum (3)",lambda:self._insert_lorem(3)); im.addSeparator()
        im.addAction("Timestamp",self._insert_timestamp)
        im.addAction("Encode Image as Base64…",self._encode_image_base64)
        ib=QAction("➕ Insert",self); ib.setMenu(im); self.etb.addAction(ib)
        tl=QMenu("Tools",self); tl.addAction("Beautify HTML (Ctrl+Shift+B)",self._beautify); tl.addSeparator()
        tl.addAction("Sort Lines A→Z",self._sort_lines); tl.addAction("Remove Duplicates",self._dedupe_lines)
        tl.addAction("Remove Blank Lines",self._remove_blank_lines)
        tb2=QAction("🔧 Tools",self); tb2.setMenu(tl); self.etb.addAction(tb2); self.etb.addSeparator()
        _a("🔍 Find/Replace","",self._open_find_replace)
        lay.addWidget(self.etb)
        self.editor=CodeEditor()
        st=QSettings(QSettings.IniFormat,QSettings.UserScope,"HTMLViewer","HTMLViewer")
        fs=int(st.value("editorFontSize",10)); self._setup_editor_font(fs)
        self.editor.setStyleSheet("QPlainTextEdit{background:#1e1e1e;color:#d4d4d4;border:none;selection-background-color:#264f78;}")
        self.editor.textChanged.connect(self._on_text_changed)
        self.highlighter=HTMLSyntaxHighlighter(self.editor.document()); lay.addWidget(self.editor,1)
        self._build_find_replace_bar(); lay.addWidget(self._frb); self._frb.setVisible(False)
        self.sb=QFrame(); self.sb.setFrameShape(QFrame.StyledPanel)
        self.sb.setStyleSheet("QFrame{background:#007acc;color:white;}QLabel{padding:2px 8px;}")
        sl=QHBoxLayout(self.sb); sl.setContentsMargins(4,2,4,2); sl.setSpacing(8)
        self.file_lbl=QLabel("No file"); sl.addWidget(self.file_lbl,1)
        self.selection_lbl=QLabel(""); sl.addWidget(self.selection_lbl)
        self.word_count_lbl=QLabel("0 words"); sl.addWidget(self.word_count_lbl)
        self.cursor_lbl=QLabel("Ln 1, Col 1"); sl.addWidget(self.cursor_lbl)
        self.mod_lbl=QLabel("●"); self.mod_lbl.setStyleSheet("color:#ffd700;font-size:14px;"); sl.addWidget(self.mod_lbl)
        lay.addWidget(self.sb); self.editor.cursorPositionChanged.connect(self._update_cursor_pos)
    def _build_find_replace_bar(self):
        self._frb=QFrame(); self._frb.setObjectName("FindBar"); self._frb.setFrameShape(QFrame.StyledPanel)
        lay=QHBoxLayout(self._frb); lay.setContentsMargins(8,4,8,4); lay.setSpacing(6)
        lay.addWidget(QLabel("Find:")); self.code_find_edit=QLineEdit()
        self.code_find_edit.setClearButtonEnabled(True); self.code_find_edit.returnPressed.connect(self._find_next)
        lay.addWidget(self.code_find_edit,1)
        self.regex_btn=QPushButton(".*"); self.regex_btn.setCheckable(True)
        self.regex_btn.setToolTip("Regex"); self.regex_btn.setFixedWidth(34); lay.addWidget(self.regex_btn)
        self.case_btn=QPushButton("Aa"); self.case_btn.setCheckable(True)
        self.case_btn.setToolTip("Match case"); self.case_btn.setFixedWidth(34); lay.addWidget(self.case_btn)
        self.match_count_lbl=QLabel("0/0"); self.match_count_lbl.setStyleSheet("color:#888;padding:0 4px;")
        lay.addWidget(self.match_count_lbl)
        lay.addWidget(QPushButton("Next ▶",clicked=self._find_next)); lay.addSpacing(10)
        lay.addWidget(QLabel("Replace:")); self.code_replace_edit=QLineEdit(); lay.addWidget(self.code_replace_edit,1)
        lay.addWidget(QPushButton("Replace",clicked=self._replace_one))
        lay.addWidget(QPushButton("Replace All",clicked=self._replace_all))
        lay.addWidget(QPushButton("✕",clicked=self._close_find_replace))
        self.code_find_edit.textChanged.connect(self._update_find_count)
        self.regex_btn.toggled.connect(self._update_find_count)
        self.case_btn.toggled.connect(self._update_find_count)
    def _setup_editor_font(self,size):
        f=_get_monospace_font(size); self.editor.setFont(f)
        self.editor.setTabStopDistance(self.editor.fontMetrics().horizontalAdvance(' ')*4)
    def _toggle_word_wrap(self,c): self.editor.setLineWrapMode(QPlainTextEdit.WidgetWidth if c else QPlainTextEdit.NoWrap)
    def _new_file(self):
        if self._modified:
            r=QMessageBox.question(self,"New File","Discard changes?",QMessageBox.Yes|QMessageBox.No)
            if r!=QMessageBox.Yes: return
        self._remove_file_watch(); self.current_file=None
        self.editor.setPlainText(HTML5_TEMPLATE); self._modified=False
        self._update_status(); self._prepare_update_preview()
        log_editor.info("New file created")
    def _open_file(self):
        p,_=QFileDialog.getOpenFileName(self,"Open HTML file",str(self.viewer.input_dir),"HTML files (*.html *.htm *.xhtml);;All files (*.*)")
        if p: self.load_file(Path(p))
    def load_file(self,path):
        if not path.exists(): QMessageBox.warning(self,"Open Error",f"File not found: {path}"); return
        fs=path.stat().st_size
        if fs>100_000:
            log_editor.info("Large file (%s) — async: %s",_human_size(fs),path.name)
            self._file_load_worker=FileLoadWorker(path,self)
            self._file_load_worker.loaded.connect(self._on_file_loaded)
            self._file_load_worker.failed.connect(self._on_file_load_failed)
            self._file_load_worker.start(); self.viewer._notify(f"Loading {path.name}…")
        else:
            try: self._apply_loaded_text(path,path.read_text(encoding='utf-8'))
            except OSError as e: QMessageBox.warning(self,"Open Error",str(e))
    def _on_file_loaded(self,path,content): self._apply_loaded_text(path,content)
    def _on_file_load_failed(self,path,error): QMessageBox.warning(self,"Open Error",error)
    def _apply_loaded_text(self,path,text):
        self._suppress_reload=True; self._remove_file_watch()
        self.editor.setPlainText(text); self.current_file=path; self._modified=False
        self._add_file_watch(path); self._update_status(); self._prepare_update_preview()
        self._suppress_reload=False
        log_editor.info("File loaded: %s (%d chars, %d lines)",path.name,len(text),text.count('\n')+1)
    def _save_file(self):
        if not self.current_file: return self._save_as()
        try:
            self._suppress_reload=True; content=self.editor.toPlainText()
            self.current_file.write_text(content,encoding='utf-8')
            self._modified=False; self._update_status()
            self.viewer._notify(f"Saved: {self.current_file.name}")
            QTimer.singleShot(200,lambda:setattr(self,'_suppress_reload',False))
            log_editor.info("File saved: %s (%d chars)",self.current_file.name,len(content)); return True
        except OSError as e:
            log_editor.exception("Save failed: %s",self.current_file)
            QMessageBox.warning(self,"Save Error",str(e)); self._suppress_reload=False; return False
    def _save_as(self):
        dn=self.current_file.name if self.current_file else "untitled.html"
        dp=str(self.viewer.input_dir/dn)
        p,_=QFileDialog.getSaveFileName(self,"Save HTML file",dp,"HTML files (*.html *.htm *.xhtml);;All files (*.*)")
        if p:
            self._remove_file_watch(); self.current_file=Path(p)
            if self._save_file(): self._add_file_watch(self.current_file); self.viewer._refresh_file_list(); return True
        return False
    def _load_from_viewer(self):
        if not self.viewer._current_path: QMessageBox.information(self,"No File","No file in viewer."); return
        p=Path(self.viewer._current_path)
        if self._modified:
            r=QMessageBox.question(self,"Load File","Discard changes and load viewer's file?",QMessageBox.Yes|QMessageBox.No)
            if r!=QMessageBox.Yes: return
        self.load_file(p)
    def _save_and_view(self):
        if not self.current_file:
            if not self._save_as(): return
        elif self._modified:
            if not self._save_file(): return
        self.viewer.tabs.setCurrentIndex(0); self.viewer._load_file(self.current_file)
    def _add_file_watch(self,p):
        try: self._file_watcher.addPath(str(p))
        except: pass
    def _remove_file_watch(self):
        if self.current_file:
            try: self._file_watcher.removePath(str(self.current_file))
            except: pass
    def _on_file_changed(self,p):
        if self._suppress_reload: return
        if not self.current_file or str(self.current_file)!=p: return
        if not Path(p).exists(): log_editor.warning("File deleted: %s",p); return
        if self._modified:
            r=QMessageBox.question(self,"File Changed",f"{Path(p).name} was modified externally.\nReload?",QMessageBox.Yes|QMessageBox.No)
            if r==QMessageBox.Yes: self.load_file(Path(p))
        else: self.load_file(Path(p))
    def _toggle_auto_preview(self,c): self._auto_preview=c
    def _prepare_update_preview(self):
        if self._auto_preview: self.preview.page().runJavaScript("window.scrollY",self._update_preview_with_scroll)
    def _update_preview_with_scroll(self,sp):
        self._preview_scroll=int(sp) if sp else 0
        hc=self.editor.toPlainText()
        if hc.strip():
            bu=QUrl.fromLocalFile(str(self.viewer.input_dir.resolve())+"/")
            self.preview.setHtml(hc,bu)
            QTimer.singleShot(150,self._restore_preview_scroll)
    def _restore_preview_scroll(self):
        if self._preview_scroll>0: self.preview.page().runJavaScript(f"window.scrollTo(0,{self._preview_scroll});")
    def _on_console_message(self,msg,ln,ln_name,color):
        log_preview.debug("JS Console [%s L%d]: %s",ln_name,ln,msg)
        sm=html_module.escape(msg)
        self.console.append(f'<span style="color:{color};">[{ln_name} Ln {ln}] {sm}</span>')
    def _on_text_changed(self):
        self._modified=True; self._update_status()
        if self._auto_preview: self._preview_timer.start()
        if self.auto_save_act.isChecked() and self.current_file: self._auto_save_timer.start()
    def _insert_text(self,t):
        c=self.editor.textCursor(); c.insertText(t); self.editor.setTextCursor(c)
    def _insert_template(self,n):
        t=self.TEMPLATES.get(n,"")
        if not t: return
        if not self.editor.toPlainText().strip(): self.editor.setPlainText(t)
        else: self.editor.textCursor().insertText("\n"+t+"\n")
        self._modified=True; self._update_status()
    def _insert_lorem(self,p=1):
        self._insert_text((LOREM_IPSUM+"\n\n")*p)
        self._modified=True; self._update_status()
    def _insert_timestamp(self): self._insert_text(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    def _encode_image_base64(self):
        p,_=QFileDialog.getOpenFileName(self,"Select Image",str(self.viewer.input_dir),"Images (*.png *.jpg *.jpeg *.gif *.svg *.webp *.ico);;All files (*.*)")
        if not p: return
        try:
            ext=Path(p).suffix.lower()
            mm={'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.gif':'image/gif','.svg':'image/svg+xml','.webp':'image/webp','.ico':'image/x-icon'}
            mime=mm.get(ext,'application/octet-stream')
            with open(p,'rb') as f: data=base64.b64encode(f.read()).decode('ascii')
            self._insert_text(f'data:{mime};base64,{data}')
            log_editor.info("Base64 encoded: %s → %d chars",Path(p).name,len(data))
        except Exception as e: QMessageBox.warning(self,"Encode Error",str(e))
    def _beautify(self):
        log_editor.info("Beautify HTML requested")
        hc=self.editor.toPlainText()
        if not hc.strip(): return
        t0=time.perf_counter(); bf=_beautify_html(hc)
        c=self.editor.textCursor(); c.select(QTextCursor.Document); c.insertText(bf)
        self._modified=True; self._update_status()
        log_editor.info("HTML beautified: %d → %d chars in %.1fms",len(hc),len(bf),(time.perf_counter()-t0)*1000)
        self.viewer._notify("HTML beautified")
    def _sort_lines(self):
        c=self.editor.textCursor()
        if not c.hasSelection(): c.select(QTextCursor.BlockUnderCursor)
        t=c.selectedText().replace('\u2029','\n')
        lines=sorted(t.split('\n'),key=lambda l:l.lower())
        c.insertText('\n'.join(lines))
    def _dedupe_lines(self):
        c=self.editor.textCursor()
        if not c.hasSelection(): c.select(QTextCursor.BlockUnderCursor)
        t=c.selectedText().replace('\u2029','\n')
        seen=set(); lines=[]
        for l in t.split('\n'):
            if l not in seen: seen.add(l); lines.append(l)
        c.insertText('\n'.join(lines))
    def _remove_blank_lines(self):
        c=self.editor.textCursor()
        if not c.hasSelection(): c.select(QTextCursor.Document)
        t=c.selectedText().replace('\u2029','\n')
        c.insertText('\n'.join(l for l in t.split('\n') if l.strip()))
    def _open_find_replace(self):
        self._frb.setVisible(True); self.code_find_edit.setFocus(); self.code_find_edit.selectAll()
    def _close_find_replace(self):
        self._frb.setVisible(False); self.editor.setFocus()
    def _find_next(self):
        t=self.code_find_edit.text()
        if not t: return
        if self.regex_btn.isChecked():
            try:
                opts=QRegularExpression.CaseInsensitiveOption if not self.case_btn.isChecked() else QRegularExpression.NoPatternOption
                pat=QRegularExpression(t,opts)
                if not pat.isValid(): return
                c=self.editor.textCursor(); m=pat.match(self.editor.toPlainText(),c.selectionEnd())
                if m.hasMatch():
                    c.setPosition(m.capturedStart(0)); c.setPosition(m.capturedEnd(0),QTextCursor.KeepAnchor)
                    self.editor.setTextCursor(c)
            except: pass
        else:
            flags=QTextCursor.FindFlag(0)
            if self.case_btn.isChecked(): flags|=QTextCursor.FindCaseSensitively
            self.editor.find(t,flags)
    def _replace_one(self):
        ft=self.code_find_edit.text(); rt=self.code_replace_edit.text()
        if not ft: return
        c=self.editor.textCursor()
        if c.hasSelection() and c.selectedText()==ft: c.insertText(rt)
        self._find_next()
    def _replace_all(self):
        ft=self.code_find_edit.text(); rt=self.code_replace_edit.text()
        if not ft: return
        self.editor.setPlainText(self.editor.toPlainText().replace(ft,rt))
        self._update_find_count()
    def _update_find_count(self):
        ft=self.code_find_edit.text()
        if not ft: self.match_count_lbl.setText("0/0"); return
        full=self.editor.toPlainText()
        if self.regex_btn.isChecked():
            try:
                opts=QRegularExpression.CaseInsensitiveOption if not self.case_btn.isChecked() else QRegularExpression.NoPatternOption
                pat=QRegularExpression(ft,opts)
                if not pat.isValid(): self.match_count_lbl.setText("?"); return
                count=0; it=pat.globalMatch(full)
                while it.hasNext(): it.next(); count+=1
                self.match_count_lbl.setText(f"{count} matches")
            except: self.match_count_lbl.setText("?")
        else:
            count=full.count(ft) if self.case_btn.isChecked() else full.lower().count(ft.lower())
            self.match_count_lbl.setText(f"{count} matches")
    def go_to_line_dialog(self):
        ml=self.editor.blockCount()
        dlg=QInputDialog(self); dlg.setWindowTitle("Go to Line")
        dlg.setLabelText(f"Line number (1 - {ml}):")
        dlg.setIntMinimum(1); dlg.setIntMaximum(ml)
        if dlg.exec()==QDialog.Accepted:
            ln=dlg.intValue(); b=self.editor.document().findBlockByNumber(ln-1)
            if b.isValid():
                c=self.editor.textCursor(); c.setPosition(b.position())
                self.editor.setTextCursor(c); self.editor.setFocus()
    def _update_cursor_pos(self):
        c=self.editor.textCursor(); ln=c.blockNumber()+1; col=c.columnNumber()+1
        self.cursor_lbl.setText(f"Ln {ln}, Col {col}")
        if c.hasSelection():
            st=c.selectedText(); ch=len(st); w=len(st.split())
            self.selection_lbl.setText(f"🎯 {ch} chars · {w} words")
        else: self.selection_lbl.setText("")
        text=self.editor.toPlainText()
        self.word_count_lbl.setText(f"{len(text.split())} words · {len(text)} chars")
    def _update_status(self):
        if self.current_file: self.file_lbl.setText(f"📄 {self.current_file.name}  —  {self.current_file.parent}")
        else: self.file_lbl.setText("📄 (unsaved)")
        self.mod_lbl.setText("● Modified" if self._modified else "✓ Saved")
        self.mod_lbl.setStyleSheet("color:#ffd700;font-size:12px;" if self._modified else "color:#4ec9b0;font-size:12px;")
        self._update_cursor_pos()
    def check_save_before_close(self):
        if not self._modified: return True
        r=QMessageBox.question(self,"Unsaved Changes","Save before closing?",QMessageBox.Save|QMessageBox.Discard|QMessageBox.Cancel)
        if r==QMessageBox.Save: return self._save_file()
        elif r==QMessageBox.Discard: return True
        return False

# ======================================================================
class HTMLViewer(QMainWindow):
    HIDE_CURSOR_MS=2500; MAX_RECENT_FILES=10
    def __init__(self,input_dir=INPUT_DIR):
        super().__init__()
        log_app.info("HTMLViewer.__init__ input_dir=%s",input_dir)
        self.setWindowTitle("HTML Viewer & Editor"); self.resize(1400,900)
        self.input_dir=Path(input_dir); self._is_full_screen=False
        self._previous_geometry=None; self._previous_state=None
        self._current_path=None; self._recent_files=[]
        self._task_mgr=TaskManager(self); self._playwright_pool=PlaywrightPool()
        self._jpg_worker=None; self._install_worker=None
        self._cursor_hide_timer=QTimer(self); self._cursor_hide_timer.setSingleShot(True)
        self._cursor_hide_timer.setInterval(self.HIDE_CURSOR_MS)
        self._cursor_hide_timer.timeout.connect(self._hide_cursor)
        self._transparent_cursor=_make_transparent_cursor()
        self._build_ui(); self._wire_shortcuts(); self._ensure_input_dir()
        self._setup_watcher(); self._load_settings()
        self._refresh_file_list(initial=True); self._populate_recent_menu()
        self._cursor_filter=CursorHideFilter(self)
        QApplication.instance().installEventFilter(self._cursor_filter)
        self._load_home(); self._on_tab_changed(0)
        log_app.info("HTMLViewer initialised — %d recent files",len(self._recent_files))
    def _build_ui(self):
        self.tabs=QTabWidget(); self.tabs.setDocumentMode(True); self.tabs.setMovable(False)
        self.setCentralWidget(self.tabs)
        # Viewer tab
        vw=QWidget(); vl=QVBoxLayout(vw); vl.setContentsMargins(0,0,0,0); vl.setSpacing(0)
        self.web_view=QWebEngineView(); prof=QWebEngineProfile.defaultProfile()
        self.page=FullScreenWebPage(prof,self.web_view); self.web_view.setPage(self.page)
        s=self.web_view.settings()
        for attr in[QWebEngineSettings.FullScreenSupportEnabled,QWebEngineSettings.JavascriptEnabled,QWebEngineSettings.LocalContentCanAccessFileUrls,QWebEngineSettings.LocalContentCanAccessRemoteUrls,QWebEngineSettings.PluginsEnabled,QWebEngineSettings.LocalStorageEnabled,QWebEngineSettings.AutoLoadImages,QWebEngineSettings.ScrollAnimatorEnabled,QWebEngineSettings.SpatialNavigationEnabled]:
            s.setAttribute(attr,True)
        s.setAttribute(QWebEngineSettings.AllowRunningInsecureContent,False)
        s.setAttribute(QWebEngineSettings.AllowWindowActivationFromJavaScript,False)
        self.web_view.loadFinished.connect(self._on_load_finished)
        self.web_view.titleChanged.connect(self._on_title_changed)
        self.web_view.urlChanged.connect(self._on_url_changed)
        self.web_view.renderProcessTerminated.connect(self._on_render_crash)
        self._build_toolbar(); vl.addWidget(self.toolbar); vl.addWidget(self.web_view,1)
        self._build_find_bar(); vl.addWidget(self._find_bar); self._find_bar.setVisible(False)
        self.tabs.addTab(vw,"🔍  Viewer")
        # Editor tab
        self.editor=HTMLEditor(self); self.tabs.addTab(self.editor,"✏️  Editor")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        # File explorer dock
        self.file_dock=QDockWidget("Explorer",self); self.file_dock.setObjectName("FileExplorerDock")
        self.file_dock.setAllowedAreas(Qt.LeftDockWidgetArea|Qt.RightDockWidgetArea)
        self.tree_view=QTreeView(); self.tree_view.setHeaderHidden(True)
        self.tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self._show_tree_context_menu)
        self.file_model=QFileSystemModel(); self.file_model.setRootPath(str(self.input_dir))
        self.proxy_model=FileTreeProxyModel(); self.proxy_model.setSourceModel(self.file_model)
        self.tree_view.setModel(self.proxy_model)
        self.tree_view.setRootIndex(self.proxy_model.mapFromSource(self.file_model.index(str(self.input_dir))))
        for i in range(1,4): self.tree_view.hideColumn(i)
        self.tree_view.doubleClicked.connect(self._on_tree_double_click)
        self.file_dock.setWidget(self.tree_view); self.addDockWidget(Qt.LeftDockWidgetArea,self.file_dock)
        # Preview dock
        self.preview_dock=QDockWidget("Live Preview",self); self.preview_dock.setObjectName("LivePreviewDock")
        self.preview_dock.setAllowedAreas(Qt.AllDockWidgetAreas)
        pc=QWidget(); pl=QVBoxLayout(pc); pl.setContentsMargins(0,0,0,0); pl.setSpacing(0)
        ptb=QToolBar(); ptb.setMovable(False); ptb.setObjectName("PreviewToolBar")
        ptb.addWidget(QLabel(" Viewport: "))
        for lab,tip,w in[("📱","Mobile (375px)",375),("📐","Tablet (768px)",768),("💻","Desktop (1280px)",1280),("🖥️","Full HD (1920px)",1920),("🔃","Auto",-1)]:
            a=QAction(lab,self); a.setToolTip(tip)
            a.triggered.connect(lambda _=False,wv=w:self._set_preview_viewport(wv)); ptb.addAction(a)
        ptb.addSeparator()
        ra=QAction("🔄 Refresh",self); ra.triggered.connect(self.editor._prepare_update_preview); ptb.addAction(ra)
        pl.addWidget(ptb); pl.addWidget(self.editor.preview)
        self.preview_dock.setWidget(pc); self.addDockWidget(Qt.RightDockWidgetArea,self.preview_dock)
        # Console dock
        self.console_dock=QDockWidget("Console",self); self.console_dock.setObjectName("ConsoleDock")
        self.console_dock.setAllowedAreas(Qt.AllDockWidgetAreas)
        cw=QWidget(); cl=QVBoxLayout(cw); cl.setContentsMargins(0,0,0,0); cl.setSpacing(0)
        cbar=QToolBar(); cbar.setMovable(False); cbar.setObjectName("ConsoleToolBar")
        cbar.addWidget(QLabel(" Console: "))
        ca=QAction("Clear",self); ca.triggered.connect(lambda:self.editor.console.clear()); cbar.addAction(ca)
        cl.addWidget(cbar); cl.addWidget(self.editor.console)
        self.console_dock.setWidget(cw); self.addDockWidget(Qt.BottomDockWidgetArea,self.console_dock)
        # Log viewer dock
        self.log_dock=LogViewerDock(self); self.addDockWidget(Qt.BottomDockWidgetArea,self.log_dock); self.log_dock.setVisible(False)
        self._build_menubar(); self._build_statusbar()
        self.setAcceptDrops(True); self.web_view.setAcceptDrops(False)
    def _show_tree_context_menu(self,pos):
        pi=self.tree_view.indexAt(pos)
        si=self.proxy_model.mapToSource(pi) if pi.isValid() else None
        m=QMenu(self)
        nf=m.addAction("📄 New File"); nd=m.addAction("📁 New Folder"); m.addSeparator()
        ov=oe=rn=dl=cp=None; path=None
        if si and si.isValid():
            path=self.file_model.filePath(si)
            if os.path.isfile(path) and path.lower().endswith((".html",".htm",".xhtml")):
                ov=m.addAction("👁 Open in Viewer"); oe=m.addAction("✏️ Open in Editor"); m.addSeparator()
            cp=m.addAction("📋 Copy Path"); rn=m.addAction("✏️ Rename"); dl=m.addAction("🗑️ Delete")
        a=m.exec_(self.tree_view.viewport().mapToGlobal(pos))
        if not a: return
        if a==nf:
            fp,ok=QInputDialog.getText(self,"New File","File name:")
            if ok and fp:
                try:(self.input_dir/fp).touch()
                except OSError as e: QMessageBox.warning(self,"Error",str(e))
        elif a==nd:
            dp,ok=QInputDialog.getText(self,"New Folder","Folder name:")
            if ok and dp:
                try:(self.input_dir/dp).mkdir()
                except OSError as e: QMessageBox.warning(self,"Error",str(e))
        elif a==rn and path:
            nn,ok=QInputDialog.getText(self,"Rename","New name:",text=os.path.basename(path))
            if ok and nn:
                try: os.rename(path,os.path.join(os.path.dirname(path),nn))
                except OSError as e: QMessageBox.warning(self,"Error",str(e))
        elif a==dl and path:
            r=QMessageBox.question(self,"Delete",f"Delete:\n{path}?",QMessageBox.Yes|QMessageBox.No)
            if r==QMessageBox.Yes:
                try:
                    if os.path.isdir(path): os.rmdir(path)
                    else: os.remove(path)
                except OSError as e: QMessageBox.warning(self,"Error",str(e))
        elif a==cp and path: QApplication.clipboard().setText(path); self._notify(f"Copied: {path}")
        elif a==ov and path: self.tabs.setCurrentIndex(0); self._load_file(Path(path))
        elif a==oe and path: self.tabs.setCurrentIndex(1); self.editor.load_file(Path(path))
    def _on_tree_double_click(self,pi):
        si=self.proxy_model.mapToSource(pi); path=self.file_model.filePath(si)
        if path.lower().endswith((".html",".htm",".xhtml")): self._load_file(Path(path))
    def _build_toolbar(self):
        tb=QToolBar("Main"); tb.setMovable(False); tb.setObjectName("MainToolBar"); self.toolbar=tb
        self.back_act=QAction("◀ Back",self); self.back_act.triggered.connect(self._back); tb.addAction(self.back_act)
        self.fwd_act=QAction("Forward ▶",self); self.fwd_act.triggered.connect(self._forward); tb.addAction(self.fwd_act)
        tb.addSeparator()
        self.refresh_act=QAction("Refresh list",self); self.refresh_act.triggered.connect(self._refresh_file_list); tb.addAction(self.refresh_act)
        self.reload_act=QAction("Reload",self); self.reload_act.triggered.connect(self._reload); tb.addAction(self.reload_act)
        tb.addSeparator()
        self.zoom_out_act=QAction("Zoom −",self); self.zoom_out_act.triggered.connect(self._context_zoom_out); tb.addAction(self.zoom_out_act)
        self.zoom_pct_lbl=QLabel("100%"); self.zoom_pct_lbl.setMinimumWidth(48); self.zoom_pct_lbl.setAlignment(Qt.AlignCenter); tb.addWidget(self.zoom_pct_lbl)
        self.zoom_in_act=QAction("Zoom +",self); self.zoom_in_act.triggered.connect(self._context_zoom_in); tb.addAction(self.zoom_in_act)
        tb.addSeparator()
        self.fullscreen_act=QAction("Full Screen",self); self.fullscreen_act.triggered.connect(self.toggle_full_screen); tb.addAction(self.fullscreen_act)
        tb.addSeparator()
        self.find_act_tb=QAction("Find…",self); self.find_act_tb.triggered.connect(self._open_find); tb.addAction(self.find_act_tb)
        tb.addSeparator()
        self.edit_current_act=QAction("✏️ Edit Current",self); self.edit_current_act.triggered.connect(self._edit_current_file); tb.addAction(self.edit_current_act)
        self.open_browser_act=QAction("Open in Browser",self); self.open_browser_act.triggered.connect(self._open_in_browser); tb.addAction(self.open_browser_act)
        self.open_folder_act=QAction("Open Folder",self); self.open_folder_act.triggered.connect(self._open_input_folder); tb.addAction(self.open_folder_act)
        tb.addSeparator()
        self.save_jpg_act=QAction("📷 Save JPG",self); self.save_jpg_act.setToolTip("Save as JPG (Ctrl+Shift+J)"); self.save_jpg_act.triggered.connect(self._save_as_jpg); tb.addAction(self.save_jpg_act)
    def _build_find_bar(self):
        bar=QFrame(); bar.setObjectName("FindBar"); bar.setFrameShape(QFrame.StyledPanel)
        lay=QHBoxLayout(bar); lay.setContentsMargins(8,4,8,4); lay.setSpacing(6)
        lay.addWidget(QLabel("Find:")); self.find_edit=QLineEdit(); self.find_edit.setPlaceholderText("Search in page…")
        self.find_edit.setClearButtonEnabled(True); self.find_edit.textChanged.connect(self._find_text_changed)
        self.find_edit.returnPressed.connect(self._find_next); lay.addWidget(self.find_edit,1)
        lay.addWidget(QPushButton("◀ Prev",clicked=self._find_prev)); lay.addWidget(QPushButton("Next ▶",clicked=self._find_next))
        lay.addWidget(QPushButton("✕",clicked=self._close_find)); self._find_bar=bar
    def _build_menubar(self):
        mb=self.menuBar()
        fm=mb.addMenu("&File")
        fm.addAction("Open File…",self._open_file_dialog,"Ctrl+O")
        fm.addAction("New HTML File…",self._new_html_file,"Ctrl+N")
        fm.addAction("Save File",self._editor_save,"Ctrl+S")
        fm.addAction("Save File As…",self._editor_save_as,"Ctrl+Shift+S")
        fm.addAction("Save as JPG…",self._save_as_jpg,"Ctrl+Shift+J")
        fm.addAction("Quick Open…",self._quick_open,"Ctrl+P")
        fm.addSeparator()
        fm.addAction("Open Input Folder",self._open_input_folder)
        fm.addAction("Open in Browser",self._open_in_browser)
        fm.addSeparator()
        self._recent_menu=fm.addMenu("Recent Files"); fm.addSeparator()
        fm.addAction("Reload",self._reload,"F5")
        fm.addAction("Hard Reload (no cache)",self._hard_reload,"Ctrl+Shift+R")
        fm.addSeparator()
        fm.addAction("Print…",self._print_page,"Ctrl+Shift+P"); fm.addSeparator()
        fm.addAction("Quit",self.close,"Ctrl+Q")
        em=mb.addMenu("&Edit")
        em.addAction("Editor: New File",self.editor._new_file)
        em.addAction("Editor: Open File",self.editor._open_file)
        em.addAction("Editor: Save",self._editor_save)
        em.addAction("Editor: Save As",self._editor_save_as); em.addSeparator()
        em.addAction("Editor: Find/Replace",self.editor._open_find_replace)
        em.addAction("Editor: Go to Line…",self.editor.go_to_line_dialog,"Ctrl+G")
        em.addAction("Editor: Beautify HTML",self.editor._beautify,"Ctrl+Shift+B"); em.addSeparator()
        em.addAction("Editor: Toggle Comment",self.editor.editor.toggle_comment,"Ctrl+/")
        em.addAction("Editor: Duplicate Line",self.editor.editor.duplicate_line,"Ctrl+D")
        em.addAction("Editor: Delete Line",self.editor.editor.delete_line,"Ctrl+Shift+K")
        em.addAction("Editor: Move Line Up",lambda:self.editor.editor.move_line(-1),"Alt+Up")
        em.addAction("Editor: Move Line Down",lambda:self.editor.editor.move_line(1),"Alt+Down"); em.addSeparator()
        em.addAction("Editor: Sort Lines",self.editor._sort_lines)
        em.addAction("Editor: Remove Duplicates",self.editor._dedupe_lines)
        em.addAction("Editor: Remove Blank Lines",self.editor._remove_blank_lines); em.addSeparator()
        em.addAction("Editor: Insert Lorem Ipsum",lambda:self.editor._insert_lorem(1))
        em.addAction("Editor: Insert Timestamp",self.editor._insert_timestamp)
        em.addAction("Editor: Encode Image as Base64",self.editor._encode_image_base64); em.addSeparator()
        em.addAction("Editor: Apply Preview",self.editor._prepare_update_preview)
        em.addAction("Editor: Toggle Auto-Preview",lambda:self.editor.auto_preview_act.toggle())
        em.addAction("Editor: Toggle Auto-Save",lambda:self.editor.auto_save_act.toggle())
        em.addAction("Editor: Toggle Word Wrap",lambda:self.editor.word_wrap_act.toggle()); em.addSeparator()
        ent_m=em.addMenu("Insert HTML Entity")
        for ent,desc in HTML_ENTITIES.items():
            ent_m.addAction(f"{ent}  ({desc})",lambda _=False,e=ent:self.editor._insert_text(e))
        tpl_m=em.addMenu("Insert Template")
        for n in HTMLEditor.TEMPLATES: tpl_m.addAction(n,lambda _=False,n2=n:self.editor._insert_template(n2))
        vm=mb.addMenu("&View")
        vm.addAction("Switch to Viewer Tab",lambda:self.tabs.setCurrentIndex(0),"Alt+1")
        vm.addAction("Switch to Editor Tab",lambda:self.tabs.setCurrentIndex(1),"Alt+2"); vm.addSeparator()
        vm.addAction("Zoom In",self._context_zoom_in,"Ctrl+=")
        vm.addAction("Zoom Out",self._context_zoom_out,"Ctrl+-")
        vm.addAction("Reset Zoom",self._zoom_reset,"Ctrl+0"); vm.addSeparator()
        vm.addAction("Full Screen",self.toggle_full_screen,"F11"); vm.addSeparator()
        vm.addAction("Find in Page…",self._open_find)
        vm.addAction("Scroll to Top",self._scroll_top,"Home")
        vm.addAction("Scroll to Bottom",self._scroll_bottom,"End"); vm.addSeparator()
        vm.addAction(self.file_dock.toggleViewAction())
        vm.addAction(self.preview_dock.toggleViewAction())
        vm.addAction(self.console_dock.toggleViewAction())
        vm.addAction(self.log_dock.toggleViewAction()); vm.addSeparator()
        vm.addAction("Open DevTools",self.open_devtools,"Ctrl+Shift+I")
        gm=mb.addMenu("&Go")
        gm.addAction("Back",self._back,"Alt+Left"); gm.addAction("Forward",self._forward,"Alt+Right")
        hm=mb.addMenu("&Help"); hm.addAction("About",self._show_about)
    def _build_statusbar(self):
        sb=self.statusBar()
        self.path_lbl=QLabel("No file loaded"); self.path_lbl.setStyleSheet("padding:0 6px;"); sb.addWidget(self.path_lbl,1)
        self.size_lbl=QLabel(""); self.size_lbl.setStyleSheet("padding:0 6px;color:#ddd;"); sb.addPermanentWidget(self.size_lbl)
        self.zoom_status_lbl=QLabel("100%"); self.zoom_status_lbl.setStyleSheet("padding:0 6px;color:#ddd;"); sb.addPermanentWidget(self.zoom_status_lbl)
    def _wire_shortcuts(self):
        QShortcut(QKeySequence("Escape"),self,activated=self._on_escape)
        QShortcut(QKeySequence("Ctrl+R"),self,activated=self._reload)
        QShortcut(QKeySequence("Ctrl+L"),self,activated=self._refresh_file_list)
        QShortcut(QKeySequence("Ctrl+F"),self,activated=self._context_find)
        QShortcut(QKeySequence("Ctrl++"),self,activated=self._context_zoom_in)
        QShortcut(QKeySequence("F3"),self,activated=self._context_find_next)
        QShortcut(QKeySequence("Shift+F3"),self,activated=self._context_find_prev)
    def _context_find_next(self):
        if self.tabs.currentIndex()==0: self._find_next()
        else: self.editor._find_next()
    def _context_find_prev(self):
        if self.tabs.currentIndex()==0: self._find_prev()
        else: self.editor._find_next()
    def open_devtools(self):
        tp=self.web_view.page() if self.tabs.currentIndex()==0 else self.editor.preview.page()
        log_viewer.info("Opening DevTools")
        self.dev_window=QMainWindow(self); self.dev_window.setWindowTitle("Developer Tools")
        self.dev_window.resize(900,600); dv=QWebEngineView(); self.dev_window.setCentralWidget(dv)
        dv.page().setInspectedPage(tp); self.dev_window.show()
    def _context_zoom_in(self):
        if self.tabs.currentIndex()==0: self._zoom_in()
        else: self.editor._setup_editor_font(self.editor.editor.font().pointSize()+1)
    def _context_zoom_out(self):
        if self.tabs.currentIndex()==0: self._zoom_out()
        else:
            f=self.editor.editor.font()
            if f.pointSize()>6: self.editor._setup_editor_font(f.pointSize()-1)
    def _context_find(self):
        if self.tabs.currentIndex()==0: self._open_find()
        else: self.editor._open_find_replace()
    def _on_tab_changed(self,idx):
        log_viewer.debug("Tab → %s",("Viewer" if idx==0 else "Editor"))
        self.toolbar.setVisible(idx==0); self.file_dock.setVisible(True)
        self.preview_dock.setVisible(idx==1); self.console_dock.setVisible(idx==1)
        if idx==1: self.editor._update_cursor_pos()
    def _edit_current_file(self):
        if not self._current_path: self._notify("No file loaded."); return
        self.tabs.setCurrentIndex(1); self.editor.load_file(Path(self._current_path))
    def _new_html_file(self): self.tabs.setCurrentIndex(1); self.editor._new_file()
    def _editor_save(self): self.tabs.setCurrentIndex(1); self.editor._save_file()
    def _editor_save_as(self): self.tabs.setCurrentIndex(1); self.editor._save_as()
    def _ensure_input_dir(self):
        if not self.input_dir.exists():
            try: self.input_dir.mkdir(parents=True,exist_ok=True)
            except OSError as e: self._notify(f"Could not create input folder: {e}")
    def _list_html_files(self):
        if not self.input_dir.exists(): return[]
        exts=(".html",".htm",".xhtml")
        return sorted((p for p in self.input_dir.iterdir() if p.is_file() and p.suffix.lower() in exts),key=lambda p:p.name.lower())
    def _refresh_file_list(self,initial=False):
        self.tree_view.setRootIndex(self.proxy_model.mapFromSource(self.file_model.index(str(self.input_dir))))
        self._notify(f"Watching {self.input_dir}")
    def _setup_watcher(self):
        self._watcher=QFileSystemWatcher(self)
        if self.input_dir.exists(): self._watcher.addPath(str(self.input_dir))
        self._watcher.directoryChanged.connect(lambda _: QTimer.singleShot(50,self._refresh_file_list))
    def _load_file(self,path):
        if not path.exists(): log_viewer.warning("Not found: %s",path); self._notify(f"File not found: {path}"); return
        self._current_path=str(path.absolute()); log_viewer.info("Loading: %s",path.name)
        self.web_view.setUrl(QUrl.fromLocalFile(self._current_path))
        self._update_status(path); self._add_recent(self._current_path)
    def _load_home(self):
        self.web_view.setHtml(HOME_PAGE_HTML,QUrl("about:blank"))
        self._current_path=None; self.path_lbl.setText("No file loaded")
        self.size_lbl.setText(""); self.setWindowTitle("HTML Viewer & Editor")
    def _on_load_finished(self,ok):
        if not ok: log_viewer.error("Page load FAILED: %s",self._current_path); return
        log_viewer.debug("Page loaded OK: %s",self._current_path)
        css=FORCE_FILL_CSS.replace("\n"," "); js=FORCE_FILL_JS_TEMPLATE.format(css=css)
        self.web_view.page().runJavaScript(js); self._update_nav_actions()
    def _on_title_changed(self,title):
        if title: self.setWindowTitle(f"HTML Viewer & Editor — {title}")
        elif self._current_path: self.setWindowTitle(f"HTML Viewer & Editor — {Path(self._current_path).name}")
    def _on_url_changed(self,_url): self._update_nav_actions()
    def _on_render_crash(self,st,co):
        log_viewer.error("Render CRASH — status=%s code=%s",st,co)
        self._notify("Render process crashed — reloading…"); QTimer.singleShot(500,self._reload)
    def _back(self):
        if self.web_view.history().canGoBack(): self.web_view.back()
    def _forward(self):
        if self.web_view.history().canGoForward(): self.web_view.forward()
    def _update_nav_actions(self):
        h=self.web_view.history(); self.back_act.setEnabled(h.canGoBack()); self.fwd_act.setEnabled(h.canGoForward())
    def _reload(self): log_viewer.debug("Reload"); self.web_view.reload()
    def _hard_reload(self):
        if self._current_path: self.web_view.page().action(QWebEnginePage.ReloadAndBypassCache).trigger()
        else: self._reload()
    def _zoom_in(self):
        z=min(5.0,self.web_view.zoomFactor()+0.1); self.web_view.setZoomFactor(z); self._update_zoom_label()
    def _zoom_out(self):
        z=max(0.2,self.web_view.zoomFactor()-0.1); self.web_view.setZoomFactor(z); self._update_zoom_label()
    def _zoom_reset(self):
        if self.tabs.currentIndex()==0: self.web_view.setZoomFactor(1.0); self._update_zoom_label()
        else: self.editor._setup_editor_font(10)
    def _update_zoom_label(self):
        pct=int(round(self.web_view.zoomFactor()*100)); t=f"{pct}%"
        self.zoom_pct_lbl.setText(t); self.zoom_status_lbl.setText(t)
    def _set_preview_viewport(self,w):
        if w<=0: js="document.documentElement.style.width='';document.body.style.width='';"
        else: js=f"document.documentElement.style.width='{w}px';document.body.style.width='{w}px';"
        self.editor.preview.page().runJavaScript(js)
    def _open_find(self):
        if self.tabs.currentIndex()!=0: self.tabs.setCurrentIndex(0)
        self._find_bar.setVisible(True); self.find_edit.setFocus(); self.find_edit.selectAll()
    def _close_find(self):
        self._find_bar.setVisible(False); self.web_view.page().findText(""); self.web_view.setFocus()
    def _find_text_changed(self,t): self.web_view.page().findText(t)
    def _find_next(self): self.web_view.page().findText(self.find_edit.text())
    def _find_prev(self): self.web_view.page().findText(self.find_edit.text(),QWebEnginePage.FindBackward)
    def _scroll_top(self): self.web_view.page().runJavaScript("window.scrollTo(0,0);")
    def _scroll_bottom(self): self.web_view.page().runJavaScript("window.scrollTo(0,document.body.scrollHeight);")
    def _print_page(self):
        printer=QPrinter(); dlg=QPrintDialog(printer,self); dlg.setWindowTitle("Print HTML Document")
        if dlg.exec()==QPrintDialog.Accepted: self.web_view.page().print(printer,lambda ok:None)
    def _quick_open(self): log_viewer.info("Quick Open"); QuickOpenDialog(self,self).exec()
    def _save_as_jpg(self):
        log_jpg.info("=== Save as JPG started ===")
        if self._task_mgr.is_running("jpg_export"):
            log_jpg.warning("JPG already running"); QMessageBox.information(self,"Busy","A JPG export is already running."); return
        use_file=False; source_path=None; html_content=None; source_name="untitled"
        if self.tabs.currentIndex()==0:
            if not self._current_path: QMessageBox.information(self,"No Page","No file loaded."); return
            source_path=Path(self._current_path); source_name=source_path.stem; use_file=True
        else:
            html_content=self.editor.editor.toPlainText()
            if not html_content.strip(): QMessageBox.information(self,"No Content","Editor is empty."); return
            source_name=self.editor.current_file.stem if self.editor.current_file else "untitled"
            if self.editor.current_file and self.editor.current_file.exists() and not self.editor._modified:
                source_path=self.editor.current_file; use_file=True
        default_name=f"{source_name}.jpg"
        path,_=QFileDialog.getSaveFileName(self,"Save as JPG",str(self.input_dir/default_name),"JPEG Image (*.jpg *.jpeg);;All files (*.*)")
        if not path: return
        dlg=QDialog(self); dlg.setWindowTitle("JPG Options"); dlg.setMinimumWidth(300)
        dlg.setStyleSheet("QDialog{background:#2d2d2d;color:#d4d4d4;}QLabel{color:#d4d4d4;}QComboBox{background:#3a3d41;color:white;border:1px solid #1e1e1e;padding:4px;border-radius:3px;}QPushButton{background:#3a3d41;color:white;border:1px solid #1e1e1e;padding:6px 16px;border-radius:3px;}QPushButton:hover{background:#4e5256;}")
        dl=QVBoxLayout(dlg); dl.setSpacing(10); dl.setContentsMargins(12,12,12,12)
        mr=QHBoxLayout(); mr.addWidget(QLabel("Mode:")); mc=QComboBox(); mc.addItems(["Full page","Visible viewport"]); mr.addWidget(mc,1); dl.addLayout(mr)
        qr=QHBoxLayout(); qr.addWidget(QLabel("Quality:")); qc=QComboBox()
        for q in[100,95,90,85,80,70,50]: qc.addItem(f"{q}%",q)
        qc.setCurrentIndex(2); qr.addWidget(qc,1); dl.addLayout(qr)
        wr=QHBoxLayout(); wr.addWidget(QLabel("Width:")); wc=QComboBox()
        for lab,val in[("375 (Mobile)",375),("768 (Tablet)",768),("1280 (HD)",1280),("1920 (Full HD)",1920),("2560 (QHD)",2560)]: wc.addItem(lab,val)
        wc.setCurrentIndex(3); wr.addWidget(wc,1); dl.addLayout(wr)
        br=QHBoxLayout(); br.addStretch(); br.addWidget(QPushButton("Save",clicked=dlg.accept)); br.addWidget(QPushButton("Cancel",clicked=dlg.reject)); dl.addLayout(br)
        if dlg.exec()==QDialog.Rejected: return
        full_page=(mc.currentIndex()==0); quality=qc.currentData(); viewport_width=wc.currentData()
        log_jpg.info("Options: full_page=%s quality=%d width=%d",full_page,quality,viewport_width)
        if not use_file and self.editor.current_file: temp_dir=self.editor.current_file.parent
        else: self._ensure_input_dir(); temp_dir=self.input_dir
        self._jpg_worker=JPGExportWorker(str(source_path) if use_file else None,html_content if not use_file else None,path,full_page,quality,viewport_width,self._playwright_pool,temp_dir,source_name,self)
        self._task_mgr.register("jpg_export",self._jpg_worker)
        self._jpg_worker.progress.connect(self._on_jpg_progress)
        self._jpg_worker.finished_result.connect(self._on_jpg_finished)
        self._jpg_progress=QProgressDialog("Starting…","Cancel",0,100,self)
        self._jpg_progress.setWindowModality(Qt.WindowModal); self._jpg_progress.setWindowTitle("Save as JPG")
        self._jpg_progress.setMinimumDuration(0); self._jpg_progress.setAutoClose(False)
        self._jpg_progress.setAutoReset(False); self._jpg_progress.canceled.connect(self._on_jpg_cancel)
        self._jpg_progress.show(); self._jpg_worker.start(); log_jpg.info("Worker started")
    def _on_jpg_progress(self,pct,msg):
        self._jpg_progress.setLabelText(msg); self._jpg_progress.setValue(pct)
        log_jpg.debug("Progress: %d%% — %s",pct,msg)
    def _on_jpg_cancel(self):
        log_jpg.info("User cancelled JPG"); self._task_mgr.cancel("jpg_export")
    def _on_jpg_finished(self,success,info):
        self._jpg_progress.close()
        if success: log_jpg.info("=== JPG saved: %s ===",info); self._notify(f"Saved JPG: {Path(info).name}")
        else:
            if info=="IMPORT_ERROR":
                r=QMessageBox.question(self,"Playwright Not Installed","Install now?",QMessageBox.Yes|QMessageBox.No)
                if r==QMessageBox.Yes: self._install_playwright()
            elif info=="CANCELLED": log_jpg.info("JPG cancelled"); self._notify("JPG export cancelled")
            else: log_jpg.error("JPG failed: %s",info); QMessageBox.warning(self,"Save Error",f"Failed:\n{info}")
        if self._jpg_worker: self._jpg_worker.deleteLater(); self._jpg_worker=None
    def _install_playwright(self):
        if self._task_mgr.is_running("pw_install"): return
        log_playw.info("Installing Playwright…")
        self._install_worker=PlaywrightInstallerWorker(False,self)
        self._task_mgr.register("pw_install",self._install_worker)
        self._install_progress=QProgressDialog("Installing Playwright…","Cancel",0,100,self)
        self._install_progress.setWindowModality(Qt.WindowModal); self._install_progress.setWindowTitle("Installing")
        self._install_progress.setMinimumDuration(0); self._install_progress.setAutoClose(False); self._install_progress.setAutoReset(False)
        self._install_progress.canceled.connect(lambda:self._task_mgr.cancel("pw_install")); self._install_progress.show()
        self._install_worker.progress.connect(lambda p,m:(self._install_progress.setValue(p),self._install_progress.setLabelText(m)))
        self._install_worker.finished_result.connect(self._on_playwright_installed)
        self._install_worker.start()
    def _on_playwright_installed(self,success,error):
        self._install_progress.close()
        if self._install_worker: self._install_worker.deleteLater(); self._install_worker=None
        if success: log_playw.info("Playwright installed"); QMessageBox.information(self,"Success","Playwright + Chromium installed!\n\nUse Save as JPG (Ctrl+Shift+J).")
        else: log_playw.error("Install failed: %s",error); QMessageBox.warning(self,"Install Error",f"Failed:\n{error}\n\nManual:\n  pip install playwright\n  playwright install chromium")
    def toggle_full_screen(self):
        if self._is_full_screen: self.exit_full_screen()
        else: self.enter_full_screen()
    def enter_full_screen(self):
        if self._is_full_screen: return
        log_viewer.info("→ Enter fullscreen")
        self._previous_geometry=self.saveGeometry(); self._previous_state=self.saveState()
        self._is_full_screen=True; self.toolbar.setVisible(False)
        if hasattr(self,'editor'): self.editor.etb.setVisible(False); self.editor.sb.setVisible(False); self.editor._frb.setVisible(False)
        self.menuBar().setVisible(False); self.statusBar().setVisible(False); self._find_bar.setVisible(False)
        self.tabs.tabBar().setVisible(False); self.file_dock.setVisible(False)
        self.preview_dock.setVisible(False); self.console_dock.setVisible(False); self.log_dock.setVisible(False)
        self.showFullScreen(); self._cursor_hide_timer.start()
    def exit_full_screen(self):
        if not self._is_full_screen: return
        log_viewer.info("← Exit fullscreen")
        self._is_full_screen=False; self._cursor_hide_timer.stop(); QApplication.restoreOverrideCursor(); self.showNormal()
        self.menuBar().setVisible(True); self.statusBar().setVisible(True); self.tabs.tabBar().setVisible(True)
        self.toolbar.setVisible(self.tabs.currentIndex()==0); self.file_dock.setVisible(True)
        self.preview_dock.setVisible(self.tabs.currentIndex()==1); self.console_dock.setVisible(self.tabs.currentIndex()==1)
        if hasattr(self,'editor'): self.editor.etb.setVisible(True); self.editor.sb.setVisible(True)
        if self._previous_geometry is not None: self.restoreGeometry(self._previous_geometry); self._previous_geometry=None
        if self._previous_state is not None: self.restoreState(self._previous_state); self._previous_state=None
    def _hide_cursor(self):
        if self._is_full_screen: QApplication.setOverrideCursor(self._transparent_cursor)
    def _on_escape(self):
        if self._find_bar.isVisible(): self._close_find()
        elif hasattr(self,'editor') and self.editor._frb.isVisible(): self.editor._close_find_replace()
        elif self._is_full_screen: self.exit_full_screen()
    def _open_file_dialog(self):
        p,_=QFileDialog.getOpenFileName(self,"Open HTML file",str(self.input_dir),"HTML files (*.html *.htm *.xhtml);;All files (*.*)")
        if p: self.tabs.setCurrentIndex(0); self._load_file(Path(p))
    def _open_input_folder(self):
        self._ensure_input_dir(); QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.input_dir.resolve())))
    def _open_in_browser(self):
        if not self._current_path: self._notify("No file loaded."); return
        QDesktopServices.openUrl(QUrl.fromLocalFile(self._current_path))
    def _add_recent(self,path):
        if path in self._recent_files: self._recent_files.remove(path)
        self._recent_files.insert(0,path); del self._recent_files[self.MAX_RECENT_FILES:]
        self._populate_recent_menu()
    def _populate_recent_menu(self):
        self._recent_menu.clear()
        if not self._recent_files:
            a=self._recent_menu.addAction("(none)"); a.setEnabled(False); return
        for p in self._recent_files:
            lbl=Path(p).name; ac=self._recent_menu.addAction(lbl); ac.setToolTip(p)
            ac.triggered.connect(lambda _=False,pp=p:self._load_file(Path(pp)))
    def _load_settings(self):
        log_settings.info("Loading settings…")
        self._settings=QSettings(QSettings.IniFormat,QSettings.UserScope,"HTMLViewer","HTMLViewer")
        g=self._settings.value("geometry")
        if isinstance(g,(bytes,bytearray)) and not isinstance(g,str): self.restoreGeometry(QByteArray(g))
        st=self._settings.value("windowState")
        if isinstance(st,(bytes,bytearray)) and not isinstance(st,str): self.restoreState(QByteArray(st))
        r=self._settings.value("recentFiles") or[]
        if isinstance(r,list): self._recent_files=[x for x in r if isinstance(x,str) and Path(x).exists()]
        log_settings.info("  recent: %d",len(self._recent_files))
        last=self._settings.value("lastFile")
        if isinstance(last,str) and Path(last).exists():
            QTimer.singleShot(100,lambda:self._load_file(Path(last)))
        ef=self._settings.value("editorFile")
        if isinstance(ef,str) and Path(ef).exists():
            QTimer.singleShot(200,lambda:self.editor.load_file(Path(ef)))
        cp=self._settings.value("editorCursorPos")
        if isinstance(cp,int) and cp>=0: QTimer.singleShot(300,lambda:self._restore_editor_cursor(cp))
        sv=self._settings.value("editorScroll")
        if isinstance(sv,int) and sv>=0:
            QTimer.singleShot(350,lambda:self.editor.preview.page().runJavaScript(f"window.scrollTo(0,{sv});"))
        log_settings.info("Settings loaded")
    def _restore_editor_cursor(self,pos):
        c=self.editor.editor.textCursor(); c.setPosition(pos); self.editor.editor.setTextCursor(c)
    def _save_settings(self):
        log_settings.info("Saving settings…")
        s=self._settings
        if self._is_full_screen and self._previous_geometry is not None: s.setValue("geometry",bytes(self._previous_geometry))
        else: s.setValue("geometry",bytes(self.saveGeometry()))
        s.setValue("windowState",bytes(self.saveState())); s.setValue("recentFiles",self._recent_files)
        if self._current_path: s.setValue("lastFile",self._current_path)
        if self.editor.current_file: s.setValue("editorFile",str(self.editor.current_file))
        s.setValue("editorFontSize",self.editor.editor.font().pointSize())
        s.setValue("editorCursorPos",self.editor.editor.textCursor().position())
        log_settings.info("Settings saved")
    def _notify(self,msg): QTimer.singleShot(0,lambda:self.statusBar().showMessage(msg,4000))
    def _update_status(self,path):
        try:
            st=path.stat(); mt=datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")
            self.path_lbl.setText(f"{path.name}  ·  {path.parent}")
            self.size_lbl.setText(f"{_human_size(st.st_size)}  ·  modified {mt}")
        except OSError: self.path_lbl.setText(str(path)); self.size_lbl.setText("")
    def _show_about(self):
        QMessageBox.about(self,"About","<h3>HTML Viewer & Editor v9</h3><p>PySide6/QtWebEngine-based viewer and editor with Emmet, beautify, auto-pair tags, indent guides, bracket matching, color swatches, TODO highlight, selection occurrence, HTML entities, Lorem ipsum, base64 encoder, line ops, regex find/replace, auto-reload, Quick Open, responsive preview, JPG export via Playwright, comprehensive logging, TaskManager, PlaywrightPool, and LogViewerDock.</p>")
    def dragEnterEvent(self,ev):
        if ev.mimeData().hasUrls() and any(u.toLocalFile().lower().endswith((".html",".htm",".xhtml")) for u in ev.mimeData().urls()): ev.acceptProposedAction()
        else: ev.ignore()
    def dropEvent(self,ev):
        for u in ev.mimeData().urls():
            local=u.toLocalFile()
            if local.lower().endswith((".html",".htm",".xhtml")):
                if self.tabs.currentIndex()==1: self.editor.load_file(Path(local))
                else: self._load_file(Path(local))
                ev.acceptProposedAction(); return
        ev.ignore()
    def keyPressEvent(self,ev):
        if self._find_bar.isVisible() and self.find_edit.hasFocus():
            if ev.key() in(Qt.Key_Return,Qt.Key_Enter) and(ev.modifiers()&Qt.ShiftModifier): self._find_prev(); ev.accept(); return
            if ev.key()==Qt.Key_Escape: self._close_find(); ev.accept(); return
        super().keyPressEvent(ev)
    def closeEvent(self,ev):
        log_app.info("closeEvent — shutting down")
        if hasattr(self,'_task_mgr'):
            for tid in["jpg_export","pw_install"]:
                if self._task_mgr.is_running(tid):
                    log_app.info("Cancelling: %s",tid); self._task_mgr.cancel(tid)
                    w=self._task_mgr.get_worker(tid)
                    if w: w.wait(3000)
        if hasattr(self,'editor') and not self.editor.check_save_before_close():
            log_app.info("Close cancelled"); ev.ignore(); return
        self._save_settings()
        if hasattr(self,'_playwright_pool'):
            log_app.info("Cleaning up Playwright pool…"); self._playwright_pool.cleanup()
        if hasattr(self,'editor') and hasattr(self.editor,'_file_load_worker'):
            if self.editor._file_load_worker and self.editor._file_load_worker.isRunning():
                self.editor._file_load_worker.wait(2000)
        super().closeEvent(ev)
        log_app.info("Window closed — session %s ended",SESSION_ID)

def main():
    _setup_logging(); install_excepthook()
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app=QApplication(sys.argv)
    app.setApplicationName("HTML Viewer & Editor"); app.setOrganizationName("HTMLViewer")
    app.setStyleSheet(APP_STYLESHEET)
    log_app.info("QApplication created — launching main window")
    viewer=HTMLViewer(input_dir=INPUT_DIR); viewer.show()
    log_app.info("Main window shown — entering event loop (session=%s)",SESSION_ID)
    ec=app.exec()
    log_app.info("Event loop ended (code=%s)",ec); sys.exit(ec)

if __name__=="__main__":
    main()