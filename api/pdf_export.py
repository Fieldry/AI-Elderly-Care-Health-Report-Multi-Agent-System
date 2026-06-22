"""
PDF 导出：将报告 payload 转为 PDF bytes（基于 ReportLab）。
"""

from __future__ import annotations

import html
from io import BytesIO
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

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
    Path("/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.otf"),
    Path("/usr/share/fonts/google-noto-cjk/NotoSerifCJK-Regular.ttc"),
]

_BUILTIN_FONT = "Helvetica"
_CJK_FONT_NAME = "CJKHealthReport"
_CID_CJK_FONT_NAME = "STSong-Light"
_FONT_SEARCH_DIRS: List[Path] = [
    Path("/usr/share/fonts/google-noto-cjk"),
    Path("/usr/share/fonts/truetype/noto"),
    Path("/usr/share/fonts/opentype/noto"),
    Path("/usr/share/fonts"),
]
_FONT_NAME_PATTERNS = [
    "NotoSansCJK*Regular*.otf",
    "NotoSansCJK*Regular*.ttf",
    "NotoSerifCJK*Regular*.otf",
    "NotoSerifCJK*Regular*.ttf",
    "SourceHanSans*Regular*.otf",
    "SourceHanSans*Regular*.ttf",
    "SourceHanSerif*Regular*.otf",
    "SourceHanSerif*Regular*.ttf",
    "wqy-microhei*.ttc",
    "wqy-zenhei*.ttc",
    "NotoSansCJK*Regular*.ttc",
    "NotoSerifCJK*Regular*.ttc",
]
_TTC_SIMPLIFIED_CHINESE_MARKERS = (
    "cjk sc",
    "simplified chinese",
    "简体",
    "sc",
)
_FONT_CACHE_DIR = Path("/tmp/ai_elderly_pdf_fonts")


def _find_cjk_font() -> Path | None:
    for path in _FONT_SEARCH_PATHS:
        if path.exists():
            return _prepare_font_for_pdf(path)
    for directory in _FONT_SEARCH_DIRS:
        if not directory.exists():
            continue
        for pattern in _FONT_NAME_PATTERNS:
            match = next(directory.rglob(pattern), None)
            if match and match.exists():
                return _prepare_font_for_pdf(match)
    return None


def _prepare_font_for_pdf(font_path: Path) -> Path:
    """Return a single-font file that the PDF engine can embed reliably."""
    if font_path.suffix.lower() != ".ttc":
        return font_path

    extracted = _extract_simplified_chinese_font_from_ttc(font_path)
    return extracted or font_path


def _extract_simplified_chinese_font_from_ttc(font_path: Path) -> Path | None:
    """Extract one SC face from a TTC collection for stable PDF embedding."""
    try:
        from fontTools.ttLib import TTCollection
    except ImportError:
        return None

    try:
        collection = TTCollection(str(font_path))
    except Exception:
        return None

    selected_index = 0
    for index, font in enumerate(collection.fonts):
        names = _font_name_candidates(font)
        if any(marker in name for name in names for marker in _TTC_SIMPLIFIED_CHINESE_MARKERS):
            selected_index = index
            break

    cache_path = _FONT_CACHE_DIR / f"{font_path.stem}-{selected_index}.ttf"
    try:
        _FONT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        if not cache_path.exists() or cache_path.stat().st_mtime < font_path.stat().st_mtime:
            collection.fonts[selected_index].save(str(cache_path))
    except Exception:
        return None
    return cache_path


def _font_name_candidates(font: Any) -> List[str]:
    names: List[str] = []
    try:
        name_table = font["name"]
    except Exception:
        return names

    for record in name_table.names:
        if record.nameID not in {1, 2, 4, 16, 17}:
            continue
        try:
            names.append(record.toUnicode().lower())
        except Exception:
            continue
    return names


# -- Markdown → PDF 渲染 ---------------------------------------------------

_HEADING_RE = re.compile(r"^(#{1,3})\s+(.*)")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_RE = re.compile(r"\*(.+?)\*")
_ORDERED_RE = re.compile(r"^\d+[.)、]\s*(.*)")
_UNORDERED_RE = re.compile(r"^[-*]\s+(.*)")

# Colors
_H1_COLOR = colors.HexColor("#2A6496")
_H2_COLOR = colors.HexColor("#2A6496")
_H3_COLOR = colors.HexColor("#333333")
_BODY_COLOR = colors.HexColor("#222222")
_MUTED_COLOR = colors.HexColor("#666666")


def _register_pdf_font(font_path: Path | None) -> str:
    if font_path:
        try:
            pdfmetrics.getFont(_CJK_FONT_NAME)
            return _CJK_FONT_NAME
        except KeyError:
            pass

        try:
            pdfmetrics.registerFont(TTFont(_CJK_FONT_NAME, str(font_path)))
            return _CJK_FONT_NAME
        except Exception:
            pass

    try:
        pdfmetrics.getFont(_CID_CJK_FONT_NAME)
    except KeyError:
        try:
            pdfmetrics.registerFont(UnicodeCIDFont(_CID_CJK_FONT_NAME))
        except Exception:
            return _BUILTIN_FONT
    return _CID_CJK_FONT_NAME


def _build_styles(font_name: str) -> Dict[str, ParagraphStyle]:
    base = ParagraphStyle(
        "ReportBody",
        fontName=font_name,
        fontSize=11,
        leading=18,
        textColor=_BODY_COLOR,
        wordWrap="CJK",
        spaceAfter=4,
    )
    return {
        "body": base,
        "h1": ParagraphStyle(
            "ReportH1",
            parent=base,
            fontSize=18,
            leading=26,
            alignment=1,
            textColor=_H1_COLOR,
            spaceBefore=8,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "ReportH2",
            parent=base,
            fontSize=14,
            leading=22,
            textColor=_H2_COLOR,
            leftIndent=6,
            borderColor=_H2_COLOR,
            borderWidth=0,
            borderPadding=0,
            spaceBefore=10,
            spaceAfter=4,
        ),
        "h3": ParagraphStyle(
            "ReportH3",
            parent=base,
            fontSize=12,
            leading=19,
            textColor=_H3_COLOR,
            spaceBefore=6,
            spaceAfter=2,
        ),
        "list": ParagraphStyle(
            "ReportList",
            parent=base,
            leftIndent=14,
            firstLineIndent=-10,
            spaceAfter=3,
        ),
        "muted": ParagraphStyle(
            "ReportMuted",
            parent=base,
            fontSize=9,
            leading=14,
            textColor=_MUTED_COLOR,
        ),
    }


def _render_markdown_to_flowables(md_text: str, styles: Dict[str, ParagraphStyle]) -> List[Any]:
    flowables: List[Any] = []
    for line in md_text.split("\n"):
        stripped = line.strip()
        if not stripped:
            flowables.append(Spacer(1, 4))
            continue

        if stripped in ("---", "***", "___"):
            flowables.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#C8C8C8")))
            flowables.append(Spacer(1, 6))
            continue

        heading_match = _HEADING_RE.match(stripped)
        if heading_match:
            level = len(heading_match.group(1))
            text = _markdown_inline_to_reportlab(heading_match.group(2).strip())
            if level == 1:
                flowables.append(Paragraph(text, styles["h1"]))
                flowables.append(HRFlowable(width="100%", thickness=0.8, color=_H1_COLOR))
                flowables.append(Spacer(1, 8))
            elif level == 2:
                flowables.append(Paragraph(text, styles["h2"]))
            else:
                flowables.append(Paragraph(text, styles["h3"]))
            continue

        ordered_match = _ORDERED_RE.match(stripped)
        if ordered_match:
            flowables.append(Paragraph(_markdown_inline_to_reportlab(ordered_match.group(1)), styles["list"]))
            continue

        unordered_match = _UNORDERED_RE.match(stripped)
        if unordered_match:
            flowables.append(Paragraph("• " + _markdown_inline_to_reportlab(unordered_match.group(1)), styles["list"]))
            continue

        if stripped.startswith("*") and stripped.endswith("*") and not stripped.startswith("**"):
            flowables.append(Paragraph(_markdown_inline_to_reportlab(stripped.strip("*").strip()), styles["muted"]))
            continue

        flowables.append(Paragraph(_markdown_inline_to_reportlab(stripped), styles["body"]))
    return flowables


def _markdown_inline_to_reportlab(text: str) -> str:
    pieces: List[str] = []
    last_end = 0
    for match in _BOLD_RE.finditer(text):
        if match.start() > last_end:
            plain = _ITALIC_RE.sub(r"\1", text[last_end : match.start()])
            pieces.append(html.escape(plain))
        pieces.append(f"<b>{html.escape(match.group(1))}</b>")
        last_end = match.end()
    if last_end < len(text):
        remaining = _ITALIC_RE.sub(r"\1", text[last_end:])
        pieces.append(html.escape(remaining))
    return "".join(pieces) if pieces else html.escape(text)


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

    font_name = _register_pdf_font(_find_cjk_font())
    styles = _build_styles(font_name)
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="健康评估与照护行动计划",
    )
    doc.build(_render_markdown_to_flowables(markdown_text, styles))
    return buffer.getvalue()
