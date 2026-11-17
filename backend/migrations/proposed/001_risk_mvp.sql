-- PROPOSAL ONLY: review with Datta; never auto-applied to shared DB.

CREATE TABLE risk_course_offerings (
	id SERIAL NOT NULL,
	course_id INTEGER NOT NULL,
	term VARCHAR(50) NOT NULL,
	starts_at TIMESTAMP WITH TIME ZONE NOT NULL,
	ends_at TIMESTAMP WITH TIME ZONE NOT NULL,
	timezone VARCHAR(50) NOT NULL,
	known_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (course_id, term),
	CHECK (ends_at > starts_at),
	FOREIGN KEY(course_id) REFERENCES courses (course_id)
)

;

CREATE TABLE risk_assessments (
	id SERIAL NOT NULL,
	offering_id INTEGER NOT NULL,
	label VARCHAR(100) NOT NULL,
	kind VARCHAR(20) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(offering_id) REFERENCES risk_course_offerings (id)
)

;

CREATE TABLE risk_activity_events (
	id SERIAL NOT NULL,
	enrollment_id INTEGER NOT NULL,
	source_event_id VARCHAR(100) NOT NULL,
	occurred_at TIMESTAMP WITH TIME ZONE NOT NULL,
	known_at TIMESTAMP WITH TIME ZONE NOT NULL,
	count INTEGER NOT NULL,
	event_type VARCHAR(30) NOT NULL,
	PRIMARY KEY (id),
	CHECK (count >= 0),
	CHECK (known_at >= occurred_at),
	FOREIGN KEY(enrollment_id) REFERENCES enrollments (enrollment_id),
	UNIQUE (source_event_id)
)

;

CREATE TABLE risk_assessment_versions (
	id SERIAL NOT NULL,
	assessment_id INTEGER NOT NULL,
	version INTEGER NOT NULL,
	due_at TIMESTAMP WITH TIME ZONE NOT NULL,
	max_score DOUBLE PRECISION NOT NULL,
	known_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (assessment_id, version),
	CHECK (max_score > 0),
	FOREIGN KEY(assessment_id) REFERENCES risk_assessments (id)
)

;

CREATE TABLE risk_enrollment_history (
	id SERIAL NOT NULL,
	enrollment_id INTEGER NOT NULL,
	status VARCHAR(30) NOT NULL,
	grade VARCHAR(5),
	grade_points DOUBLE PRECISION,
	effective_at TIMESTAMP WITH TIME ZONE NOT NULL,
	known_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (enrollment_id, known_at),
	FOREIGN KEY(enrollment_id) REFERENCES enrollments (enrollment_id)
)

;

CREATE TABLE risk_enrollment_offerings (
	enrollment_id INTEGER NOT NULL,
	offering_id INTEGER NOT NULL,
	registered_at TIMESTAMP WITH TIME ZONE NOT NULL,
	known_at TIMESTAMP WITH TIME ZONE NOT NULL,
	pattern VARCHAR(50) NOT NULL,
	PRIMARY KEY (enrollment_id),
	FOREIGN KEY(enrollment_id) REFERENCES enrollments (enrollment_id),
	FOREIGN KEY(offering_id) REFERENCES risk_course_offerings (id)
)

;

CREATE TABLE risk_source_coverage (
	id SERIAL NOT NULL,
	enrollment_id INTEGER NOT NULL,
	source VARCHAR(20) NOT NULL,
	starts_at TIMESTAMP WITH TIME ZONE NOT NULL,
	through_at TIMESTAMP WITH TIME ZONE NOT NULL,
	known_at TIMESTAMP WITH TIME ZONE NOT NULL,
	complete BOOLEAN NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (enrollment_id, source, known_at),
	CHECK (through_at >= starts_at),
	FOREIGN KEY(enrollment_id) REFERENCES enrollments (enrollment_id)
)

;

CREATE TABLE risk_submission_versions (
	id SERIAL NOT NULL,
	enrollment_id INTEGER NOT NULL,
	assessment_id INTEGER NOT NULL,
	version INTEGER NOT NULL,
	submitted_at TIMESTAMP WITH TIME ZONE NOT NULL,
	known_at TIMESTAMP WITH TIME ZONE NOT NULL,
	grade_available_at TIMESTAMP WITH TIME ZONE,
	score DOUBLE PRECISION,
	status VARCHAR(20) NOT NULL,
	is_banked BOOLEAN NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (enrollment_id, assessment_id, version),
	CHECK (known_at >= submitted_at),
	CHECK (score IS NULL OR score >= 0),
	FOREIGN KEY(enrollment_id) REFERENCES enrollments (enrollment_id),
	FOREIGN KEY(assessment_id) REFERENCES risk_assessments (id)
)

;
CREATE INDEX ix_risk_activity_events_occurred_at ON risk_activity_events (occurred_at);
CREATE INDEX ix_risk_activity_events_enrollment_id ON risk_activity_events (enrollment_id);
CREATE INDEX ix_risk_assessment_versions_assessment_id ON risk_assessment_versions (assessment_id);
CREATE INDEX ix_risk_assessment_versions_known_at ON risk_assessment_versions (known_at);
CREATE INDEX ix_risk_enrollment_history_enrollment_id ON risk_enrollment_history (enrollment_id);
CREATE INDEX ix_risk_source_coverage_enrollment_id ON risk_source_coverage (enrollment_id);
CREATE INDEX ix_risk_submission_versions_enrollment_id ON risk_submission_versions (enrollment_id);
CREATE INDEX ix_risk_submission_versions_known_at ON risk_submission_versions (known_at);
