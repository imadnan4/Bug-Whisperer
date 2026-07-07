"""Bug Whisperer — FastAPI Backend"""

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from .models import (
    BugMemoryEntry,
    BugSeverity,
    NewBugRequest,
    FixSubmission,
    RecallResult,
    StatsResponse,
)
from .memory import (
    initialize_memory,
    ensure_memory_initialized,
    remember_bug,
    recall_similar_bugs,
    analyze_bug,
    error_signature,
    get_stats,
    _get_memory_entries,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown"""
    yield


app = FastAPI(
    title="Bug Whisperer API",
    description="AI Debugger with Persistent Memory powered by Cognee",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"name": "Bug Whisperer", "status": "online", "memory_engine": "Cognee"}


@app.post("/api/bugs/analyze", response_model=dict)
async def analyze_new_bug(req: NewBugRequest, request: Request):
    """Analyze a new bug. Uses X-API-Key header if provided, else returns error."""
    await ensure_memory_initialized()

    api_key = request.headers.get("X-API-Key")
    if not api_key and not os.environ.get("LLM_API_KEY"):
        raise HTTPException(
            status_code=401,
            detail="API key required. Pass X-API-Key header or set LLM_API_KEY on server.",
        )

    # 1. Check memory for similar bugs
    recall = await recall_similar_bugs(req.error_message, req.stack_trace, api_key=api_key)

    # 2. Analyze with LLM (augmented by memory)
    analysis = await analyze_bug(req.error_message, req.stack_trace, recall, api_key=api_key)

    # 3. Auto-save to Cognee memory so CLI and dashboard stay in sync
    sig = error_signature(
        analysis.get("root_cause_analysis", req.error_message),
        analysis.get("suggested_fix", ""),
    )
    entry = BugMemoryEntry(
        error_signature=sig,
        error_message=req.error_message,
        stack_trace=req.stack_trace,
        root_cause=analysis.get("root_cause_analysis", req.error_message),
        fix_description=analysis.get("suggested_fix", ""),
        code_snippet=analysis.get("code_snippet"),
        files_involved=req.files_involved,
        language=req.language,
        severity=BugSeverity(analysis.get("severity", "medium")),
    )
    try:
        await remember_bug(entry, from_memory=recall.found, confidence=recall.confidence, api_key=api_key)
    except Exception:
        pass  # Non-critical: memory storage can fail gracefully

    return {
        "recall": recall.model_dump(),
        "analysis": analysis,
        "session_id": f"session_{datetime.now().timestamp()}",
    }


@app.post("/api/bugs/remember", response_model=dict)
async def remember_fix(submission: FixSubmission):
    """Store a bug and its fix in Cognee memory"""
    await ensure_memory_initialized()
    entry = BugMemoryEntry(
        error_signature=error_signature(
            submission.root_cause, submission.fix_description
        ),
        error_message=submission.root_cause,
        stack_trace="",
        root_cause=submission.root_cause,
        fix_description=submission.fix_description,
        code_snippet=submission.code_snippet,
        files_involved=submission.files_changed,
        severity=BugSeverity.MEDIUM,
    )

    sig = await remember_bug(entry)
    return {"status": "remembered", "error_signature": sig}


@app.get("/api/stats", response_model=StatsResponse)
async def get_dashboard_stats():
    """Get dashboard statistics"""
    await ensure_memory_initialized()
    stats = await get_stats()
    return StatsResponse(**stats)


@app.get("/api/memory/entries")
async def get_memory_entries():
    """Get recent bug entries for the Memory Explorer."""
    await ensure_memory_initialized()
    return _get_memory_entries()


@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}
