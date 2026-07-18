import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtCore, QtGui, QtTest, QtWidgets

from core.tasks import FileLoadTask
from main import application_icon
from models.view_data import ViewData
from ui.main_window import DICOMViewer


def url_drop_event(path):
    mime = QtCore.QMimeData()
    mime.setUrls([QtCore.QUrl.fromLocalFile(str(path))])
    event = QtGui.QDropEvent(
        QtCore.QPointF(20, 20),
        QtCore.Qt.DropAction.CopyAction,
        mime,
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
    )
    event._mime_data_ref = mime
    return event


class FinalPolishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_cadence_application_icon_is_bundled(self):
        self.assertFalse(application_icon().isNull())

    def test_window_title_uses_short_patient_name_and_iso_date(self):
        window = DICOMViewer(settings=False)
        self.assertEqual(window.windowTitle(), "Просмотр снимков")
        window.view_data[0] = ViewData(
            file_path=r"C:\study\image.dcm",
            patient_name="Иванова^Ирина^Ивановна",
            study_date="20240315",
        )
        window._study_title_context_active = True

        window._update_window_title()

        self.assertEqual(window.windowTitle(), "Просмотр снимков — Иванова И.И. — 2024-03-15")
        window.close()

    def test_first_run_welcome_is_shown_only_once(self):
        with tempfile.TemporaryDirectory(prefix="welcome settings ") as directory:
            settings_path = str(Path(directory) / "viewer.ini")
            first_settings = QtCore.QSettings(settings_path, QtCore.QSettings.Format.IniFormat)
            first_messages = []
            first = DICOMViewer(settings=first_settings)
            first._notify = lambda *args, **kwargs: first_messages.append((args, kwargs))
            first.show()
            QtTest.QTest.qWait(550)
            self.app.processEvents()

            self.assertEqual(len(first_messages), 1)
            self.assertEqual(first_messages[0][0][:3], (
                "info",
                "Добро пожаловать!",
                "Нажмите «Открыть папку», чтобы загрузить снимки.",
            ))
            first.close()

            restored_settings = QtCore.QSettings(settings_path, QtCore.QSettings.Format.IniFormat)
            restored_messages = []
            restored = DICOMViewer(settings=restored_settings)
            restored._notify = lambda *args, **kwargs: restored_messages.append((args, kwargs))
            restored.show()
            QtTest.QTest.qWait(550)
            self.app.processEvents()

            self.assertEqual(restored_messages, [])
            restored.close()

    def test_viewport_drop_loads_complete_parent_study(self):
        with tempfile.TemporaryDirectory(prefix="drop study ") as directory:
            root = Path(directory)
            first = root / "image_01.dcm"
            second = root / "image_02.dcm"
            ignored = root / "notes.txt"
            first.touch()
            second.touch()
            ignored.touch()
            loaded = []
            window = DICOMViewer(settings=False)
            window.load_files = lambda files: loaded.extend(files)
            event = url_drop_event(first)

            window.all_views[0].dropEvent(event)

            self.assertTrue(event.isAccepted())
            self.assertEqual({Path(path).name for path in loaded}, {first.name, second.name})
            self.assertEqual(window.last_opened_folder, str(root))
            window.close()

    def test_sidebar_drop_forwards_folder_to_main_window(self):
        with tempfile.TemporaryDirectory(prefix="sidebar drop ") as directory:
            root = Path(directory)
            dicom = root / "image.dcm"
            dicom.touch()
            loaded = []
            window = DICOMViewer(settings=False)
            window.load_files = lambda files: loaded.extend(files)
            event = url_drop_event(root)

            window.sidebar.list_view.dropEvent(event)

            self.assertTrue(event.isAccepted())
            self.assertEqual(loaded, [str(dicom)])
            window.close()

    def test_missing_folder_has_human_readable_warning(self):
        messages = []
        window = DICOMViewer(settings=False)
        window._notify = lambda *args, **kwargs: messages.append((args, kwargs))

        window.open_folder(str(Path(tempfile.gettempdir()) / "folder-that-does-not-exist"))

        self.assertEqual(messages[0][0][0], "warning")
        self.assertEqual(messages[0][0][1], "Папка не найдена")
        window.close()

    def test_sidebar_search_is_debounced(self):
        window = DICOMViewer(settings=False)
        window.sidebar.extra_files = [r"C:\study\alpha.dcm", r"C:\study\beta.dcm"]
        window.sidebar.update_sidebar()

        window.sidebar.search_bar.setText("beta")

        self.assertTrue(window.sidebar._search_timer.isActive())
        self.assertEqual(window.sidebar.proxy_model.rowCount(), 2)
        QtTest.QTest.qWait(275)
        self.app.processEvents()
        self.assertEqual(window.sidebar.proxy_model.rowCount(), 1)
        window.close()

    def test_close_waits_for_active_decoder_and_drops_late_signal(self):
        started = threading.Event()

        def slow_run(task):
            started.set()
            time.sleep(0.15)
            task.signals.succeeded.emit(task.token, ViewData(file_path=task.file_path))

        window = DICOMViewer(settings=False)
        window.show()
        with patch.object(FileLoadTask, "run", slow_run):
            window._start_file_load("slow-test.dcm", 0)
            self.assertTrue(started.wait(1.0))
            before_close = time.monotonic()
            window.close()
            close_duration = time.monotonic() - before_close

        self.assertGreaterEqual(close_duration, 0.1)
        self.assertEqual(window.load_pool.activeThreadCount(), 0)
        self.assertEqual(window._pending_loads, {})
        self.assertTrue(window._is_closing)


if __name__ == "__main__":
    unittest.main()
