import { useState, useEffect } from "react";
import { INITIAL_DATA } from "./telemetryData";
import { StatusData } from "./types";

const STYLES = {
  container: {
    minHeight: "100vh",
    backgroundColor: "#09090b",
    color: "#f4f4f5",
    fontFamily: "Inter, system-ui, -apple-system, sans-serif",
    padding: "24px 32px",
    boxSizing: "border-box" as const,
  },
  card: {
    padding: "18px",
    backgroundColor: "#18181b",
    borderRadius: "10px",
    border: "1px solid #27272a",
  },
  statTitle: {
    fontSize: "11px",
    fontWeight: 600,
    color: "#a1a1aa",
    textTransform: "uppercase" as const,
    letterSpacing: "0.05em",
  },
  statValue: {
    fontSize: "17px",
    fontWeight: 700,
    color: "#fafafa",
    marginTop: "6px",
  },
  badge: {
    fontSize: "11px",
    padding: "3px 8px",
    borderRadius: "4px",
    fontWeight: 600,
    display: "inline-block",
  },
};

type TabId = "overview" | "architecture" | "simulator" | "ledger" | "skills" | "commands";

export default function App() {
  const [data, setData] = useState<StatusData>(INITIAL_DATA);
  const [isLive, setIsLive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<TabId>("overview");
  const [copiedCmd, setCopiedCmd] = useState<string | null>(null);

  // Architecture tab state
  const [selectedGate, setSelectedGate] = useState<0 | 1 | 2 | 3>(0);

  // Simulator tab state
  const [simScenario, setSimScenario] = useState<"eustress" | "distress" | "confounded">("eustress");
  const [simStep, setSimStep] = useState<number>(1);

  const fetchStatus = () => {
    setLoading(true);
    const url = (window.location.pathname.endsWith("/") ? window.location.pathname : window.location.pathname + "/") + "status.json?t=" + Date.now();
    fetch(url)
      .then((res) => (res.ok ? res.json() : null))
      .then((json: StatusData | null) => {
        if (json && json.model && json.agent) {
          setData(json);
          setIsLive(true);
        }
        setLoading(false);
      })
      .catch(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const copyToClipboard = async (text: string) => {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        const textarea = document.createElement("textarea");
        textarea.value = text;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
      }
      setCopiedCmd(text);
      setTimeout(() => setCopiedCmd(null), 2000);
    } catch {
      setCopiedCmd("ERROR");
      setTimeout(() => setCopiedCmd(null), 2000);
    }
  };

  const getReboundBadge = (status: string) => {
    switch (status) {
      case "REBOUND_CONFIRMED":
        return { bg: "rgba(34, 197, 94, 0.15)", color: "#4ade80", text: "REBOUND CONFIRMED" };
      case "PARTIAL_REBOUND":
        return { bg: "rgba(234, 179, 8, 0.15)", color: "#facc15", text: "PARTIAL REBOUND" };
      case "NO_REBOUND":
        return { bg: "rgba(239, 68, 68, 0.15)", color: "#f87171", text: "NO REBOUND" };
      case "EXPIRED_NO_DATA":
        return { bg: "rgba(113, 113, 122, 0.15)", color: "#a1a1aa", text: "EXPIRED (NO DATA)" };
      default:
        return { bg: "rgba(59, 130, 246, 0.15)", color: "#60a5fa", text: "PENDING VERIFICATION" };
    }
  };

  const GATES_INFO = [
    {
      id: 0,
      title: "Gate 0: The Steel Thread",
      tagline: "Mock Trigger → Self-Distanced Observer Chat (≤ 2 turns)",
      goal: "Validate end-to-end messaging flow and basic prompt framing over the channel without depending on live health APIs.",
      ships: [
        "Simulated anomaly trigger script (simulate_trigger.py)",
        "Outbound 3rd-person observer check-in",
        "User reply capture and logging",
        "Guardrail: session hard-stop after ≤ 2 turns",
      ],
      leverage: "Confirms user engagement, channel routing, and prompt tone with zero biometric API dependencies.",
      invariant: "Silence is free; speech is ledgered. Capped at 2 turns maximum.",
    },
    {
      id: 1,
      title: "Gate 1: Baseline & Confounder Engine",
      tagline: "Rolling z-score (μ ± 1.5σ) + Workout Exertion Filter",
      goal: "Prevent false alarms by comparing against individual baselines and filtering out athletic fatigue.",
      ships: [
        "Samsung Health and Garmin Connect export ingestion and SQLite normalization",
        "28-day rolling mean & standard deviation (μ ± 1.5σ) slope break detection",
        "Confounder Filter: prior day workout strain ≥ 14.0 suppresses mental check-ins",
        "Frequency guardrail: at most 1 morning check-in per day (quiet hours: 08:00–21:00)",
      ],
      leverage: "Eliminates 70%+ of spurious alerts caused by gym sessions or temporary physical exertion.",
      invariant: "Compare against the person's own baseline, never population averages.",
    },
    {
      id: 2,
      title: "Gate 2: Cognitive Appraisal & Action Triage",
      tagline: "Diagram.md 4-Way Triage Matrix + Exactly 1 Micro-Action",
      goal: "Attribute root cause and prescribe an immediate, actionable coping step under strict anti-rumination boundaries.",
      ships: [
        "Context Extraction: user names friction from external observer stance",
        "4-Way Triage: Eustress (High Control) vs. Distress (Low Control) vs. Recovery Drain vs. Clarifying question",
        "Single Micro-Action Commitment: lock in 1 tactical step; no 5+ habit menus",
        "Anti-rumination circuit breaker: hard ceiling of ≤ 3 turns total",
      ],
      leverage: "Focuses on immediate actionable momentum rather than open-ended psychiatric diagnosis or ruminative spiraling.",
      invariant: "Adversarial restraint: the agent interrupts cyclic venting and terminates upon action confirmation.",
    },
    {
      id: 3,
      title: "Gate 3: Closed-Loop Outcome Ledger",
      tagline: "Next-Day Biometric Rebound Verification + Memory Writeback",
      goal: "Close the empirical feedback loop by verifying whether the prescribed intervention helped normalize physiology.",
      ships: [
        "Outcome Ledger SQLite store (date, metric, sigma, cause, intervention, rating, rebound)",
        "Next-Day Verification: compares subsequent night against clean unpolluted baseline",
        "Personal Adaptation: reflects habits with confirmed recovery into MEMORY.md (N ≥ 3)",
        "Weekly 1-line recap summarizing verified recovery associations",
      ],
      leverage: "Provides empirical accountability—verifying that advice translates into measurable physical recovery.",
      invariant: "Context rent rule: raw vitals are never logged in memory; only verified correlations graduate.",
    },
  ];

  return (
    <div style={STYLES.container}>
      {/* Header */}
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        borderBottom: "1px solid #27272a",
        paddingBottom: "18px",
        marginBottom: "24px"
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          <div style={{
            width: "44px",
            height: "44px",
            borderRadius: "12px",
            backgroundColor: "#27272a",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "24px"
          }}>
            🧠
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <h1 style={{ margin: 0, fontSize: "20px", fontWeight: "700", letterSpacing: "-0.02em" }}>
                The Overthinkers
              </h1>
              <span style={{ fontSize: "11px", padding: "2px 8px", backgroundColor: "#18181b", border: "1px solid #27272a", borderRadius: "12px", color: "#a1a1aa" }}>
                80/20 Delivery Architecture
              </span>
            </div>
            <p style={{ margin: "3px 0 0 0", fontSize: "13px", color: "#a1a1aa" }}>
              Biometric Anomaly to Cognitive Dialogue Loop on Hermes Agent
            </p>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div style={{ fontSize: "12px", color: "#71717a" }}>
            Telemetry: {new Date(data.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </div>
          <button
            onClick={fetchStatus}
            style={{
              padding: "7px 14px",
              backgroundColor: "#18181b",
              color: "#e4e4e7",
              border: "1px solid #27272a",
              borderRadius: "6px",
              cursor: "pointer",
              fontSize: "12px",
              fontWeight: 500
            }}
          >
            {loading ? "Refreshing..." : "↻ Refresh"}
          </button>
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            padding: "6px 12px",
            borderRadius: "20px",
            backgroundColor: data.gateway.running ? "rgba(34, 197, 94, 0.12)" : "rgba(239, 68, 68, 0.12)",
            border: `1px solid ${data.gateway.running ? "rgba(34, 197, 94, 0.3)" : "rgba(239, 68, 68, 0.3)"}`,
            fontSize: "12px",
            fontWeight: 600,
            color: data.gateway.running ? "#4ade80" : "#f87171"
          }}>
            <span style={{
              width: "8px",
              height: "8px",
              borderRadius: "50%",
              backgroundColor: data.gateway.running ? "#22c55e" : "#ef4444"
            }} />
            Gateway {data.gateway.running ? "Active" : "Inactive"}
          </div>
          <span style={{
            fontSize: "11px",
            padding: "4px 8px",
            borderRadius: "4px",
            backgroundColor: isLive ? "rgba(59, 130, 246, 0.15)" : "#27272a",
            color: isLive ? "#60a5fa" : "#a1a1aa",
            fontWeight: 600
          }}>
            {isLive ? "LIVE SYNC" : "BUNDLED"}
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: "8px", marginBottom: "24px", borderBottom: "1px solid #18181b", paddingBottom: "12px" }}>
        {[
          { id: "overview", label: "Overview & Status" },
          { id: "architecture", label: "How It Works (PLAN.md)" },
          { id: "simulator", label: "Interactive Stepper" },
          { id: "ledger", label: `Outcome Ledger (${data.ledger.total_entries})` },
          { id: "skills", label: "Skills Inventory" },
          { id: "commands", label: "Terminal Commands" },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as TabId)}
            style={{
              padding: "8px 18px",
              borderRadius: "6px",
              backgroundColor: activeTab === tab.id ? "#27272a" : "transparent",
              color: activeTab === tab.id ? "#ffffff" : "#a1a1aa",
              border: "none",
              cursor: "pointer",
              fontSize: "13px",
              fontWeight: activeTab === tab.id ? 600 : 500,
              transition: "all 0.15s ease"
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* TAB 1: OVERVIEW */}
      {activeTab === "overview" && (
        <div>
          {/* Key Stat Grid */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "16px", marginBottom: "24px" }}>
            <div style={STYLES.card}>
              <div style={STYLES.statTitle}>Active Inference Model</div>
              <div style={STYLES.statValue}>{data.model.default}</div>
              <div style={{ fontSize: "12px", color: "#60a5fa", marginTop: "4px" }}>
                Provider: {data.model.provider} (Google AI Studio)
              </div>
            </div>

            <div style={STYLES.card}>
              <div style={STYLES.statTitle}>TTS Voice Model</div>
              <div style={STYLES.statValue}>{data.tts.model}</div>
              <div style={{ fontSize: "12px", color: "#a78bfa", marginTop: "4px" }}>
                Voice Persona: {data.tts.voice} (Multimodal PCM)
              </div>
            </div>

            <div style={STYLES.card}>
              <div style={STYLES.statTitle}>Morning Cron Schedule</div>
              <div style={STYLES.statValue}>
                {data.cron_jobs[0]?.schedule || "0 8 * * *"} ({data.proactive_settings.timezone})
              </div>
              <div style={{ fontSize: "12px", color: "#34d399", marginTop: "4px" }}>
                {data.cron_jobs[0]?.name || "overthinkers-morning-check"}
              </div>
            </div>

            <div style={STYLES.card}>
              <div style={STYLES.statTitle}>Quiet Hours Guardrail</div>
              <div style={STYLES.statValue}>{data.proactive_settings.quiet_hours}</div>
              <div style={{ fontSize: "12px", color: "#fbbf24", marginTop: "4px" }}>
                Silence by default outside threshold
              </div>
            </div>
          </div>

          {/* Persona Card */}
          <div style={{ ...STYLES.card, padding: "20px", marginBottom: "24px" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
              <div style={{ fontSize: "15px", fontWeight: 600, color: "#fafafa" }}>
                Active AI Stance: {data.agent.persona}
              </div>
              <span style={{ fontSize: "11px", padding: "4px 8px", backgroundColor: "#27272a", borderRadius: "4px", color: "#d4d4d8" }}>
                ≤ {data.agent.max_turns} Turns Ceiling
              </span>
            </div>
            <p style={{ margin: "0 0 14px 0", fontSize: "13px", lineHeight: "1.6", color: "#a1a1aa" }}>
              The coach monitors nightly autonomic tone (HRV slope breaks & sleep fragmentation). When an authentic anomaly occurs, it initiates a 3rd-person observer dialogue to identify the friction, categorize control (Eustress vs. Distress vs. Drain), and confirm exactly 1 micro-action.
            </p>
            <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
              <span style={{ fontSize: "12px", padding: "4px 10px", backgroundColor: "#09090b", border: "1px solid #27272a", borderRadius: "6px", color: "#e4e4e7" }}>
                🛡️ Anti-rumination circuit breaker (≤ 3 turns)
              </span>
              <span style={{ fontSize: "12px", padding: "4px 10px", backgroundColor: "#09090b", border: "1px solid #27272a", borderRadius: "6px", color: "#e4e4e7" }}>
                🏋️ Athletic confounder filter (strain ≥ 14.0)
              </span>
              <span style={{ fontSize: "12px", padding: "4px 10px", backgroundColor: "#09090b", border: "1px solid #27272a", borderRadius: "6px", color: "#e4e4e7" }}>
                📈 Closed-loop outcome ledger verification
              </span>
            </div>
          </div>

          {/* Quick Terminal Launcher */}
          <div style={{ ...STYLES.card, padding: "20px" }}>
            <h3 style={{ margin: "0 0 14px 0", fontSize: "14px", fontWeight: 600, color: "#fafafa" }}>
              Terminal Quick Actions (Click to Copy)
            </h3>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "12px" }}>
              {data.quick_commands.slice(0, 4).map((qc, idx) => (
                <div
                  key={idx}
                  onClick={() => copyToClipboard(qc.command)}
                  style={{
                    padding: "12px 14px",
                    backgroundColor: "#09090b",
                    borderRadius: "8px",
                    border: "1px solid #27272a",
                    cursor: "pointer",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    transition: "border-color 0.15s ease"
                  }}
                >
                  <div style={{ overflow: "hidden" }}>
                    <div style={{ fontSize: "13px", fontWeight: 600, color: "#f4f4f5" }}>{qc.label}</div>
                    <code style={{ fontSize: "11px", color: "#a1a1aa", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", display: "block", marginTop: "2px" }}>
                      {qc.command}
                    </code>
                  </div>
                  <span style={{ fontSize: "11px", color: copiedCmd === qc.command ? "#4ade80" : "#71717a", fontWeight: 600, paddingLeft: "10px" }}>
                    {copiedCmd === qc.command ? "COPIED!" : "COPY"}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: ARCHITECTURE & HOW IT WORKS */}
      {activeTab === "architecture" && (
        <div>
          <div style={{ marginBottom: "24px" }}>
            <h2 style={{ margin: "0 0 6px 0", fontSize: "18px", fontWeight: 700 }}>
              The 80/20 Delivery Architecture (`Plan/PLAN.md`)
            </h2>
            <p style={{ margin: 0, fontSize: "13px", lineHeight: "1.6", color: "#a1a1aa" }}>
              The Overthinkers delivers 80% of actionable user value (physiological anomaly attribution, cognitive appraisal triage, and closed-loop rebound verification) with 20% of implementation complexity, while preserving strict repository safety and zero rumination.
            </p>
          </div>

          {/* Core Invariants */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "14px", marginBottom: "28px" }}>
            <div style={STYLES.card}>
              <div style={{ fontSize: "13px", fontWeight: 700, color: "#60a5fa", marginBottom: "6px" }}>
                1. "Silence is free; speech is ledgered."
              </div>
              <p style={{ margin: 0, fontSize: "12px", lineHeight: "1.5", color: "#a1a1aa" }}>
                Proactive check-ins fire at most <strong>once per day</strong>, strictly when an authentic anomaly crosses threshold. Normal variance equals complete silence.
              </p>
            </div>

            <div style={STYLES.card}>
              <div style={{ fontSize: "13px", fontWeight: 700, color: "#34d399", marginBottom: "6px" }}>
                2. "Personal Baseline, Never Population Norm."
              </div>
              <p style={{ margin: 0, fontSize: "12px", lineHeight: "1.5", color: "#a1a1aa" }}>
                Slope breaks evaluate against the person's own 28-day rolling window (μ ± 1.5σ), eliminating population bias.
              </p>
            </div>

            <div style={STYLES.card}>
              <div style={{ fontSize: "13px", fontWeight: 700, color: "#facc15", marginBottom: "6px" }}>
                3. The Evidence & Confounder Interlock
              </div>
              <p style={{ margin: 0, fontSize: "12px", lineHeight: "1.5", color: "#a1a1aa" }}>
                Physical exertion (prior-day workout strain) bypasses mental stress triage and logs physical recovery strain to suppress false alarms.
              </p>
            </div>

            <div style={STYLES.card}>
              <div style={{ fontSize: "13px", fontWeight: 700, color: "#f87171", marginBottom: "6px" }}>
                4. Adversarial Restraint (≤ 3 Turns)
              </div>
              <p style={{ margin: 0, fontSize: "12px", lineHeight: "1.5", color: "#a1a1aa" }}>
                Open-ended venting is treated as a clinical hazard. The agent clarifies friction, locks in 1 micro-action, and exits.
              </p>
            </div>
          </div>

          {/* Interactive Gate Stepper */}
          <div style={{ ...STYLES.card, padding: "24px", marginBottom: "28px" }}>
            <h3 style={{ margin: "0 0 16px 0", fontSize: "15px", fontWeight: 700 }}>
              The 4 Vertical Ship Gates (Click to Inspect)
            </h3>

            {/* Gate selector pills */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "10px", marginBottom: "20px" }}>
              {GATES_INFO.map((g) => (
                <button
                  key={g.id}
                  onClick={() => setSelectedGate(g.id as any)}
                  style={{
                    padding: "12px 14px",
                    borderRadius: "8px",
                    backgroundColor: selectedGate === g.id ? "#27272a" : "#09090b",
                    border: `1px solid ${selectedGate === g.id ? "#60a5fa" : "#27272a"}`,
                    color: selectedGate === g.id ? "#ffffff" : "#a1a1aa",
                    cursor: "pointer",
                    textAlign: "left",
                    transition: "all 0.15s ease",
                  }}
                >
                  <div style={{ fontSize: "11px", fontWeight: 600, color: selectedGate === g.id ? "#60a5fa" : "#71717a" }}>
                    GATE {g.id}
                  </div>
                  <div style={{ fontSize: "13px", fontWeight: 600, marginTop: "2px" }}>
                    {g.id === 0 ? "Steel Thread" : g.id === 1 ? "Baseline & Confounders" : g.id === 2 ? "Cognitive Triage" : "Outcome Ledger"}
                  </div>
                </button>
              ))}
            </div>

            {/* Gate Detail Card */}
            {(() => {
              const cur = GATES_INFO[selectedGate];
              return (
                <div style={{ padding: "20px", backgroundColor: "#09090b", borderRadius: "8px", border: "1px solid #27272a" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                    <div style={{ fontSize: "16px", fontWeight: 700, color: "#fafafa" }}>{cur.title}</div>
                    <span style={{ fontSize: "12px", color: "#60a5fa", fontWeight: 600 }}>{cur.tagline}</span>
                  </div>
                  <p style={{ margin: "0 0 16px 0", fontSize: "13px", color: "#a1a1aa", lineHeight: "1.6" }}>
                    <strong>Goal:</strong> {cur.goal}
                  </p>

                  <div style={{ marginBottom: "16px" }}>
                    <div style={{ fontSize: "12px", fontWeight: 600, color: "#d4d4d8", marginBottom: "8px" }}>What Ships in this Vertical Slice:</div>
                    <ul style={{ margin: 0, paddingLeft: "20px", fontSize: "13px", color: "#a1a1aa", lineHeight: "1.6" }}>
                      {cur.ships.map((s, idx) => (
                        <li key={idx}>{s}</li>
                      ))}
                    </ul>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginTop: "16px", paddingTop: "14px", borderTop: "1px solid #1f1f23" }}>
                    <div>
                      <span style={{ fontSize: "11px", fontWeight: 600, color: "#34d399", textTransform: "uppercase" }}>80/20 Leverage</span>
                      <p style={{ margin: "4px 0 0 0", fontSize: "12px", color: "#d4d4d8" }}>{cur.leverage}</p>
                    </div>
                    <div>
                      <span style={{ fontSize: "11px", fontWeight: 600, color: "#fbbf24", textTransform: "uppercase" }}>Architectural Invariant</span>
                      <p style={{ margin: "4px 0 0 0", fontSize: "12px", color: "#d4d4d8" }}>{cur.invariant}</p>
                    </div>
                  </div>
                </div>
              );
            })()}
          </div>

          {/* Cognitive Appraisal Matrix (Diagram.md) */}
          <div style={{ ...STYLES.card, padding: "24px" }}>
            <h3 style={{ margin: "0 0 8px 0", fontSize: "15px", fontWeight: 700 }}>
              The Cognitive Appraisal Matrix (`Diagram.md` / Gate 2)
            </h3>
            <p style={{ margin: "0 0 20px 0", fontSize: "13px", color: "#a1a1aa" }}>
              How the coach categorizes user tension during Turn 2 and routes to exactly 1 tactical coping intervention:
            </p>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "14px" }}>
              <div style={{ padding: "16px", backgroundColor: "#09090b", borderRadius: "8px", border: "1px solid #27272a" }}>
                <div style={{ fontSize: "12px", fontWeight: 700, color: "#34d399", marginBottom: "4px" }}>
                  EUSTRESS (High Control / Challenge)
                </div>
                <div style={{ fontSize: "11px", color: "#a1a1aa", marginBottom: "10px" }}>
                  High-stakes delivery, presentation, competition
                </div>
                <div style={{ fontSize: "12px", color: "#fafafa" }}>
                  <strong>Prescribed Action:</strong> Single #1 Task Lock & Boundary Defense. Defer secondary threads.
                </div>
              </div>

              <div style={{ padding: "16px", backgroundColor: "#09090b", borderRadius: "8px", border: "1px solid #27272a" }}>
                <div style={{ fontSize: "12px", fontWeight: 700, color: "#f87171", marginBottom: "4px" }}>
                  DISTRESS (Low Control / Threat)
                </div>
                <div style={{ fontSize: "11px", color: "#a1a1aa", marginBottom: "10px" }}>
                  Uncontrollable re-org, interpersonal conflict, uncertainty
                </div>
                <div style={{ fontSize: "12px", color: "#fafafa" }}>
                  <strong>Prescribed Action:</strong> Physiological Down-Regulation (3x Physiological Sigh, 15-min Outdoor Walk).
                </div>
              </div>

              <div style={{ padding: "16px", backgroundColor: "#09090b", borderRadius: "8px", border: "1px solid #27272a" }}>
                <div style={{ fontSize: "12px", fontWeight: 700, color: "#fbbf24", marginBottom: "4px" }}>
                  RECOVERY DRAIN (Sleep / Bio Depletion)
                </div>
                <div style={{ fontSize: "11px", color: "#a1a1aa", marginBottom: "10px" }}>
                  Accumulated sleep debt, circadian disruption, travel
                </div>
                <div style={{ fontSize: "12px", color: "#fafafa" }}>
                  <strong>Prescribed Action:</strong> Active Rest & Evening Boundary Defense. Screen curfew 60m before bed.
                </div>
              </div>

              <div style={{ padding: "16px", backgroundColor: "#09090b", borderRadius: "8px", border: "1px solid #27272a" }}>
                <div style={{ fontSize: "12px", fontWeight: 700, color: "#a78bfa", marginBottom: "4px" }}>
                  UNCERTAIN (Ambiguous Friction)
                </div>
                <div style={{ fontSize: "11px", color: "#a1a1aa", marginBottom: "10px" }}>
                  User gives vague single-word answer
                </div>
                <div style={{ fontSize: "12px", color: "#fafafa" }}>
                  <strong>Prescribed Action:</strong> Exactly 1 clarifying follow-up question, then immediate closure.
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: INTERACTIVE CLOSED-LOOP SIMULATOR */}
      {activeTab === "simulator" && (
        <div>
          <div style={{ marginBottom: "20px" }}>
            <h2 style={{ margin: "0 0 6px 0", fontSize: "18px", fontWeight: 700 }}>
              Interactive Closed-Loop Simulator
            </h2>
            <p style={{ margin: 0, fontSize: "13px", color: "#a1a1aa" }}>
              Walk through the exact 5-step loop executed every morning by the Hermes orchestrator.
            </p>
          </div>

          {/* Scenario Selector */}
          <div style={{ display: "flex", gap: "10px", marginBottom: "24px" }}>
            {[
              { id: "eustress", label: "Scenario A: High-Pressure Deadline (Eustress)" },
              { id: "distress", label: "Scenario B: Uncontrollable Friction (Distress)" },
              { id: "confounded", label: "Scenario C: Hard Gym Session (Confounder Filter)" },
            ].map((sc) => (
              <button
                key={sc.id}
                onClick={() => {
                  setSimScenario(sc.id as any);
                  setSimStep(1);
                }}
                style={{
                  padding: "10px 16px",
                  borderRadius: "8px",
                  backgroundColor: simScenario === sc.id ? "#27272a" : "#18181b",
                  border: `1px solid ${simScenario === sc.id ? "#60a5fa" : "#27272a"}`,
                  color: simScenario === sc.id ? "#ffffff" : "#a1a1aa",
                  cursor: "pointer",
                  fontSize: "12px",
                  fontWeight: 600,
                }}
              >
                {sc.label}
              </button>
            ))}
          </div>

          {/* Stepper Progress Bar */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "8px", marginBottom: "24px" }}>
            {[
              "1. Nightly Biometrics",
              "2. Confounder Filter",
              "3. Observer Check-In",
              "4. Cognitive Triage",
              "5. Outcome Ledger",
            ].map((label, idx) => {
              const stepNum = idx + 1;
              const isActive = simStep === stepNum;
              const isDone = simStep > stepNum;
              return (
                <div
                  key={idx}
                  onClick={() => setSimStep(stepNum)}
                  style={{
                    padding: "10px",
                    borderRadius: "6px",
                    backgroundColor: isActive ? "#27272a" : isDone ? "rgba(34, 197, 94, 0.1)" : "#18181b",
                    border: `1px solid ${isActive ? "#60a5fa" : isDone ? "rgba(34, 197, 94, 0.3)" : "#27272a"}`,
                    cursor: "pointer",
                    textAlign: "center",
                  }}
                >
                  <div style={{ fontSize: "10px", fontWeight: 700, color: isActive ? "#60a5fa" : isDone ? "#4ade80" : "#71717a" }}>
                    STEP {stepNum}
                  </div>
                  <div style={{ fontSize: "12px", fontWeight: 600, color: isActive || isDone ? "#fafafa" : "#a1a1aa", marginTop: "2px" }}>
                    {label.split(". ")[1]}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Active Step Content */}
          <div style={{ ...STYLES.card, padding: "24px" }}>
            {simStep === 1 && (
              <div>
                <div style={{ fontSize: "14px", fontWeight: 700, color: "#60a5fa", marginBottom: "6px" }}>
                  Step 1: Nightly Wearable Evaluation & Slope Break
                </div>
                <p style={{ fontSize: "13px", color: "#a1a1aa", margin: "0 0 16px 0" }}>
                  The engine loads the 28-day rolling window for HRV and sleep fragmentation from <code>~/health/data/health.db</code>:
                </p>
                <div style={{ padding: "16px", backgroundColor: "#09090b", borderRadius: "8px", border: "1px solid #27272a", fontFamily: "monospace", fontSize: "12px" }}>
                  <div>Target Date: 2026-10-04</div>
                  <div>HRV Metric: 42.0 ms (28-day baseline: μ=58.2 ms, σ=8.1 ms)</div>
                  <div style={{ color: "#f87171", fontWeight: 700, marginTop: "4px" }}>
                    Calculated z-score: -2.00σ (Slope break crosses -1.50σ threshold!)
                  </div>
                </div>
              </div>
            )}

            {simStep === 2 && (
              <div>
                <div style={{ fontSize: "14px", fontWeight: 700, color: "#34d399", marginBottom: "6px" }}>
                  Step 2: Athletic Workout Confounder Interlock
                </div>
                <p style={{ fontSize: "13px", color: "#a1a1aa", margin: "0 0 16px 0" }}>
                  Before alarming the user, the engine checks prior-day workout strain to verify whether physiological exertion explains the dip:
                </p>
                {simScenario === "confounded" ? (
                  <div style={{ padding: "16px", backgroundColor: "rgba(234, 179, 8, 0.1)", borderRadius: "8px", border: "1px solid rgba(234, 179, 8, 0.3)", fontSize: "13px" }}>
                    <div style={{ color: "#facc15", fontWeight: 700 }}>Confounder Found! Prior Workout Strain = 18.2 (Threshold: 14.0)</div>
                    <div style={{ marginTop: "6px", color: "#d4d4d8" }}>
                      Result: Tagged as <code>PHYSICAL_RECOVERY_STRAIN</code>.
                    </div>
                    <div style={{ marginTop: "6px", color: "#a1a1aa", fontStyle: "italic" }}>
                      Rule Enforced: Mental stress check-in suppressed. Silence by default.
                    </div>
                  </div>
                ) : (
                  <div style={{ padding: "16px", backgroundColor: "rgba(34, 197, 94, 0.1)", borderRadius: "8px", border: "1px solid rgba(34, 197, 94, 0.3)", fontSize: "13px" }}>
                    <div style={{ color: "#4ade80", fontWeight: 700 }}>Confounder Clear: Prior Workout Strain = 4.2 (Rest / Light activity)</div>
                    <div style={{ marginTop: "6px", color: "#d4d4d8" }}>
                      Result: Authentic unconfounded autonomic anomaly detected. Ready for cognitive appraisal.
                    </div>
                  </div>
                )}
              </div>
            )}

            {simStep === 3 && (
              <div>
                <div style={{ fontSize: "14px", fontWeight: 700, color: "#a78bfa", marginBottom: "6px" }}>
                  Step 3: Self-Distanced 3rd-Person Observer Opening (Turn 1)
                </div>
                <p style={{ fontSize: "13px", color: "#a1a1aa", margin: "0 0 16px 0" }}>
                  Hermes dispatches the opening prompt formatted from the outside observer stance:
                </p>
                <div style={{ padding: "16px", backgroundColor: "#09090b", borderRadius: "8px", border: "1px solid #27272a" }}>
                  <div style={{ fontSize: "12px", color: "#60a5fa", fontWeight: 600, marginBottom: "4px" }}>Hermes Coach (Turn 1):</div>
                  <blockquote style={{ margin: 0, fontSize: "14px", color: "#fafafa", fontStyle: "italic" }}>
                    "Morning. Biometrics show an autonomic dip today. Looking at things from the outside, what's taking up your bandwidth?"
                  </blockquote>
                </div>
              </div>
            )}

            {simStep === 4 && (
              <div>
                <div style={{ fontSize: "14px", fontWeight: 700, color: "#fbbf24", marginBottom: "6px" }}>
                  Step 4: Cognitive Appraisal Triage & Action Prescription (Turn 2)
                </div>
                <p style={{ fontSize: "13px", color: "#a1a1aa", margin: "0 0 16px 0" }}>
                  User replies; Hermes immediately classifies perceived control and confirms 1 micro-action:
                </p>
                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  <div style={{ padding: "14px", backgroundColor: "#09090b", borderRadius: "8px", border: "1px solid #27272a" }}>
                    <div style={{ fontSize: "12px", color: "#a1a1aa", fontWeight: 600 }}>User:</div>
                    <div style={{ fontSize: "13px", color: "#fafafa", marginTop: "2px" }}>
                      {simScenario === "eustress"
                        ? "Urgent production release today with 3 stakeholders pinging for status."
                        : "Worrying about company re-org rumors and things I can't influence."}
                    </div>
                  </div>

                  <div style={{ padding: "14px", backgroundColor: "#09090b", borderRadius: "8px", border: "1px solid #27272a" }}>
                    <div style={{ fontSize: "12px", color: "#34d399", fontWeight: 600 }}>
                      Hermes Coach ({simScenario === "eustress" ? "EUSTRESS / CHALLENGE" : "DISTRESS / THREAT"}):
                    </div>
                    <div style={{ fontSize: "13px", color: "#fafafa", marginTop: "2px", lineHeight: "1.5" }}>
                      {simScenario === "eustress"
                        ? "The body has registered the acute demand. In control: your release sequence. Out of control: inbound pings. Prescribed micro-action: Send 1 broadcast status update establishing a heads-down window until 13:00, then lock focus exclusively on release. Session closed."
                        : "The body is reacting to uncertainty. External re-org decisions are out of control. Prescribed micro-action: Step away from screen for a 15-minute walk outside and 3 cycles of physiological sighs. Session closed."}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {simStep === 5 && (
              <div>
                <div style={{ fontSize: "14px", fontWeight: 700, color: "#34d399", marginBottom: "6px" }}>
                  Step 5: Outcome Ledger & Next-Day Verification
                </div>
                <p style={{ fontSize: "13px", color: "#a1a1aa", margin: "0 0 16px 0" }}>
                  The session is logged into SQLite. Tomorrow morning, the orchestrator inspects whether HRV rebounds:
                </p>
                <div style={{ padding: "16px", backgroundColor: "#09090b", borderRadius: "8px", border: "1px solid #27272a", fontSize: "13px", lineHeight: "1.6" }}>
                  <div>• Session ID: <code>rec_e491fa</code> logged in <code>~/health/data/ledger.db</code></div>
                  <div>• Initial Sigma: -2.00σ | Cause: CHALLENGE_LOAD | Action: PRIORITY_LOCK</div>
                  <div>• Next-Day HRV: Rebounded to 56.4 ms (-0.22σ)</div>
                  <div style={{ color: "#4ade80", fontWeight: 700, marginTop: "4px" }}>
                    • Status: REBOUND_CONFIRMED (+1.78σ recovery rebound)
                  </div>
                  <div>• Reflection: Habit correlation logged to <code>MEMORY.md</code> under context rent.</div>
                </div>
              </div>
            )}

            {/* Step navigation buttons */}
            <div style={{ display: "flex", justifyContent: "space-between", marginTop: "20px", paddingTop: "16px", borderTop: "1px solid #27272a" }}>
              <button
                disabled={simStep <= 1}
                onClick={() => setSimStep((s) => Math.max(1, s - 1))}
                style={{
                  padding: "8px 16px",
                  borderRadius: "6px",
                  backgroundColor: simStep <= 1 ? "#18181b" : "#27272a",
                  color: simStep <= 1 ? "#52525b" : "#e4e4e7",
                  border: "none",
                  cursor: simStep <= 1 ? "not-allowed" : "pointer",
                  fontSize: "12px",
                  fontWeight: 600,
                }}
              >
                ← Previous Step
              </button>
              <button
                disabled={simStep >= 5}
                onClick={() => setSimStep((s) => Math.min(5, s + 1))}
                style={{
                  padding: "8px 16px",
                  borderRadius: "6px",
                  backgroundColor: simStep >= 5 ? "#18181b" : "#60a5fa",
                  color: simStep >= 5 ? "#52525b" : "#09090b",
                  border: "none",
                  cursor: simStep >= 5 ? "not-allowed" : "pointer",
                  fontSize: "12px",
                  fontWeight: 700,
                }}
              >
                Next Step →
              </button>
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: OUTCOME LEDGER */}
      {activeTab === "ledger" && (
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "18px" }}>
            <div>
              <h2 style={{ margin: 0, fontSize: "16px", fontWeight: 700 }}>Closed-Loop Outcome Ledger</h2>
              <p style={{ margin: "2px 0 0 0", fontSize: "13px", color: "#a1a1aa" }}>
                Tracking biometric anomalies, committed micro-actions, and next-day autonomic rebound.
              </p>
            </div>
            <div style={{ display: "flex", gap: "12px" }}>
              <div style={{ padding: "8px 16px", backgroundColor: "#18181b", borderRadius: "8px", border: "1px solid #27272a", textAlign: "center" }}>
                <div style={{ fontSize: "10px", color: "#a1a1aa", textTransform: "uppercase" }}>Total Logged</div>
                <div style={{ fontSize: "16px", fontWeight: 700 }}>{data.ledger.total_entries}</div>
              </div>
              <div style={{ padding: "8px 16px", backgroundColor: "#18181b", borderRadius: "8px", border: "1px solid #27272a", textAlign: "center" }}>
                <div style={{ fontSize: "10px", color: "#a1a1aa", textTransform: "uppercase" }}>Recovery Rate</div>
                <div style={{ fontSize: "16px", fontWeight: 700, color: "#34d399" }}>{data.ledger.recovery_rate_pct}%</div>
              </div>
            </div>
          </div>

          {data.ledger.entries.length === 0 ? (
            <div style={{ padding: "40px", backgroundColor: "#18181b", borderRadius: "10px", border: "1px solid #27272a", textAlign: "center" }}>
              <p style={{ margin: 0, fontSize: "14px", color: "#a1a1aa" }}>
                No stress check-in sessions recorded in <code>~/health/data/ledger.db</code> yet.
              </p>
              <p style={{ margin: "8px 0 0 0", fontSize: "12px", color: "#71717a" }}>
                Entries are created automatically when Hermes completes a stress dialogue, or via <code>python3 scripts/orchestrator.py</code>.
              </p>
            </div>
          ) : (
            <div style={{ overflowX: "auto", backgroundColor: "#18181b", borderRadius: "10px", border: "1px solid #27272a" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px", textAlign: "left" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid #27272a", backgroundColor: "#09090b" }}>
                    <th style={{ padding: "12px 16px", color: "#a1a1aa", fontWeight: 600 }}>Date</th>
                    <th style={{ padding: "12px 16px", color: "#a1a1aa", fontWeight: 600 }}>Metric</th>
                    <th style={{ padding: "12px 16px", color: "#a1a1aa", fontWeight: 600 }}>Deviation</th>
                    <th style={{ padding: "12px 16px", color: "#a1a1aa", fontWeight: 600 }}>Attributed Cause</th>
                    <th style={{ padding: "12px 16px", color: "#a1a1aa", fontWeight: 600 }}>Prescribed Action</th>
                    <th style={{ padding: "12px 16px", color: "#a1a1aa", fontWeight: 600 }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data.ledger.entries.map((row) => {
                    const badge = getReboundBadge(row.rebound_status);
                    return (
                      <tr key={row.id} style={{ borderBottom: "1px solid #1f1f23" }}>
                        <td style={{ padding: "12px 16px", fontWeight: 500 }}>{row.date}</td>
                        <td style={{ padding: "12px 16px" }}>
                          <span style={{ padding: "3px 8px", backgroundColor: "#27272a", borderRadius: "4px", fontSize: "11px" }}>
                            {row.trigger_metric}
                          </span>
                        </td>
                        <td style={{ padding: "12px 16px", color: row.deviation_sigma < 0 ? "#f87171" : "#fbbf24" }}>
                          {row.deviation_sigma > 0 ? `+${row.deviation_sigma}σ` : `${row.deviation_sigma}σ`}
                        </td>
                        <td style={{ padding: "12px 16px", maxWidth: "220px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                          {row.attributed_cause}
                        </td>
                        <td style={{ padding: "12px 16px", maxWidth: "260px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                          {row.intervention_type}
                        </td>
                        <td style={{ padding: "12px 16px" }}>
                          <span style={{
                            padding: "3px 8px",
                            borderRadius: "4px",
                            fontSize: "11px",
                            fontWeight: 600,
                            backgroundColor: badge.bg,
                            color: badge.color
                          }}>
                            {badge.text}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* TAB 5: SKILLS INVENTORY */}
      {activeTab === "skills" && (
        <div>
          <h2 style={{ margin: "0 0 6px 0", fontSize: "16px", fontWeight: 700 }}>Installed Hermes Skills</h2>
          <p style={{ margin: "0 0 20px 0", fontSize: "13px", color: "#a1a1aa" }}>
            The Overthinkers first-party skills discovered and verified in <code>~/.hermes/skills/</code>.
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "16px" }}>
            {data.skills.map((sk) => (
              <div key={sk.name} style={STYLES.card}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                  <code style={{ fontSize: "14px", fontWeight: 600, color: "#60a5fa" }}>{sk.name}</code>
                  <span style={{ fontSize: "11px", padding: "2px 8px", backgroundColor: "rgba(34, 197, 94, 0.15)", color: "#4ade80", borderRadius: "4px", fontWeight: 600 }}>
                    {sk.status}
                  </span>
                </div>
                <p style={{ margin: 0, fontSize: "12px", lineHeight: "1.5", color: "#a1a1aa" }}>
                  {sk.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 6: COMMANDS */}
      {activeTab === "commands" && (
        <div>
          <h2 style={{ margin: "0 0 6px 0", fontSize: "16px", fontWeight: 700 }}>Terminal Operations Guide</h2>
          <p style={{ margin: "0 0 20px 0", fontSize: "13px", color: "#a1a1aa" }}>
            Essential commands for running, testing, and managing your coach inside the Matrix Terminal.
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            {data.quick_commands.map((cmd) => (
              <div key={cmd.command} style={{ ...STYLES.card, padding: "16px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                  <div style={{ fontSize: "14px", fontWeight: 600, color: "#f4f4f5" }}>{cmd.label}</div>
                  <button
                    onClick={() => copyToClipboard(cmd.command)}
                    style={{
                      padding: "4px 10px",
                      backgroundColor: "#27272a",
                      color: copiedCmd === cmd.command ? "#4ade80" : "#d4d4d8",
                      border: "none",
                      borderRadius: "4px",
                      cursor: "pointer",
                      fontSize: "11px",
                      fontWeight: 600
                    }}
                  >
                    {copiedCmd === cmd.command ? "COPIED!" : "COPY COMMAND"}
                  </button>
                </div>
                <p style={{ margin: "0 0 10px 0", fontSize: "12px", color: "#a1a1aa" }}>{cmd.description}</p>
                <code style={{
                  display: "block",
                  padding: "10px 12px",
                  backgroundColor: "#09090b",
                  borderRadius: "6px",
                  fontSize: "12px",
                  color: "#e4e4e7",
                  border: "1px solid #27272a",
                  fontFamily: "monospace"
                }}>
                  {cmd.command}
                </code>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
