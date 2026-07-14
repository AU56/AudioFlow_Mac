from __future__ import annotations

from pathlib import Path

from raw_loader import exec_raw


_entry_module_name = __name__
try:
    globals()["__name__"] = "main"
    exec_raw("main.raw", globals())
finally:
    globals()["__name__"] = _entry_module_name

try:
    QSizePolicy
except NameError:
    from PySide6.QtWidgets import QSizePolicy


_raw_init = MainWindow.__init__
_raw_build_middle = MainWindow._build_middle
_raw_choose_output_dir = MainWindow.choose_output_dir
_raw_start_processing = MainWindow.start_processing
_raw_open_output_dir = MainWindow.open_output_dir
_raw_show = MainWindow.show
_raw_worker_run = ProcessWorker.run


def _size_policy(name):
    policy = getattr(QSizePolicy, "Policy", QSizePolicy)
    return getattr(policy, name)


def _short_output_path(text, max_chars=34):
    text = str(text or "")
    if len(text) <= max_chars:
        return text
    try:
        path = Path(text)
        drive = path.drive
        name = path.name
        if drive and name:
            return f"{drive}\\...\\{name}"
    except Exception:
        pass
    keep_tail = max(12, max_chars - 14)
    return f"{text[:10]}...{text[-keep_tail:]}"


def _force_audioflow_icon(self):
    try:
        icon = QIcon(str(resource_path("assets/audioflow.ico")))
        if icon.isNull():
            icon = QIcon(str(resource_path("assets/app_icon.ico")))
        if icon.isNull():
            icon = QIcon(str(Path(__file__).resolve().parent / "app_icon.ico"))
        if not icon.isNull():
            self.setWindowIcon(icon)
            app = QApplication.instance()
            if app is not None:
                app.setWindowIcon(icon)
    except Exception:
        pass


def _init_with_icon(self, *args, **kwargs):
    _raw_init(self, *args, **kwargs)
    _force_audioflow_icon(self)


def _hide_style_strategy_entry(self):
    try:
        self.advanced_scroll.setVisible(True)
        self.advanced_toggle.setVisible(False)
    except Exception:
        pass

    try:
        for button in self.category_buttons.values():
            box = button.parentWidget()
            while box is not None and box.objectName() != "card":
                box = box.parentWidget()
            if box is not None:
                box.setVisible(False)
                box.setMaximumHeight(0)
                box.setMinimumHeight(0)
                break
    except Exception:
        pass

    try:
        self.category_desc.setVisible(False)
        self.category_desc.setMaximumHeight(0)
        self.category_desc.setMinimumHeight(0)
    except Exception:
        pass


def _compact_scheme_grid(self):
    try:
        scroll = getattr(self, "advanced_scroll", None)
        if scroll is None:
            return
        box = scroll.widget()
        if box is None or box.layout() is None:
            return
        layout = box.layout()
        cards = getattr(self, "cards", None)
        if not cards:
            return

        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(10)
        try:
            layout.setContentsMargins(0, 0, 0, 0)
        except Exception:
            pass

        for col in range(3):
            try:
                layout.setColumnStretch(col, 1)
            except Exception:
                pass

        for idx, sid in enumerate(sorted(cards)):
            card = cards[sid]
            layout.addWidget(card, idx // 3, idx % 3)
            try:
                card.setMinimumWidth(0)
                card.setMinimumHeight(128)
                card.setSizePolicy(_size_policy("Expanding"), _size_policy("Preferred"))
            except Exception:
                pass
            try:
                card.setMaximumWidth(16777215)
            except Exception:
                pass
            try:
                for label in card.findChildren(QLabel):
                    if label.objectName() == "muted" and label.wordWrap():
                        label.setMaximumHeight(60)
            except Exception:
                pass
    except Exception:
        pass


def _fix_output_path_display(self):
    try:
        text = str(self.out_edit.text() or "")
        stored = str(getattr(self, "_output_path_full", "") or "")
        if stored and text == _short_output_path(stored):
            text = stored
        if text:
            self._output_path_full = text
            self.out_edit.setToolTip(text)
            display = _short_output_path(text)
            if self.out_edit.text() != display:
                self.out_edit.setText(display)
            self.out_edit.setCursorPosition(0)
            self.out_edit.setMinimumWidth(max(self.out_edit.minimumWidth(), 240))
            self.out_edit.setSizePolicy(_size_policy("Expanding"), _size_policy("Fixed"))
            try:
                self.out_edit.home(False)
            except Exception:
                pass
    except Exception:
        pass


def _init_with_ui_tweaks(self, *args, **kwargs):
    _raw_init(self, *args, **kwargs)
    _force_audioflow_icon(self)
    try:
        self._ui_tweaks_applied = False
    except Exception:
        pass
    _schedule_ui_tweaks(self)


def _build_middle_without_style_shortcuts(self):
    panel = _raw_build_middle(self)
    _hide_style_strategy_entry(self)
    _compact_scheme_grid(self)
    return panel


def _disable_style_shortcut_toggle(self):
    _hide_style_strategy_entry(self)
    _compact_scheme_grid(self)


def _choose_output_dir_with_head(self):
    _raw_choose_output_dir(self)
    _fix_output_path_display(self)


def _restore_output_path_for_action(self):
    try:
        text = str(self.out_edit.text() or "")
        stored = str(getattr(self, "_output_path_full", "") or "")
        if stored and text == _short_output_path(stored):
            text = stored
        if text:
            self._output_path_full = text
            self.out_edit.setText(text)
            self.out_edit.setToolTip(text)
            self.out_edit.setCursorPosition(0)
            try:
                self.output_dir = Path(text)
            except Exception:
                pass
    except Exception:
        pass


def _start_processing_with_full_path(self):
    _restore_output_path_for_action(self)
    try:
        return _raw_start_processing(self)
    finally:
        _fix_output_path_display(self)


def _open_output_dir_with_full_path(self):
    _restore_output_path_for_action(self)
    try:
        return _raw_open_output_dir(self)
    finally:
        _fix_output_path_display(self)


def _apply_post_show_ui_tweaks(self):
    _fix_output_path_display(self)
    _compact_scheme_grid(self)


def _schedule_ui_tweaks(self):
    _apply_post_show_ui_tweaks(self)
    for delay in (0, 120, 500):
        try:
            QTimer.singleShot(delay, lambda self=self: _apply_post_show_ui_tweaks(self))
        except Exception:
            pass


def _show_event_with_ui_tweaks(self, event):
    try:
        QMainWindow.showEvent(self, event)
    except Exception:
        pass
    try:
        if not getattr(self, "_ui_tweaks_applied", False):
            self._ui_tweaks_applied = True
            _schedule_ui_tweaks(self)
    except Exception:
        _apply_post_show_ui_tweaks(self)


def _show_with_ui_tweaks(self):
    result = _raw_show(self)
    _schedule_ui_tweaks(self)
    return result


def _run_worker_with_effective_threads(self):
    original_workers = getattr(self, "workers", 1)
    try:
        file_count = len(getattr(self, "files", []) or [])
        if file_count > 0:
            effective_workers = max(1, min(int(original_workers or 1), file_count))
            if effective_workers != original_workers:
                try:
                    self.log.emit(
                        f"\u6027\u80fd\u8c03\u5ea6\uff1a\u5f53\u524d {file_count} \u4e2a\u6587\u4ef6\uff0c\u81ea\u52a8\u628a\u5e76\u53d1\u4ece {original_workers} \u8c03\u6574\u4e3a {effective_workers}"
                    )
                except Exception:
                    pass
                self.workers = effective_workers
        return _raw_worker_run(self)
    finally:
        try:
            self.workers = original_workers
        except Exception:
            pass


ProcessWorker.run = _run_worker_with_effective_threads

MainWindow._build_middle = _build_middle_without_style_shortcuts
MainWindow.toggle_advanced_schemes = _disable_style_shortcut_toggle
MainWindow.choose_output_dir = _choose_output_dir_with_head
MainWindow.start_processing = _start_processing_with_full_path
MainWindow.open_output_dir = _open_output_dir_with_full_path
MainWindow.__init__ = _init_with_ui_tweaks
MainWindow.showEvent = _show_event_with_ui_tweaks
MainWindow.show = _show_with_ui_tweaks


if __name__ == "__main__":
    raise SystemExit(main())
