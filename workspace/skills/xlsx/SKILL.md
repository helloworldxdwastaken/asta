---
name: xlsx
description: "Excel Spreadsheet Handler: Comprehensive Microsoft Excel (.xlsx) document creation, editing, and analysis with support for formulas, formatting, data analysis, and visualization. Use any time spreadsheets, tables, trackers, budgets, schedules, or data exports are requested."
compatibility: anthropic
---

# Excel Spreadsheet Skill

Use the `generate_xlsx` tool whenever the user asks for:
- A spreadsheet, tracker, table, or grid of data
- A budget, expense sheet, or financial tracker
- A schedule, calendar, or timeline in spreadsheet form
- Any data that should be in Excel (.xlsx) format
- A "project tracker", "task list", or similar organizer

## How to use

Call `generate_xlsx` with a structured `sheets` array. Each sheet has:
- `name` — sheet tab name (max 31 chars)
- `headers` — column header labels
- `rows` — 2D array of data values matching the headers

The tool returns a path. The backend emits:
`Spreadsheet generated successfully. Download: /api/files/download-office/<filename>`

Always relay that download line verbatim so the user gets the download button.

## Example call

```json
{
  "filename": "project-tracker.xlsx",
  "sheets": [
    {
      "name": "Tasks",
      "headers": ["Task", "Owner", "Due Date", "Status", "Priority"],
      "rows": [
        ["Design mockup", "Alice", "2026-03-10", "In Progress", "High"],
        ["Backend API", "Bob", "2026-03-15", "Pending", "High"]
      ]
    }
  ]
}
```

## Rules
- NEVER use exec + Python/openpyxl manually — always use `generate_xlsx`
- Always include the `Download:` line from the tool result in your reply
- Use descriptive sheet names and clear column headers
- Put all numeric values as numbers (not strings) so Excel can do math on them
