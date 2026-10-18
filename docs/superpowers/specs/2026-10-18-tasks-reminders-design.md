# Specification: Smart Tasks & Reminders (Personal Assistant Upgrade)

**Date:** 2026-10-18  
**Status:** Approved  
**Author:** droritos & Antigravity  
**Repository:** [droritos/TickerPing](https://github.com/droritos/TickerPing)

---

## 1. Overview & Goals

Transform `TickerPing` into a multi-purpose personal assistant bot by adding a lightweight, decoupled **Tasks & Reminders** engine.
- A reminder is treated as a **timed task** (with a deadline/alarm).
- A to-do item is treated as an **untimed task** (checklist item).
- 100% modular architecture: stock alerting (`engine.py`, `alarms_manager.py`) remains untouched and isolated.
- 24/7 autonomous monitoring on GitHub Actions: checks reminders every minute alongside stock alarms.
- Reminders and tasks are persisted in `reminders.json` and automatically synced to Git.

---

## 2. User Experience & Telegram Interface

### 2.1 Setting Tasks & Reminders
Users can use `/remind`, `/todo`, or `/task` interchangeably:

| Input Example | Type | Scheduled Time | Note |
| :--- | :--- | :--- | :--- |
| `/remind 25m Check oven` | Relative Timer | Now + 25 minutes | "Check oven" |
| `/remind 2h Take laundry out` | Relative Timer | Now + 2 hours | "Take laundry out" |
| `/remind 18:30 Call doctor` | Specific Time | Today at 18:30 (or tomorrow if past) | "Call doctor" |
| `/remind tomorrow 09:00 Buy groceries` | Tomorrow Time | Tomorrow at 09:00 | "Buy groceries" |
| `/remind 18/11 Wedding` | Calendar Date | Nov 18 at 09:00 AM | "Wedding" |
| `/remind 18/11 19:30 Wedding` | Calendar + Time | Nov 18 at 19:30 | "Wedding" |
| `/todo Buy milk` | General To-Do | None (Open checklist) | "Buy milk" |

### 2.2 Viewing Active Tasks (`/tasks`, `/todo`, `/reminders`)
Sending `/tasks` displays all active items with interactive inline buttons:

```
📋 Your Tasks & Reminders:
━━━━━━━━━━━━━━━━━━━━
1. ⏰ [Today 18:30] Call doctor
   [ ✅ Done ] [ 🗑️ Delete ]

2. 📝 Buy milk
   [ ✅ Done ] [ 🗑️ Delete ]

3. ⏰ [18 Nov 19:30] Wedding
   [ ✅ Done ] [ 🗑️ Delete ]
```

* **Tap `[ ✅ Done ]`:** Marks task as completed.
* **Tap `[ 🗑️ Delete ]`:** Deletes the task immediately.

### 2.3 Triggered Reminder Notification
When a reminder's scheduled time arrives, the 24/7 cloud runner sends an alert with 1-tap snooze and completion buttons:

```
⏰ REMINDER ALERT!
━━━━━━━━━━━━━━━━━━━━
Check oven!
🕒 Scheduled for 13:25
```
**Inline Keyboard:**
| Button 1 | Button 2 | Button 3 |
| :--- | :--- | :--- |
| `[ ✅ Done ]` | `[ ⏰ Snooze 10m ]` | `[ ⏰ Snooze 1h ]` |

---

## 3. Architecture & Component Design

```mermaid
flowchart TD
    User["📱 User (Telegram)"] --> Handler["TelegramCommandHandler"]
    
    subgraph Routing
        Handler -->|"/remind", "/todo", "/task"| ParseTask["parse_reminder_input()"]
        ParseTask --> RemindMgr["ReminderManager"]
        Handler -->|"/tasks", "/reminders"| ListTasks["ReminderManager.get_reminders()"]
        Handler -->|"task_done:ID", "task_snooze:ID:10"| CbTask["handle_callback_query()"]
    end
    
    subgraph Storage
        RemindMgr --> RemindersJSON["reminders.json"]
    end

    subgraph 24/7 Cloud Loop
        CloudRunner["cloud_runner.py"] -->|Every 60s| CheckReminders["ReminderManager.get_due_reminders()"]
        CheckReminders -->|Due| Notifier["send_telegram_msg() with Snooze/Done buttons"]
        CheckReminders -->|State Changed| GitSync["git_sync_changes()"]
    end
```

### 3.1 `reminders_manager.py` (New Module)
- `parse_reminder_input(raw_text: str, now: Optional[datetime] = None) -> Tuple[Optional[datetime], str]`
- `ReminderManager(storage_path="reminders.json")` with full CRUD, snooze, and atomic file persistence.

### 3.2 `telegram_command_handler.py` Upgrades
- Routes `/remind`, `/todo`, `/task`, `/tasks`, `/reminders`.
- Handles callback queries `task_done:<id>`, `task_del:<id>`, `task_snooze:<id>:<minutes>`.

### 3.3 `cloud_runner.py` Upgrades
- Adds `evaluate_due_reminders()` to the 24/7 runner loop.
- Automatically commits and syncs `reminders.json` to GitHub.

---

## 4. Verification & Testing Plan
- Unit tests for date/time parser across relative, time-of-day, tomorrow, and calendar dates.
- Unit tests for `ReminderManager` CRUD and snooze.
- Unit tests for `TelegramCommandHandler` task commands and callbacks.
- Full pytest test suite execution ensuring 100% pass rate.
