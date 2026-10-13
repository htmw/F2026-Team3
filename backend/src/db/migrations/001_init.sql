-- Acadmate initial schema.
-- Conventions: uuid ids for anything that appears in URLs and is user-owned, serial ids for catalog data,
-- timestamptz everywhere, enum-like columns as text + CHECK so new values are a one-line migration.

CREATE EXTENSION IF NOT EXISTS citext;

-- ---------------------------------------------------------------- identity & auth

CREATE TABLE users (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email          citext NOT NULL UNIQUE,
  password_hash  text,
  full_name      text NOT NULL,
  preferred_name text,
  role           text NOT NULL CHECK (role IN ('student', 'advisor', 'admin')),
  status         text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'invited', 'deactivated')),
  google_sub     text UNIQUE,
  google_email   text,
  totp_secret    text,
  totp_enabled   boolean NOT NULL DEFAULT false,
  preferences    jsonb NOT NULL DEFAULT '{}'::jsonb,
  -- Secret for the subscribable .ics feed (calendar apps can't send session cookies).
  calendar_token text UNIQUE,
  last_login_at  timestamptz,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX users_role_idx ON users (role);

CREATE TABLE sessions (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  token_hash   text NOT NULL UNIQUE,
  remember     boolean NOT NULL DEFAULT false,
  expires_at   timestamptz NOT NULL,
  last_seen_at timestamptz NOT NULL DEFAULT now(),
  ip           text,
  user_agent   text,
  created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX sessions_user_idx ON sessions (user_id);

-- Pending second step of a staff sign-in (password or Google already checked).
CREATE TABLE login_challenges (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  token_hash text NOT NULL UNIQUE,
  remember   boolean NOT NULL DEFAULT false,
  attempts   integer NOT NULL DEFAULT 0,
  expires_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- One-time links: password reset and account invite.
CREATE TABLE auth_tokens (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  purpose    text NOT NULL CHECK (purpose IN ('reset', 'invite')),
  token_hash text NOT NULL UNIQUE,
  expires_at timestamptz NOT NULL,
  used_at    timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------- catalog

CREATE TABLE programs (
  id   serial PRIMARY KEY,
  name text NOT NULL UNIQUE
);

CREATE TABLE requirement_groups (
  id             serial PRIMARY KEY,
  program_id     integer NOT NULL REFERENCES programs (id) ON DELETE CASCADE,
  name           text NOT NULL,
  course_type    text NOT NULL CHECK (course_type IN ('Foundation', 'Core', 'Elective', 'Capstone')),
  required_count integer NOT NULL CHECK (required_count >= 0),
  sort_order     integer NOT NULL DEFAULT 0,
  UNIQUE (program_id, course_type)
);

CREATE TABLE courses (
  id         serial PRIMARY KEY,
  code       text NOT NULL UNIQUE,
  name       text NOT NULL,
  credits    integer NOT NULL DEFAULT 3 CHECK (credits > 0),
  type       text NOT NULL CHECK (type IN ('Foundation', 'Core', 'Elective', 'Capstone')),
  offered    boolean NOT NULL DEFAULT true,
  offer_term text,
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE course_prerequisites (
  course_id integer NOT NULL REFERENCES courses (id) ON DELETE CASCADE,
  prereq_id integer NOT NULL REFERENCES courses (id) ON DELETE CASCADE,
  PRIMARY KEY (course_id, prereq_id)
);

CREATE TABLE terms (
  id                 serial PRIMARY KEY,
  name               text NOT NULL UNIQUE,
  starts_on          date NOT NULL,
  ends_on            date NOT NULL,
  is_current         boolean NOT NULL DEFAULT false,
  registration_opens date,
  last_add           date,
  last_drop          date,
  classes_begin      date
);
CREATE UNIQUE INDEX terms_one_current ON terms (is_current) WHERE is_current;

CREATE TABLE sections (
  id           serial PRIMARY KEY,
  course_id    integer NOT NULL REFERENCES courses (id) ON DELETE CASCADE,
  term_id      integer NOT NULL REFERENCES terms (id) ON DELETE CASCADE,
  instructor   text,
  days         text[] NOT NULL DEFAULT '{}',
  start_time   time,
  end_time     time,
  room         text,
  office_hours text,
  UNIQUE (course_id, term_id)
);

-- Snapshot written each time an admin publishes the catalog.
CREATE TABLE catalog_versions (
  id           serial PRIMARY KEY,
  snapshot     jsonb NOT NULL,
  published_by uuid REFERENCES users (id) ON DELETE SET NULL,
  published_at timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------- people

CREATE TABLE student_profiles (
  user_id        uuid PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
  student_number text UNIQUE,
  program_id     integer REFERENCES programs (id) ON DELETE SET NULL,
  advisor_id     uuid REFERENCES users (id) ON DELETE SET NULL,
  study_goal_hours numeric NOT NULL DEFAULT 20
);
CREATE INDEX student_profiles_advisor_idx ON student_profiles (advisor_id);

CREATE TABLE staff_profiles (
  user_id        uuid PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
  title          text,
  department     text,
  office         text,
  capacity       integer NOT NULL DEFAULT 40 CHECK (capacity >= 0),
  helps          text,
  bookable       boolean NOT NULL DEFAULT true,
  meeting_length integer NOT NULL DEFAULT 30 CHECK (meeting_length IN (15, 30, 45, 60)),
  booking_window_weeks integer NOT NULL DEFAULT 2 CHECK (booking_window_weeks IN (1, 2, 4)),
  settings       jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE office_hours (
  id         serial PRIMARY KEY,
  staff_id   uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  day        text NOT NULL CHECK (day IN ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')),
  start_time time NOT NULL,
  end_time   time NOT NULL CHECK (end_time > start_time),
  location   text
);

-- ---------------------------------------------------------------- academics

CREATE TABLE enrollments (
  id           serial PRIMARY KEY,
  student_id   uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  course_id    integer NOT NULL REFERENCES courses (id) ON DELETE RESTRICT,
  term_id      integer REFERENCES terms (id) ON DELETE SET NULL,
  status       text NOT NULL CHECK (status IN ('current', 'completed', 'planned', 'dropped')),
  grade        text CHECK (grade IN ('A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D', 'F')),
  progress_pct integer NOT NULL DEFAULT 0 CHECK (progress_pct BETWEEN 0 AND 100),
  absences     integer NOT NULL DEFAULT 0 CHECK (absences >= 0),
  plan_status  text CHECK (plan_status IN ('Recommended', 'Needs approval', 'Pending approval', 'Approved')),
  plan_note    text,
  created_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (student_id, course_id, term_id)
);
CREATE INDEX enrollments_student_idx ON enrollments (student_id);

CREATE TABLE grade_components (
  id            serial PRIMARY KEY,
  enrollment_id integer NOT NULL REFERENCES enrollments (id) ON DELETE CASCADE,
  label         text NOT NULL,
  weight        numeric NOT NULL CHECK (weight >= 0 AND weight <= 100),
  score         numeric CHECK (score >= 0 AND score <= 100),
  due_on        date,
  sort_order    integer NOT NULL DEFAULT 0
);

-- Course assignments apply to everyone enrolled; student_id set = an item for one student (e.g. an advising form).
CREATE TABLE assignments (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  course_id   integer REFERENCES courses (id) ON DELETE CASCADE,
  term_id     integer REFERENCES terms (id) ON DELETE CASCADE,
  student_id  uuid REFERENCES users (id) ON DELETE CASCADE,
  title       text NOT NULL,
  description text,
  type        text NOT NULL DEFAULT 'Individual' CHECK (type IN ('Individual', 'Team', 'Form')),
  weight_pct  numeric CHECK (weight_pct >= 0 AND weight_pct <= 100),
  due_at      timestamptz NOT NULL,
  steps       jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX assignments_due_idx ON assignments (due_at);

CREATE TABLE submissions (
  assignment_id uuid NOT NULL REFERENCES assignments (id) ON DELETE CASCADE,
  student_id    uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  status        text NOT NULL DEFAULT 'To do' CHECK (status IN ('To do', 'In progress', 'Submitted', 'Graded')),
  score         numeric CHECK (score >= 0 AND score <= 100),
  submitted_at  timestamptz,
  steps_done    integer[] NOT NULL DEFAULT '{}',
  updated_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (assignment_id, student_id)
);

-- ---------------------------------------------------------------- calendar & meetings

CREATE TABLE events (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id   uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  title      text NOT NULL,
  type       text NOT NULL CHECK (type IN ('Class', 'Office hours', 'Advising', 'Study', 'Team')),
  starts_at  timestamptz NOT NULL,
  ends_at    timestamptz NOT NULL CHECK (ends_at > starts_at),
  location   text,
  note       text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX events_owner_time_idx ON events (owner_id, starts_at);

CREATE TABLE meetings (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  student_id         uuid REFERENCES users (id) ON DELETE CASCADE,
  staff_id           uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  starts_at          timestamptz NOT NULL,
  ends_at            timestamptz NOT NULL CHECK (ends_at > starts_at),
  format             text NOT NULL CHECK (format IN ('In person', 'Online')),
  topic              text NOT NULL,
  student_note       text,
  attach_plan        boolean NOT NULL DEFAULT false,
  status             text NOT NULL DEFAULT 'confirmed'
                       CHECK (status IN ('requested', 'confirmed', 'proposed', 'declined', 'cancelled')),
  proposed_starts_at timestamptz,
  location           text,
  video_link         text,
  notes              text,
  created_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX meetings_staff_time_idx ON meetings (staff_id, starts_at);
CREATE INDEX meetings_student_time_idx ON meetings (student_id, starts_at);

-- ---------------------------------------------------------------- messaging

CREATE TABLE conversations (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  kind       text NOT NULL CHECK (kind IN ('direct', 'group', 'system')),
  title      text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE conversation_members (
  conversation_id uuid NOT NULL REFERENCES conversations (id) ON DELETE CASCADE,
  user_id         uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  last_read_at    timestamptz NOT NULL DEFAULT '-infinity',
  PRIMARY KEY (conversation_id, user_id)
);
CREATE INDEX conversation_members_user_idx ON conversation_members (user_id);

CREATE TABLE messages (
  id              bigserial PRIMARY KEY,
  conversation_id uuid NOT NULL REFERENCES conversations (id) ON DELETE CASCADE,
  sender_id       uuid REFERENCES users (id) ON DELETE SET NULL,
  sender_name     text,
  body            text NOT NULL,
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX messages_conversation_idx ON messages (conversation_id, created_at);

-- ---------------------------------------------------------------- advising

CREATE TABLE approvals (
  id            serial PRIMARY KEY,
  student_id    uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  advisor_id    uuid REFERENCES users (id) ON DELETE SET NULL,
  type          text NOT NULL CHECK (type IN ('Course plan', 'Form', 'Request')),
  title         text NOT NULL,
  lines         jsonb NOT NULL DEFAULT '[]'::jsonb,
  payload       jsonb NOT NULL DEFAULT '{}'::jsonb,
  status        text NOT NULL DEFAULT 'Pending' CHECK (status IN ('Pending', 'Approved', 'Changes requested')),
  precheck_ok   boolean,
  precheck_text text,
  comment       text,
  decided_by    uuid REFERENCES users (id) ON DELETE SET NULL,
  decided_at    timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX approvals_advisor_status_idx ON approvals (advisor_id, status);

CREATE TABLE advisor_notes (
  id         serial PRIMARY KEY,
  student_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  author_id  uuid REFERENCES users (id) ON DELETE SET NULL,
  body       text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------- administration

CREATE TABLE ai_flags (
  id          serial PRIMARY KEY,
  question    text NOT NULL,
  issue       text NOT NULL,
  source      text NOT NULL,
  status      text NOT NULL DEFAULT 'Open' CHECK (status IN ('Open', 'Resolved', 'Dismissed')),
  resolved_by uuid REFERENCES users (id) ON DELETE SET NULL,
  resolved_at timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE integrations (
  id           text PRIMARY KEY,
  name         text NOT NULL,
  description  text NOT NULL,
  connected    boolean NOT NULL DEFAULT false,
  last_sync_at timestamptz,
  log          jsonb NOT NULL DEFAULT '[]'::jsonb
);

CREATE TABLE api_keys (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name       text NOT NULL,
  key_hash   text NOT NULL UNIQUE,
  last4      text NOT NULL,
  created_by uuid REFERENCES users (id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  revoked_at timestamptz
);

CREATE TABLE app_settings (
  key        text PRIMARY KEY,
  value      jsonb NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE audit_log (
  id              bigserial PRIMARY KEY,
  actor_id        uuid REFERENCES users (id) ON DELETE SET NULL,
  actor_name      text NOT NULL,
  actor_role      text NOT NULL CHECK (actor_role IN ('Admin', 'Advisor', 'Student', 'System')),
  action          text NOT NULL,
  target_type     text,
  target_id       text,
  subject_user_id uuid REFERENCES users (id) ON DELETE SET NULL,
  ip              text,
  result          text NOT NULL DEFAULT 'Success',
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX audit_log_created_idx ON audit_log (created_at DESC);
CREATE INDEX audit_log_subject_idx ON audit_log (subject_user_id, created_at DESC);
