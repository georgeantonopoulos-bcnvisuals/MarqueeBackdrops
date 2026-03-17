"""
marquee_backdrop.py
───────────────────
Nuke 14.1 — Shift+B in the Node Graph, drag a marquee, creates a BackdropNode.

Install:  drop into ~/.nuke/ and add to menu.py:
              import marquee_backdrop

Debug:    watch the Script Editor for [MB] lines.
"""

from __future__ import print_function
import colorsys, random, traceback
import nuke

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    _PYSIDE_MAJOR = 6
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets
    _PYSIDE_MAJOR = 2


def _global_pos(event):
    """Return event global position as QPoint — compatible with Qt5 and Qt6."""
    if _PYSIDE_MAJOR >= 6:
        return event.globalPosition().toPoint()
    return event.globalPos()

# ── Config ────────────────────────────────────────────────────

SHORTCUT_KEY     = QtCore.Qt.Key_B
REQUIRE_MODIFIER = QtCore.Qt.ShiftModifier
ASK_LABEL        = True
RANDOM_COLOUR    = True
DEFAULT_COLOR    = 0x6A6A6AFF
DEBUG            = False


def _log(msg):
    if DEBUG:
        print("[MB] {}".format(msg))


# ── Helpers ───────────────────────────────────────────────────

def _random_pastel():
    h = random.random()
    s = random.uniform(0.2, 0.45)
    v = random.uniform(0.7, 0.85)
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return (int(r*255) << 24) | (int(g*255) << 16) | (int(b*255) << 8) | 0xFF


def _nuke_color_to_rgb(c):
    return ((c >> 24) & 0xFF, (c >> 16) & 0xFF, (c >> 8) & 0xFF)


def _is_dag_widget(widget):
    """Check if widget or any ancestor is a DAG panel."""
    w = widget
    for _ in range(30):
        if w is None:
            break
        try:
            cls  = w.metaObject().className().lower()
            name = w.objectName().lower()
        except RuntimeError:
            break
        for tag in ("dag", "nodegraph", "nodeeditor", "grapheditor",
                     "qglwidget", "qopenglwidget"):
            if tag in cls or tag in name:
                return True
        if hasattr(w, 'windowTitle'):
            try:
                if "node graph" in w.windowTitle().lower():
                    return True
            except RuntimeError:
                break
        w = w.parentWidget()
    return False


def _screen_to_dag(global_point):
    """
    Convert global screen QPoint → DAG coordinates.

    Uses nuke.zoom() and nuke.center() for the math.
    Uses QApplication.widgetAt() to find the widget under the cursor
    RIGHT NOW — no stored references.
    """
    zoom = nuke.zoom()
    if isinstance(zoom, (list, tuple)):
        zoom = zoom[0]
    zoom = max(float(zoom or 1.0), 0.001)

    try:
        center = nuke.center()
        if not center or len(center) < 2:
            center = [0.0, 0.0]
        else:
            center = [float(center[0]), float(center[1])]
    except Exception:
        center = [0.0, 0.0]

    _log("  _screen_to_dag: zoom={:.3f}  center=({:.0f},{:.0f})".format(
        zoom, center[0], center[1]))

    # Find the widget under the cursor at this exact moment
    widget = QtWidgets.QApplication.widgetAt(global_point)
    if widget is None:
        _log("  WARNING: widgetAt returned None")
        return center[0], center[1]

    try:
        cls = widget.metaObject().className()
        _log("  widgetAt: {}  size={}x{}".format(cls, widget.width(), widget.height()))
        local = widget.mapFromGlobal(global_point)
        pw = widget.width()
        ph = widget.height()
    except RuntimeError as e:
        _log("  WARNING: widget deleted: {}".format(e))
        return center[0], center[1]

    dag_x = center[0] + (local.x() - pw / 2.0) / zoom
    dag_y = center[1] + (local.y() - ph / 2.0) / zoom
    _log("  result: dag=({:.0f},{:.0f})".format(dag_x, dag_y))
    return dag_x, dag_y


# ── Overlay widget ────────────────────────────────────────────

class _MarqueeOverlay(QtWidgets.QWidget):
    """
    Frameless top-level transparent widget that paints a coloured rect.
    CRITICAL: WA_TransparentForMouseEvents so it doesn't steal clicks.
    """

    def __init__(self, color_rgb):
        super(_MarqueeOverlay, self).__init__(None)
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.Tool)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self._r, self._g, self._b = color_rgb

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        r, g, b = self._r, self._g, self._b
        painter.fillRect(self.rect(), QtGui.QColor(r, g, b, 70))
        pen = QtGui.QPen(QtGui.QColor(r, g, b, 220))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRect(self.rect().adjusted(1, 1, -1, -1))
        painter.end()


# ── Event filter ──────────────────────────────────────────────

class _Filter(QtCore.QObject):

    def __init__(self):
        super(_Filter, self).__init__()
        self._mode          = "idle"   # idle | armed | dragging
        self._origin_global = None     # QPoint (global screen)
        self._origin_dag    = None     # (x, y) DAG coords at mouse-down
        self._band          = None     # _MarqueeOverlay
        self._color         = None     # Pre-picked Nuke tile_color int
        self._cursor_timer  = None

    # ── cursor ────────────────────────────────────────────────

    def _start_cursor(self):
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CrossCursor)
        self._cursor_timer = QtCore.QTimer()
        self._cursor_timer.timeout.connect(self._enforce_cursor)
        self._cursor_timer.start(50)

    def _enforce_cursor(self):
        QtWidgets.QApplication.changeOverrideCursor(QtCore.Qt.CrossCursor)

    def _stop_cursor(self):
        if self._cursor_timer:
            self._cursor_timer.stop()
            self._cursor_timer.deleteLater()
            self._cursor_timer = None
        while QtWidgets.QApplication.overrideCursor() is not None:
            QtWidgets.QApplication.restoreOverrideCursor()

    # ── state ─────────────────────────────────────────────────

    def _arm(self):
        self._mode  = "armed"
        self._color = _random_pastel() if RANDOM_COLOUR else DEFAULT_COLOR
        self._start_cursor()
        _log("ARMED  color=0x{:08X}".format(self._color))

    def _disarm(self):
        self._mode          = "idle"
        self._origin_global = None
        self._origin_dag    = None
        self._stop_cursor()
        if self._band:
            self._band.hide()
            self._band.deleteLater()
            self._band = None
        _log("DISARMED")

    # ── filter ────────────────────────────────────────────────

    def eventFilter(self, obj, event):
        try:
            return self._handle(obj, event)
        except Exception:
            _log("EXCEPTION in eventFilter:\n{}".format(traceback.format_exc()))
            self._disarm()
            return False

    def _handle(self, obj, event):
        t = event.type()

        # ── IDLE ──────────────────────────────────────────────
        if self._mode == "idle":
            if t == QtCore.QEvent.KeyPress:
                if event.key() == SHORTCUT_KEY and \
                   (event.modifiers() & REQUIRE_MODIFIER):
                    focus = QtWidgets.QApplication.focusWidget()
                    if focus and _is_dag_widget(focus):
                        self._arm()
                        return True
                    else:
                        cn = "None"
                        if focus:
                            try:
                                cn = focus.metaObject().className()
                            except RuntimeError:
                                cn = "(deleted)"
                        _log("Shift+B ignored — focus: {}".format(cn))
            return False

        # ── ARMED ─────────────────────────────────────────────
        if self._mode == "armed":
            if t == QtCore.QEvent.KeyPress:
                if event.key() == QtCore.Qt.Key_Escape:
                    self._disarm()
                    return True
                return True

            if t == QtCore.QEvent.MouseButtonPress:
                if event.button() == QtCore.Qt.LeftButton:
                    gp = _global_pos(event)
                    self._origin_global = gp

                    # Convert to DAG coords NOW
                    _log("MOUSE DOWN at screen ({},{})".format(gp.x(), gp.y()))
                    self._origin_dag = _screen_to_dag(gp)
                    self._mode = "dragging"

                    # Create overlay AFTER coord conversion so widgetAt
                    # doesn't find the overlay itself
                    r, g, b = _nuke_color_to_rgb(self._color)
                    self._band = _MarqueeOverlay((r, g, b))
                    self._band.setGeometry(
                        QtCore.QRect(gp, QtCore.QSize()))
                    self._band.show()
                    _log("DRAGGING  origin_dag=({:.0f},{:.0f})".format(
                        self._origin_dag[0], self._origin_dag[1]))
                    return True

                if event.button() == QtCore.Qt.RightButton:
                    self._disarm()
                    return True

            return False

        # ── DRAGGING ──────────────────────────────────────────
        if self._mode == "dragging":
            if t == QtCore.QEvent.KeyPress:
                if event.key() == QtCore.Qt.Key_Escape:
                    self._disarm()
                    return True
                return True

            if t == QtCore.QEvent.MouseMove:
                cur = _global_pos(event)
                self._band.setGeometry(
                    QtCore.QRect(self._origin_global, cur).normalized())
                return True

            if t == QtCore.QEvent.MouseButtonRelease:
                if event.button() == QtCore.Qt.LeftButton:
                    end_global = _global_pos(event)
                    _log("MOUSE UP at screen ({},{})".format(
                        end_global.x(), end_global.y()))

                    # Hide overlay BEFORE coord conversion so widgetAt
                    # finds the DAG, not the overlay
                    if self._band:
                        self._band.hide()

                    # Convert end point NOW
                    end_dag = _screen_to_dag(end_global)

                    x1, y1 = self._origin_dag
                    x2, y2 = end_dag
                    color  = self._color

                    _log("DAG rect: ({:.0f},{:.0f}) -> ({:.0f},{:.0f})".format(
                        x1, y1, x2, y2))

                    # Clean up
                    self._disarm()

                    dw = abs(x2 - x1)
                    dh = abs(y2 - y1)
                    _log("Size: {:.0f} x {:.0f}".format(dw, dh))

                    if dw < 10 or dh < 10:
                        _log("Too small — no backdrop created")
                        return True

                    dl = min(x1, x2)
                    dt = min(y1, y2)

                    _log("About to create backdrop...")
                    bd = _create_backdrop(dl, dt, dw, dh, "", color)

                    if ASK_LABEL and bd:
                        _log("Showing label dialog...")
                        label = _ask_label()
                        if label:
                            bd['label'].setValue(label)
                            _log("Label set: {!r}".format(label))

                    _log("Done.")
                    return True

            return False

        return False


# ── Backdrop creation ─────────────────────────────────────────

def _ask_label():
    panel = nuke.Panel("Backdrop Label")
    panel.addSingleLineInput("Label:", "")
    if panel.show():
        return panel.value("Label:")
    return None


def _create_backdrop(x, y, w, h, label="", color=None):
    if color is None:
        color = _random_pastel() if RANDOM_COLOUR else DEFAULT_COLOR

    r, g, b = _nuke_color_to_rgb(color)
    _log("CREATE  pos=({:.0f},{:.0f})  size=({:.0f}x{:.0f})  "
         "rgb=({},{},{})  color=0x{:08X}".format(x, y, w, h, r, g, b, color))

    bd = nuke.nodes.BackdropNode(
        xpos=int(x), ypos=int(y),
        bdwidth=int(w), bdheight=int(h),
        tile_color=color,
        note_font_size=42,
        label=label,
    )

    # Verify what was actually set
    actual_color = bd['tile_color'].value()
    ar, ag, ab = _nuke_color_to_rgb(int(actual_color))
    _log("VERIFY  node={}  pos=({},{})  size=({},{})  "
         "tile_color=0x{:08X}  rgb=({},{},{})".format(
             bd.name(), bd.xpos(), bd.ypos(),
             int(bd['bdwidth'].value()), int(bd['bdheight'].value()),
             int(actual_color), ar, ag, ab))
    return bd


def create_backdrop_around_selected(label=""):
    sel = nuke.selectedNodes()
    if not sel:
        nuke.message("Select some nodes first.")
        return
    pad, hdr = 60, 40
    x0 = min(n.xpos() for n in sel) - pad
    y0 = min(n.ypos() for n in sel) - pad - hdr
    x1 = max(n.xpos() + n.screenWidth() for n in sel) + pad
    y1 = max(n.ypos() + n.screenHeight() for n in sel) + pad
    return _create_backdrop(x0, y0, x1 - x0, y1 - y0, label)


# ── Install ───────────────────────────────────────────────────

_filter = None

def install():
    global _filter
    if _filter:
        return
    app = QtWidgets.QApplication.instance()
    _filter = _Filter()
    app.installEventFilter(_filter)
    _log("Installed. Shift+B in Node Graph to draw.")

    # Diagnostic: dump all widget classes so we know what Nuke 14.1 calls them
    _log("  All widget classes containing 'dag/gl/graph':")
    for w in app.allWidgets():
        try:
            cls = w.metaObject().className()
        except RuntimeError:
            continue
        lcls = cls.lower()
        if any(t in lcls for t in ("dag", "nodegraph", "gl", "graph")):
            _log("    {}  name={!r}  {}x{}".format(
                cls, w.objectName(), w.width(), w.height()))


def uninstall():
    global _filter
    if _filter:
        app = QtWidgets.QApplication.instance()
        if app:
            app.removeEventFilter(_filter)
        _filter = None
        _log("Uninstalled")


if nuke.GUI:
    QtCore.QTimer.singleShot(2000, install)