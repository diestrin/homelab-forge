-- Factory control plane schema (ADR-010)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  goal TEXT NOT NULL,
  acceptance_criteria JSONB NOT NULL DEFAULT '[]'::jsonb,
  sandbox_profile TEXT NOT NULL DEFAULT 'agent-cell',
  repo_path TEXT NOT NULL DEFAULT '.',
  status TEXT NOT NULL DEFAULT 'planning',
  assignee_agent TEXT,
  artifacts JSONB NOT NULL DEFAULT '[]'::jsonb,
  risk_level TEXT NOT NULL DEFAULT 'low',
  branch TEXT,
  worker_hook TEXT,
  notes TEXT,
  github_project_item_id TEXT,
  budget_minutes INT NOT NULL DEFAULT 30,
  claimed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS tasks_status_idx ON tasks (status);
CREATE INDEX IF NOT EXISTS tasks_updated_at_idx ON tasks (updated_at DESC);

CREATE TABLE IF NOT EXISTS task_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id TEXT NOT NULL REFERENCES tasks (id) ON DELETE CASCADE,
  source TEXT NOT NULL,
  author TEXT,
  body TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS task_messages_task_id_idx ON task_messages (task_id, created_at);

CREATE TABLE IF NOT EXISTS slack_threads (
  channel_id TEXT NOT NULL,
  thread_ts TEXT NOT NULL,
  task_id TEXT NOT NULL REFERENCES tasks (id) ON DELETE CASCADE,
  pr_url TEXT,
  PRIMARY KEY (channel_id, thread_ts)
);

CREATE INDEX IF NOT EXISTS slack_threads_task_id_idx ON slack_threads (task_id);

-- Durable agent run records (TASK-011): pg-boss jobs are completed on claim,
-- so this table is the operator-visible run/job history + SDK transcript store.
CREATE TABLE IF NOT EXISTS agent_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id TEXT NOT NULL REFERENCES tasks (id) ON DELETE CASCADE,
  kind TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'running',
  worker_id TEXT,
  model TEXT,
  branch TEXT,
  agent_id TEXT,
  sdk_run_id TEXT,
  job_id TEXT,
  summary TEXT,
  error TEXT,
  transcript JSONB NOT NULL DEFAULT '[]'::jsonb,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS agent_runs_task_id_idx ON agent_runs (task_id, started_at DESC);
