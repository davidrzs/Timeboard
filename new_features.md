# Future Feature Ideas

## Reverse Scheduling

Calculate and display "start by" date based on deadline and estimated duration.

**Levels of implementation:**

1. **Simple** - Show "Start by: Thu" on task cards (deadline minus duration). Color shift as start date approaches.

2. **Hours-aware** - Factor in productive hours/day (e.g., 6hrs). Multi-day tasks spread across days: "8hr task due Monday → Start by Thursday".

3. **Calendar-aware** - Check actual free time from Google Calendar. Account for meetings and other scheduled tasks. Warn when deadline is impossible: "You have 4 free hours before Friday, this task needs 6."

**Possible behaviors:**
- Tasks with passed start date auto-surface to Today
- Block adding more to Today if already overcommitted
- Warning indicator when you're behind on a task
