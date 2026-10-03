export interface AgentInfo {
  name: string;
  persona: string;
  runtime: string;
  max_turns: number;
  silence_by_default: boolean;
}

export interface ModelInfo {
  provider: string;
  default: string;
  base_url: string;
}

export interface TtsInfo {
  provider: string;
  model: string;
  voice: string;
}

export interface GatewayInfo {
  running: boolean;
  status: string;
}

export interface CronJobInfo {
  id: string;
  name: string;
  schedule: string;
  next_run: string;
  status: string;
}

export interface ProactiveSettings {
  timezone: string;
  quiet_hours: string;
  baseline_window_days: number;
  anomaly_sigma: number;
}

export interface SkillInfo {
  name: string;
  status: string;
  description: string;
}

export interface LedgerEntry {
  id: number;
  date: string;
  trigger_metric: string;
  deviation_sigma: number;
  attributed_cause: string;
  intervention_type: string;
  cause_id?: string;
  intervention_id?: string;
  subjective_rating?: number | null;
  rebound_status: string;
  next_day_rebound_delta?: number | null;
}

export interface LedgerData {
  total_entries: number;
  confirmed_rebounds: number;
  recovery_rate_pct: number;
  entries: LedgerEntry[];
  error?: string;
}

export interface ProfileInfo {
  has_soul: boolean;
  has_user: boolean;
  has_memory: boolean;
}

export interface QuickCommand {
  label: string;
  command: string;
  description: string;
}

export interface StatusData {
  timestamp: string;
  agent: AgentInfo;
  model: ModelInfo;
  tts: TtsInfo;
  gateway: GatewayInfo;
  cron_jobs: CronJobInfo[];
  proactive_settings: ProactiveSettings;
  skills: SkillInfo[];
  ledger: LedgerData;
  profiles: ProfileInfo;
  quick_commands: QuickCommand[];
}
