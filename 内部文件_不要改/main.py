# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sys
import threading
import time
import ctypes
from ctypes import wintypes
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QPoint, QTimer
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QFont, QMouseEvent, QIcon, QGuiApplication, QCursor
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog, QFrame,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QMessageBox, QPushButton, QProgressBar, QRadioButton, QScrollArea,
    QSizeGrip, QSpinBox, QTextEdit, QVBoxLayout, QWidget, QInputDialog, QProgressDialog
)

from engine import AudioEngine, collect_audio_files, format_duration, format_size
from license_client import activate_license, local_status, machine_code, online_verify
from platform_presets import CATEGORY_ORDER, CATEGORY_PRESETS
from schemes import DISPLAY_SCHEMES, SCHEME_BY_ID
from settings import APP_NAME, APP_VERSION, CONTACT_TEXT, DEFAULT_OUTPUT_DIR, app_data_dir, resource_path
from security_guard import runtime_guard_ok
from updater import prepare_update

QSS = r"""
* { font-family: "Microsoft YaHei", "Segoe UI"; font-size: 13px; outline: none; }
QMainWindow, QDialog, QWidget#root { background: #030814; color: #e6eefc; }
QFrame#topBar { background: #030814; border: 0; }
QFrame#panel { background: #071121; border: 1px solid #1b3356; border-radius: 8px; }
QFrame#card { background: #0a1728; border: 1px solid #1d3150; border-radius: 8px; }
QFrame#cardChecked { background: #0b2230; border: 1px solid #24d3d6; border-radius: 8px; }
QFrame#dropBox { background: #071525; border: 1px dashed #386da8; border-radius: 8px; }
QLabel { color: #dbeafe; background: transparent; }
QLabel#muted { color: #8aa4c2; }
QLabel#title { font-size: 24px; font-weight: 900; color: #f8fbff; }
QLabel#section { font-size: 18px; font-weight: 900; color: #f1f7ff; }
QLabel#green { color: #24e884; font-weight: 800; }
QLabel#blue { color: #35c2ff; font-weight: 800; }
QLabel#orange { color: #ffd166; font-weight: 800; }
QPushButton { background: #0c1b31; color: #e6f1ff; border: 1px solid #203a61; border-radius: 8px; padding: 9px 13px; outline: none; }
QPushButton:hover { background: #132a4a; border-color: #238bff; }
QPushButton:focus { border: 1px solid #203a61; outline: none; }
QPushButton:pressed { border: 1px solid #203a61; outline: none; }
QPushButton#primary { background: #095ec8; border: 1px solid #238bff; font-weight: 800; }
QPushButton#ghost { background: #0b1526; border: 1px solid #203a61; }
QPushButton#danger { background: #141f31; border-color: #2a405c; }
QPushButton#windowBtn { background: transparent; border: 0; padding: 5px 10px; font-size: 18px; }
QPushButton#windowBtn:hover { background: #17365a; }
QLineEdit, QComboBox, QSpinBox { background: #06111f; color: #eaf4ff; border: 1px solid #1d3d63; border-radius: 8px; padding: 7px; selection-background-color: #0b72ff; outline: none; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1px solid #1d3d63; outline: none; }
QComboBox QAbstractItemView { background:#06111f; color:#eaf4ff; border:1px solid #1d3d63; selection-background-color:#123b61; }
QTextEdit, QListWidget { background: #050e1c; color: #eaf4ff; border: 1px solid #1b3356; border-radius: 8px; outline: none; }
QTextEdit:focus, QListWidget:focus { border: 1px solid #163252; outline: none; }
QListWidget::item { padding: 8px; border-bottom: 1px solid #102a43; }
QListWidget::item:selected { background: #123b61; color: #ffffff; }
QProgressBar { background: #10243c; color: #ffffff; border: 1px solid #1e4169; border-radius: 7px; text-align: center; height: 18px; }
QProgressBar::chunk { background: #0b86ff; border-radius: 7px; }
QRadioButton, QCheckBox { color: #eaf4ff; spacing: 8px; outline: none; }
QRadioButton:focus, QCheckBox:focus { outline: none; }
QCheckBox::indicator { width:14px; height:14px; border:1px solid #335b82; background:#06111f; border-radius:3px; }
QCheckBox::indicator:checked { background:#0b86ff; border:1px solid #35c2ff; }
QRadioButton::indicator { width:14px; height:14px; border:1px solid #335b82; background:#06111f; border-radius:7px; }
QRadioButton::indicator:checked { background:#0b86ff; border:1px solid #35c2ff; }
QScrollArea { background: #071121; border: 0; outline: none; }
QScrollArea:focus { border: 0; outline: none; }
QScrollArea > QWidget > QWidget { background: #071121; }
QScrollBar:vertical { background: #071121; width: 10px; margin: 0px; border-radius: 5px; }
QScrollBar::handle:vertical { background: #264b74; min-height: 30px; border-radius: 5px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar:horizontal { background: #071426; height: 0px; }
"""

class DropArea(QFrame):
    filesDropped = Signal(list)
    def __init__(self):
        super().__init__()
        self.setObjectName("dropBox")
        self.setAcceptDrops(True)
        self.setMinimumHeight(150)
        lay = QVBoxLayout(self); lay.setAlignment(Qt.AlignCenter)
        icon = QLabel("⇧"); icon.setAlignment(Qt.AlignCenter); icon.setStyleSheet("font-size:42px;color:#78c8ff;")
        text = QLabel("AI歌曲建议使用 MP3 格式\nWAV 可导入，但修复方案要选轻一点，避免跑偏")
        text.setAlignment(Qt.AlignCenter); text.setObjectName("blue")
        lay.addWidget(icon); lay.addWidget(text)
    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls(): e.acceptProposedAction()
    def dropEvent(self, e: QDropEvent):
        self.filesDropped.emit([u.toLocalFile() for u in e.mimeData().urls()])

class DropList(QListWidget):
    filesDropped = Signal(list)
    def __init__(self):
        super().__init__(); self.setAcceptDrops(True)
    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls(): e.acceptProposedAction()
    def dropEvent(self, e: QDropEvent):
        self.filesDropped.emit([u.toLocalFile() for u in e.mimeData().urls()])

class ActivationDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AudioFlow Studio｜输入卡密")
        self.setMinimumSize(460, 300)
        self.resize(560, 330)
        self.setStyleSheet(QSS)
        layout = QVBoxLayout(self); layout.setContentsMargins(28,24,28,24); layout.setSpacing(14)
        title = QLabel("AudioFlow Studio"); title.setObjectName("title"); layout.addWidget(title)
        sub = QLabel("首次使用前需要输入卡密激活，激活后才能进入主界面。"); sub.setObjectName("muted"); layout.addWidget(sub)
        card = QFrame(); card.setObjectName("panel"); box = QVBoxLayout(card); box.setContentsMargins(18,16,18,16)
        self.status = QLabel("未激活"); self.status.setStyleSheet("color:#ff6b6b;font-weight:800;"); box.addWidget(self.status)
        box.addWidget(QLabel("输入卡密"))
        self.key_input = QLineEdit(); self.key_input.setPlaceholderText("请输入后台生成的卡密"); box.addWidget(self.key_input)
        machine = QLabel("机器码：" + machine_code()); machine.setObjectName("muted"); box.addWidget(machine)
        row = QHBoxLayout(); self.activate_btn=QPushButton("激活并进入软件"); self.activate_btn.setObjectName("primary"); self.exit_btn=QPushButton("退出")
        row.addWidget(self.activate_btn); row.addStretch(1); row.addWidget(self.exit_btn); box.addLayout(row)
        layout.addWidget(card, 1)
        self.activate_btn.clicked.connect(self.do_activate); self.exit_btn.clicked.connect(self.reject); self.key_input.returnPressed.connect(self.do_activate)
    def do_activate(self):
        success, text, _payload = activate_license(self.key_input.text().strip())
        if success:
            QMessageBox.information(self, "激活成功", text); self.accept()
        else:
            self.status.setText(text); QMessageBox.warning(self, "激活失败", text)

INTRO_TEXT = """使用说明

1. 添加歌曲：建议导入 MP3，最终统一导出 WAV。
2. 风格推荐：按歌曲类型选择即可，常用入口有人声流行、纯音乐器乐、DJ电音、古风民谣、说唱节奏。
3. 高级方案：主界面保留 14 个核心方案，重复方向已经折进风格推荐和内部兼容链路。
4. 处理顺序：方案会按顺序逐步处理同一首歌，内部临时传递，最终只输出一个成品文件。
5. 默认优先：人声歌曲先用“人声流行”，纯音乐先用“纯音乐器乐”，低频重的歌先用“DJ电音”。
6. 组合方案：只在单风格不够时再手动叠加，程序会减少中间重复收尾，避免波形被压平。
7. 批量任务：右侧可设置并发数，普通电脑建议 1-2，高配置可适当提高。
8. 输出位置：处理完成后可直接打开输出目录查看成品。

问题咨询：Zhwdh141319
添加时备注：AI原创
不懂的可以关注我的公众号：山河网创笔记
"""


class ProcessWorker(QThread):
    log = Signal(str); progress = Signal(int, str); finishedOk = Signal(int, str); failed = Signal(str)
    def __init__(self, files: list[Path], out_dir: Path, ids: list[int], fmt: str, mode: str, workers: int = 1, variants: list[list[int]] | None = None, platform_code: str | None = None):
        super().__init__()
        self.files=files; self.out_dir=out_dir; self.ids=ids; self.fmt=(fmt or "wav").lower(); self.mode="pipeline"
        self.workers=max(1, min(int(workers or 1), max(1, len(files)), 4))
        self.variants=variants or []
        self.platform_code=platform_code
        self.stop_requested=False
    def request_stop(self): self.stop_requested=True
    def run(self):
        cpu_count = os.cpu_count() or 4
        ffmpeg_threads = max(1, cpu_count // max(1, self.workers))
        engine = AudioEngine(log=lambda m: self.log.emit(m), ffmpeg_threads=ffmpeg_threads)
        ok, msg = engine.validate()
        if not ok: self.failed.emit(msg); return
        success=0; total=len(self.files); lock=threading.Lock(); file_progress={i: 0 for i in range(1, total + 1)}

        def update_progress(idx: int, file: Path, p: int, text: str):
            with lock:
                file_progress[idx] = max(0, min(100, int(p)))
                overall = int(sum(file_progress.values()) / max(1, total))
            self.progress.emit(overall, f"{file.name}｜{text}")

        def process_one(idx: int, file: Path) -> int:
            if self.stop_requested:
                return 0
            local_engine = AudioEngine(
                log=lambda m, f=file: self.log.emit(f"{f.name}｜{m}"),
                ffmpeg_threads=ffmpeg_threads,
            )
            self.log.emit(f"开始处理：{file.name}")
            local_engine.process_pipeline(file, self.out_dir, self.ids, self.fmt, progress=lambda p,t: update_progress(idx, file, p, t), platform_code=self.platform_code)
            update_progress(idx, file, 100, "完成")
            return 1

        try:
            self.log.emit(f"批量队列：{total} 个文件，并发 {self.workers}，每任务 FFmpeg 线程 {ffmpeg_threads}")
            executor = ThreadPoolExecutor(max_workers=self.workers)
            futures = [executor.submit(process_one, idx, f) for idx, f in enumerate(self.files, start=1)]
            error = None
            try:
                for fut in as_completed(futures):
                    if self.stop_requested:
                        break
                    try:
                        success += fut.result()
                    except Exception as e:
                        error = e
                        self.stop_requested = True
                        break
            finally:
                executor.shutdown(wait=True, cancel_futures=True)
            if error:
                raise error
            self.progress.emit(100, "全部任务完成")
            self.finishedOk.emit(success, str(self.out_dir))
        except Exception as e:
            self.failed.emit(str(e))


class FeatureWorker(QThread):
    log = Signal(str); progress = Signal(int, str); finishedOk = Signal(int, str); failed = Signal(str)
    def __init__(self, task: str, files: list[Path], out_dir: Path, style: str = "natural"):
        super().__init__()
        self.task = task
        self.files = files
        self.out_dir = out_dir
        self.style = style
        self.stop_requested = False
    def request_stop(self): self.stop_requested = True
    def run(self):
        try:
            if self.task == "master":
                engine = AudioEngine(log=lambda m: self.log.emit(m))
                total = max(1, len(self.files))
                done = 0
                for i, f in enumerate(self.files, 1):
                    if self.stop_requested:
                        break
                    self.progress.emit(int((i - 1) * 100 / total), f"智能母音升级：{f.name}")
                    out = engine.smart_master_upgrade(f, self.out_dir, self.style, "mp3")
                    self.log.emit(f"升级完成：{out.name}")
                    done += 1
                self.progress.emit(100, "智能母音升级完成")
                self.finishedOk.emit(done, str(self.out_dir / "智能母音升级"))
                return
            raise RuntimeError("未知任务")
        except Exception as e:
            self.failed.emit(str(e))


class FeatureActionCard(QFrame):
    def __init__(self, title: str, desc: str, button: str, callback, accent: str = "#0b63ce"):
        super().__init__()
        self.setObjectName("card")
        self.setMinimumHeight(124)
        lay = QVBoxLayout(self); lay.setContentsMargins(14,12,14,12); lay.setSpacing(6)
        title_label = QLabel(title); title_label.setStyleSheet("font-size:15px;font-weight:900;color:#f8fbff;")
        desc_label = QLabel(desc); desc_label.setObjectName("muted"); desc_label.setWordWrap(True)
        btn = QPushButton(button); btn.setObjectName("primary"); btn.setStyleSheet(f"background:{accent};border-color:{accent};font-weight:800;")
        btn.clicked.connect(callback)
        lay.addWidget(title_label); lay.addWidget(desc_label, 1); lay.addWidget(btn)

class SchemeCard(QFrame):
    toggled = Signal(int, bool)
    def __init__(self, scheme: dict, selected: bool=False):
        super().__init__(); self.scheme=scheme; self.setObjectName("cardChecked" if selected else "card"); self.setMinimumHeight(108); self.setCursor(Qt.PointingHandCursor)
        lay = QVBoxLayout(self); lay.setContentsMargins(10,8,10,8); lay.setSpacing(3)
        top = QHBoxLayout(); self.cb=QCheckBox(str(scheme["index"])); self.cb.setChecked(selected)
        name=QLabel(scheme["name"]); name.setStyleSheet("font-size:13px;font-weight:900;")
        tag=QLabel(scheme.get("tag", "")); tag.setObjectName("orange")
        top.addWidget(self.cb); top.addWidget(name,1); top.addWidget(tag); lay.addLayout(top)
        role_text = str(scheme.get("focus") or f"{scheme.get('tag', '处理')}方向")
        role=QLabel(role_text); role.setObjectName("blue"); lay.addWidget(role)
        desc=QLabel(scheme.get("desc", "")); desc.setWordWrap(True); desc.setObjectName("muted"); desc.setMaximumHeight(44); lay.addWidget(desc,1)
        self.cb.toggled.connect(self._on_toggled)
    def _on_toggled(self, checked: bool):
        self.setObjectName("cardChecked" if checked else "card"); self.style().unpolish(self); self.style().polish(self); self.toggled.emit(int(self.scheme["index"]), checked)
    def set_checked(self, value: bool):
        self.cb.blockSignals(True); self.cb.setChecked(value); self.cb.blockSignals(False)
        self.setObjectName("cardChecked" if value else "card"); self.style().unpolish(self); self.style().polish(self)
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton: self.cb.setChecked(not self.cb.isChecked())
        super().mousePressEvent(event)

class MainWindow(QMainWindow):
    update_ready = Signal(str)
    update_ready_silent = Signal(str)
    update_progress = Signal(int, str)
    _RESIZE_BORDER = 8

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setMinimumSize(960, 620)
        self.setMouseTracking(True)
        self.setStyleSheet(QSS)
        icon_path = resource_path("assets/audioflow.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.files: list[Path] = []; self.selected_order=[1]; self.selected_variants=None; self.selected_category="POP"; self.category_buttons={}; self.cards={}; self.worker=None; self.update_dialog=None; self.output_dir=Path(DEFAULT_OUTPUT_DIR); self.engine=AudioEngine(log=self.log); self._drag_pos=QPoint()
        self.update_ready.connect(self.notify_update_ready)
        self.update_ready_silent.connect(self.notify_update_ready_silent)
        self.update_progress.connect(self.notify_update_progress)
        self._build(); self._fit_initial_window(); self.refresh_license(); self.apply_category_template(self.selected_category); self.refresh_order_ui(); self.log(f"AudioFlow Studio v{APP_VERSION} 已启动")
        QTimer.singleShot(450, self.show_intro_once)
        QTimer.singleShot(1600, self.check_update_silently)
    def _fit_initial_window(self):
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            self.resize(1320, 760)
            return
        geo = screen.availableGeometry()
        width = min(1420, max(960, int(geo.width() * 0.90)))
        height = min(820, max(620, int(geo.height() * 0.88)))
        self.resize(width, height)
        self.move(geo.x() + max(0, (geo.width() - width) // 2), geo.y() + max(0, (geo.height() - height) // 2))
    def _panel(self, title: str):
        frame=QFrame(); frame.setObjectName("panel"); lay=QVBoxLayout(frame); lay.setContentsMargins(18,18,18,18); lay.setSpacing(12); label=QLabel(title); label.setObjectName("section"); lay.addWidget(label); return frame,lay
    def _build(self):
        root=QWidget(); root.setObjectName("root"); self.setCentralWidget(root); main=QVBoxLayout(root); main.setContentsMargins(14,12,14,14); main.setSpacing(10)
        header=QFrame(); header.setObjectName("topBar"); header.installEventFilter(self); h=QHBoxLayout(header); h.setContentsMargins(4,0,4,0)
        logo=QLabel("≋"); logo.setStyleSheet("font-size:26px;color:#5aa2ff;font-weight:900;"); title=QLabel("AudioFlow Studio"); title.setObjectName("title"); sub=QLabel("｜音频自然修复｜批量方案流水线"); sub.setObjectName("muted")
        self.open_out_btn=QPushButton("打开输出目录"); self.contact_btn=QPushButton("问题咨询"); self.lic_btn=QPushButton("授权 / 续期"); self.lic_label=QLabel(""); self.lic_label.setObjectName("green"); self.version_label=QLabel(f"v{APP_VERSION}"); self.version_label.setObjectName("muted")
        mini=QPushButton("—"); mini.setObjectName("windowBtn"); close=QPushButton("×"); close.setObjectName("windowBtn")
        mini.clicked.connect(self.showMinimized); close.clicked.connect(self.close)
        h.addWidget(logo); h.addWidget(title); h.addWidget(sub); h.addStretch(1); h.addWidget(self.open_out_btn); h.addWidget(self.contact_btn); h.addWidget(self.lic_btn); h.addWidget(self.lic_label); h.addSpacing(6); h.addWidget(self.version_label); h.addSpacing(8); h.addWidget(mini); h.addWidget(close)
        main.addWidget(header)
        grid=QHBoxLayout(); grid.setSpacing(10); grid.addWidget(self._build_left(), 3); grid.addWidget(self._build_middle(), 6); grid.addWidget(self._build_right(), 4); main.addLayout(grid,1)
        grip_row=QHBoxLayout(); grip_row.setContentsMargins(0,0,0,0); grip_row.addStretch(1); grip_row.addWidget(QSizeGrip(self)); main.addLayout(grip_row)
        self.open_out_btn.clicked.connect(self.open_output_dir); self.contact_btn.clicked.connect(self.show_contact_dialog); self.lic_btn.clicked.connect(self.show_license_dialog)

    def nativeEvent(self, event_type, message):
        event_name = bytes(event_type).decode(errors="ignore") if isinstance(event_type, (bytes, bytearray)) else str(event_type)
        if sys.platform.startswith("win") and event_name == "windows_generic_MSG" and not self.isMaximized():
            try:
                msg = wintypes.MSG.from_address(int(message))
            except (TypeError, ValueError, OSError):
                return super().nativeEvent(event_type, message)
            if msg.message == 0x0084:  # WM_NCHITTEST
                pos = QCursor.pos()
                rect = self.frameGeometry()
                x = pos.x() - rect.x()
                y = pos.y() - rect.y()
                w = rect.width()
                h = rect.height()
                border = self._RESIZE_BORDER
                left = x <= border
                right = x >= w - border
                top = y <= border
                bottom = y >= h - border
                if top and left:
                    return True, 13  # HTTOPLEFT
                if top and right:
                    return True, 14  # HTTOPRIGHT
                if bottom and left:
                    return True, 16  # HTBOTTOMLEFT
                if bottom and right:
                    return True, 17  # HTBOTTOMRIGHT
                if left:
                    return True, 10  # HTLEFT
                if right:
                    return True, 11  # HTRIGHT
                if top:
                    return True, 12  # HTTOP
                if bottom:
                    return True, 15  # HTBOTTOM
        return super().nativeEvent(event_type, message)

    def eventFilter(self, obj, event):
        if isinstance(event, QMouseEvent) and obj.objectName()=="topBar":
            if event.type()==QMouseEvent.MouseButtonPress and event.button()==Qt.LeftButton: self._drag_pos=event.globalPosition().toPoint()-self.frameGeometry().topLeft(); return True
            if event.type()==QMouseEvent.MouseMove and event.buttons() & Qt.LeftButton: self.move(event.globalPosition().toPoint()-self._drag_pos); return True
        return super().eventFilter(obj,event)
    def _build_left(self):
        panel,lay=self._panel("01 素材池｜拖拽/批量导入"); row=QHBoxLayout()
        for text,cb in [("添加音频",self.add_files),("添加文件夹",self.add_folder),("清空",self.clear_files)]:
            b=QPushButton(text); b.clicked.connect(cb); row.addWidget(b)
        lay.addLayout(row); drop=DropArea(); drop.filesDropped.connect(self.add_paths); lay.addWidget(drop)
        lay.addWidget(QLabel("素材列表")); self.file_list=DropList(); self.file_list.filesDropped.connect(self.add_paths); lay.addWidget(self.file_list,1)
        self.file_count=QLabel("共 0 个文件"); self.file_count.setObjectName("muted"); lay.addWidget(self.file_count); remove=QPushButton("移除选中"); remove.clicked.connect(self.remove_selected); lay.addWidget(remove); return panel
    def _make_helper_card(self, title: str, desc: str, button: str, callback):
        card = QFrame()
        card.setObjectName("card")
        card.setMinimumHeight(108)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size:13px;font-weight:900;color:#f8fbff;")
        desc_label = QLabel(desc)
        desc_label.setWordWrap(True)
        desc_label.setObjectName("muted")
        desc_label.setMaximumHeight(42)
        btn = QPushButton(button)
        btn.setObjectName("primary")
        btn.clicked.connect(callback)
        lay.addWidget(title_label)
        lay.addWidget(desc_label, 1)
        lay.addWidget(btn)
        return card
    def _build_middle(self):
        panel,lay=self._panel("02 风格方案｜一键处理")
        category_box=QFrame(); category_box.setObjectName("card"); category_box.setMaximumHeight(168); cl=QVBoxLayout(category_box); cl.setContentsMargins(10,8,10,8); cl.setSpacing(6)
        cl.addWidget(QLabel("风格分类推荐"))
        cgrid=QGridLayout(); cgrid.setHorizontalSpacing(8); cgrid.setVerticalSpacing(8)
        for i, code in enumerate(CATEGORY_ORDER):
            preset=CATEGORY_PRESETS[code]
            b=QPushButton(preset["short"])
            b.setMinimumHeight(34)
            b.setToolTip(preset["desc"])
            b.clicked.connect(lambda _checked=False, c=code: self.apply_category_template(c))
            self.category_buttons[code]=b
            cgrid.addWidget(b, i // 4, i % 4)
        cl.addLayout(cgrid)
        self.category_desc=QLabel("")
        self.category_desc.setObjectName("muted")
        self.category_desc.setWordWrap(True)
        cl.addWidget(self.category_desc)
        lay.addWidget(category_box)

        order_box=QFrame(); order_box.setObjectName("card"); ol=QVBoxLayout(order_box); ol.setContentsMargins(10,8,10,8); ol.setSpacing(4)
        order=QHBoxLayout(); order.addWidget(QLabel("当前处理顺序")); self.order_edit=QLineEdit(); self.order_edit.setReadOnly(True); order.addWidget(self.order_edit,1); ol.addLayout(order)
        seq=QHBoxLayout(); self.seq_list=QListWidget(); self.seq_list.setMaximumHeight(66); seq.addWidget(self.seq_list,1); col=QVBoxLayout()
        for text,cb in [("上移",lambda:self.move_selected(-1)),("下移",lambda:self.move_selected(1)),("移除",self.remove_scheme_from_order)]:
            b=QPushButton(text); b.clicked.connect(cb); col.addWidget(b)
        col.addStretch(1); seq.addLayout(col); ol.addLayout(seq); lay.addWidget(order_box)

        adv_head=QHBoxLayout(); adv_title=QLabel(f"高级核心方案（{len(DISPLAY_SCHEMES)}）"); adv_title.setObjectName("muted"); adv_head.addWidget(adv_title); adv_head.addStretch(1)
        self.advanced_toggle=QPushButton("展开高级方案"); self.advanced_toggle.clicked.connect(self.toggle_advanced_schemes); adv_head.addWidget(self.advanced_toggle)
        reset_btn=QPushButton("恢复推荐"); reset_btn.clicked.connect(lambda: self.apply_category_template("POP")); adv_head.addWidget(reset_btn); lay.addLayout(adv_head)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); scroll.setFrameShape(QFrame.NoFrame); scroll.setFocusPolicy(Qt.NoFocus); scroll.viewport().setStyleSheet("background:#071426;border:0;")
        box=QWidget(); box.setStyleSheet("background:#071426;border:0;"); sg=QGridLayout(box); sg.setSpacing(10); sg.setContentsMargins(0,0,0,0)
        for i,s in enumerate(DISPLAY_SCHEMES):
            card=SchemeCard(s, int(s["index"]) in self.selected_order); card.setFocusPolicy(Qt.NoFocus); card.toggled.connect(self.on_card_toggled); self.cards[int(s["index"])]=card; sg.addWidget(card, i//4, i%4)
        scroll.setWidget(box); self.advanced_scroll=scroll; self.advanced_scroll.setVisible(False); lay.addWidget(scroll,1)
        return panel
    def _build_right(self):
        panel,lay=self._panel("03 输出 / 任务队列")
        self.pipeline_radio=QRadioButton("顺序流水线处理，最终只输出一个文件")
        self.pipeline_radio.setChecked(True)
        self.pipeline_radio.setVisible(False)
        row=QHBoxLayout(); row.addWidget(QLabel("输出格式：")); self.format_combo=QComboBox(); self.format_combo.addItems(["WAV", "小体积MP3"]); self.format_combo.setToolTip("WAV 保留最高质量；小体积MP3 会控制体积，适合需要快速上传或试听的场景。"); row.addWidget(self.format_combo); row.addWidget(QLabel("并发数：")); self.worker_spin=QSpinBox(); self.worker_spin.setRange(1,4); self.worker_spin.setValue(3); row.addWidget(self.worker_spin); row.addStretch(1); lay.addLayout(row)
        out=QHBoxLayout(); out.addWidget(QLabel("输出目录：")); self.out_edit=QLineEdit(str(self.output_dir)); out.addWidget(self.out_edit,1); browse=QPushButton("浏览"); browse.clicked.connect(self.choose_output_dir); out.addWidget(browse); lay.addLayout(out)
        self.start_btn=QPushButton("按当前方案开始"); self.start_btn.setObjectName("primary"); self.stop_btn=QPushButton("停止队列"); self.stop_btn.setObjectName("danger"); self.open_dir_btn=QPushButton("打开输出目录")
        self.start_btn.clicked.connect(self.start_processing); self.stop_btn.clicked.connect(self.stop_processing); self.open_dir_btn.clicked.connect(self.open_output_dir)
        lay.addWidget(self.start_btn); lay.addWidget(self.stop_btn); lay.addWidget(self.open_dir_btn); lay.addWidget(QLabel("任务进度")); self.progress=QProgressBar(); lay.addWidget(self.progress); self.status=QLabel("等待任务"); self.status.setObjectName("muted"); lay.addWidget(self.status); lay.addWidget(QLabel("运行日志")); self.log_box=QTextEdit(); self.log_box.setReadOnly(True); lay.addWidget(self.log_box,1); return panel
    def log(self,msg):
        if hasattr(self,"log_box"): self.log_box.append(f"[{time.strftime('%H:%M:%S')}] {msg}")
    def refresh_license(self):
        ok,msg,_=local_status(); self.lic_label.setText(msg); self.lic_label.setStyleSheet("color:#25e986;font-weight:800;" if ok else "color:#ff6b6b;font-weight:800;")
    def show_license_dialog(self):
        ok,msg,_=online_verify()
        prompt = f"当前状态：{msg}\n\n输入新的卡密即可续费。续费会绑定当前设备，不支持解绑换机。"
        new_key, accepted = QInputDialog.getText(self, "授权 / 续期", prompt)
        if not accepted or not new_key.strip():
            QMessageBox.information(self, "授权状态", msg)
            self.refresh_license()
            return
        success, text, _payload = activate_license(new_key.strip())
        if success:
            QMessageBox.information(self, "续费成功", text)
        else:
            QMessageBox.warning(self, "续费失败", text)
        self.refresh_license()
    def show_contact_dialog(self):
        QMessageBox.information(self, "问题咨询", CONTACT_TEXT)

    def show_intro_once(self):
        marker = app_data_dir() / f"intro_seen_{APP_VERSION}.txt"
        if marker.exists():
            return
        QMessageBox.information(self, "使用说明", INTRO_TEXT)
        marker.write_text(str(time.time()), encoding="utf-8")
    def check_update_silently(self):
        def worker():
            try:
                ready, version, show_ui = prepare_update(APP_VERSION, progress=lambda p, t: self.update_progress.emit(int(p), str(t)))
            except Exception:
                return
            if ready:
                if show_ui:
                    self.update_ready.emit(version)
                else:
                    self.update_ready_silent.emit(version)
        threading.Thread(target=worker, daemon=True).start()
    def notify_update_progress(self, value: int, text: str):
        if self.update_dialog is None:
            self.update_dialog = QProgressDialog("正在检查自动更新", None, 0, 100, self)
            self.update_dialog.setWindowTitle("自动更新")
            self.update_dialog.setCancelButton(None)
            self.update_dialog.setAutoClose(False)
            self.update_dialog.setAutoReset(False)
            self.update_dialog.setMinimumDuration(0)
        self.update_dialog.setLabelText(text or "正在下载自动更新")
        self.update_dialog.setValue(max(0, min(100, int(value))))
        self.update_dialog.show()
    def notify_update_ready(self, version: str):
        if self.update_dialog is not None:
            self.update_dialog.setValue(100)
            self.update_dialog.close()
            self.update_dialog = None
        QMessageBox.information(
            self,
            "自动更新已准备",
            f"发现新版 {version}，更新包已下载。关闭当前软件后会自动替换并重新打开。",
        )
    def notify_update_ready_silent(self, version: str):
        if self.update_dialog is not None:
            self.update_dialog.close()
            self.update_dialog = None
        self.log(f"后台已准备新版 {version}，关闭软件后自动替换。")
    def add_files(self):
        files,_=QFileDialog.getOpenFileNames(self,"选择音频",str(Path.home()),"Audio Files (*.mp3 *.wav)"); self.add_paths(files)
    def add_folder(self):
        d=QFileDialog.getExistingDirectory(self,"选择文件夹",str(Path.home()));
        if d: self.add_paths([d])
    def add_paths(self,paths):
        new=collect_audio_files(paths); old={str(p).lower() for p in self.files}
        wav_count = len([p for p in new if p.suffix.lower() == ".wav"])
        if wav_count:
            self.log(f"已导入 WAV：{wav_count} 个。建议使用轻处理方案，避免跑调或曲谱受损。")
        for f in new:
            if str(f).lower() not in old: self.files.append(f); old.add(str(f).lower())
        self.refresh_file_list();
        if new: self.log(f"导入音频：新增 {len(new)} 个")
    def _feature_files(self) -> list[Path]:
        if self.files:
            return list(self.files)
        files,_=QFileDialog.getOpenFileNames(self,"选择 MP3",str(Path.home()),"MP3 Audio (*.mp3)")
        return [Path(f) for f in files]
    def start_master_feature(self):
        ok,msg,_=online_verify()
        if not ok:
            QMessageBox.warning(self,"需要激活","请先输入卡密激活。"); return
        files = self._feature_files()
        if not files:
            return
        style_label, accepted = QInputDialog.getItem(self, "智能母音升级", "处理风格：", ["自然精修", "柔和保真", "精细整理"], 0, False)
        if not accepted:
            return
        style = {"自然精修": "natural", "柔和保真": "soft", "精细整理": "detect"}.get(style_label, "natural")
        self.start_btn.setEnabled(False); self.progress.setValue(0)
        self.worker=FeatureWorker("master", files, Path(self.out_edit.text()).resolve(), style)
        self.worker.log.connect(self.log); self.worker.progress.connect(lambda p,s:(self.progress.setValue(p),self.status.setText(s)))
        self.worker.finishedOk.connect(self.on_finished); self.worker.failed.connect(self.on_failed); self.worker.start()
    def apply_builtin_combo(self, ids: list[int], label: str):
        self.selected_category = None
        self.selected_variants = None
        self.selected_order = [int(x) for x in ids if int(x) in SCHEME_BY_ID]
        for btn in getattr(self, "category_buttons", {}).values():
            btn.setObjectName("")
            btn.style().unpolish(btn); btn.style().polish(btn)
        if hasattr(self, "category_desc"):
            self.category_desc.setText("已切到手动 / 自定义组合。")
        self.refresh_order_ui()
        self.log(f"已选择{label}：方案 {'-'.join(map(str, self.selected_order))}")
    def apply_category_template(self, code: str):
        preset = CATEGORY_PRESETS.get(code)
        if not preset:
            return
        self.selected_category = code
        self.selected_variants = None
        self.selected_order = list(preset["schemes"])
        fmt = str(preset.get("format") or "WAV").upper()
        for i in range(self.format_combo.count()):
            if self.format_combo.itemText(i).upper().startswith(fmt):
                self.format_combo.setCurrentIndex(i)
                break
        self.category_desc.setText(f"{preset['name']}：{preset['desc']}｜方案 {'-'.join(map(str, self.selected_order))}｜输出 {fmt}")
        for c, btn in self.category_buttons.items():
            btn.setObjectName("primary" if c == code else "")
            btn.style().unpolish(btn); btn.style().polish(btn)
        self.refresh_order_ui()
        self.log(f"已应用分类推荐：{preset['name']}，方案 {'-'.join(map(str, self.selected_order))}，输出 {fmt}")
    def toggle_advanced_schemes(self):
        visible = not self.advanced_scroll.isVisible()
        self.advanced_scroll.setVisible(visible)
        self.advanced_toggle.setText("收起高级方案" if visible else "展开高级方案")
    def refresh_file_list(self):
        self.file_list.clear(); total=0; dur=0
        for f in self.files:
            info=self.engine.probe(f); total+=info.size; dur+=info.duration
            item=QListWidgetItem(f"♫  {f.name}        {format_duration(info.duration)}        {format_size(info.size)}"); item.setData(Qt.UserRole,str(f)); self.file_list.addItem(item)
        self.file_count.setText(f"共 {len(self.files)} 个文件（{format_size(total)}）      总时长 {format_duration(dur)}")
    def clear_files(self): self.files.clear(); self.refresh_file_list()
    def remove_selected(self):
        rows=sorted([i.row() for i in self.file_list.selectedIndexes()], reverse=True)
        for r in rows:
            if 0<=r<len(self.files): self.files.pop(r)
        self.refresh_file_list()
    def refresh_order_ui(self):
        self.seq_list.clear()
        if self.selected_variants:
            self.order_edit.setText(" / ".join("-".join(map(str,v)) for v in self.selected_variants)+"（三版候选）")
            for i,variant in enumerate(self.selected_variants,1):
                names=" → ".join(SCHEME_BY_ID[sid]["name"] for sid in variant)
                self.seq_list.addItem(f"{i:02d}.  {'-'.join(map(str,variant))}  {names}")
            used={sid for variant in self.selected_variants for sid in variant}
            for sid,card in self.cards.items(): card.set_checked(sid in used)
            return
        self.order_edit.setText("-".join(map(str,self.selected_order))+"（只读）")
        self.seq_list.clear()
        for i,sid in enumerate(self.selected_order,1):
            s=SCHEME_BY_ID[sid]; self.seq_list.addItem(f"{i:02d}.  {sid:02d}  方案{sid:02d}｜{s['name']}")
        for sid,card in self.cards.items(): card.set_checked(sid in self.selected_order)
    def on_card_toggled(self,sid,checked):
        self.selected_variants=None
        if self.selected_category:
            self.selected_category=None
            if hasattr(self, "category_desc"):
                self.category_desc.setText("已切回手动方案：按当前勾选顺序处理，最终只输出一个文件。")
            for btn in getattr(self, "category_buttons", {}).values():
                btn.setObjectName("")
                btn.style().unpolish(btn); btn.style().polish(btn)
        if checked:
            if sid not in self.selected_order: self.selected_order.append(sid)
        else: self.selected_order=[x for x in self.selected_order if x!=sid]
        self.refresh_order_ui()
    def move_selected(self,delta):
        self.selected_variants=None
        row=self.seq_list.currentRow(); new=row+delta
        if row<0 or new<0 or new>=len(self.selected_order): return
        self.selected_order[row],self.selected_order[new]=self.selected_order[new],self.selected_order[row]; self.refresh_order_ui(); self.seq_list.setCurrentRow(new)
    def remove_scheme_from_order(self):
        self.selected_variants=None
        row=self.seq_list.currentRow()
        if row>=0: self.selected_order.pop(row); self.refresh_order_ui()
    def choose_output_dir(self):
        d=QFileDialog.getExistingDirectory(self,"选择输出目录",self.out_edit.text())
        if d: self.out_edit.setText(d)
    def open_output_dir(self):
        import os
        p=Path(self.out_edit.text()).resolve(); p.mkdir(parents=True,exist_ok=True)
        if sys.platform.startswith("win"): os.startfile(str(p))
    def start_processing(self):
        ok,msg,_=online_verify()
        if not ok: QMessageBox.warning(self,"需要激活","请先输入卡密激活。"); return
        if not self.files: QMessageBox.warning(self,"缺少素材","请先添加或拖拽音频。"); return
        if not self.selected_order: QMessageBox.warning(self,"缺少方案","请至少选择一个方案。"); return
        out=Path(self.out_edit.text()).resolve(); mode="pipeline"; workers=self.worker_spin.value(); self.start_btn.setEnabled(False); self.progress.setValue(0)
        fmt = "mp3" if self.format_combo.currentText().upper().startswith("MP3") else "wav"
        self.worker=ProcessWorker(self.files,out,self.selected_order,fmt,mode,workers=workers,variants=None,platform_code=None); self.worker.log.connect(self.log); self.worker.progress.connect(lambda p,s:(self.progress.setValue(p),self.status.setText(s))); self.worker.finishedOk.connect(self.on_finished); self.worker.failed.connect(self.on_failed); self.worker.start()
    def stop_processing(self):
        if self.worker: self.worker.request_stop(); self.log("已请求停止。")
    def on_finished(self,count,out_dir):
        self.start_btn.setEnabled(True); self.progress.setValue(100); self.status.setText("全部任务完成")
        box=QMessageBox(self); box.setWindowTitle("处理完成"); box.setText(f"处理完成：已输出最终文件 {count} 个\n输出目录：{out_dir}"); open_btn=box.addButton("打开输出目录",QMessageBox.ActionRole); box.addButton("确定",QMessageBox.AcceptRole); box.exec();
        if box.clickedButton()==open_btn: self.open_output_dir()
    def on_failed(self,error):
        self.start_btn.setEnabled(True); self.status.setText("处理失败"); self.log("失败："+error); QMessageBox.critical(self,"处理失败",error)
    def convert_audio(self):
        files,_=QFileDialog.getOpenFileNames(self,"选择要转换的音频",str(Path.home()),"Audio Files (*.mp3 *.wav *.flac *.m4a *.aac *.ogg *.wma *.aiff *.aif)")
        if not files: return
        fmt,ok=QInputDialog.getItem(self,"选择格式","输出格式：",["WAV","MP3","FLAC"],0,False)
        if not ok: return
        engine=AudioEngine(log=self.log); out=Path(self.out_edit.text()).resolve(); done=0
        try:
            for f in files: engine.convert_format(Path(f),out,fmt); done+=1
            QMessageBox.information(self,"转换完成",f"已转换 {done} 个文件。")
        except Exception as e: QMessageBox.critical(self,"转换失败",str(e))
    def light_split(self):
        files,_=QFileDialog.getOpenFileNames(self,"选择要分轨的音频",str(Path.home()),"Audio Files (*.mp3 *.wav *.flac *.m4a *.aac *.ogg *.wma *.aiff *.aif)")
        if not files: return
        engine=AudioEngine(log=self.log); out=Path(self.out_edit.text()).resolve(); done=0
        try:
            for f in files: engine.light_split(Path(f),out); done+=1
            QMessageBox.information(self,"分轨完成",f"已输出 {done} 个文件的轻量人声/伴奏辅助分轨。\n说明：内置轻量分轨不是 Demucs 专业 AI 分轨，适合做基础预处理。")
        except Exception as e: QMessageBox.critical(self,"分轨失败",str(e))

def main():
    app=QApplication(sys.argv); app.setStyleSheet(QSS)
    icon_path = resource_path("assets/audioflow.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    guard_ok, guard_msg = runtime_guard_ok()
    if not guard_ok:
        QMessageBox.critical(None, "运行环境异常", guard_msg)
        return 1
    ok,_msg,_payload=local_status()
    if not ok:
        ok,_msg,_payload=online_verify()
    if not ok:
        dlg=ActivationDialog()
        if dlg.exec()!=QDialog.Accepted: return 0
    w=MainWindow(); w.show(); return app.exec()
if __name__=="__main__": raise SystemExit(main())
