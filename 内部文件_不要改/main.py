# -*- coding: utf-8 -*-
from __future__ import annotations

import marshal
import shutil
import sys
from pathlib import Path

# Keep these imports explicit so PyInstaller bundles the runtime modules that
# the restored compiled main program imports dynamically.
import engine  # noqa: F401
import license_client  # noqa: F401
import platform_presets  # noqa: F401
import schemes  # noqa: F401
import security_guard  # noqa: F401
import settings  # noqa: F401
import updater  # noqa: F401
from PySide6.QtCore import Qt  # noqa: F401
from PySide6.QtWidgets import QLabel, QFrame, QWidget


AUDIO_EXTS = {
    ".mp3",
    ".wav",
    ".flac",
    ".m4a",
    ".aac",
    ".ogg",
    ".wma",
    ".aiff",
    ".aif",
    ".ape",
    ".alac",
}
AUDIO_FILTER = (
    "Audio Files (*.mp3 *.wav *.flac *.m4a *.aac *.ogg *.wma *.aiff *.aif *.ape *.alac)"
)


def _resource_path(relative: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative
    return Path(__file__).resolve().parent / relative


def _load_main_namespace() -> dict:
    base = _resource_path("")
    if str(base) not in sys.path:
        sys.path.insert(0, str(base))
    code = marshal.loads(_resource_path("main.raw").read_bytes())
    namespace = {
        "__name__": "audioflow_restored_v367",
        "__file__": str(_resource_path("main.raw")),
        "__package__": None,
    }
    exec(code, namespace)
    return namespace


def _find_category_box(window) -> QWidget | None:
    desc = getattr(window, "category_desc", None)
    parent = desc.parentWidget() if desc is not None else None
    while parent is not None:
        if isinstance(parent, QFrame) and parent.objectName() == "card":
            return parent
        parent = parent.parentWidget()
    return None


def _patch_scheme_card(namespace: dict) -> None:
    scheme_card = namespace.get("SchemeCard")
    if scheme_card is None:
        return
    original_init = scheme_card.__init__

    def compact_init(self, scheme, selected):
        original_init(self, scheme, selected)
        self.setMinimumHeight(96)
        self.setMaximumHeight(118)
        for label in self.findChildren(QLabel):
            name = label.objectName()
            if name == "muted":
                label.setMaximumHeight(30)
                label.setWordWrap(True)
            elif name == "blue":
                label.setMaximumHeight(20)

    scheme_card.__init__ = compact_init


def _iter_audio_files(paths) -> list[Path]:
    result: list[Path] = []
    for raw in paths or []:
        text = str(raw or "").strip().strip('"')
        if not text:
            continue
        path = Path(text).expanduser()
        if path.is_file():
            if path.suffix.lower() in AUDIO_EXTS:
                result.append(path)
            continue
        if path.is_dir():
            for child in path.rglob("*"):
                if child.is_file() and child.suffix.lower() in AUDIO_EXTS:
                    result.append(child)
    return result


def _patch_import_flow(namespace: dict) -> None:
    settings.SUPPORTED_AUDIO_EXTS = set(AUDIO_EXTS)
    if hasattr(engine, "SUPPORTED_AUDIO_EXTS"):
        engine.SUPPORTED_AUDIO_EXTS = set(AUDIO_EXTS)
    namespace["collect_audio_files"] = _iter_audio_files

    drop_area = namespace.get("DropArea")
    if drop_area is not None:
        original_drop_init = drop_area.__init__

        def drop_init(self):
            original_drop_init(self)
            self.setMinimumHeight(132)
            for label in self.findChildren(QLabel):
                if "MP3" in label.text() or "WAV" in label.text():
                    label.setText("支持 MP3 / WAV / FLAC / M4A 等音频\n处理时自动转换，最终导出 WAV 成品")

        drop_area.__init__ = drop_init

    main_window = namespace.get("MainWindow")
    if main_window is None:
        return

    def add_files(self):
        files, _ = namespace["QFileDialog"].getOpenFileNames(
            self,
            "选择音频文件",
            str(Path.home()),
            AUDIO_FILTER,
        )
        self.add_paths(files)

    def add_paths(self, paths):
        new = _iter_audio_files(paths)
        old = {str(path).lower() for path in self.files}
        added = 0
        for file in new:
            key = str(file).lower()
            if key in old:
                continue
            self.files.append(file)
            old.add(key)
            added += 1
        self.refresh_file_list()
        if added:
            self.log(f"导入音频：新增 {added} 个")

    main_window.add_files = add_files
    main_window.add_paths = add_paths


def _replace_audio_file(engine_obj, source: Path, filter_args: list[str], desc: str) -> None:
    source = Path(source)
    tmp = source.with_name(source.stem + "_qai_light_tmp" + source.suffix)
    try:
        codec_args = engine_obj._codec_args_for_output(tmp)
    except TypeError:
        codec_args = engine_obj._codec_args_for_output(
            tmp,
            source.suffix.lower().lstrip(".") or "wav",
        )
    args = [
        engine_obj.ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        source,
        "-vn",
        *filter_args,
        "-ar",
        "48000",
        "-ac",
        "2",
        "-map_metadata",
        "-1",
        *codec_args,
        tmp,
    ]
    engine_obj._run(args, desc, capture=False)
    if not tmp.exists() or tmp.stat().st_size < 1024:
        try:
            tmp.unlink(missing_ok=True)
        except TypeError:
            if tmp.exists():
                tmp.unlink()
        raise RuntimeError(desc + " did not create a valid file")
    shutil.move(str(tmp), str(source))


def _patch_audio_chain() -> None:
    engine_cls = getattr(engine, "AudioEngine", None)
    if engine_cls is None:
        return
    original_legacy_final_master = engine_cls._apply_legacy_final_master
    original_scheme9_tone_match = engine_cls._apply_legacy_scheme9_tone_match
    original_legacy_step_enhance = engine_cls._apply_legacy_step_enhance
    original_multiband_natural_polish = engine_cls._apply_multiband_natural_polish
    original_reserve_output_headroom = engine_cls._reserve_output_headroom

    def legacy_final_master(self, out_file):
        light_filter = (
            "highpass=f=30,"
            "equalizer=f=45:g=-2.4:width_type=h:width=42,"
            "equalizer=f=85:g=0.55:width_type=h:width=75,"
            "equalizer=f=165:g=0.35:width_type=h:width=130,"
            "equalizer=f=520:g=0.20:width_type=h:width=420,"
            "equalizer=f=3200:g=0.55:width_type=h:width=2400,"
            "equalizer=f=7800:g=0.30:width_type=h:width=4200,"
            "equalizer=f=15000:g=-0.20:width_type=h:width=5200,"
            "volume=0.45dB,"
            "alimiter=limit=0.990:level=false"
        )
        _replace_audio_file(self, Path(out_file), ["-af", light_filter], "light final master")

    def scheme9_tone_match(self, out_file):
        light_filter = (
            "highpass=f=30,"
            "equalizer=f=45:g=-2.8:width_type=h:width=42,"
            "equalizer=f=85:g=0.65:width_type=h:width=75,"
            "equalizer=f=180:g=0.45:width_type=h:width=140,"
            "equalizer=f=850:g=0.20:width_type=h:width=700,"
            "equalizer=f=3200:g=0.45:width_type=h:width=2200,"
            "equalizer=f=8000:g=0.25:width_type=h:width=4200,"
            "stereotools=slev=1.01,"
            "volume=0.35dB,"
            "alimiter=limit=0.990:level=false"
        )
        _replace_audio_file(self, Path(out_file), ["-af", light_filter], "scheme 9 light tone match")

    def multiband_natural_polish(self, out_file, mode="balanced"):
        mode_name = str(mode or "balanced").strip().lower()
        if mode_name == "none":
            self.log("最终保真收尾：单方案轻修，跳过多频段重组")
            return
        light_filter = (
            "highpass=f=30,"
            "lowpass=f=19000,"
            "equalizer=f=45:g=-1.8:width_type=h:width=42,"
            "equalizer=f=90:g=0.35:width_type=h:width=80,"
            "equalizer=f=250:g=0.20:width_type=h:width=180,"
            "equalizer=f=3200:g=0.20:width_type=h:width=2200,"
            "equalizer=f=8200:g=0.12:width_type=h:width=4200,"
            "acompressor=threshold=-18dB:ratio=1.03:attack=35:release=260:makeup=1.0,"
            "alimiter=limit=0.990:level=false"
        )
        _replace_audio_file(self, Path(out_file), ["-af", light_filter], "light natural polish")

    def reserve_output_headroom(self, out_file, mode="balanced"):
        reference_tone_filter = (
            "highpass=f=38,"
            "equalizer=f=45:g=-6.8:width_type=h:width=42,"
            "equalizer=f=90:g=-0.9:width_type=h:width=75,"
            "equalizer=f=170:g=0.8:width_type=h:width=130,"
            "equalizer=f=2800:g=1.2:width_type=h:width=1500,"
            "equalizer=f=3600:g=3.2:width_type=h:width=2400,"
            "equalizer=f=8500:g=-7.0:width_type=h:width=4200,"
            "equalizer=f=12500:g=-11.0:width_type=h:width=5000,"
            "equalizer=f=16000:g=-12.0:width_type=h:width=5200,"
            "lowpass=f=17800,"
            "volume=2.50dB,"
            "alimiter=limit=0.980:level=false,"
            "equalizer=f=45:g=-1.2:width_type=h:width=42,"
            "equalizer=f=650:g=-0.8:width_type=h:width=600,"
            "equalizer=f=1500:g=-1.9:width_type=h:width=1200,"
            "equalizer=f=6500:g=-0.9:width_type=h:width=3000,"
            "equalizer=f=9500:g=-2.0:width_type=h:width=4200,"
            "equalizer=f=14500:g=-4.0:width_type=h:width=5200,"
            "lowpass=f=19000,"
            "volume=0.65dB"
        )
        complex_filter = (
            f"[0:a]{reference_tone_filter}[a];"
            "anoisesrc=color=white:amplitude=0.00055:sample_rate=48000[n];"
            "[n]highpass=f=17800,lowpass=f=22000[n2];"
            "[a][n2]amix=inputs=2:duration=first:weights='1 1':normalize=0,"
            "alimiter=limit=0.985:level=false[contour];"
            "[contour]aexciter=amount=0.38:drive=2.7:blend=0.032:freq=2600:ceil=15500,"
            "crystalizer=i=0.065:c=0,"
            "aecho=0.82:0.90:14:0.018,"
            "stereotools=slev=1.025[detail];"
            "anoisesrc=color=pink:amplitude=0.00020:sample_rate=48000[pn];"
            "[pn]highpass=f=160,lowpass=f=17000[pn2];"
            "[detail][pn2]amix=inputs=2:duration=first:weights='1 1':normalize=0,"
            "volume=2.38dB,"
            "alimiter=limit=0.985:level=false[out]"
        )
        _replace_audio_file(
            self,
            Path(out_file),
            ["-filter_complex", complex_filter, "-map", "[out]"],
            "final spectral contour",
        )

    def restored_multiband_natural_polish(self, out_file, mode="balanced"):
        mode_name = str(mode or "balanced").strip().lower()
        if mode_name == "none":
            self.log("final natural polish: skip extra multiband for single scheme")
            return
        original_multiband_natural_polish(self, out_file, mode_name)

    def restored_legacy_step_enhance(self, out_path, scheme, tmp_dir):
        try:
            scheme_id = int(scheme.get("index", 0))
        except Exception:
            scheme_id = 0
        if scheme_id >= 10:
            self.log(f"scheme {scheme_id:02d}: skip legacy noise layer")
            return out_path
        return original_legacy_step_enhance(self, out_path, scheme, tmp_dir)

    def restored_reserve_output_headroom(self, out_file, mode="balanced"):
        mode_name = str(mode or "balanced").strip().lower()
        original_reserve_output_headroom(self, out_file, mode)
        if mode_name == "vocal":
            qai_match_filter = (
                "highpass=f=38,"
                "equalizer=f=52:g=-5.6:width_type=h:width=40,"
                "equalizer=f=112:g=7.5:width_type=h:width=90,"
                "equalizer=f=170:g=0.8:width_type=h:width=130,"
                "equalizer=f=320:g=-1.0:width_type=h:width=220,"
                "equalizer=f=720:g=-0.9:width_type=h:width=520,"
                "equalizer=f=1700:g=-0.8:width_type=h:width=1200,"
                "equalizer=f=3900:g=1.9:width_type=h:width=2200,"
                "equalizer=f=7800:g=-9.2:width_type=h:width=4400,"
                "lowpass=f=14500,"
                "stereotools=slev=1.00,"
                "crystalizer=i=0.030:c=0,"
                "compand=attacks=0.022:decays=0.260:"
                "points=-80/-80|-36/-31.5|-22/-17|-10/-7.4|0/-1.2:"
                "soft-knee=5:gain=0.2,"
                "volume=1.0dB,"
                "alimiter=limit=0.940:level=false"
            )
            _replace_audio_file(
                self,
                Path(out_file),
                ["-af", qai_match_filter],
                "vocal 1-9 QAI tone match",
            )
            return
        _replace_audio_file(
            self,
            Path(out_file),
            ["-af", "alimiter=limit=0.985:level=false"],
            "final safety limiter",
        )

    engine_cls._apply_legacy_final_master = original_legacy_final_master
    engine_cls._apply_legacy_scheme9_tone_match = original_scheme9_tone_match
    engine_cls._apply_legacy_step_enhance = restored_legacy_step_enhance
    engine_cls._apply_multiband_natural_polish = restored_multiband_natural_polish
    engine_cls._reserve_output_headroom = restored_reserve_output_headroom


def _patch_main_window(namespace: dict) -> None:
    main_window = namespace.get("MainWindow")
    if main_window is None:
        return

    original_fit = main_window._fit_initial_window

    def fit_initial_window(self):
        try:
            screen = self.screen() or namespace["QApplication"].primaryScreen()
            available = screen.availableGeometry()
            width = min(1320, max(1080, int(available.width() * 0.9)))
            height = min(860, max(700, int(available.height() * 0.88)))
            width = min(width, max(960, available.width() - 40))
            height = min(height, max(620, available.height() - 60))
            self.setMinimumSize(960, 620)
            self.resize(width, height)
            frame = self.frameGeometry()
            frame.moveCenter(available.center())
            self.move(frame.topLeft())
        except Exception:
            original_fit(self)

    def build_middle(self):
        QHBoxLayout = namespace["QHBoxLayout"]
        QVBoxLayout = namespace["QVBoxLayout"]
        QGridLayout = namespace["QGridLayout"]
        QLineEdit = namespace["QLineEdit"]
        QListWidget = namespace["QListWidget"]
        QPushButton = namespace["QPushButton"]
        QScrollArea = namespace["QScrollArea"]
        QtObj = namespace["Qt"]
        SchemeCard = namespace["SchemeCard"]

        panel, lay = self._panel("02 AI歌曲真人化｜顺序方案库")

        order_box = QFrame()
        order_box.setObjectName("card")
        ol = QVBoxLayout(order_box)
        ol.setContentsMargins(10, 8, 10, 8)
        ol.setSpacing(6)

        order = QHBoxLayout()
        order.addWidget(QLabel("已选顺序："))
        self.order_edit = QLineEdit()
        self.order_edit.setReadOnly(True)
        order.addWidget(self.order_edit, 1)
        ol.addLayout(order)

        seq = QHBoxLayout()
        self.seq_list = QListWidget()
        self.seq_list.setMaximumHeight(92)
        seq.addWidget(self.seq_list, 1)
        col = QVBoxLayout()
        for text, cb in (
            ("上移", lambda: self.move_selected(-1)),
            ("下移", lambda: self.move_selected(1)),
            ("移除", self.remove_scheme_from_order),
        ):
            b = QPushButton(text)
            b.clicked.connect(cb)
            col.addWidget(b)
        col.addStretch(1)
        seq.addLayout(col)
        ol.addLayout(seq)
        lay.addWidget(order_box)

        self.category_desc = QLabel("")
        self.category_desc.setVisible(False)

        adv_head = QHBoxLayout()
        adv_title = QLabel(f"方案库（{len(namespace['DISPLAY_SCHEMES'])} 套完整方案）")
        adv_title.setObjectName("muted")
        adv_head.addWidget(adv_title)
        adv_head.addStretch(1)
        lay.addLayout(adv_head)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtObj.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setFocusPolicy(QtObj.NoFocus)
        scroll.viewport().setStyleSheet("background:#071426;border:0;")
        scroll.setMinimumHeight(250)

        box = QWidget()
        box.setStyleSheet("background:#071426;border:0;")
        sg = QGridLayout(box)
        sg.setSpacing(10)
        sg.setContentsMargins(0, 0, 0, 0)
        self.cards.clear()
        for i, scheme in enumerate(namespace["DISPLAY_SCHEMES"]):
            card = SchemeCard(scheme, int(scheme["index"]) in self.selected_order)
            card.setFocusPolicy(QtObj.NoFocus)
            card.toggled.connect(self.on_card_toggled)
            self.cards[int(scheme["index"])] = card
            sg.addWidget(card, i // 3, i % 3)

        scroll.setWidget(box)
        self.advanced_scroll = scroll
        self.advanced_scroll.setVisible(True)
        lay.addWidget(scroll, 1)
        return panel

    def apply_category_template(self, code):
        preset = namespace["CATEGORY_PRESETS"].get(code) or namespace["CATEGORY_PRESETS"].get("POP")
        if not preset:
            return
        self.selected_category = code
        self.selected_variants = None
        self.selected_order = list(preset["schemes"])
        self.format_combo.setCurrentIndex(0)
        self.refresh_order_ui()
        self.log(
            "已恢复默认方案："
            + "-".join(map(str, self.selected_order))
            + "，输出 WAV"
        )

    main_window._fit_initial_window = fit_initial_window
    main_window._build_middle = build_middle
    main_window.apply_category_template = apply_category_template


def _apply_runtime_patches(namespace: dict) -> None:
    _patch_scheme_card(namespace)
    _patch_import_flow(namespace)
    _patch_audio_chain()
    _patch_main_window(namespace)


def _self_test(namespace: dict) -> int:
    missing = [
        name
        for name in ("MainWindow", "DropArea", "DISPLAY_SCHEMES", "main")
        if name not in namespace
    ]
    unsupported = sorted(AUDIO_EXTS - set(getattr(settings, "SUPPORTED_AUDIO_EXTS", set())))
    if unsupported:
        missing.append("unsupported audio extensions: " + ", ".join(unsupported))
    audio_engine = getattr(engine, "AudioEngine", None)
    if audio_engine is None:
        missing.append("AudioEngine")
    else:
        ok, msg = audio_engine().validate()
        if not ok:
            missing.append(msg)
    if missing:
        print("SELF_TEST_FAIL: " + " | ".join(missing))
        return 2
    print("SELF_TEST_OK: AudioFlow Studio 3.6.7")
    return 0


def main() -> int:
    namespace = _load_main_namespace()
    namespace["INTRO_TEXT"] = (
        "使用说明\n\n"
        "1. 添加歌曲：支持 MP3 / WAV / FLAC / M4A 等常见音频，处理时自动转换，最终统一导出 WAV。\n"
        "2. 方案库：按需要手动勾选方案，右侧会显示当前处理顺序。\n"
        "3. 处理顺序：方案会按顺序逐步处理同一首歌，最终只输出一个成品文件。\n"
        "4. 组合方案：建议先少量测试，再按歌曲情况叠加，避免过度处理导致细节变平。\n"
        "5. 输出位置：处理完成后可直接打开输出目录查看成品。\n\n"
        "问题咨询：Zhwdh141319\n"
        "添加时备注：AI原创\n"
        "不懂的可以关注我的公众号：山河网创笔记\n"
    )
    _apply_runtime_patches(namespace)
    if "--self-test" in sys.argv:
        return _self_test(namespace)
    return int(namespace["main"]() or 0)


if __name__ == "__main__":
    raise SystemExit(main())
