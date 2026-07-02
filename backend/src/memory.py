"""Bug Whisperer — Cognee Memory Operations"""

import asyncio
import hashlib
import json
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


async def initialize_memory():
    """Initialize Cognee memory - call once at startup"""
    try:
        await cognee.prune.prune_data()
        await cognee.prune.prune_system(metadata=True)
    except Exception:
        pass
    # Seed with a minimal entry to establish the database
    await cognee.remember("Bug Whisperer initialized. Ready to store and recall bugs.")


_memory_initialized = False


async def ensure_memory_initialized():
    """Lazy initialization of Cognee memory"""
    global _memory_initialized
    if not _memory_initialized:
        await initialize_memory()
        _memory_initialized = True


async def remember_bug(entry: BugMemoryEntry) -> str:
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
            # Clean up the response - extract JSON
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
            found=parsed.get("found", False),
            confidence=parsed.get("confidence", 0.0),
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
    """Get Bug Whisperer statistics"""
    try:
        results = await cognee.recall(
            query_text="List all bug records, their occurrences, and recall counts"
        )
        
        total_entries = len(results)
        
        # Count resolved and recalled
        recalled = sum(1 for r in results if "recalled" in r.text.lower())
        
        # Estimate time saved (5 min per recall)
        time_saved = recalled * 5
        
        return {
            "total_bugs": total_entries,
            "bugs_recalled_from_memory": recalled,
            "bugs_resolved": total_entries,
            "recall_hit_rate": (recalled / total_entries * 100) if total_entries > 0 else 0,
            "estimated_time_saved_minutes": time_saved,
            "memory_graph_size": total_entries,
        }
    except Exception:
        return {
            "total_bugs": 0,
            "bugs_recalled_from_memory": 0,
            "bugs_resolved": 0,
            "recall_hit_rate": 0,
            "estimated_time_saved_minutes": 0,
            "memory_graph_size": 0,
        }
