"""
PDF 导出：将报告 payload 转为 PDF bytes（基于 fpdf2）。
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from fpdf import FPDF

from report_utils import generate_markdown_report

# -- 中文字体查找 ----------------------------------------------------------

_FONT_SEARCH_PATHS: List[Path] = [
    Path("/System/Library/Fonts/STHeiti Medium.ttc"),
    Path("/System/Library/Fonts/STHeiti Light.ttc"),
    Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
    Path("/System/Library/Fonts/Supplemental/Songti.ttc"),
    Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
]

_BUILTIN_FONT = "Helvetica"


def _find_cjk_font() -> Path | None:
    for path in _FONT_SEARCH_PATHS:
        if path.exists():
            return path
    return None


# -- Markdown → PDF 渲染 ---------------------------------------------------

_HEADING_RE = re.compile(r"^(#{1,3})\s+(.*)")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_RE = re.compile(r"\*(.+?)\*")
_ORDERED_RE = re.compile(r"^\d+[.)、]\s*(.*)")
_UNORDERED_RE = re.compile(r"^[-*]\s+(.*)")

# Colors
_H1_COLOR = (42, 100, 150)
_H2_COLOR = (42, 100, 150)
_H3_COLOR = (51, 51, 51)
_BODY_COLOR = (34, 34, 34)
_MUTED_COLOR = (102, 102, 102)


class _ReportPDF(FPDF):
    """FPDF subclass with helpers for the health report layout."""

    def __init__(self, font_path: Path | None):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_auto_page_break(auto=True, margin=20)
        self._font_name = _BUILTIN_FONT
        if font_path:
            name = "CJK"
            self.add_font(name, fname=str(font_path), uni=True)
            self.add_font(name, style="B", fname=str(font_path), uni=True)
            self.add_font(name, style="I", fname=str(font_path), uni=True)
            self._font_name = name

    def _set_font(self, style: str = "", size: int = 11):
        self.set_font(self._font_name, style=style, size=size)

    def _colored_text(self, r: int, g: int, b: int):
        self.set_text_color(r, g, b)

    def render_markdown(self, md_text: str):
        """Parse markdown line by line and render into the PDF."""
        self.add_page()
        lines = md_text.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # Blank line → small gap
            if not stripped:
                self.ln(2)
                i += 1
                continue

            # Horizontal rule
            if stripped in ("---", "***", "___"):
                y = self.get_y()
                self.set_draw_color(200, 200, 200)
                self.line(self.l_margin, y, self.w - self.r_margin, y)
                self.ln(4)
                i += 1
                continue

            # Headings
            heading_match = _HEADING_RE.match(stripped)
            if heading_match:
                level = len(heading_match.group(1))
                text = heading_match.group(2).strip()
                self._render_heading(text, level)
                i += 1
                continue

            # Ordered list
            ordered_match = _ORDERED_RE.match(stripped)
            if ordered_match:
                self._render_list_item(ordered_match.group(1), ordered=True)
                i += 1
                continue

            # Unordered list
            unordered_match = _UNORDERED_RE.match(stripped)
            if unordered_match:
                self._render_list_item(unordered_match.group(1), ordered=False)
                i += 1
                continue

            # Normal paragraph
            self._render_paragraph(stripped)
            i += 1

    def _render_heading(self, text: str, level: int):
        if level == 1:
            self.ln(3)
            self._colored_text(*_H1_COLOR)
            self._set_font("B", 18)
            self.cell(0, 12, text, align="C", new_x="LMARGIN", new_y="NEXT")
            # underline
            y = self.get_y()
            self.set_draw_color(*_H1_COLOR)
            self.set_line_width(0.5)
            self.line(self.l_margin, y, self.w - self.r_margin, y)
            self.ln(5)
        elif level == 2:
            self.ln(4)
            self._colored_text(*_H2_COLOR)
            self._set_font("B", 14)
            # left accent bar
            y = self.get_y()
            self.set_fill_color(*_H2_COLOR)
            self.rect(self.l_margin, y, 1.2, 7, "F")
            self.set_x(self.l_margin + 4)
            self.cell(0, 7, text, new_x="LMARGIN", new_y="NEXT")
            self.ln(2)
        else:
            self.ln(2)
            self._colored_text(*_H3_COLOR)
            self._set_font("B", 12)
            self.cell(0, 7, text, new_x="LMARGIN", new_y="NEXT")
            self.ln(1)

    def _render_list_item(self, text: str, ordered: bool):
        self._colored_text(*_BODY_COLOR)
        self._set_font(size=11)
        bullet = "·  " if not ordered else ""
        indent = self.l_margin + 6
        self.set_x(indent)
        self._write_rich_text(bullet + text, line_height=6)
        self.ln(1)

    def _render_paragraph(self, text: str):
        self._colored_text(*_BODY_COLOR)
        self._set_font(size=11)
        # Check if it's an italic-only line (footer)
        if text.startswith("*") and text.endswith("*") and not text.startswith("**"):
            self._colored_text(*_MUTED_COLOR)
            self._set_font("I", 9)
            clean = text.strip("*").strip()
            self.multi_cell(0, 5, clean)
            self.ln(1)
            return
        self._write_rich_text(text, line_height=6)
        self.ln(1)

    def _write_rich_text(self, text: str, line_height: float = 6):
        """Write text with **bold** inline formatting via multi_cell."""
        # For simplicity, strip markdown bold/italic markers and render plain
        # fpdf2 doesn't support inline style switching inside multi_cell easily,
        # so we render bold segments by splitting.
        segments = _split_bold_segments(text)
        if len(segments) == 1 and not segments[0][1]:
            # All plain text
            self.multi_cell(0, line_height, segments[0][0])
            return

        # Mix of bold and normal — use write() for inline rendering
        for content, is_bold in segments:
            if is_bold:
                self._set_font("B", 11)
            else:
                self._set_font(size=11)
            self.write(line_height, content)
        self.ln(line_height)


def _split_bold_segments(text: str) -> List[tuple[str, bool]]:
    """Split text into (content, is_bold) segments."""
    segments: List[tuple[str, bool]] = []
    last_end = 0
    for match in _BOLD_RE.finditer(text):
        if match.start() > last_end:
            plain = text[last_end : match.start()]
            # Strip italic markers from plain text
            plain = _ITALIC_RE.sub(r"\1", plain)
            segments.append((plain, False))
        segments.append((match.group(1), True))
        last_end = match.end()
    if last_end < len(text):
        remaining = text[last_end:]
        remaining = _ITALIC_RE.sub(r"\1", remaining)
        segments.append((remaining, False))
    return segments if segments else [(text, False)]


# -- 公共 API --------------------------------------------------------------


def generate_report_pdf(payload: Dict[str, Any]) -> bytes:
    """将报告 payload 转为 PDF bytes。"""
    profile = payload.get("profile") or {}
    results = payload.get("raw_results") or {}
    report_data = payload.get("report_data") or {}
    generated_at = payload.get("generated_at") or ""

    try:
        timestamp = datetime.fromisoformat(str(generated_at))
    except (ValueError, TypeError):
        timestamp = datetime.now()

    markdown_text = generate_markdown_report(profile, results, report_data, timestamp)

    font_path = _find_cjk_font()
    pdf = _ReportPDF(font_path)
    pdf.render_markdown(markdown_text)
    return bytes(pdf.output())
