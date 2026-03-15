import builtins
import contextlib
import datetime
import io
import re
import unittest
from pathlib import Path

import task_manager_v6


REPO_ROOT = Path(__file__).resolve().parents[1]
TASKS_FILE = REPO_ROOT / "tasks.txt"
CURRENT_OUTPUT = REPO_ROOT / "current_output.txt"
TARGET_OUTPUT = REPO_ROOT / "target_output.txt"
MANUAL_DATE = "2026-03-15"
EMPTY_DAY_LINE = re.compile(r"^Day \d+:$")


def normalize_newlines(text):
    return text.replace("\r\n", "\n")


class AutoPlanOutputTests(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        task_manager_v6.TASKS_FILE = str(TASKS_FILE)
        task_manager_v6.tasks = {}
        task_manager_v6.task_counter = 1
        task_manager_v6.load_tasks()
        self.rendered_output = self.render_auto_plan_output()

    def render_auto_plan_output(self):
        buffer = io.StringIO()
        original_input = builtins.input
        builtins.input = lambda prompt="": MANUAL_DATE
        try:
            with contextlib.redirect_stdout(buffer):
                task_manager_v6.auto_plan(use_system_time=False)
        finally:
            builtins.input = original_input
        return normalize_newlines(buffer.getvalue())

    @staticmethod
    def extract_schedule_lines(output):
        schedule_lines = []
        for line in normalize_newlines(output).split("\n"):
            if line == "Tasks:":
                break
            if line:
                schedule_lines.append(line)
        return schedule_lines

    @staticmethod
    def extract_today_section_lines(output):
        lines = normalize_newlines(output).split("\n")
        section_start = lines.index("To be done today:") + 1
        return [line for line in lines[section_start:] if line]

    def test_auto_plan_matches_target_output(self):
        expected_output = normalize_newlines(TARGET_OUTPUT.read_text(encoding="utf-8"))
        self.assertEqual(self.rendered_output, expected_output)

    def test_schedule_allocation_matches_previous_output_when_empty_days_are_removed(self):
        previous_output = normalize_newlines(CURRENT_OUTPUT.read_text(encoding="utf-8"))
        expected_schedule_lines = [
            line
            for line in self.extract_schedule_lines(previous_output)
            if not EMPTY_DAY_LINE.match(line)
        ]
        self.assertEqual(self.extract_schedule_lines(self.rendered_output), expected_schedule_lines)

    def test_today_section_contains_unique_day_zero_tasks_in_requested_order(self):
        day_zero_line = next(
            line for line in self.extract_schedule_lines(self.rendered_output)
            if line.startswith("Day 0: ")
        )
        day_zero_ids = [int(task_id) for task_id in day_zero_line.split(": ", 1)[1].split(", ")]
        expected_today_ids = sorted(
            set(day_zero_ids),
            key=lambda task_id: (
                task_manager_v6.tasks[task_id].priority,
                task_manager_v6.tasks[task_id].deadline
                if task_manager_v6.tasks[task_id].deadline is not None
                else datetime.datetime.max,
                -task_id,
            ),
        )
        expected_today_lines = [str(task_manager_v6.tasks[task_id]) for task_id in expected_today_ids]
        actual_today_lines = self.extract_today_section_lines(self.rendered_output)

        self.assertEqual(actual_today_lines, expected_today_lines)
        self.assertEqual(len(actual_today_lines), len(set(day_zero_ids)))


if __name__ == "__main__":
    unittest.main()
