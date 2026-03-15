import datetime
import json
import os
import random
import math

TASKS_FILE = "tasks.txt"


class Task:
    def __init__(self, task_id, title, deadline, priority, weight):
        self.id = task_id
        self.title = title
        self.deadline = self.parse_deadline(deadline)
        self.priority = priority
        self.weight = weight

    def parse_deadline(self, deadline_str):
        if not deadline_str:
            return None
        try:
            return datetime.datetime.strptime(deadline_str, "%Y-%m-%d")
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")
            return None

    def deadline_str(self):
        return self.deadline.strftime("%Y-%m-%d") if self.deadline else ""

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "deadline": self.deadline_str(),
            "priority": self.priority,
            "weight": self.weight,
        }

    def __str__(self):
        deadline_display = self.deadline.strftime("%Y-%m-%d") if self.deadline else "No deadline"
        return f"[{self.id}] {self.title} | Deadline: {deadline_display} | Priority: {self.priority} | Weight: {self.weight}"


tasks = {}
task_counter = 1


def random_custom(seed_):

    for i in range(random.randint(0, 63)):
        seed_ = 4 * seed_ * (1-seed_)
    return seed_


def count_tasks_without_deadline():
    return sum(1 for task in tasks.values() if task.deadline is None)


def task_deadline_sort_value(task):
    return task.deadline if task.deadline is not None else datetime.datetime.max


def day_allocation_sort_key(task_id):
    task = tasks[task_id]
    return task.priority, task_deadline_sort_value(task)


def today_section_sort_key(task_id):
    task = tasks[task_id]
    return task.priority, task_deadline_sort_value(task), -task.id


def filter_non_empty_days(day_lists):
    return {day: task_ids for day, task_ids in day_lists.items() if task_ids}


def save_tasks():
    data = [task.to_dict() for task in tasks.values()]
    try:
        with open(TASKS_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"Error saving tasks: {e}")


def load_tasks():
    global tasks, task_counter
    if os.path.exists(TASKS_FILE):
        try:
            with open(TASKS_FILE, "r") as f:
                data = json.load(f)
                for item in data:
                    task_id = item["id"]
                    title = item["title"]
                    deadline = item["deadline"]
                    priority = item["priority"]
                    weight = item["weight"]
                    task = Task(task_id, title, deadline, priority, weight)
                    tasks[task_id] = task
                if tasks:
                    task_counter = max(tasks.keys()) + 1
        except Exception as e:
            print(f"Error loading tasks: {e}")


def add_task():
    global task_counter
    title = input("Enter task title: ")
    deadline = input("Enter deadline (YYYY-MM-DD) or leave blank: ")
    try:
        priority = int(input("Enter priority: "))
    except ValueError:
        print("Invalid input. Setting priority to 5.")
        priority = 5
    try:
        weight = int(input("Enter weight: "))
    except ValueError:
        print("Invalid input. Setting weight to 1.")
        weight = 1
    task = Task(task_counter, title, deadline, priority, weight)
    tasks[task_counter] = task
    print("Task added:")
    print(task)
    task_counter += 1
    save_tasks()


def remove_task():
    try:
        task_id = int(input("Enter task ID to remove: "))
        if task_id in tasks:
            del tasks[task_id]
            print(f"Task {task_id} removed.")
            save_tasks()
        else:
            print("Task not found.")
    except ValueError:
        print("Invalid ID.")


def update_task():
    try:
        task_id = int(input("Enter task ID to update: "))
        if task_id in tasks:
            task = tasks[task_id]
            print("Current task details:")
            print(task)
            print("What would you like to update?")
            print("1. Title")
            print("2. Deadline")
            print("3. Priority")
            print("4. Weight")
            choice = input("Enter option (1/2/3/4): ")
            if choice == "1":
                new_title = input("Enter new title: ")
                task.title = new_title
            elif choice == "2":
                new_deadline = input("Enter new deadline (YYYY-MM-DD) or leave blank for no deadline: ")
                task.deadline = task.parse_deadline(new_deadline)
            elif choice == "3":
                try:
                    new_priority = int(input("Enter new priority: "))
                    task.priority = new_priority
                except ValueError:
                    print("Invalid input. Keeping the current priority.")
            elif choice == "4":
                try:
                    new_weight = int(input("Enter new weight: "))
                    task.weight = new_weight
                except ValueError:
                    print("Invalid input. Keeping the current weight.")
            else:
                print("Invalid option.")
            print("Updated task details:")
            print(task)
            save_tasks()
        else:
            print("Task not found.")
    except ValueError:
        print("Invalid ID.")


def list_tasks():
    if not tasks:
        print("No tasks available.")
        return
    print("Choose sorting method:")
    print("1. By deadline, then priority")
    print("2. By priority, then deadline")
    print("3. By title")
    choice = input("Enter choice (1/2/3): ")
    if choice == "1":
        key_func = lambda x: (x.deadline if x.deadline is not None else datetime.datetime.max, x.priority)
    elif choice == "2":
        key_func = lambda x: (x.priority, x.deadline if x.deadline is not None else datetime.datetime.max)
    elif choice == "3":
        key_func = lambda x: x.title.lower()
    else:
        print("Invalid choice. Using default sorting (by deadline, then priority).")
        key_func = lambda x: (x.deadline if x.deadline is not None else datetime.datetime.max, x.priority)
    sorted_tasks = sorted(tasks.values(), key=key_func)
    print("Tasks:")
    for task in sorted_tasks:
        print(task)


def suggest_schedule():
    if not tasks:
        print("No tasks available.")
        return

    print("\nGenerating probabilistic schedule:")
    today = datetime.date.today()
    seed = float(input("Enter random seed: "))

    # Precompute weights for all tasks
    task_weights = {}
    for task in tasks.values():
        if task.deadline is None:
            tasks_without_deadline = count_tasks_without_deadline()
            days_left = 7 if tasks_without_deadline <= 7 else tasks_without_deadline  # 7 days as default (you may change this according to your needs)
        else:
            deadline_date = task.deadline.date()
            days_delta = (deadline_date - today).days
            days_left = max(1, days_delta)  # Treat overdue tasks as due today
        weight = (1 / days_left) * (1 / task.priority)
        task_weights[task.id] = weight

    # Initialize task pool and weights
    task_pool = list(tasks.values())
    remaining_weights = [task_weights[task.id] for task in task_pool]
    total_weight = sum(remaining_weights)
    schedule = []

    while task_pool:
        if total_weight <= 0:  # Handle edge case, though unlikely with positive weights
            new_seed = random_custom(seed)
            seed = new_seed
            selected_index = (random.randint(0, len(task_pool) - 1) + int(new_seed * len(task_pool))) % len(task_pool)
        else:
            new_seed = random_custom(seed)
            seed = new_seed
            r = random.uniform(0, total_weight) + new_seed*total_weight
            while not r <= total_weight:
                r = r - total_weight
            current = 0
            for i, weight in enumerate(remaining_weights):
                current += weight
                if r <= current:
                    selected_index = i
                    break

        selected_task = task_pool[selected_index]
        schedule.append(selected_task)
        # Swap selected task with the last element for O(1) removal
        task_pool[selected_index], task_pool[-1] = task_pool[-1], task_pool[selected_index]
        remaining_weights[selected_index], remaining_weights[-1] = remaining_weights[-1], remaining_weights[selected_index]
        # Update total weight before popping
        total_weight -= remaining_weights[-1]
        # Remove the last element
        task_pool.pop()
        remaining_weights.pop()

    # Display schedule
    for idx, task in enumerate(schedule, 1):
        print(f"{idx}. {task}")


def auto_plan(use_system_time=True):
    if not tasks:
        print("No tasks available.")
        return

    if use_system_time:
        today = datetime.date.today()
    else:
        while True:
            try:
                # Ask user for input like: 2025-09-02
                human_input = input("Enter date (YYYY-MM-DD): ")
                year, month, day = map(int, human_input.split("-"))
                today = datetime.date(year, month, day)
                break
            except ValueError:
                print("Invalid date format or non-existent date. Please try again.")

    print(f"Current date: {today}")

    tasks_with_w = [task for task in tasks.values() if task.weight > 0]
    tasks_zero = [task for task in tasks.values() if task.weight == 0]

    tasks_deadline = [t for t in tasks_with_w if t.deadline is not None]
    tasks_no_dl = [t for t in tasks_with_w if t.deadline is None]

    sorted_deadline = sorted(tasks_deadline, key=lambda t: (task_deadline_sort_value(t), t.priority))
    sorted_no_dl = sorted(tasks_no_dl, key=lambda t: t.priority)

    flat_bound = []
    cum_w = 0
    L = {}
    for task in sorted_deadline:
        cum_w += task.weight
        dl_date = task.deadline.date()
        days_delta = (dl_date - today).days
        last_day = days_delta - 1
        if last_day < 0:
            last_day = 0
        if last_day in L:
            L[last_day] = max(L[last_day], cum_w)
        else:
            L[last_day] = cum_w

    if L:
        max_d = max(L.keys())
        total_bound = cum_w
        p = [0] * (max_d + 1)
        cum = 0
        for d in range(max_d + 1):
            max_req = 0
            for j in L:
                if j >= d:
                    remaining_days = j - d + 1
                    required = L[j] - cum
                    if required > 0:
                        avg = required / remaining_days
                        req = math.ceil(avg)
                        max_req = max(max_req, req)
            prev_p = p[d - 1] if d > 0 else float('inf')
            p[d] = min(prev_p, max_req) if max_req > 0 else 0
            cum += p[d]
    else:
        max_d = -1
        total_bound = 0

    flat_bound = []
    for task in sorted_deadline:
        flat_bound += [task.id] * task.weight

    day_lists = {}
    pos = 0
    for d in range(max_d + 1):
        day_task_ids = flat_bound[pos:pos + p[d]]
        day_task_ids.sort(key=day_allocation_sort_key)
        day_lists[d] = day_task_ids
        pos += p[d]

    if tasks_zero:
        zero_ids = [t.id for t in tasks_zero]
        zero_ids.sort(key=day_allocation_sort_key)
        if 0 in day_lists:
            day_lists[0] = zero_ids + day_lists[0]
        else:
            day_lists[0] = zero_ids

    start_day = max_d + 1 if L else 0
    pos = 0
    for task in sorted_no_dl:
        for i in range(task.weight):
            d = start_day + pos
            day_lists[d] = [task.id]
            pos += 1

    if not day_lists:
        print("No tasks to plan.")
        return

    printable_day_lists = filter_non_empty_days(day_lists)
    if not printable_day_lists:
        print("No tasks to plan.")
        return

    max_print_day = max(printable_day_lists.keys())
    current_group_start = None
    current_group_list = None
    for d in range(max_print_day + 1):
        if d in printable_day_lists:
            task_list = ', '.join(map(str, printable_day_lists[d]))
            if current_group_start is None:
                current_group_start = d
                current_group_list = task_list
            elif task_list == current_group_list and len(printable_day_lists[d]) == 1:
                pass
            else:
                if current_group_start == d - 1:
                    print(f"Day {current_group_start}: {current_group_list}")
                else:
                    print(f"Days {current_group_start} to {d-1} (inclusive): {current_group_list.replace(', ', '')} (every day)")
                current_group_start = d
                current_group_list = task_list
        else:
            if current_group_start is not None:
                if current_group_start == d - 1:
                    print(f"Day {current_group_start}: {current_group_list}")
                else:
                    print(f"Days {current_group_start} to {d-1} (inclusive): {current_group_list.replace(', ', '')} (every day)")
                current_group_start = None

    if current_group_start is not None:
        if current_group_start == max_print_day:
            print(f"Day {current_group_start}: {current_group_list}")
        else:
            print(f"Days {current_group_start} to {max_print_day} (inclusive): {current_group_list.replace(', ', '')} (every day)")

    print("\nTasks:")
    sorted_tasks = sorted(tasks.values(), key=lambda x: x.id)
    for task in sorted_tasks:
        print(task)

    print("\nTo be done today:")
    today_task_ids = sorted(set(day_lists.get(0, [])), key=today_section_sort_key)
    for task_id in today_task_ids:
        print(tasks[task_id])


def main():
    print("Current working directory:", os.getcwd())
    load_tasks()
    while True:
        try:
            print("\nTask Manager Options:")
            print("1. Add Task")
            print("2. Remove Task")
            print("3. Update Task")
            print("4. List Tasks")
            print("5. Generate Schedule")
            print("6. Exit")
            print("7. Show number of tasks with no deadlines")
            print("8. Auto Plan")
            choice = input("Select an option: ")
            if choice == "1":
                add_task()
            elif choice == "2":
                remove_task()
            elif choice == "3":
                update_task()
            elif choice == "4":
                list_tasks()
            elif choice == "5":
                suggest_schedule()
            elif choice == "6":
                print("Exiting Task Manager.")
                break
            elif choice == "7":
                print(count_tasks_without_deadline())
            elif choice == "8":
                while True:
                    human_input = input("Use the system's time? (y/n): ")
                    if human_input in ("y", "n"):
                        auto_plan(human_input == "y")
                        break
                    elif human_input == "exit":
                        print("Canceling auto-plan.")
                        break
                    else:
                        print("Invalid input. Please try again.")
            else:
                print("Invalid option. Please choose a number between 1 and 8.")
        except Exception as e:
            print(f"An error occurred: {e}")
            # Continue the loop instead of crashing

if __name__ == "__main__":
    main()
