from __future__ import annotations

import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import anyio
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field

from app.runtime import get_pubsub, get_store
from app.storage.sqlite import utc_now


logger = logging.getLogger(__name__)


def _ensure_repo_root_on_syspath() -> None:
    """Allow `import fairy` when running backend without installing the root package."""
    repo_root = Path(__file__).resolve().parents[4]
    src_root = repo_root / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))


def _preview(text: str, n: int = 120) -> str:
    t = (text or "").replace("\n", " ").strip()
    return t if len(t) <= n else t[: n - 1] + "…"


class IntentDecision(BaseModel):
    is_research: bool = Field(description="是否应走 research 工作流（demo 里一般为 true）")
    intent_label: str = Field(description="简短的用户意图标签，例如：市场调研/竞品分析/学术综述/写作辅助")


@dataclass(frozen=True)
class Orchestrator:
    async def run(self, session_id: str) -> None:
        _ensure_repo_root_on_syspath()

        store = get_store()
        pubsub = get_pubsub()

        async def emit(type: str, payload: dict[str, Any]) -> None:
            ev = store.append_event(session_id, type=type, payload=payload)
            logger.debug(
                "emit event session_id=%s event_id=%s type=%s payload_keys=%s",
                session_id,
                ev.id,
                type,
                list(payload.keys()),
            )
            # publish to in-memory SSE subscribers (best-effort)
            await pubsub.publish(
                session_id,
                {"id": ev.id, "type": ev.type, "data": {"ts": ev.ts.isoformat(), "payload": ev.payload}},
            )

        overall_start = time.perf_counter()
        try:
            session = store.get_session(session_id)
        except KeyError:
            logger.warning("pipeline abort: session not found session_id=%s", session_id)
            return

        # Find last user message for debugging (preview only)
        last_user = ""
        if session.messages:
            for m in reversed(session.messages):
                if m.get("role") == "user":
                    last_user = str(m.get("content", ""))
                    break

        logger.info(
            "pipeline start session_id=%s status=%s messages=%d last_user_preview=%s",
            session_id,
            session.status,
            len(session.messages),
            _preview(last_user),
        )

        # Build LC messages for scope graph from stored chat
        lc_messages = []
        for m in session.messages:
            role = m.get("role")
            content = m.get("content", "")
            if role == "user":
                lc_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))

        # === Intent ===
        _ensure_repo_root_on_syspath()
        from fairy.init_model import init_model  # noqa: E402

        t_intent = time.perf_counter()
        intent_model = init_model(model="gpt-4.1-mini")
        structured = intent_model.with_structured_output(IntentDecision)
        intent_prompt = (
            "你是一个 Web 研究 Agent 的意图识别器。\n"
            "给定用户最新需求，输出是否应进入 research 工作流，以及一个简短意图标签。\n"
            "如果是需要联网检索、综合信息、写研究报告的任务，一般认为 is_research=true。\n"
            "只输出结构化结果。\n\n"
            f"用户需求：{session.messages[-1]['content'] if session.messages else ''}"
        )
        intent = await anyio.to_thread.run_sync(lambda: structured.invoke([HumanMessage(content=intent_prompt)]))
        logger.info(
            "intent done session_id=%s is_research=%s label=%s duration_ms=%.1f",
            session_id,
            intent.is_research,
            intent.intent_label,
            (time.perf_counter() - t_intent) * 1000.0,
        )
        session.intent = intent.model_dump()
        session.updated_at = utc_now()
        store.save_session(session)
        await emit("intent_detected", {"intent": session.intent})

        # Demo: if not research, still stop gracefully
        if not intent.is_research:
            session.status = "completed"
            session.updated_at = utc_now()
            store.save_session(session)
            logger.info(
                "pipeline stop (non-research) session_id=%s total_duration_ms=%.1f",
                session_id,
                (time.perf_counter() - overall_start) * 1000.0,
            )
            return

        # === Scope (clarification + brief) ===
        from fairy.research_agent_scope import scope_research  # noqa: E402

        t_scope = time.perf_counter()
        scope_out: dict[str, Any] = await anyio.to_thread.run_sync(
            lambda: scope_research.invoke({"messages": lc_messages})
        )
        logger.info(
            "scope done session_id=%s has_brief=%s duration_ms=%.1f",
            session_id,
            bool(scope_out.get("research_brief")),
            (time.perf_counter() - t_scope) * 1000.0,
        )

        # If graph ended with a clarification question, it will be the last AI message.
        scope_messages = scope_out.get("messages") or []
        clarification_question: Optional[str] = None
        if scope_messages:
            last = scope_messages[-1]
            if isinstance(last, AIMessage) and last.content:
                # could be verification OR clarification; detect by presence of research_brief
                if not scope_out.get("research_brief"):
                    clarification_question = str(last.content)
                    # store assistant message in chat
                    session.messages.append({"role": "assistant", "content": clarification_question})
                else:
                    # verification message
                    session.messages.append({"role": "assistant", "content": str(last.content)})

        if clarification_question:
            session.status = "needs_clarification"
            session.clarification_question = clarification_question
            session.updated_at = utc_now()
            store.save_session(session)
            await emit("scope_clarification_needed", {"question": clarification_question})
            logger.info(
                "pipeline needs_clarification session_id=%s question_preview=%s total_duration_ms=%.1f",
                session_id,
                _preview(clarification_question),
                (time.perf_counter() - overall_start) * 1000.0,
            )
            return

        research_brief = scope_out.get("research_brief")
        if research_brief:
            session.research_brief = str(research_brief)
            session.clarification_question = None
            session.updated_at = utc_now()
            store.save_session(session)
            await emit("research_brief_ready", {"research_brief": session.research_brief})
            logger.info(
                "research_brief ready session_id=%s brief_chars=%d preview=%s",
                session_id,
                len(session.research_brief or ""),
                _preview(session.research_brief or ""),
            )
        else:
            raise RuntimeError("scope did not produce research_brief")

        # === Research ===
        from fairy.research_agent import researcher_agent  # noqa: E402

        t_research = time.perf_counter()
        await emit("research_progress", {"stage": "start", "elapsed_s": 0.0})

        # Research can take a while; emit periodic heartbeat progress so UI doesn't look stuck.
        done = anyio.Event()
        researcher_out: dict[str, Any] = {}

        async def _do_research() -> None:
            nonlocal researcher_out
            researcher_out = await anyio.to_thread.run_sync(
                lambda: researcher_agent.invoke(
                    {
                        "researcher_messages": [HumanMessage(content=f"{session.research_brief}.")],
                        "tool_call_iterations": 0,
                        "research_topic": session.research_brief or "",
                        "compressed_research": "",
                        "raw_notes": [],
                    }
                )
            )
            done.set()

        async def _heartbeat() -> None:
            # Avoid spamming; 2s is responsive enough for demo.
            while not done.is_set():
                await anyio.sleep(2.0)
                await emit(
                    "research_progress",
                    {
                        "stage": "running",
                        "elapsed_s": round(time.perf_counter() - t_research, 1),
                    },
                )

        async with anyio.create_task_group() as tg:
            tg.start_soon(_do_research)
            tg.start_soon(_heartbeat)
            await done.wait()
            tg.cancel_scope.cancel()
        logger.info(
            "research done session_id=%s duration_ms=%.1f out_keys=%s",
            session_id,
            (time.perf_counter() - t_research) * 1000.0,
            list(researcher_out.keys()),
        )
        session.compressed_research = str(researcher_out.get("compressed_research", ""))
        session.raw_notes = list(researcher_out.get("raw_notes") or [])
        session.updated_at = utc_now()
        store.save_session(session)
        await emit(
            "research_progress",
            {"stage": "complete", "elapsed_s": round(time.perf_counter() - t_research, 1)},
        )
        await emit("research_complete", {"compressed_research": session.compressed_research})
        logger.info(
            "research artifacts session_id=%s compressed_chars=%d raw_notes=%d",
            session_id,
            len(session.compressed_research or ""),
            len(session.raw_notes or []),
        )

        # === Final report ===
        from fairy.prompts import final_report_generation_prompt  # noqa: E402
        from fairy.utils import get_today_str as fairy_today  # noqa: E402

        t_report = time.perf_counter()
        report_model = init_model(model="gpt-4.1")
        prompt = final_report_generation_prompt.format(
            research_brief=session.research_brief or "",
            findings=session.compressed_research or "",
            date=fairy_today(),
        )
        report_msg = await anyio.to_thread.run_sync(lambda: report_model.invoke([HumanMessage(content=prompt)]))
        session.final_report = str(report_msg.content)
        session.status = "completed"
        session.updated_at = utc_now()
        store.save_session(session)
        await emit("final_report_ready", {"final_report": session.final_report})
        logger.info(
            "final_report ready session_id=%s duration_ms=%.1f report_chars=%d total_duration_ms=%.1f",
            session_id,
            (time.perf_counter() - t_report) * 1000.0,
            len(session.final_report or ""),
            (time.perf_counter() - overall_start) * 1000.0,
        )

    async def safe_run(self, session_id: str) -> None:
        store = get_store()
        try:
            await self.run(session_id)
        except Exception as e:  # pragma: no cover (demo safety)
            logger.exception("pipeline error session_id=%s error=%s", session_id, e)
            try:
                session = store.get_session(session_id)
                session.status = "error"
                session.last_error = str(e)
                session.updated_at = utc_now()
                store.save_session(session)
                ev = store.append_event(session_id, type="error", payload={"error": str(e)})
                pubsub = get_pubsub()
                await pubsub.publish(
                    session_id,
                    {"id": ev.id, "type": ev.type, "data": {"ts": ev.ts.isoformat(), "payload": ev.payload}},
                )
            except Exception:
                # best-effort only
                pass


orchestrator = Orchestrator()


