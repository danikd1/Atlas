"""
Рекурсивное чанкирование текста для RAG.

Разбиение по абзацам (\\n\\n), затем по строкам (\\n), затем по предложениям.
Лимит по токенам и перекрытие (overlap) между соседними чанками.
"""
from __future__ import annotations

import re
from typing import Any, List

import logging

logger = logging.getLogger(__name__)


def _count_tokens(text: str, tokenizer: Any) -> int:
    """Возвращает число токенов в тексте по переданному токенайзеру. Без токенайзера — приближение по символам (~4 символа/токен)."""
    if not text:
        return 0
    if tokenizer is not None:
        try:
            return len(tokenizer.encode(text, add_special_tokens=False, truncation=False))
        except Exception:
            pass
    return max(1, len(text) // 4)


def _split_by_sentences(text: str) -> List[str]:
    """Разбивает текст на предложения (по . ! ? с последующим пробелом)."""
    if not text or not text.strip():
        return []
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p.strip() for p in parts if p.strip()]


def _recursive_split(
    text: str,
    tokenizer: Any,
    max_tokens: int,
    separators: List[str],
) -> List[str]:
    """
    Рекурсивно разбивает текст по разделителям, пока сегменты не уложатся в max_tokens.
    separators: например ["\n\n", "\n", ". "] — сначала по абзацам, потом по строкам, потом по предложениям.
    """
    text = (text or "").strip()
    if not text:
        return []
    n = _count_tokens(text, tokenizer)
    if n <= max_tokens and n > 0:
        return [text]
    if not separators:
        # Последний уровень: режем по длине (приблизительно по символам)
        approx_chars = (max_tokens * 4)  # грубая оценка
        out = []
        start = 0
        while start < len(text):
            end = min(start + approx_chars, len(text))
            if end < len(text):
                # Пытаемся обрезать по границе слова/пробела
                last_space = text.rfind(" ", start, end + 1)
                if last_space > start:
                    end = last_space
            out.append(text[start:end].strip())
            start = end
        return [s for s in out if s]
    sep = separators[0]
    rest_seps = separators[1:]
    parts = [p.strip() for p in text.split(sep) if p.strip()]
    if len(parts) <= 1:
        return _recursive_split(text, tokenizer, max_tokens, rest_seps)
    segments = []
    for part in parts:
        segments.extend(_recursive_split(part, tokenizer, max_tokens, rest_seps))
    return segments


def merge_segments_with_overlap(
    segments: List[str],
    tokenizer: Any,
    max_tokens: int,
    overlap_tokens: int,
) -> List[str]:
    """
    Собирает сегменты в чанки не больше max_tokens, с перекрытием overlap_tokens
    (в начале каждого следующего чанка дублируются последние overlap_tokens предыдущего).
    """
    if not segments or max_tokens <= 0:
        return []
    chunks = []
    current: List[str] = []
    current_tokens = 0
    overlap_buffer: List[str] = []
    overlap_buffer_tokens = 0

    for seg in segments:
        seg_tokens = _count_tokens(seg, tokenizer)
        if seg_tokens <= 0:
            continue
        # Если один сегмент больше max_tokens — режем его по предложениям и снова собираем
        if seg_tokens > max_tokens:
            sub_segs = _split_by_sentences(seg)
            if sub_segs:
                for s in sub_segs:
                    st = _count_tokens(s, tokenizer)
                    if current_tokens + st > max_tokens and current:
                        chunk_text = " ".join(current)
                        chunks.append(chunk_text)
                        # overlap: последние сегменты, укладывающиеся в overlap_tokens
                        overlap_buffer = []
                        overlap_buffer_tokens = 0
                        for x in reversed(current):
                            xt = _count_tokens(x, tokenizer)
                            if overlap_buffer_tokens + xt <= overlap_tokens:
                                overlap_buffer.insert(0, x)
                                overlap_buffer_tokens += xt
                            else:
                                break
                        current = list(overlap_buffer)
                        current_tokens = overlap_buffer_tokens
                    current.append(s)
                    current_tokens += st
            continue
        if current_tokens + seg_tokens > max_tokens and current:
            chunk_text = " ".join(current)
            chunks.append(chunk_text)
            overlap_buffer = []
            overlap_buffer_tokens = 0
            for x in reversed(current):
                xt = _count_tokens(x, tokenizer)
                if overlap_buffer_tokens + xt <= overlap_tokens:
                    overlap_buffer.insert(0, x)
                    overlap_buffer_tokens += xt
                else:
                    break
            current = list(overlap_buffer)
            current_tokens = overlap_buffer_tokens
        current.append(seg)
        current_tokens += seg_tokens

    if current:
        chunks.append(" ".join(current))
    return chunks


def chunk_text_recursive(
    text: str,
    tokenizer: Any,
    max_tokens: int = 512,
    overlap_tokens: int = 50,
) -> List[str]:
    """
    Разбивает текст на чанки: сначала по абзацам (\\n\\n), затем по строкам (\\n),
    затем по предложениям. Размер чанка до max_tokens, между чанками overlap_tokens.

    Returns:
        Список строк-чанков.
    """
    if not text or not (text := text.strip()):
        return []
    # Сначала по абзацам, затем по строкам, затем по предложениям
    separators = ["\n\n", "\n", ". ", "? ", "! "]
    segments = _recursive_split(text, tokenizer, max_tokens, separators)
    if not segments:
        return [text] if text else []
    return merge_segments_with_overlap(segments, tokenizer, max_tokens, overlap_tokens)
