-- AI advisor conversations (spec 03). Replies are stored as sent: a transcript is a record of what the
-- student was told, not a cache of derived data. Every new reply is computed from live records.

CREATE TABLE ai_threads (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  student_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  title      text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ai_threads_student_idx ON ai_threads (student_id, updated_at DESC);

CREATE TABLE ai_messages (
  id            bigserial PRIMARY KEY,
  thread_id     uuid NOT NULL REFERENCES ai_threads (id) ON DELETE CASCADE,
  role          text NOT NULL CHECK (role IN ('user', 'ai')),
  body          text NOT NULL,
  kind          text CHECK (kind IN ('answer', 'fallback', 'handoff')),
  attachments   jsonb NOT NULL DEFAULT '{}',
  engine        text CHECK (engine IN ('rules', 'claude')),
  model         text,
  input_tokens  integer,
  output_tokens integer,
  latency_ms    integer,
  rating        smallint CHECK (rating IN (-1, 1)),
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ai_messages_thread_idx ON ai_messages (thread_id, id);
CREATE INDEX ai_messages_created_idx ON ai_messages (created_at) WHERE role = 'ai';

-- Student reports point at the answer they are about.
ALTER TABLE ai_flags
  ADD COLUMN message_id bigint REFERENCES ai_messages (id) ON DELETE SET NULL,
  ADD COLUMN student_id uuid REFERENCES users (id) ON DELETE SET NULL;
