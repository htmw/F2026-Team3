# F2026-Team3

erDiagram
    users ||--o{ advisor_availability : "staff_user_id"
    users ||--o| advisors : "user_id"
    users |o--o{ api_keys : "created_by"
    users |o--o{ audit_events : "actor_id"
    users ||--o{ auth_tokens : "user_id"
    users |o--o{ catalog_drafts : "created_by"
    users |o--o{ conversations : "created_by"
    courses ||--o{ course_offerings : "course_id"
    terms ||--o{ course_offerings : "term_id"
    courses ||--o{ course_prerequisites : "course_id"
    courses ||--o{ course_prerequisites : "prerequisite_id"
    courses ||--o{ course_sections : "course_id"
    terms ||--o{ course_sections : "term_id"
    users |o--o{ course_sections : "instructor_user_id"
    users |o--o{ import_jobs : "actor_id"
    integrations ||--o{ integration_events : "integration_id"
    programs ||--o{ program_requirements : "program_id"
    users ||--o{ sessions : "user_id"
    users ||--o| students : "user_id"
    programs ||--o{ students : "program_id"
    terms |o--o{ students : "start_term_id"
    users |o--o{ system_settings : "updated_by"
    users ||--o| user_preferences : "user_id"
    students ||--o| advisor_student_assignments : "student_id"
    advisors ||--o{ advisor_student_assignments : "advisor_id"
    students ||--o{ ai_threads : "student_id"
    students ||--o{ approval_requests : "student_id"
    advisors |o--o{ approval_requests : "advisor_id"
    terms |o--o{ approval_requests : "term_id"
    users |o--o{ approval_requests : "decided_by"
    students ||--o| calendar_feeds : "student_id"
    conversations ||--o{ conversation_participants : "conversation_id"
    users ||--o{ conversation_participants : "user_id"
    students ||--o{ enrollments : "student_id"
    courses ||--o{ enrollments : "course_id"
    course_sections |o--o{ enrollments : "section_id"
    students ||--o{ events : "student_id"
    students ||--o{ meetings : "student_id"
    advisors |o--o{ meetings : "advisor_id"
    users ||--o{ meetings : "staff_user_id"
    conversations ||--o{ messages : "conversation_id"
    users |o--o{ messages : "sender_id"
    students ||--o{ plan_items : "student_id"
    courses ||--o{ plan_items : "course_id"
    terms ||--o{ plan_items : "term_id"
    students ||--o{ study_sessions : "student_id"
    ai_threads ||--o{ ai_messages : "thread_id"
    enrollments ||--o{ grade_items : "enrollment_id"
    ai_messages |o--o{ ai_flags : "message_id"
    students |o--o{ ai_flags : "student_id"
    users |o--o{ ai_flags : "resolved_by"
    course_sections |o--o{ assignments : "section_id"
    programs |o--o{ assignments : "program_id"
    grade_items |o--o{ assignments : "grade_item_id"
    assignments ||--o{ assignment_submissions : "assignment_id"
    students ||--o{ assignment_submissions : "student_id"

    users {
        int user_id PK
        string email UK
        string google_sub UK
    }
    students {
        int student_id PK
        int user_id FK, UK
        string email UK
        string student_number UK
        int program_id FK
        int start_term_id FK
    }
    advisors {
        int advisor_id PK
        int user_id FK, UK
    }
    advisor_student_assignments {
        int student_id PK, FK
        int advisor_id FK
    }
    sessions {
        int id PK
        int user_id FK
        string token_hash UK
    }
    auth_tokens {
        int id PK
        int user_id FK
        string token_hash UK
    }
    login_attempts {
        int id PK
    }
    user_preferences {
        int user_id PK, FK
    }
    programs {
        int program_id PK
    }
    program_requirements {
        int requirement_id PK
        int program_id FK
    }
    courses {
        int course_id PK
        string course_code UK
    }
    course_prerequisites {
        int course_id PK, FK
        int prerequisite_id PK, FK
    }
    course_offerings {
        int course_id PK, FK
        int term_id PK, FK
    }
    catalog_drafts {
        int id PK
        int created_by FK
    }
    terms {
        int id PK
        string name UK
    }
    course_sections {
        int id PK
        int course_id FK
        int term_id FK
        int instructor_user_id FK
    }
    enrollments {
        int enrollment_id PK
        int student_id FK
        int course_id FK
        int section_id FK
    }
    grade_items {
        int id PK
        int enrollment_id FK
    }
    study_sessions {
        int id PK
        int student_id FK
    }
    plan_items {
        int id PK
        int student_id FK
        int course_id FK
        int term_id FK
    }
    approval_requests {
        int id PK
        int student_id FK
        int advisor_id FK
        int term_id FK
        int decided_by FK
    }
    assignments {
        int id PK
        int section_id FK
        int program_id FK
        int grade_item_id FK
    }
    assignment_submissions {
        int id PK
        int assignment_id FK
        int student_id FK
    }
    conversations {
        int id PK
        int created_by FK
    }
    conversation_participants {
        int conversation_id PK, FK
        int user_id PK, FK
    }
    messages {
        int id PK
        int conversation_id FK
        int sender_id FK
    }
    meetings {
        int id PK
        int student_id FK
        int advisor_id FK
        int staff_user_id FK
    }
    advisor_availability {
        int id PK
        int staff_user_id FK
    }
    events {
        int id PK
        int student_id FK
    }
    calendar_feeds {
        int student_id PK, FK
        string token_hash UK
    }
    ai_threads {
        int id PK
        int student_id FK
    }
    ai_messages {
        int id PK
        int thread_id FK
    }
    ai_flags {
        int id PK
        int message_id FK
        int student_id FK
        int resolved_by FK
    }
    system_settings {
        string key PK
        int updated_by FK
    }
    audit_events {
        bigint id PK
        int actor_id FK
    }
    integrations {
        string id PK
    }
    integration_events {
        int id PK
        string integration_id FK
    }
    import_jobs {
        int id PK
        int actor_id FK
    }
    api_keys {
        int id PK
        string key_hash UK
        int created_by FK
    }
