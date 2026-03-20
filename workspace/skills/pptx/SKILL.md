---
name: pptx
description: "PowerPoint Presentation Handler: Use this skill any time a .pptx file is involved in any way — as input, output, or both. This includes: creating slide decks, pitch decks, or presentations; reading, parsing, or extracting text from an existing .pptx; editing or updating slides."
compatibility: anthropic
---

# PowerPoint Presentation Skill

Use the `generate_pptx` tool whenever the user asks for:
- A presentation, slide deck, or slides
- A pitch deck, pitch presentation
- Any content in PowerPoint (.pptx) format

## How to use

Call `generate_pptx` with a `slides` array. Each slide has:
- `title` — slide heading
- `content` — bullet points (array of strings) or paragraph (string)
- `notes` — optional speaker notes

The tool returns a path. The backend emits:
`Presentation generated successfully. Download: /api/files/download-office/<filename>`

Always relay that download line verbatim so the user gets the download button.

## Example call

```json
{
  "filename": "product-pitch.pptx",
  "theme": "dark",
  "slides": [
    {
      "title": "Product Overview",
      "content": ["Simple to use", "Works offline", "Cross-platform"],
      "notes": "Start with the problem we solve"
    },
    {
      "title": "Key Metrics",
      "content": "10k users in 3 months, 4.8 star rating, 95% retention",
      "notes": ""
    }
  ]
}
```

## Rules
- NEVER use exec + Python/python-pptx manually — always use `generate_pptx`
- Always include the `Download:` line from the tool result in your reply
- Use `theme: "dark"` by default unless user asks for light
- Each slide should have 3–6 bullet points for best readability
- Include speaker notes for complex slides
