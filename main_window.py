from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QSlider, QCheckBox, QGroupBox, QTabWidget,
    QScrollArea, QFileDialog, QFrame, QGridLayout,
    QLineEdit, QMessageBox, QToolBar, QStatusBar,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage, QDragEnterEvent, QDropEvent, QPalette, QColor, QAction

from PIL import Image
from generators import TextureGenerator


MAP_NAMES  = ['diffuse', 'normal', 'height', 'reflection', 'glossiness', 'ao', 'metallic']
MAP_LABELS = ['Diffuse', 'Normal Map', 'Height', 'Reflection', 'Glossiness', 'AO', 'Metallic']
PREVIEW_PX = 210


# ── helpers ─────────────────────────────────────────────────────────────────

def pil_to_pixmap(img: Image.Image, size: int = PREVIEW_PX) -> QPixmap:
    thumb = img.copy()
    thumb.thumbnail((size, size), Image.LANCZOS)
    rgb = thumb.convert('RGB')
    data = rgb.tobytes('raw', 'RGB')
    w, h = rgb.size
    qimg = QImage(data, w, h, w * 3, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg)


# ── background worker ────────────────────────────────────────────────────────

class GeneratorThread(QThread):
    map_ready = pyqtSignal(str, object)
    all_done  = pyqtSignal()
    failed    = pyqtSignal(str)

    def __init__(self, gen: TextureGenerator, settings: dict):
        super().__init__()
        self._gen = gen
        self._s   = settings

    def run(self):
        try:
            s = self._s
            order = ['diffuse', 'height', 'normal', 'reflection', 'glossiness', 'ao', 'metallic']
            for name in order:
                img = getattr(self._gen, name)(**s[name])
                self.map_ready.emit(name, img)
            self.all_done.emit()
        except Exception as ex:
            self.failed.emit(str(ex))


# ── drag-and-drop image zone ─────────────────────────────────────────────────

class DropZone(QLabel):
    image_loaded = pyqtSignal(str)

    _EXTS = ('.png', '.jpg', '.jpeg', '.bmp', '.tga', '.tiff', '.tif')

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._idle_style()

    def _idle_style(self):
        self.setText("Drop image here\nor click to open")
        self.setStyleSheet("""
            DropZone {
                border: 2px dashed #555;
                border-radius: 8px;
                color: #888;
                font-size: 13px;
                background: #252525;
                min-height: 165px;
            }
        """)

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self.setStyleSheet(self.styleSheet().replace('#555', '#3a8fd6'))

    def dragLeaveEvent(self, _):
        self._idle_style()

    def dropEvent(self, e: QDropEvent):
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if any(path.lower().endswith(x) for x in self._EXTS):
                self.image_loaded.emit(path)
        self._idle_style()

    def mousePressEvent(self, _):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Texture Sample", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tga *.tiff *.tif)"
        )
        if path:
            self.image_loaded.emit(path)


# ── labelled slider ──────────────────────────────────────────────────────────

class Slider(QWidget):
    value_changed = pyqtSignal(float)

    def __init__(self, label: str, lo: float, hi: float, val: float,
                 decimals: int = 2, ticks: int = 200):
        super().__init__()
        self._lo, self._hi, self._ticks = lo, hi, ticks
        self._dec = decimals

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 2, 0, 2)

        lbl = QLabel(label)
        lbl.setFixedWidth(115)
        lbl.setStyleSheet("color:#bbb;font-size:11px;")

        self._sl = QSlider(Qt.Orientation.Horizontal)
        self._sl.setRange(0, ticks)
        self._sl.setValue(self._enc(val))

        self._disp = QLabel(f"{val:.{decimals}f}")
        self._disp.setFixedWidth(40)
        self._disp.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._disp.setStyleSheet("color:#5aadff;font-size:11px;")

        self._sl.valueChanged.connect(self._emit)

        row.addWidget(lbl)
        row.addWidget(self._sl)
        row.addWidget(self._disp)

    def _enc(self, v: float) -> int:
        return round((v - self._lo) / (self._hi - self._lo) * self._ticks)

    def _dec_val(self, t: int) -> float:
        return self._lo + t / self._ticks * (self._hi - self._lo)

    def _emit(self, t: int):
        v = self._dec_val(t)
        self._disp.setText(f"{v:.{self._dec}f}")
        self.value_changed.emit(v)

    def value(self) -> float:
        return self._dec_val(self._sl.value())


# ── single map preview card ──────────────────────────────────────────────────

class MapCard(QFrame):
    def __init__(self, name: str, label: str):
        super().__init__()
        self.name = name
        self._image: Image.Image | None = None

        self.setStyleSheet("""
            MapCard {
                background: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 8px;
            }
        """)

        col = QVBoxLayout(self)
        col.setContentsMargins(8, 8, 8, 8)
        col.setSpacing(6)

        title = QLabel(label)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color:#ddd;font-weight:bold;font-size:12px;")

        self._preview = QLabel("—")
        self._preview.setFixedSize(PREVIEW_PX, PREVIEW_PX)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setStyleSheet("background:#1e1e1e;border-radius:4px;color:#555;")

        self._btn = QPushButton("Save")
        self._btn.setEnabled(False)
        self._btn.setStyleSheet("""
            QPushButton {
                background:#383838;border:1px solid #505050;
                border-radius:4px;color:#ccc;padding:5px;
            }
            QPushButton:hover{background:#484848;color:white;}
            QPushButton:disabled{color:#484848;}
        """)
        self._btn.clicked.connect(self._save)

        col.addWidget(title)
        col.addWidget(self._preview)
        col.addWidget(self._btn)

    def set_image(self, img: Image.Image):
        self._image = img
        self._preview.setPixmap(pil_to_pixmap(img, PREVIEW_PX))
        self._btn.setEnabled(True)

    def export_to(self, folder: str, base: str):
        if self._image:
            self._image.save(os.path.join(folder, f"{base}_{self.name}.png"))

    def _save(self):
        if self._image is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, f"Save {self.name} map", f"{self.name}.png",
            "PNG (*.png);;JPEG (*.jpg);;TIFF (*.tiff)"
        )
        if path:
            self._image.save(path)


# ── main window ──────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self._gen    = TextureGenerator()
        self._thread: GeneratorThread | None = None
        self._base   = "texture"
        self._out    = str(Path.home() / "Desktop")

        self._settings = {
            'diffuse':    {'saturation': 1.0, 'remove_specular': True, 'spec_threshold': 0.88},
            'height':     {'blur': 0.0, 'contrast': 1.0, 'invert': False},
            'normal':     {'strength': 3.0, 'blur': 1.0},
            'reflection': {'intensity': 0.8, 'gamma': 1.0, 'contrast': 1.0},
            'glossiness': {'base': 0.8, 'variance_scale': 5.0},
            'ao':         {'radius': 15, 'intensity': 0.8, 'blur': 2.0},
            'metallic':   {'invert': False, 'blur': 2.0},
        }

        self._build_ui()
        self._apply_theme()
        self.setWindowTitle("VRay Texture Map Generator  ·  3ds Max")
        self.setMinimumSize(1100, 700)
        self.resize(1300, 830)

    # ── build ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        tb = QToolBar()
        tb.setMovable(False)
        tb.setStyleSheet("QToolBar{background:#282828;border-bottom:1px solid #3a3a3a;padding:4px 8px;spacing:6px;}")
        self.addToolBar(tb)

        gen_btn = QPushButton("⚡  Generate All")
        gen_btn.setStyleSheet(self._btn_css("#1a6abd", "#2077cc"))
        gen_btn.clicked.connect(self.generate_all)
        tb.addWidget(gen_btn)

        tb.addSeparator()
        lbl = QLabel("  Output folder:")
        lbl.setStyleSheet("color:#aaa;")
        tb.addWidget(lbl)

        self._out_edit = QLineEdit(self._out)
        self._out_edit.setFixedWidth(330)
        self._out_edit.setStyleSheet(
            "background:#333;border:1px solid #555;border-radius:3px;color:#ddd;padding:2px 6px;"
        )
        self._out_edit.textChanged.connect(lambda t: setattr(self, '_out', t))
        tb.addWidget(self._out_edit)

        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_out)
        tb.addWidget(browse_btn)

        tb.addSeparator()
        exp_btn = QPushButton("Export All Maps")
        exp_btn.setStyleSheet(self._btn_css("#2a7a2a", "#357035"))
        exp_btn.clicked.connect(self.export_all)
        tb.addWidget(exp_btn)

        center = QWidget()
        self.setCentralWidget(center)
        row = QHBoxLayout(center)
        row.setContentsMargins(8, 8, 8, 8)
        row.setSpacing(10)
        row.addWidget(self._build_left())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;}")
        grid_w = QWidget()
        self._grid = QGridLayout(grid_w)
        self._grid.setSpacing(10)

        self._cards: dict[str, MapCard] = {}
        positions = [(r, c) for r in range(3) for c in range(3)]
        for pos, (name, lbl_text) in zip(positions, zip(MAP_NAMES, MAP_LABELS)):
            card = MapCard(name, lbl_text)
            self._cards[name] = card
            self._grid.addWidget(card, *pos)

        scroll.setWidget(grid_w)
        row.addWidget(scroll, 1)

        sb = QStatusBar()
        sb.setStyleSheet("QStatusBar{background:#282828;color:#888;border-top:1px solid #3a3a3a;}")
        self.setStatusBar(sb)
        sb.showMessage("Ready — drop or open a texture sample image.")

    def _build_left(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(315)
        col = QVBoxLayout(panel)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(8)

        in_grp = QGroupBox("Input Image")
        in_col = QVBoxLayout(in_grp)

        self._drop = DropZone()
        self._drop.image_loaded.connect(self._load_image)

        self._info = QLabel("No image loaded")
        self._info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._info.setStyleSheet("color:#777;font-size:11px;")

        gen_big = QPushButton("Generate All Maps")
        gen_big.setStyleSheet(
            self._btn_css("#1a6abd", "#2077cc") + "font-size:13px;font-weight:bold;padding:10px;"
        )
        gen_big.clicked.connect(self.generate_all)

        in_col.addWidget(self._drop)
        in_col.addWidget(self._info)
        in_col.addWidget(gen_big)
        col.addWidget(in_grp)

        cfg_grp = QGroupBox("Map Settings")
        cfg_col = QVBoxLayout(cfg_grp)
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane{border:none;}
            QTabBar::tab{background:#333;color:#999;padding:4px 9px;font-size:11px;}
            QTabBar::tab:selected{background:#444;color:#eee;}
        """)
        self._populate_tabs(tabs)
        cfg_col.addWidget(tabs)
        col.addWidget(cfg_grp, 1)

        return panel

    def _populate_tabs(self, tabs: QTabWidget):
        s = self._settings

        def tab(label: str, widgets: list):
            w = QWidget()
            v = QVBoxLayout(w)
            v.setSpacing(2)
            v.setContentsMargins(4, 4, 4, 4)
            for ww in widgets:
                v.addWidget(ww)
            v.addStretch()
            tabs.addTab(w, label)

        # ── Diffuse ──
        d_sat  = Slider("Saturation",      0.0, 2.0, 1.0)
        d_spec = QCheckBox("Remove Specular Highlights")
        d_spec.setChecked(True)
        d_thr  = Slider("Spec Threshold",  0.5, 1.0, 0.88)
        d_sat .value_changed.connect(lambda v: s['diffuse'].update({'saturation': v}))
        d_spec.toggled      .connect(lambda v: s['diffuse'].update({'remove_specular': v}))
        d_thr .value_changed.connect(lambda v: s['diffuse'].update({'spec_threshold': v}))
        tab("Diff", [d_sat, d_spec, d_thr])

        # ── Height ──
        h_blur = Slider("Blur",     0.0, 10.0, 0.0)
        h_con  = Slider("Contrast", 0.5,  3.0, 1.0)
        h_inv  = QCheckBox("Invert")
        h_blur.value_changed.connect(lambda v: s['height'].update({'blur': v}))
        h_con .value_changed.connect(lambda v: s['height'].update({'contrast': v}))
        h_inv .toggled      .connect(lambda v: s['height'].update({'invert': v}))
        tab("Height", [h_blur, h_con, h_inv])

        # ── Normal ──
        n_str  = Slider("Strength", 0.5, 10.0, 3.0)
        n_blur = Slider("Blur",     0.0,  5.0, 1.0)
        n_str .value_changed.connect(lambda v: s['normal'].update({'strength': v}))
        n_blur.value_changed.connect(lambda v: s['normal'].update({'blur': v}))
        tab("Normal", [n_str, n_blur])

        # ── Reflection ──
        r_int = Slider("Intensity", 0.0, 1.0, 0.8)
        r_gam = Slider("Gamma",     0.1, 3.0, 1.0)
        r_con = Slider("Contrast",  0.5, 3.0, 1.0)
        r_int.value_changed.connect(lambda v: s['reflection'].update({'intensity': v}))
        r_gam.value_changed.connect(lambda v: s['reflection'].update({'gamma': v}))
        r_con.value_changed.connect(lambda v: s['reflection'].update({'contrast': v}))
        tab("Reflect", [r_int, r_gam, r_con])

        # ── Glossiness ──
        g_base = Slider("Base Gloss",     0.0, 1.0,  0.8)
        g_var  = Slider("Variance Scale", 1.0, 20.0, 5.0, decimals=1)
        g_base.value_changed.connect(lambda v: s['glossiness'].update({'base': v}))
        g_var .value_changed.connect(lambda v: s['glossiness'].update({'variance_scale': v}))
        tab("Gloss", [g_base, g_var])

        # ── AO ──
        a_rad = Slider("Radius",    3,  50, 15, decimals=0, ticks=47)
        a_int = Slider("Intensity", 0.0, 1.0, 0.8)
        a_blur = Slider("Blur",     0.0, 10.0, 2.0)
        a_rad .value_changed.connect(lambda v: s['ao'].update({'radius': max(3, int(round(v)))}))
        a_int .value_changed.connect(lambda v: s['ao'].update({'intensity': v}))
        a_blur.value_changed.connect(lambda v: s['ao'].update({'blur': v}))
        tab("AO", [a_rad, a_int, a_blur])

        # ── Metallic ──
        m_blur = Slider("Blur", 0.0, 10.0, 2.0)
        m_inv  = QCheckBox("Invert")
        m_blur.value_changed.connect(lambda v: s['metallic'].update({'blur': v}))
        m_inv .toggled      .connect(lambda v: s['metallic'].update({'invert': v}))
        tab("Metal", [m_blur, m_inv])

    # ── actions ──────────────────────────────────────────────────────────────

    def _load_image(self, path: str):
        try:
            self._gen.load(path)
            self._base = Path(path).stem

            thumb = Image.open(path)
            thumb.thumbnail((295, 160))
            self._drop.setPixmap(pil_to_pixmap(thumb, 295))
            self._info.setText(f"{Path(path).name}  ·  {self._gen.width} × {self._gen.height} px")
            self.statusBar().showMessage(f"Loaded: {path}")
            self.generate_all()
        except Exception as ex:
            self.statusBar().showMessage(f"Error loading image: {ex}")

    def generate_all(self):
        if self._gen.source is None:
            self.statusBar().showMessage("No image loaded.")
            return
        if self._thread and self._thread.isRunning():
            return

        self.statusBar().showMessage("Generating maps…")
        self._thread = GeneratorThread(self._gen, self._settings)
        self._thread.map_ready.connect(self._on_map_ready)
        self._thread.all_done .connect(lambda: self.statusBar().showMessage("All maps generated."))
        self._thread.failed   .connect(lambda e: self.statusBar().showMessage(f"Error: {e}"))
        self._thread.start()

    def _on_map_ready(self, name: str, img: Image.Image):
        if name in self._cards:
            self._cards[name].set_image(img)

    def _browse_out(self):
        d = QFileDialog.getExistingDirectory(self, "Select Output Folder", self._out)
        if d:
            self._out = d
            self._out_edit.setText(d)

    def export_all(self):
        ready = [c for c in self._cards.values() if c._image]
        if not ready:
            self.statusBar().showMessage("Generate maps first.")
            return
        os.makedirs(self._out, exist_ok=True)
        for card in ready:
            card.export_to(self._out, self._base)
        self.statusBar().showMessage(f"Exported {len(ready)} maps → {self._out}")
        QMessageBox.information(
            self, "Export Complete",
            f"Saved {len(ready)} maps to:\n{self._out}\n\nFilename format: {self._base}_<map>.png"
        )

    # ── styling ───────────────────────────────────────────────────────────────

    @staticmethod
    def _btn_css(bg: str, hover: str) -> str:
        return (
            f"QPushButton{{background:{bg};border:none;border-radius:5px;"
            f"color:white;padding:6px 14px;}}"
            f"QPushButton:hover{{background:{hover};}}"
        )

    def _apply_theme(self):
        p = QPalette()
        C = QColor
        p.setColor(QPalette.ColorRole.Window,          C(45, 45, 45))
        p.setColor(QPalette.ColorRole.WindowText,      C(220, 220, 220))
        p.setColor(QPalette.ColorRole.Base,            C(35, 35, 35))
        p.setColor(QPalette.ColorRole.AlternateBase,   C(50, 50, 50))
        p.setColor(QPalette.ColorRole.Text,            C(220, 220, 220))
        p.setColor(QPalette.ColorRole.Button,          C(55, 55, 55))
        p.setColor(QPalette.ColorRole.ButtonText,      C(220, 220, 220))
        p.setColor(QPalette.ColorRole.Highlight,       C(26, 106, 189))
        p.setColor(QPalette.ColorRole.HighlightedText, C(255, 255, 255))
        self.setPalette(p)
