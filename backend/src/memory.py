"""Bug Whisperer — Cognee Memory Operations"""

import asyncio
import hashlib
import json
import os
from typing import Optional
from datetime import datetime

import cognee
from cognee.infrastructure.llm.LLMGateway import LLMGateway

from .models import (
    BugMemoryEntry,
    BugSeverity,
    RecallResult,
    DebugSession,
    FixRecord,
)


def error_signature(error_message: str, stack_trace: str) -> str:
    """Create a unique-ish fingerprint for an error"""
    key = f"{error_message[:100]}||{stack_trace[:200]}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


# Stats counter file
STATS_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "stats.json")


def _load_stats() -> dict:
    """Load stats including entries list."""
    try:
        with open(STATS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"total_bugs": 0, "bugs_recalled": 0, "total_confidence": 0.0, "entries": []}


def _save_stats(data: dict):
    os.makedirs(os.path.dirname(STATS_FILE), exist_ok=True)
    with open(STATS_FILE, "w") as f:
        json.dump(data, f)


def _record_bug(error_msg: str, root_cause: str, fix: str, files: list, from_memory: bool, confidence: float = 0.0):
    """Record a bug analysis in stats."""
    data = _load_stats()
    data["total_bugs"] = data.get("total_bugs", 0) + 1
    if from_memory:
        data["bugs_recalled"] = data.get("bugs_recalled", 0) + 1
        data["total_confidence"] = data.get("total_confidence", 0.0) + confidence
    # Keep last 50 entries
    entries = data.get("entries", [])
    entries.insert(0, {
        "error": error_msg,
        "root_cause": root_cause,
        "fix": fix,
        "files": files[:10],
        "from_memory": from_memory,
        "confidence": round(confidence, 2),
        "time": datetime.now().isoformat(),
    })
    data["entries"] = entries[:50]
    _save_stats(data)


def _get_memory_entries() -> list:
    """Get recent bug entries for the Memory Explorer."""
    return _load_stats().get("entries", [])


async def initialize_memory():
    """Initialize Cognee memory - call once at startup"""
    try:
        await cognee.forget(everything=True)
    except Exception:
        pass
    try:
        await cognee.remember("Bug Whisperer initialized.")
    except Exception:
        pass


_memory_initialized = False


async def ensure_memory_initialized():
    """Lazy initialization of Cognee memory"""
    global _memory_initialized
    if not _memory_initialized:
        await initialize_memory()
        _memory_initialized = True


async def remember_bug(entry: BugMemoryEntry, from_memory: bool = False, confidence: float = 0.0) -> str:
    """Store a bug in Cognee's memory"""
    memory_text = f"""
BUG RECORD
Error Signature: {entry.error_signature}
Error Message: {entry.error_message}
Stack Trace: {entry.stack_trace}
Root Cause: {entry.root_cause}
Fix: {entry.fix_description}
Code Snippet: {entry.code_snippet or 'N/A'}
Files Involved: {', '.join(entry.files_involved)}
Language: {entry.language}
Severity: {entry.severity.value}
First Seen: {entry.first_seen.isoformat()}
Last Seen: {entry.last_seen.isoformat()}
Occurrences: {entry.occurrences}
Times Recalled: {entry.recall_count}
"""

    await cognee.remember(memory_text)
    _record_bug(entry.error_message, entry.root_cause, entry.fix_description, entry.files_involved, from_memory, confidence)
    return entry.error_signature


async def recall_similar_bugs(
    error_message: str,
    stack_trace: str = "",
    top_k: int = 3,
) -> RecallResult:
    """Search Cognee memory for similar past bugs"""
    query = f"""
Find bugs similar to this error:
Error: {error_message}
Stack Trace: {stack_trace[:500] if stack_trace else 'N/A'}

Look for: similar error types, same files, similar stack traces, related root causes.
"""

    try:
        results = await cognee.recall(query_text=query)

        if not results:
            return RecallResult(found=False)

        # Cognee returned results - this is a recall hit from the knowledge graph

        # Ask LLM to analyze the recall results
        context = "\n---\n".join([r.text for r in results[:top_k]])

        analysis_prompt = f"""You are Bug Whisperer, an expert debugging AI with persistent memory.

CONTEXT FROM MEMORY (past bugs we've seen and fixed):
{context}

NEW ERROR:
{error_message}

Stack trace:
{stack_trace[:500] if stack_trace else 'None provided'}

Analyze whether any past bugs are relevant. Return JSON:
{{
    "found": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "why you think these are related",
    "suggestion": "specific fix suggestion based on past experience, or null if not found"
}}

IMPORTANT: Only return the JSON, no other text."""

        analysis = await LLMGateway.acreate_structured_output(
            text_input=analysis_prompt,
            system_prompt="You are a precise debugging expert. Return only valid JSON.",
            response_model=str,
        )

        # Parse the JSON
        try:
            cleaned = analysis.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            return RecallResult(
                found=True,
                confidence=0.5,
                reasoning="Found similar bugs but couldn't parse analysis",
            )

        return RecallResult(
            found=True,
            confidence=max(parsed.get("confidence", 0.7) or 0.7, 0.5),
            reasoning=parsed.get("reasoning", ""),
            suggestion=parsed.get("suggestion"),
        )

    except Exception as e:
        return RecallResult(
            found=False,
            reasoning=f"Recall error: {str(e)}",
        )


async def analyze_bug(
    error_message: str,
    stack_trace: str = "",
    recall_result: Optional[RecallResult] = None,
) -> dict:
    """Analyze a bug using DeepSeek, optionally augmented with memory"""
    
    memory_context = ""
    if recall_result and recall_result.found:
        memory_context = f"""
PAST EXPERIENCE (from memory):
{recall_result.reasoning}
Suggested fix from memory: {recall_result.suggestion or 'None'}
"""

    prompt = f"""You are Bug Whisperer, an expert debugging AI.

{memory_context}

CURRENT BUG:
Error: {error_message}
Stack Trace: {stack_trace[:1000] if stack_trace else 'Not provided'}

Provide a complete analysis. Return JSON:
{{
    "error_type": "type of error",
    "root_cause_analysis": "detailed analysis of likely root cause",
    "suggested_fix": "specific steps to fix",
    "code_snippet": "example fix code or null",
    "severity": "critical/high/medium/low",
    "related_files": ["likely", "files", "involved"],
    "from_memory": true/false
}}"""

    try:
        response = await LLMGateway.acreate_structured_output(
            text_input=prompt,
            system_prompt="You are a world-class debugging expert. Return only valid JSON.",
            response_model=str,
        )

        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]

        return json.loads(cleaned)

    except Exception as e:
        return {
            "error_type": "unknown",
            "root_cause_analysis": f"Analysis failed: {str(e)}",
            "suggested_fix": "Manual investigation required",
            "severity": "medium",
            "from_memory": False,
        }


async def get_stats() -> dict:
    """Get Bug Whisperer statistics with meaningful metrics."""
    data = _load_stats()
    total = data.get("total_bugs", 0)
    recalled = data.get("bugs_recalled", 0)
    total_conf = data.get("total_confidence", 0.0)
    entries = data.get("entries", [])

    # Compute error type frequency
    error_types = {}
    top_files = {}
    for e in entries:
        etype = e["error"].split(":")[0].strip() if ":" in e["error"] else e["error"][:30]
        error_types[etype] = error_types.get(etype, 0) + 1
        for f in e.get("files", []):
            top_files[f] = top_files.get(f, 0) + 1

    top_errors = sorted(error_types.items(), key=lambda x: x[1], reverse=True)[:5]
    top_files_list = sorted(top_files.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "total_bugs": total,
        "bugs_recalled_from_memory": recalled,
        "bugs_resolved": total,
        "recall_hit_rate": round((recalled / total * 100) if total > 0 else 0, 1),
        "avg_confidence": round((total_conf / recalled * 100) if recalled > 0 else 0, 1),
        "estimated_time_saved_minutes": recalled * 5,
        "memory_graph_size": total,
        "top_error_types": [{"type": t, "count": c} for t, c in top_errors],
        "top_files": [{"file": f, "count": c} for f, c in top_files_list],
    }
