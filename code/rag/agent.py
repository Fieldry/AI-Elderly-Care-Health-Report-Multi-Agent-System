from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .page_index import page_index
from .page_index_md import md_to_tree
from .utils import DEFAULT_CHAT_MODEL


SUPPORTED_SOURCE_TYPES = {
    ".md": "markdown",
    ".markdown": "markdown",
    ".pdf": "pdf",
}


def _unique_keep_order(items: Iterable[str]) -> List[str]:
    seen = set()
    output: List[str] = []
    for item in items:
        if not item:
            continue
        if item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output


def _normalize_text(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "||".join(str(part or "") for part in parts)
    digest = hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def _shorten_text(text: Any, max_len: int = 240) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(value) <= max_len:
        return value
    return f"{value[: max_len - 3].rstrip()}..."


def _tokenize_query(query: str) -> List[str]:
    normalized = _normalize_text(query)
    if not normalized:
        return []

    tokens: List[str] = []
    for item in re.findall(r"[\u4e00-\u9fff]{2,}|[a-z0-9_]+", normalized):
        tokens.append(item)
        if re.fullmatch(r"[\u4e00-\u9fff]{3,}", item):
            tokens.extend(item[idx: idx + 2] for idx in range(len(item) - 1))
    return _unique_keep_order(tokens)


class PageIndexRAGAgent:
    """基于 PageIndex 结构树的轻量检索 Agent。"""

    def __init__(self, index_path: Optional[str] = None, model: Optional[str] = None):
        self.model = model or DEFAULT_CHAT_MODEL
        self.index_path = str(Path(index_path).resolve()) if index_path else None
        self.index_data: Optional[Dict[str, Any]] = None

        if self.index_path and Path(self.index_path).exists():
            self.index_data = self.load_index(self.index_path)

    def build_index(
        self,
        source_paths: Sequence[str] | str,
        output_path: str,
        if_add_node_summary: str = "no",
        summary_token_threshold: int = 200,
        if_add_doc_description: str = "yes",
    ) -> Dict[str, Any]:
        sources = self._collect_source_paths(source_paths)
        if not sources:
            raise ValueError("未找到可索引的 Markdown/PDF 文档")

        documents: List[Dict[str, Any]] = []
        chunks: List[Dict[str, Any]] = []

        for doc_index, source_path in enumerate(sources, start=1):
            doc_result = self._build_document_result(
                source_path=source_path,
                if_add_node_summary=if_add_node_summary,
                summary_token_threshold=summary_token_threshold,
                if_add_doc_description=if_add_doc_description,
            )
            doc_id = _stable_id("doc", doc_index, source_path)
            doc_result["doc_id"] = doc_id
            documents.append(doc_result)
            chunks.extend(
                self._flatten_structure(
                    structure=doc_result.get("structure", []),
                    doc_id=doc_id,
                    doc_name=doc_result.get("doc_name") or source_path.stem,
                    source_path=str(source_path.resolve()),
                    source_type=doc_result.get("source_type", "unknown"),
                )
            )

        index_data = {
            "built_at": datetime.now().isoformat(),
            "model": self.model,
            "documents": documents,
            "chunks": chunks,
        }
        index_data = self._finalize_index_data(index_data)

        output = Path(output_path).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", encoding="utf-8") as file:
            json.dump(index_data, file, ensure_ascii=False, indent=2)

        self.index_path = str(output)
        self.index_data = index_data
        return index_data

    def load_index(self, index_path: Optional[str] = None) -> Dict[str, Any]:
        target_path = Path(index_path or self.index_path or "").resolve()
        if not target_path.exists():
            raise FileNotFoundError(f"索引文件不存在: {target_path}")
        with open(target_path, "r", encoding="utf-8") as file:
            data = json.load(file)
        data = self._finalize_index_data(data)
        self.index_path = str(target_path)
        self.index_data = data
        return data

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        index_data = self._require_index()
        tokens = _tokenize_query(query)
        normalized_query = _normalize_text(query)

        hits: List[Dict[str, Any]] = []
        for chunk in index_data.get("chunks", []):
            score, matched_terms = self._score_chunk(chunk, tokens, normalized_query)
            if score <= 0:
                continue

            excerpt = self._build_excerpt(chunk, matched_terms)
            hits.append(
                {
                    "score": score,
                    "doc_name": chunk.get("doc_name"),
                    "source_path": chunk.get("source_path"),
                    "source_type": chunk.get("source_type"),
                    "title": chunk.get("title"),
                    "path": chunk.get("path"),
                    "node_id": chunk.get("node_id"),
                    "start_index": chunk.get("start_index"),
                    "end_index": chunk.get("end_index"),
                    "line_num": chunk.get("line_num"),
                    "matched_terms": matched_terms,
                    "excerpt": excerpt,
                    "text": chunk.get("text", ""),
                }
            )

        hits.sort(key=lambda item: (-item["score"], item.get("doc_name") or "", item.get("path") or ""))
        return hits[:top_k]

    def build_context(self, query: str, top_k: int = 3) -> Dict[str, Any]:
        hits = self.retrieve(query, top_k=top_k)
        context_parts = []
        for idx, hit in enumerate(hits, start=1):
            location = []
            if hit.get("line_num") is not None:
                location.append(f"line={hit['line_num']}")
            if hit.get("start_index") is not None:
                location.append(f"page={hit['start_index']}")
            location_text = f" ({', '.join(location)})" if location else ""
            context_parts.append(
                f"[参考{idx}] {hit.get('doc_name', '未知文档')} / {hit.get('path', hit.get('title', '未命名节点'))}{location_text}\n"
                f"{hit.get('excerpt', '')}"
            )

        return {
            "query": query,
            "hits": hits,
            "context": "\n\n".join(context_parts),
        }

    def retrieve_for_profile(
        self,
        profile: Any,
        status_result: Dict[str, Any],
        risk_result: Dict[str, Any],
        factor_result: Dict[str, Any],
        top_k: int = 3,
    ) -> Dict[str, Any]:
        query = self.build_profile_query(profile, status_result, risk_result, factor_result)
        payload = self.build_context(query, top_k=top_k)
        payload["enabled"] = True
        return payload

    def build_profile_query(
        self,
        profile: Any,
        status_result: Dict[str, Any],
        risk_result: Dict[str, Any],
        factor_result: Dict[str, Any],
    ) -> str:
        chronic_fields = {
            "hypertension": "高血压",
            "diabetes": "糖尿病",
            "heart_disease": "心脏病",
            "stroke": "中风",
            "arthritis": "关节炎",
            "cancer": "肿瘤",
        }

        active_conditions = [
            label
            for field, label in chronic_fields.items()
            if str(getattr(profile, field, "") or "").strip() in {"是", "有", "患有", "1", "true", "True"}
        ]

        risk_names = [
            item.get("risk", "")
            for item in (risk_result.get("short_term_risks", []) + risk_result.get("medium_term_risks", []))
        ]

        factor_keywords = []
        for item in factor_result.get("main_problems", []) or []:
            if isinstance(item, str):
                factor_keywords.append(item)
            elif isinstance(item, dict):
                factor_keywords.extend(
                    [item.get("problem", ""), item.get("impact", "")]
                )

        query_parts = _unique_keep_order(
            [
                f"{getattr(profile, 'age', '')}岁老人",
                str(getattr(profile, "sex", "") or ""),
                status_result.get("status_name", ""),
                risk_result.get("overall_risk_level", ""),
                *risk_names[:4],
                *factor_keywords[:4],
                *active_conditions,
                "老年照护",
                "居家照护",
            ]
        )
        return " ".join([part for part in query_parts if str(part).strip()])

    def _require_index(self) -> Dict[str, Any]:
        if self.index_data is None:
            if not self.index_path:
                raise ValueError("RAG 索引尚未加载，请先 build_index 或 load_index")
            self.index_data = self.load_index(self.index_path)
        return self.index_data

    def _collect_source_paths(self, source_paths: Sequence[str] | str) -> List[Path]:
        if isinstance(source_paths, (str, os.PathLike)):
            raw_inputs = [source_paths]
        else:
            raw_inputs = list(source_paths)

        collected: List[Path] = []
        for raw in raw_inputs:
            path = Path(raw).expanduser().resolve()
            if not path.exists():
                continue
            if path.is_dir():
                for suffix in SUPPORTED_SOURCE_TYPES:
                    collected.extend(sorted(path.rglob(f"*{suffix}")))
            elif path.suffix.lower() in SUPPORTED_SOURCE_TYPES:
                collected.append(path)

        unique_paths = []
        seen = set()
        for path in collected:
            resolved = str(path.resolve())
            if resolved in seen:
                continue
            seen.add(resolved)
            unique_paths.append(path)
        return unique_paths

    def _build_document_result(
        self,
        source_path: Path,
        if_add_node_summary: str,
        summary_token_threshold: int,
        if_add_doc_description: str,
    ) -> Dict[str, Any]:
        source_type = SUPPORTED_SOURCE_TYPES.get(source_path.suffix.lower())
        if source_type == "markdown":
            result = asyncio.run(
                md_to_tree(
                    md_path=str(source_path),
                    if_thinning=False,
                    min_token_threshold=None,
                    if_add_node_summary=if_add_node_summary,
                    summary_token_threshold=summary_token_threshold,
                    model=self.model,
                    if_add_doc_description=if_add_doc_description,
                    if_add_node_text="yes",
                    if_add_node_id="yes",
                )
            )
        elif source_type == "pdf":
            result = page_index(
                str(source_path),
                model=self.model,
                if_add_node_id="yes",
                if_add_node_summary=if_add_node_summary,
                if_add_doc_description=if_add_doc_description,
                if_add_node_text="yes",
            )
        else:
            raise ValueError(f"不支持的文档类型: {source_path}")

        result["source_path"] = str(source_path.resolve())
        result["source_type"] = source_type
        return result

    def _flatten_structure(
        self,
        structure: Any,
        doc_id: str,
        doc_name: str,
        source_path: str,
        source_type: str,
        parents: Optional[List[str]] = None,
        level: int = 1,
    ) -> List[Dict[str, Any]]:
        if parents is None:
            parents = []

        chunks: List[Dict[str, Any]] = []

        if isinstance(structure, list):
            for node in structure:
                chunks.extend(
                    self._flatten_structure(
                        structure=node,
                        doc_id=doc_id,
                        doc_name=doc_name,
                        source_path=source_path,
                        source_type=source_type,
                        parents=parents,
                        level=level,
                    )
                )
            return chunks

        if not isinstance(structure, dict):
            return chunks

        title = structure.get("title", "")
        path_titles = [*parents, title] if title else parents
        chunks.append(
            {
                "doc_id": doc_id,
                "doc_name": doc_name,
                "source_path": source_path,
                "source_type": source_type,
                "title": title,
                "path": " > ".join(path_titles),
                "level": level,
                "node_id": structure.get("node_id"),
                "summary": structure.get("summary") or structure.get("prefix_summary") or "",
                "text": structure.get("text") or "",
                "line_num": structure.get("line_num"),
                "start_index": structure.get("start_index"),
                "end_index": structure.get("end_index"),
            }
        )

        for child in structure.get("nodes", []) or []:
            chunks.extend(
                self._flatten_structure(
                    structure=child,
                    doc_id=doc_id,
                    doc_name=doc_name,
                    source_path=source_path,
                    source_type=source_type,
                    parents=path_titles,
                    level=level + 1,
                )
            )
        return chunks

    @staticmethod
    def _is_outline_candidate(title: str, level: int) -> bool:
        normalized = _normalize_text(title)
        if not normalized:
            return False
        if normalized in {"preface", "contents", "目 次", "目次", "目录", "前言"}:
            return False
        return level <= 3

    def _build_outline_nodes(self, chunks: List[Dict[str, Any]], limit: int = 40) -> List[Dict[str, Any]]:
        outline: List[Dict[str, Any]] = []
        seen_paths = set()
        for chunk in sorted(chunks, key=lambda item: (item.get("level", 99), item.get("path") or "")):
            title = str(chunk.get("title") or "").strip()
            path = str(chunk.get("path") or "").strip()
            level = int(chunk.get("level") or 99)
            if not self._is_outline_candidate(title, level):
                continue
            if path in seen_paths:
                continue
            seen_paths.add(path)
            outline.append(
                {
                    "node_id": chunk.get("node_id"),
                    "title": title,
                    "path": path,
                    "summary": _shorten_text(chunk.get("summary") or chunk.get("text"), 180),
                    "level": level,
                }
            )
            if len(outline) >= limit:
                break
        return outline

    def _synthesize_doc_summary(self, document: Dict[str, Any], chunks: List[Dict[str, Any]]) -> str:
        doc_description = str(document.get("doc_description") or "").strip()
        if doc_description:
            return _shorten_text(doc_description, 240)

        outline = self._build_outline_nodes(chunks, limit=6)
        titles = [item["title"] for item in outline if item.get("title")]
        if titles:
            return _shorten_text(
                f"重点章节包括：{'；'.join(titles[:6])}。适合从这些章节中继续定位与病例相关的建议和标准。",
                240,
            )

        first_text = next((str(chunk.get("text") or "").strip() for chunk in chunks if str(chunk.get("text") or "").strip()), "")
        if first_text:
            return _shorten_text(first_text, 240)

        return _shorten_text(document.get("doc_name"), 240)

    def _finalize_index_data(self, index_data: Dict[str, Any]) -> Dict[str, Any]:
        documents = index_data.get("documents", []) or []
        chunks = index_data.get("chunks", []) or []

        doc_lookup: Dict[str, Dict[str, Any]] = {}
        doc_chunks: Dict[str, List[Dict[str, Any]]] = {}
        for doc_index, document in enumerate(documents, start=1):
            doc_id = document.get("doc_id") or _stable_id(
                "doc",
                doc_index,
                document.get("source_path"),
                document.get("doc_name"),
            )
            document["doc_id"] = doc_id
            doc_lookup[doc_id] = document
            doc_chunks.setdefault(doc_id, [])

        for chunk_index, chunk in enumerate(chunks, start=1):
            source_path = chunk.get("source_path")
            doc_name = chunk.get("doc_name")
            doc_id = chunk.get("doc_id")
            if not doc_id:
                matched_doc = next(
                    (
                        document
                        for document in documents
                        if document.get("source_path") == source_path and document.get("doc_name") == doc_name
                    ),
                    None,
                )
                if matched_doc is None:
                    doc_id = _stable_id("doc", source_path, doc_name)
                    matched_doc = {
                        "doc_id": doc_id,
                        "doc_name": doc_name,
                        "source_path": source_path,
                        "source_type": chunk.get("source_type"),
                        "structure": [],
                    }
                    documents.append(matched_doc)
                else:
                    doc_id = matched_doc["doc_id"]
                chunk["doc_id"] = doc_id
                doc_lookup[doc_id] = matched_doc
                doc_chunks.setdefault(doc_id, [])
            source_node_id = chunk.get("node_id")
            chunk["source_node_id"] = source_node_id
            chunk["node_id"] = _stable_id(
                "node",
                doc_id,
                source_node_id,
                chunk_index,
                chunk.get("path"),
                chunk.get("title"),
            )
            chunk["level"] = int(chunk.get("level") or max(len(str(chunk.get("path") or "").split(" > ")), 1))
            chunk["summary"] = _shorten_text(chunk.get("summary"), 240)
            doc_chunks.setdefault(doc_id, []).append(chunk)

        document_catalog: List[Dict[str, Any]] = []
        node_catalog: List[Dict[str, Any]] = []

        for document in documents:
            doc_id = document["doc_id"]
            current_chunks = doc_chunks.get(doc_id, [])
            doc_summary = self._synthesize_doc_summary(document, current_chunks)
            document["doc_summary"] = doc_summary
            outline_nodes = self._build_outline_nodes(current_chunks)
            document["outline_nodes"] = outline_nodes
            document_catalog.append(
                {
                    "doc_id": doc_id,
                    "doc_name": document.get("doc_name"),
                    "source_path": document.get("source_path"),
                    "source_type": document.get("source_type"),
                    "doc_summary": doc_summary,
                    "chunk_count": len(current_chunks),
                    "outline_nodes": outline_nodes,
                }
            )

            seen_paths = set()
            for chunk in sorted(current_chunks, key=lambda item: (item.get("level", 99), item.get("path") or "")):
                path = str(chunk.get("path") or "").strip()
                if path in seen_paths:
                    continue
                seen_paths.add(path)
                node_catalog.append(
                    {
                        "node_id": chunk.get("node_id"),
                        "doc_id": doc_id,
                        "doc_name": chunk.get("doc_name"),
                        "title": chunk.get("title"),
                        "path": path,
                        "summary": _shorten_text(chunk.get("summary") or chunk.get("text"), 220),
                        "level": chunk.get("level"),
                        "line_num": chunk.get("line_num"),
                        "start_index": chunk.get("start_index"),
                        "end_index": chunk.get("end_index"),
                        "source_path": chunk.get("source_path"),
                        "source_type": chunk.get("source_type"),
                        "source_node_id": chunk.get("source_node_id"),
                    }
                )

        index_data["documents"] = documents
        index_data["chunks"] = chunks
        index_data["document_catalog"] = document_catalog
        index_data["node_catalog"] = node_catalog
        return index_data

    def get_document_catalog(self) -> List[Dict[str, Any]]:
        index_data = self._require_index()
        return list(index_data.get("document_catalog", []))

    def get_node_catalog(
        self,
        doc_ids: Optional[Sequence[str]] = None,
        max_level: int = 3,
        limit_per_doc: int = 40,
    ) -> List[Dict[str, Any]]:
        index_data = self._require_index()
        allowed_doc_ids = set(doc_ids or [])
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for node in index_data.get("node_catalog", []):
            if allowed_doc_ids and node.get("doc_id") not in allowed_doc_ids:
                continue
            if int(node.get("level") or 99) > max_level:
                continue
            grouped.setdefault(node.get("doc_id"), []).append(node)

        selected: List[Dict[str, Any]] = []
        for doc_id, nodes in grouped.items():
            for node in sorted(nodes, key=lambda item: (item.get("level", 99), item.get("path") or ""))[:limit_per_doc]:
                selected.append(node)
        return selected

    def get_nodes_by_ids(self, node_ids: Sequence[str]) -> List[Dict[str, Any]]:
        index_data = self._require_index()
        lookup = {chunk.get("node_id"): chunk for chunk in index_data.get("chunks", [])}
        matched = []
        for node_id in node_ids:
            chunk = lookup.get(node_id)
            if chunk is not None:
                matched.append(chunk)
        return matched

    def _score_chunk(
        self,
        chunk: Dict[str, Any],
        query_tokens: List[str],
        normalized_query: str,
    ) -> tuple[int, List[str]]:
        title = _normalize_text(chunk.get("title"))
        path = _normalize_text(chunk.get("path"))
        summary = _normalize_text(chunk.get("summary"))
        text = _normalize_text(chunk.get("text"))

        score = 0
        matched_terms: List[str] = []

        if normalized_query and normalized_query in title:
            score += 15
            matched_terms.append(normalized_query)
        elif normalized_query and normalized_query in text:
            score += 8
            matched_terms.append(normalized_query)

        for token in query_tokens:
            if token in title:
                score += 8
                matched_terms.append(token)
            elif token in path:
                score += 5
                matched_terms.append(token)
            elif token in summary:
                score += 4
                matched_terms.append(token)
            elif token in text:
                score += 2
                matched_terms.append(token)

        return score, _unique_keep_order(matched_terms)

    def _build_excerpt(self, chunk: Dict[str, Any], matched_terms: List[str], max_len: int = 280) -> str:
        base_text = str(chunk.get("text") or chunk.get("summary") or chunk.get("title") or "").strip()
        if not base_text:
            return ""

        lowered = base_text.lower()
        for token in matched_terms:
            position = lowered.find(token.lower())
            if position >= 0:
                start = max(position - 80, 0)
                end = min(position + max_len, len(base_text))
                snippet = base_text[start:end].strip()
                return snippet if start == 0 else f"...{snippet}"

        return base_text[:max_len].strip()
