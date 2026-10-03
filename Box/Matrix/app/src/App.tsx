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
};

export default function App() {
  const [data, setData] = useState<StatusData>(INITIAL_DATA);
  const [isLive, setIsLive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"overview" | "ledger" | "skills" | "commands">("overview");
  const [copiedCmd, setCopiedCmd] = useState<string | null>(null);

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
            width: "42px",
            height: "42px",
            borderRadius: "10px",
            backgroundColor: "#27272a",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "22px"
          }}>
            🧠
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: "20px", fontWeight: "700", letterSpacing: "-0.02em" }}>
              The Overthinkers
            </h1>
            <p style={{ margin: "2px 0 0 0", fontSize: "13px", color: "#a1a1aa" }}>
              Hermes Agent Live Control Center & Outcome Ledger
            </p>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div style={{ fontSize: "12px", color: "#71717a" }}>
            Updated: {new Date(data.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
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
        {(["overview", "ledger", "skills", "commands"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: "8px 18px",
              borderRadius: "6px",
              backgroundColor: activeTab === tab ? "#27272a" : "transparent",
              color: activeTab === tab ? "#ffffff" : "#a1a1aa",
              border: "none",
              cursor: "pointer",
              fontSize: "13px",
              fontWeight: activeTab === tab ? 600 : 500,
              textTransform: "capitalize",
              transition: "all 0.15s ease"
            }}
          >
            {tab === "ledger" ? `Outcome Ledger (${data.ledger.total_entries})` : tab}
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
                Voice Persona: {data.tts.voice}
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
            <p style={{ margin: "0 0 12px 0", fontSize: "13px", lineHeight: "1.6", color: "#a1a1aa" }}>
              Hermes monitors nightly biometric slope breaks (HRV drops & sleep fragmentation). When an authentic anomaly occurs, it initiates a 3rd-person observer dialogue to identify the friction, categorize control (Eustress vs. Distress vs. Drain), and confirm exactly 1 micro-action.
            </p>
            <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
              <span style={{ fontSize: "12px", padding: "4px 10px", backgroundColor: "#09090b", border: "1px solid #27272a", borderRadius: "6px", color: "#e4e4e7" }}>
                🛡️ Anti-rumination circuit breaker
              </span>
              <span style={{ fontSize: "12px", padding: "4px 10px", backgroundColor: "#09090b", border: "1px solid #27272a", borderRadius: "6px", color: "#e4e4e7" }}>
                🏋️ Athletic confounder filter
              </span>
              <span style={{ fontSize: "12px", padding: "4px 10px", backgroundColor: "#09090b", border: "1px solid #27272a", borderRadius: "6px", color: "#e4e4e7" }}>
                📈 Next-day closed-loop verification
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

      {/* TAB 2: OUTCOME LEDGER */}
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

      {/* TAB 3: SKILLS */}
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

      {/* TAB 4: COMMANDS */}
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
