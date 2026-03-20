---
name: notion
description: Notion integration via MCP server. Create, read, update, and query pages, databases (data sources), and blocks. Use when the user mentions Notion, asks to save to Notion, check a Notion board, query a Notion database, or manage Notion pages.
metadata: {"clawdbot":{"emoji":"\U0001F4DD"}}
---

# Notion (MCP)

You have direct access to Notion through MCP tools. **Do NOT use curl or exec for Notion operations — use the MCP tools instead.**

## Available MCP Tools

| Tool | What it does |
|------|-------------|
| `mcp_notion_API-post-search` | Search for pages and databases by title |
| `mcp_notion_API-retrieve-a-page` | Get a page by ID |
| `mcp_notion_API-retrieve-a-page-property` | Get a specific page property |
| `mcp_notion_API-get-block-children` | Get page content (blocks) |
| `mcp_notion_API-post-page` | Create a new page |
| `mcp_notion_API-patch-page` | Update page properties |
| `mcp_notion_API-patch-block-children` | Add blocks (content) to a page |
| `mcp_notion_API-retrieve-a-block` | Get a single block |
| `mcp_notion_API-update-a-block` | Update a block |
| `mcp_notion_API-delete-a-block` | Delete a block |
| `mcp_notion_API-retrieve-a-database` | Get database schema |
| `mcp_notion_API-retrieve-a-data-source` | Get data source info |
| `mcp_notion_API-query-data-source` | Query a database with filters/sorts |
| `mcp_notion_API-API-create-a-data-source` | Create a new database |
| `mcp_notion_API-update-a-data-source` | Update database schema |
| `mcp_notion_API-list-data-source-templates` | List database templates |
| `mcp_notion_API-create-a-comment` | Add a comment to a page |
| `mcp_notion_API-retrieve-a-comment` | Get comments on a page |
| `mcp_notion_API-move-page` | Move a page to a different parent |
| `mcp_notion_API-get-users` | List workspace users |
| `mcp_notion_API-get-user` | Get a specific user |
| `mcp_notion_API-get-self` | Get the integration's own user info |

## Workflow

1. **Search first**: Use `mcp_notion_API-post-search` to find existing pages/databases before creating new ones
2. **Fetch to inspect**: Use `mcp_notion_API-retrieve-a-page` + `mcp_notion_API-get-block-children` to read full page content
3. **Present findings**: Show the user what you found before making changes
4. **Update**: Use `mcp_notion_API-patch-page` for properties, `mcp_notion_API-patch-block-children` to add content

## Notes

- Authentication is handled automatically via the MCP server (uses NOTION_API_KEY from Settings > Keys)
- No curl, no bash scripts, no exec needed for Notion operations
- The MCP server handles pagination, rate limiting, and error handling
- Page/database IDs are UUIDs (with or without dashes)
