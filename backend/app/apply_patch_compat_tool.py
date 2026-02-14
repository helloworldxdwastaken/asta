"""OpenClaw-compatible apply_patch tool (workspace-scoped)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings

BEGIN_PATCH_MARKER = "*** Begin Patch"
END_PATCH_MARKER = "*** End Patch"
ADD_FILE_MARKER = "*** Add File: "
DELETE_FILE_MARKER = "*** Delete File: "
UPDATE_FILE_MARKER = "*** Update File: "
MOVE_TO_MARKER = "*** Move to: "
EOF_MARKER = "*** End of File"
CHANGE_CONTEXT_MARKER = "@@ "
EMPTY_CHANGE_CONTEXT_MARKER = "@@"


@dataclass
class UpdateFileChunk:
    change_context: str | None
    old_lines: list[str]
    new_lines: list[str]
    is_end_of_file: bool


@dataclass
class AddFileHunk:
    path: str
    contents: str


@dataclass
class DeleteFileHunk:
    path: str


@dataclass
class UpdateFileHunk:
    path: str
    move_path: str | None
    chunks: list[UpdateFileChunk]


def get_apply_patch_compat_tool_openai_def() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "apply_patch",
                "description": (
                    "Apply multi-file patches using the OpenClaw/Codex patch format. "
                    "Input must include *** Begin Patch and *** End Patch."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "input": {"type": "string"},
                        "patch": {"type": "string", "description": "Alias for input"},
                    },
                    "required": ["input"],
                },
            },
        }
    ]


def parse_apply_patch_compat_args(arguments_str: str | dict) -> dict:
    data: dict = {}
    try:
        if isinstance(arguments_str, dict):
            data = arguments_str
        else:
            parsed = json.loads(arguments_str)
            data = parsed if isinstance(parsed, dict) else {}
    except Exception:
        data = {}
    out = dict(data)
    if not isinstance(out.get("input"), str) and isinstance(out.get("patch"), str):
        out["input"] = out["patch"]
    return out


def _workspace_root() -> Path:
    root = get_settings().workspace_path
    if not root:
        raise ValueError("Workspace is not configured.")
    return root.resolve()


def _resolve_workspace_path(raw_path: str, root: Path) -> tuple[Path, str]:
    p = Path((raw_path or "").strip())
    if not p.is_absolute():
        p = (root / p).resolve()
    else:
        p = p.resolve()
    try:
        rel = p.relative_to(root).as_posix()
    except Exception:
        raise ValueError(f"path must be inside workspace: {raw_path}")
    return p, rel


def _check_patch_boundaries(lines: list[str]) -> None:
    if not lines:
        raise ValueError("Invalid patch: input is empty.")
    if lines[0].strip() != BEGIN_PATCH_MARKER:
        raise ValueError("The first line of the patch must be '*** Begin Patch'")
    if lines[-1].strip() != END_PATCH_MARKER:
        raise ValueError("The last line of the patch must be '*** End Patch'")


def _parse_update_chunk(lines: list[str], line_number: int, allow_missing_context: bool) -> tuple[UpdateFileChunk, int]:
    if not lines:
        raise ValueError(f"Invalid patch hunk at line {line_number}: Update hunk is empty")
    change_context: str | None = None
    start_index = 0
    if lines[0] == EMPTY_CHANGE_CONTEXT_MARKER:
        start_index = 1
    elif lines[0].startswith(CHANGE_CONTEXT_MARKER):
        change_context = lines[0][len(CHANGE_CONTEXT_MARKER) :]
        start_index = 1
    elif not allow_missing_context:
        raise ValueError(
            f"Invalid patch hunk at line {line_number}: expected '@@' context marker, got: '{lines[0]}'"
        )

    old_lines: list[str] = []
    new_lines: list[str] = []
    is_end_of_file = False
    parsed_lines = 0

    for line in lines[start_index:]:
        if line == EOF_MARKER:
            if parsed_lines == 0:
                raise ValueError(f"Invalid patch hunk at line {line_number}: empty update chunk")
            is_end_of_file = True
            parsed_lines += 1
            break
        if line == "":
            old_lines.append("")
            new_lines.append("")
            parsed_lines += 1
            continue
        marker = line[0]
        if marker == " ":
            old_lines.append(line[1:])
            new_lines.append(line[1:])
            parsed_lines += 1
            continue
        if marker == "+":
            new_lines.append(line[1:])
            parsed_lines += 1
            continue
        if marker == "-":
            old_lines.append(line[1:])
            parsed_lines += 1
            continue
        if parsed_lines == 0:
            raise ValueError(
                f"Invalid patch hunk at line {line_number}: unexpected update line '{line}'"
            )
        break

    return (
        UpdateFileChunk(
            change_context=change_context,
            old_lines=old_lines,
            new_lines=new_lines,
            is_end_of_file=is_end_of_file,
        ),
        parsed_lines + start_index,
    )


def _parse_patch_text(input_text: str) -> list[AddFileHunk | DeleteFileHunk | UpdateFileHunk]:
    trimmed = (input_text or "").strip()
    if not trimmed:
        raise ValueError("Invalid patch: input is empty.")
    lines = trimmed.splitlines()
    _check_patch_boundaries(lines)

    hunks: list[AddFileHunk | DeleteFileHunk | UpdateFileHunk] = []
    body = lines[1:-1]
    index = 0
    while index < len(body):
        line = body[index]
        line_number = index + 2
        if not line.strip():
            index += 1
            continue

        if line.startswith(ADD_FILE_MARKER):
            path = line[len(ADD_FILE_MARKER) :]
            index += 1
            contents: list[str] = []
            while index < len(body) and body[index].startswith("+"):
                contents.append(body[index][1:])
                index += 1
            hunks.append(AddFileHunk(path=path, contents=("\n".join(contents) + ("\n" if contents else ""))))
            continue

        if line.startswith(DELETE_FILE_MARKER):
            path = line[len(DELETE_FILE_MARKER) :]
            hunks.append(DeleteFileHunk(path=path))
            index += 1
            continue

        if line.startswith(UPDATE_FILE_MARKER):
            path = line[len(UPDATE_FILE_MARKER) :]
            index += 1
            move_path: str | None = None
            if index < len(body) and body[index].startswith(MOVE_TO_MARKER):
                move_path = body[index][len(MOVE_TO_MARKER) :]
                index += 1
            chunks: list[UpdateFileChunk] = []
            while index < len(body):
                if not body[index].strip():
                    index += 1
                    continue
                if body[index].startswith("***"):
                    break
                chunk, consumed = _parse_update_chunk(
                    body[index:],
                    line_number=index + 2,
                    allow_missing_context=(len(chunks) == 0),
                )
                chunks.append(chunk)
                index += consumed
            if not chunks:
                raise ValueError(f"Invalid patch hunk at line {line_number}: empty update hunk")
            hunks.append(UpdateFileHunk(path=path, move_path=move_path, chunks=chunks))
            continue

        raise ValueError(f"Invalid patch hunk at line {line_number}: {line}")

    return hunks


def _lines_match(lines: list[str], pattern: list[str], start: int, normalize) -> bool:
    for idx, expected in enumerate(pattern):
        if normalize(lines[start + idx]) != normalize(expected):
            return False
    return True


def _seek_sequence(lines: list[str], pattern: list[str], start: int, eof: bool) -> int | None:
    if not pattern:
        return start
    if len(pattern) > len(lines):
        return None
    max_start = len(lines) - len(pattern)
    search_start = max_start if eof and len(lines) >= len(pattern) else start
    if search_start > max_start:
        return None

    normalizers = (
        (lambda s: s),
        (lambda s: s.rstrip()),
        (lambda s: s.strip()),
    )
    for normalize in normalizers:
        for i in range(search_start, max_start + 1):
            if _lines_match(lines, pattern, i, normalize):
                return i
    return None


def _compute_replacements(
    original_lines: list[str],
    chunks: list[UpdateFileChunk],
    file_display: str,
) -> list[tuple[int, int, list[str]]]:
    replacements: list[tuple[int, int, list[str]]] = []
    line_index = 0
    for chunk in chunks:
        if chunk.change_context:
            ctx_index = _seek_sequence(original_lines, [chunk.change_context], line_index, False)
            if ctx_index is None:
                raise ValueError(f"Failed to find context '{chunk.change_context}' in {file_display}")
            line_index = ctx_index + 1

        if not chunk.old_lines:
            insertion_index = len(original_lines) - 1 if original_lines and original_lines[-1] == "" else len(original_lines)
            replacements.append((insertion_index, 0, chunk.new_lines))
            continue

        pattern = list(chunk.old_lines)
        new_slice = list(chunk.new_lines)
        found = _seek_sequence(original_lines, pattern, line_index, chunk.is_end_of_file)
        if found is None and pattern and pattern[-1] == "":
            pattern = pattern[:-1]
            if new_slice and new_slice[-1] == "":
                new_slice = new_slice[:-1]
            found = _seek_sequence(original_lines, pattern, line_index, chunk.is_end_of_file)
        if found is None:
            block = "\n".join(chunk.old_lines)
            raise ValueError(f"Failed to find expected lines in {file_display}:\n{block}")

        replacements.append((found, len(pattern), new_slice))
        line_index = found + len(pattern)

    replacements.sort(key=lambda x: x[0])
    return replacements


def _apply_update_hunk(file_path: Path, chunks: list[UpdateFileChunk], display_path: str) -> str:
    original_contents = file_path.read_text(encoding="utf-8", errors="replace")
    original_lines = original_contents.split("\n")
    if original_lines and original_lines[-1] == "":
        original_lines.pop()

    replacements = _compute_replacements(original_lines, chunks, display_path)
    result = list(original_lines)
    for start_index, old_len, new_lines in reversed(replacements):
        for _ in range(old_len):
            if start_index < len(result):
                result.pop(start_index)
        for i, line in enumerate(new_lines):
            result.insert(start_index + i, line)
    if not result or result[-1] != "":
        result.append("")
    return "\n".join(result)


def _format_summary(summary: dict[str, list[str]]) -> str:
    lines = ["Success. Updated the following files:"]
    for p in summary["added"]:
        lines.append(f"A {p}")
    for p in summary["modified"]:
        lines.append(f"M {p}")
    for p in summary["deleted"]:
        lines.append(f"D {p}")
    return "\n".join(lines)


async def run_apply_patch_compat(params: dict) -> str:
    patch_input = (params.get("input") or "").strip()
    if not patch_input:
        return "Error: input is required."
    try:
        hunks = _parse_patch_text(patch_input)
        if not hunks:
            return "Error: No files were modified."
        root = _workspace_root()
        summary = {"added": [], "modified": [], "deleted": []}
        seen = {"added": set(), "modified": set(), "deleted": set()}

        def _record(bucket: str, display: str) -> None:
            if display not in seen[bucket]:
                seen[bucket].add(display)
                summary[bucket].append(display)

        for hunk in hunks:
            if isinstance(hunk, AddFileHunk):
                target, display = _resolve_workspace_path(hunk.path, root)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(hunk.contents, encoding="utf-8")
                _record("added", display)
                continue
            if isinstance(hunk, DeleteFileHunk):
                target, display = _resolve_workspace_path(hunk.path, root)
                if not target.exists():
                    raise ValueError(f"File does not exist: {display}")
                target.unlink()
                _record("deleted", display)
                continue

            target, display = _resolve_workspace_path(hunk.path, root)
            if not target.is_file():
                raise ValueError(f"File does not exist: {display}")
            applied = _apply_update_hunk(target, hunk.chunks, display)
            if hunk.move_path:
                move_target, move_display = _resolve_workspace_path(hunk.move_path, root)
                move_target.parent.mkdir(parents=True, exist_ok=True)
                move_target.write_text(applied, encoding="utf-8")
                target.unlink()
                _record("modified", move_display)
            else:
                target.write_text(applied, encoding="utf-8")
                _record("modified", display)

        return _format_summary(summary)
    except Exception as e:
        return f"Error: {e}"
