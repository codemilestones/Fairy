"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type EventMsg = {
  id?: number;
  type: string;
  data: any;
};

const steps = [
  { key: "intent", label: "用户意图" },
  { key: "scope", label: "范围界定" },
  { key: "brief", label: "研究简报" },
  { key: "research", label: "执行研究" },
  { key: "report", label: "最终报告" }
] as const;

function backendUrl() {
  return process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
}

export default function Page() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [events, setEvents] = useState<EventMsg[]>([]);
  const [status, setStatus] = useState<string>("new");
  const [clarification, setClarification] = useState<string | null>(null);
  const [brief, setBrief] = useState<string | null>(null);
  const [report, setReport] = useState<string | null>(null);
  const [rawNotes, setRawNotes] = useState<string[]>([]);
  const [showRawNotes, setShowRawNotes] = useState(false);

  const esRef = useRef<EventSource | null>(null);
  const lastEventId = useMemo(() => {
    const last = events[events.length - 1];
    return last?.id ?? 0;
  }, [events]);

  const hasResearchStarted = useMemo(() => {
    // 后端在开始研究时会 emit("research_progress", {stage:"start"})
    // 研究完成/报告完成也一定意味着已经进入过研究阶段
    return events.some(
      (e) =>
        e.type === "research_progress" ||
        e.type === "research_complete" ||
        e.type === "final_report_ready"
    );
  }, [events]);

  const latestResearchProgress = useMemo(() => {
    // 事件 data 结构：{ ts, payload: {...} }
    for (let i = events.length - 1; i >= 0; i--) {
      const ev = events[i];
      if (ev.type !== "research_progress") continue;
      const payload = ev?.data?.payload || {};
      const stage = typeof payload.stage === "string" ? payload.stage : "unknown";
      const elapsed_s = typeof payload.elapsed_s === "number" ? payload.elapsed_s : undefined;
      return { stage, elapsed_s };
    }
    return null;
  }, [events]);

  const currentStepIndex = useMemo(() => {
    if (report) return 4;
    // 一旦收到 research_progress（start）就应进入“执行研究”阶段展示
    if (hasResearchStarted) return 3;
    if (brief) return 2;
    if (clarification) return 1;
    if (sessionId) return 0;
    return 0;
  }, [report, hasResearchStarted, brief, clarification, sessionId]);

  async function ensureSession() {
    if (sessionId) return sessionId;
    const res = await fetch(`${backendUrl()}/api/sessions`, { method: "POST" });
    const json = await res.json();
    setSessionId(json.session_id);
    setEvents([]);
    return json.session_id as string;
  }

  async function refreshSession(sid: string) {
    const res = await fetch(`${backendUrl()}/api/sessions/${sid}`);
    const json = await res.json();
    setStatus(json.session?.status || "unknown");
    setClarification(json.session?.clarification_question || null);
    setBrief(json.session?.research_brief || null);
    setReport(json.session?.final_report || null);
    setRawNotes(Array.isArray(json.session?.raw_notes) ? json.session.raw_notes : []);
  }

  async function send() {
    const content = input.trim();
    if (!content) return;
    setInput("");
    const sid = await ensureSession();
    await refreshSession(sid);
    await fetch(`${backendUrl()}/api/sessions/${sid}/messages`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ content })
    });
  }

  function resetSession() {
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
    setSessionId(null);
    setEvents([]);
    setStatus("new");
    setClarification(null);
    setBrief(null);
    setReport(null);
    setRawNotes([]);
    setShowRawNotes(false);
  }

  function downloadReport() {
    if (!report) return;
    const blob = new Blob([report], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `fairy-report-${sessionId || "session"}.md`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  useEffect(() => {
    if (!sessionId) return;
    if (esRef.current) return;
    const url = `${backendUrl()}/api/sessions/${sessionId}/events?after_id=${lastEventId}`;
    const es = new EventSource(url);
    esRef.current = es;

    es.onmessage = () => {};
    es.addEventListener("error", () => {});
    steps.forEach(() => {});

    const handler = (type: string) => (e: MessageEvent) => {
      let data: any = {};
      try {
        data = JSON.parse(e.data);
      } catch {
        data = { raw: e.data };
      }
      const id = (e as any).lastEventId ? Number((e as any).lastEventId) : undefined;
      setEvents((prev) => [...prev, { id, type, data }]);
      refreshSession(sessionId).catch(() => {});
    };

    es.addEventListener("intent_detected", handler("intent_detected"));
    es.addEventListener("scope_clarification_needed", handler("scope_clarification_needed"));
    es.addEventListener("research_brief_ready", handler("research_brief_ready"));
    es.addEventListener("research_progress", handler("research_progress"));
    es.addEventListener("research_complete", handler("research_complete"));
    es.addEventListener("final_report_ready", handler("final_report_ready"));
    es.addEventListener("error", handler("error"));

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [sessionId, lastEventId]);

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "#fafafa" }}>
      <div style={{ width: 380, borderRight: "1px solid #eee", padding: 16, background: "#fff" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ fontSize: 18, fontWeight: 800 }}>Fairy Research Agent Demo</div>
          <button
            onClick={resetSession}
            style={{
              padding: "6px 10px",
              borderRadius: 8,
              border: "1px solid #ddd",
              background: "#fff",
              cursor: "pointer"
            }}
          >
            新会话
          </button>
        </div>
        <div style={{ marginTop: 8, color: "#666", fontSize: 12, lineHeight: 1.6 }}>
          <div>session: {sessionId || "(未创建)"}</div>
          <div>status: {status}</div>
        </div>

        <div style={{ marginTop: 16 }}>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="输入你的研究需求（支持中文）..."
            rows={5}
            style={{ width: "100%", padding: 10, border: "1px solid #ddd", borderRadius: 8 }}
          />
          <button
            onClick={send}
            style={{
              marginTop: 8,
              width: "100%",
              padding: "10px 12px",
              borderRadius: 8,
              border: "1px solid #111",
              background: "#111",
              color: "#fff",
              cursor: "pointer"
            }}
          >
            发送
          </button>
        </div>

        <div style={{ marginTop: 16 }}>
          <div style={{ fontWeight: 700, marginBottom: 8 }}>流程</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {steps.map((s, idx) => {
              const isActive = idx === currentStepIndex;
              const isDone = idx < currentStepIndex;
              return (
                <div
                  key={s.key}
                  style={{
                    padding: "10px 12px",
                    borderRadius: 10,
                    border: "1px solid #eee",
                    background: isActive ? "#111" : "#fff",
                    color: isActive ? "#fff" : "#111",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between"
                  }}
                >
                  <div style={{ fontWeight: 700 }}>{s.label}</div>
                  <div style={{ fontSize: 12, color: isActive ? "#fff" : isDone ? "#2a7" : "#888" }}>
                    {isDone ? "完成" : isActive ? "进行中" : "等待"}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div style={{ marginTop: 16 }}>
          <div style={{ fontWeight: 700, marginBottom: 8 }}>事件</div>
          <div style={{ fontSize: 12, color: "#444", maxHeight: 320, overflow: "auto" }}>
            {events.length === 0 ? (
              <div style={{ color: "#888" }}>等待事件...</div>
            ) : (
              events.slice(-50).map((ev, idx) => (
                <div key={idx} style={{ marginBottom: 6 }}>
                  <div style={{ fontWeight: 700 }}>{ev.type}</div>
                  <div style={{ color: "#666" }}>
                    {typeof ev.data === "string" ? ev.data : JSON.stringify(ev.data)}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      <div style={{ flex: 1, padding: 16 }}>
        {clarification ? (
          <section style={{ marginBottom: 16 }}>
            <div style={{ fontWeight: 700, marginBottom: 8 }}>需要澄清</div>
            <div style={{ whiteSpace: "pre-wrap", border: "1px solid #eee", borderRadius: 12, padding: 12, background: "#fff" }}>
              {clarification}
            </div>
            <div style={{ marginTop: 8, color: "#666", fontSize: 12 }}>
              直接在左侧输入框回答澄清问题，然后再次点击「发送」。
            </div>
          </section>
        ) : null}

        {brief ? (
          <section style={{ marginBottom: 16 }}>
            <div style={{ fontWeight: 700, marginBottom: 8 }}>研究简报</div>
            <div style={{ whiteSpace: "pre-wrap", border: "1px solid #eee", borderRadius: 12, padding: 12, background: "#fff" }}>
              {brief}
            </div>
          </section>
        ) : null}

        {hasResearchStarted && !report ? (
          <section style={{ marginBottom: 16 }}>
            <div style={{ fontWeight: 700, marginBottom: 8 }}>执行研究</div>
            <div
              style={{
                border: "1px solid #eee",
                borderRadius: 12,
                padding: 12,
                background: "#fff",
                color: "#444"
              }}
            >
              <div>正在自动执行研究，请稍候…</div>
              {latestResearchProgress ? (
                <div style={{ marginTop: 6, fontSize: 12, color: "#666" }}>
                  stage: {latestResearchProgress.stage}
                  {typeof latestResearchProgress.elapsed_s === "number" ? ` · 已用时 ${latestResearchProgress.elapsed_s}s` : ""}
                </div>
              ) : null}
            </div>
          </section>
        ) : null}

        {rawNotes.length > 0 ? (
          <section style={{ marginBottom: 16 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
              <div style={{ fontWeight: 700 }}>原始笔记（Raw Notes）</div>
              <button
                onClick={() => setShowRawNotes((v) => !v)}
                style={{
                  padding: "6px 10px",
                  borderRadius: 8,
                  border: "1px solid #ddd",
                  background: "#fff",
                  cursor: "pointer"
                }}
              >
                {showRawNotes ? "收起" : "展开"}
              </button>
            </div>
            {showRawNotes ? (
              <div style={{ whiteSpace: "pre-wrap", border: "1px solid #eee", borderRadius: 12, padding: 12, background: "#fff" }}>
                {rawNotes.join("\n\n---\n\n")}
              </div>
            ) : null}
          </section>
        ) : null}

        {report ? (
          <section>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
              <div style={{ fontWeight: 700 }}>最终报告</div>
              <button
                onClick={downloadReport}
                style={{
                  padding: "6px 10px",
                  borderRadius: 8,
                  border: "1px solid #ddd",
                  background: "#fff",
                  cursor: "pointer"
                }}
              >
                导出 .md
              </button>
            </div>
            <div style={{ whiteSpace: "pre-wrap", border: "1px solid #eee", borderRadius: 12, padding: 12, background: "#fff" }}>
              {report}
            </div>
          </section>
        ) : (
          <div style={{ color: "#888" }}>报告将在流程完成后显示。</div>
        )}
      </div>
    </div>
  );
}


