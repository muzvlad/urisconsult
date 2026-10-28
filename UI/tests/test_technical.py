"""Технические тесты UI без проверки визуального вида."""
from unittest.mock import Mock

import pytest

tk = pytest.importorskip("tkinter")

from src.models import Worker
from src.widgets import WorkerListWidget


@pytest.fixture
def tk_root():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk недоступен")
    root.withdraw()
    yield root
    root.destroy()


class TestMeetingDialog:
    def test_invalid_time_does_not_call_api(self, tk_root, monkeypatch):
        from src.dialogs import MeetingDialog

        warnings = []
        api = Mock()
        monkeypatch.setattr("src.dialogs.messagebox.showwarning",
                            lambda *args, **kwargs: warnings.append(args))
        monkeypatch.setattr("src.dialogs.get_api_client", lambda: api)

        dialog = MeetingDialog(tk_root, Worker(id="1", name="Иванов"), lambda: None)
        dialog.date_entry.delete(0, tk.END)
        dialog.date_entry.insert(0, "26.10.2026")
        dialog.time_entry.delete(0, tk.END)
        dialog.time_entry.insert(0, "9:30")
        dialog._save()

        assert warnings
        api.add_meeting.assert_not_called()

    def test_valid_input_saves_and_closes(self, tk_root, monkeypatch):
        from src.dialogs import MeetingDialog

        api = Mock()
        api.add_meeting.return_value = 1
        monkeypatch.setattr("src.dialogs.get_api_client", lambda: api)
        added = []
        dialog = MeetingDialog(tk_root, Worker(id="1", name="Иванов"),
                               lambda: added.append(True))
        dialog.date_entry.delete(0, tk.END)
        dialog.date_entry.insert(0, "26.10.2026")
        dialog.time_entry.delete(0, tk.END)
        dialog.time_entry.insert(0, "09:30")
        dialog._save()

        api.add_meeting.assert_called_once_with("1", "26.10.2026 09:30", "")
        assert added == [True]


class TestWorkerListTechnical:
    def test_tags_and_hr_label(self, tk_root):
        widget = WorkerListWidget(tk_root)
        widget.set_workers([
            Worker(id="1", name="Иванов", hr_status="employed",
                   archived_at="2026-01-01T10:00:00"),
            Worker(id="2", name="Петров", hr_status="unknown"),
        ])

        archived = widget.tree.item("1")
        active = widget.tree.item("2")
        assert list(archived["tags"]) == ["hr_employed", "archived"]
        assert archived["values"][8] == "Трудоустроен"
        assert list(active["tags"]) == ["hr_not_processed"]
        assert active["values"][8] == "Новый"


class TestRefreshCurrentWorker:
    def test_refreshes_card_list_and_selection(self):
        from src.main import DBViewerApp

        app = DBViewerApp.__new__(DBViewerApp)
        old = Worker(id="1", name="Старое")
        fresh = Worker(id="1", name="Новое")
        app.current_worker = old
        app.api = Mock()
        app.api.get_worker.return_value = fresh
        app._display_worker_details = Mock()
        app._refresh_current_list = Mock()
        app.list_widget = Mock()

        app._refresh_current_worker()

        assert app.current_worker is fresh
        app._display_worker_details.assert_called_once_with(fresh)
        app._refresh_current_list.assert_called_once()
        app.list_widget.select_by_id.assert_called_once_with("1")
