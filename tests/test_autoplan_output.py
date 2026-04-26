import builtins
import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_FILE = REPO_ROOT / "auto-planner_v1.1.py"


def load_app_module():
    spec = importlib.util.spec_from_file_location("auto_planner_v1_1", APP_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AutoPlannerTests(unittest.TestCase):
    def setUp(self):
        self.app = load_app_module()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        temp_path = Path(self.temp_dir.name)
        self.tasks_file = temp_path / "tasks.txt"
        self.throughput_file = temp_path / "task_throughput.txt"
        self.app.TASKS_FILE = str(self.tasks_file)
        self.app.THROUGHPUT_FILE = str(self.throughput_file)
        self.app.tasks = {}
        self.app.task_counter = 1

    def write_throughput(self, days=None, current_day_weight_units=0, enabled=True):
        if days is None:
            days = [0] * self.app.THROUGHPUT_WINDOW_DAYS
        payload = {
            "enabled": enabled,
            "current_day_weight_units": current_day_weight_units,
            "days": days,
            "moving_average_weight_units": self.app.calculate_moving_average(days),
        }
        self.throughput_file.write_text(json.dumps(payload), encoding="utf-8")

    def read_throughput(self):
        return json.loads(self.throughput_file.read_text(encoding="utf-8"))

    def capture_output(self, callback, inputs=None):
        buffer = io.StringIO()
        original_input = builtins.input
        input_iter = iter(inputs or [])
        builtins.input = lambda prompt="": next(input_iter)
        try:
            with contextlib.redirect_stdout(buffer):
                callback()
        finally:
            builtins.input = original_input
        return buffer.getvalue()

    def add_task(self, task_id, title="Task", deadline="", priority=5, weight=1):
        self.app.tasks[task_id] = self.app.Task(task_id, title, deadline, priority, weight)

    def test_auto_plan_supports_tomorrow_as_planning_date(self):
        self.add_task(1, deadline="2026-04-27", priority=1, weight=2)

        output = self.capture_output(
            lambda: self.app.auto_plan(
                use_system_time=True,
                planning_date_offset_days=1,
                today_provider=lambda: self.app.datetime.date(2026, 4, 25),
            )
        )

        self.assertIn("Planning date: 2026-04-26", output)
        self.assertIn("Day 0: 1, 1", output)
        self.assertIn("To be done on planning date:", output)

    def test_finish_day_rotates_history_updates_average_and_warns(self):
        self.write_throughput(days=[20] * 60, current_day_weight_units=15)

        output = self.capture_output(self.app.finish_day)
        data = self.read_throughput()

        self.assertEqual(len(data["days"]), 60)
        self.assertEqual(data["days"][-1], 15)
        self.assertEqual(data["current_day_weight_units"], 0)
        self.assertAlmostEqual(data["moving_average_weight_units"], (20 * 59 + 15) / 60)
        self.assertIn("Previous 60-day average: 20.00 weight units.", output)
        self.assertIn("Warning:", output)

    def test_finish_day_does_not_run_when_tracking_is_disabled(self):
        self.write_throughput(days=[20] * 60, current_day_weight_units=15, enabled=False)

        output = self.capture_output(self.app.finish_day)
        data = self.read_throughput()

        self.assertEqual(data["current_day_weight_units"], 15)
        self.assertEqual(data["days"], [20] * 60)
        self.assertIn("Task throughput tracking is disabled.", output)

    def test_remove_task_prompts_before_deletion_and_tracks_weight_when_confirmed(self):
        self.write_throughput()
        self.add_task(1, weight=8)

        output = self.capture_output(self.app.remove_task, inputs=["1", "y"])
        data = self.read_throughput()

        self.assertNotIn(1, self.app.tasks)
        self.assertEqual(data["current_day_weight_units"], 8)
        self.assertIn("Task 1 removed.", output)

    def test_remove_task_can_skip_weight_tracking(self):
        self.write_throughput()
        self.add_task(1, weight=8)

        self.capture_output(self.app.remove_task, inputs=["1", "n"])
        data = self.read_throughput()

        self.assertNotIn(1, self.app.tasks)
        self.assertEqual(data["current_day_weight_units"], 0)

    def test_weight_update_y_prefix_adjusts_current_day_by_old_minus_new_weight(self):
        self.write_throughput(current_day_weight_units=1)
        self.add_task(1, weight=8)

        self.capture_output(self.app.update_task, inputs=["1", "4", "y6"])
        data = self.read_throughput()

        self.assertEqual(self.app.tasks[1].weight, 6)
        self.assertEqual(data["current_day_weight_units"], 3)

    def test_weight_update_y_prefix_clamps_tracking_at_zero_when_weight_increases(self):
        self.write_throughput(current_day_weight_units=1)
        self.add_task(1, weight=6)

        self.capture_output(self.app.update_task, inputs=["1", "4", "y8"])
        data = self.read_throughput()

        self.assertEqual(self.app.tasks[1].weight, 8)
        self.assertEqual(data["current_day_weight_units"], 0)

    def test_weight_update_n_prefix_leaves_tracking_unchanged(self):
        self.write_throughput(current_day_weight_units=4)
        self.add_task(1, weight=8)

        self.capture_output(self.app.update_task, inputs=["1", "4", "n6"])
        data = self.read_throughput()

        self.assertEqual(self.app.tasks[1].weight, 6)
        self.assertEqual(data["current_day_weight_units"], 4)

    def test_main_menu_hides_finish_day_when_tracking_is_disabled(self):
        self.write_throughput(enabled=False)

        output = self.capture_output(self.app.print_main_menu)

        self.assertIn("Auto-Planner Options:", output)
        self.assertNotIn("9. Finish Day", output)

    def test_main_hidden_tracking_commands_toggle_feature(self):
        self.write_throughput(enabled=True)

        self.capture_output(self.app.main, inputs=["tt-off", "6"])
        self.assertFalse(self.read_throughput()["enabled"])

        self.capture_output(self.app.main, inputs=["tt-on", "6"])
        self.assertTrue(self.read_throughput()["enabled"])


if __name__ == "__main__":
    unittest.main()
