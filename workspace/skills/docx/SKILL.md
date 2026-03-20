---
name: docx
description: "Word Document Handler: Use whenever the user wants to create, read, edit, or manipulate Word documents (.docx files). Triggers include: any mention of 'Word doc', 'word document', '.docx', or requests for a report, letter, contract, proposal, or essay."
compatibility: anthropic
---

# Word Document Skill

Use the `generate_docx` tool whenever the user asks for:
- A Word document, report, letter, or essay
- A contract, proposal, or formal document
- Any content in .docx format

## How to use

Call `generate_docx` with `content` in markdown format. Supports:
- `# Heading 1`, `## Heading 2`, `### Heading 3`
- `**bold**`, `*italic*`
- `- bullet list`, `1. numbered list`
- `---` for horizontal separators

The tool returns a path. The backend emits:
`Document generated successfully. Download: /api/files/download-office/<filename>`

Always relay that download line verbatim so the user gets the download button.

## Example call

```json
{
  "filename": "project-proposal.docx",
  "title": "Project Proposal",
  "content": "## Overview\n\nThis proposal outlines...\n\n## Deliverables\n\n- Phase 1: Research\n- Phase 2: Development\n- Phase 3: Testing\n\n## Timeline\n\n**Start date:** March 2026\n**End date:** June 2026"
}
```

## Rules
- NEVER use exec + Python/python-docx manually — always use `generate_docx`
- Always include the `Download:` line from the tool result in your reply
- Use the `title` field for the document title shown at the top
- Write content in clean markdown — the tool handles formatting
