---
name: pdf
description: "PDF Processing: Comprehensive PDF manipulation toolkit for extracting text and tables, creating new PDFs, merging/splitting documents, and handling forms. Use any time the user asks to create, read, extract from, or manipulate a PDF file."
compatibility: anthropic
---

# PDF Skill

Use the `generate_pdf` tool whenever the user asks to:
- Create a PDF document, report, or export
- Generate a PDF from text or markdown content
- Produce any file in .pdf format

## How to use

Call `generate_pdf` with `content` in markdown format. Same syntax as docx:
- `# Heading 1`, `## Heading 2`
- `**bold**`, `*italic*`
- `- bullet list`, `1. numbered list`

The tool returns a path. The backend emits:
`PDF generated successfully. Download: /api/files/download-pdf/<filename>`

Always relay that download line verbatim so the user gets the download button.

## Example call

```json
{
  "filename": "report.pdf",
  "title": "Monthly Report",
  "content": "## Summary\n\nThis report covers...\n\n## Key Findings\n\n- Finding 1\n- Finding 2"
}
```

## Rules
- NEVER use exec + Python manually — always use `generate_pdf`
- Always include the `Download:` line from the tool result in your reply
- Use markdown formatting in content for clean output
