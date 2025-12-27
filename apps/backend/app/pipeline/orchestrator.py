from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import anyio
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field

from app.runtime import get_pubsub, get_store
from app.storage.sqlite import utc_now


def _ensure_repo_root_on_syspath() -> None:
    """Allow `import fairy` when running backend without installing the root package."""
    repo_root = Path(__file__).resolve().parents[4]
    src_root = repo_root / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))


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
            # publish to in-memory SSE subscribers (best-effort)
            await pubsub.publish(
                session_id,
                {"id": ev.id, "type": ev.type, "data": {"ts": ev.ts.isoformat(), "payload": ev.payload}},
            )

        try:
            session = store.get_session(session_id)
        except KeyError:
            return

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
        session.intent = intent.model_dump()
        session.updated_at = utc_now()
        store.save_session(session)
        await emit("intent_detected", {"intent": session.intent})

        # Demo: if not research, still stop gracefully
        if not intent.is_research:
            session.status = "completed"
            session.updated_at = utc_now()
            store.save_session(session)
            return

        # === Scope (clarification + brief) ===
        from fairy.research_agent_scope import scope_research  # noqa: E402

        scope_out: dict[str, Any] = await anyio.to_thread.run_sync(
            lambda: scope_research.invoke({"messages": lc_messages})
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
            return

        research_brief = scope_out.get("research_brief")
        if research_brief:
            session.research_brief = str(research_brief)
            session.clarification_question = None
            session.updated_at = utc_now()
            store.save_session(session)
            await emit("research_brief_ready", {"research_brief": session.research_brief})
        else:
            raise RuntimeError("scope did not produce research_brief")

        # === Research ===
        from fairy.research_agent import researcher_agent  # noqa: E402

        await emit("research_progress", {"stage": "start"})
        researcher_out: dict[str, Any] = await anyio.to_thread.run_sync(
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
        session.compressed_research = str(researcher_out.get("compressed_research", ""))
        session.raw_notes = list(researcher_out.get("raw_notes") or [])
        session.updated_at = utc_now()
        store.save_session(session)
        await emit("research_complete", {"compressed_research": session.compressed_research})

        # === Final report ===
        from fairy.prompts import final_report_generation_prompt  # noqa: E402
        from fairy.utils import get_today_str as fairy_today  # noqa: E402

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

    async def safe_run(self, session_id: str) -> None:
        store = get_store()
        try:
            await self.run(session_id)
        except Exception as e:  # pragma: no cover (demo safety)
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


