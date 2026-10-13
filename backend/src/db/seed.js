import { fileURLToPath } from 'node:url'
import { config } from '../config.js'
import { hashPassword } from '../lib/crypto.js'
import { DEFAULT_SETTINGS, getSetting } from '../lib/settings.js'
import { addDays, localDate, mondayOf, weekday, WEEKDAYS, zonedTime } from '../lib/time.js'
import { loadStudent, loadStudents, precheck } from '../services/academics.js'
import { answer } from '../services/ai/index.js'
import { migrate } from './migrate.js'
import { pool, transaction } from './pool.js'

// Demo data matching the design prototypes (Doumentation/Frontend prototypes/acadmate-static/data).
// Calendar items, deadlines and meetings are placed relative to today so the app always looks "live".

const TZ = 'America/New_York'
const DOMAIN = 'school.edu'

const PROGRAMS = ['M.S. Computer Science', 'M.S. Data Science', 'M.S. Information Systems']
const REQUIREMENTS = [['Foundation', 'Foundation', 2], ['Core', 'Core', 4], ['Electives', 'Elective', 5], ['Capstone', 'Capstone', 1]]

const TERMS = [
  { name: 'Fall 2025', starts: '2025-08-25', ends: '2025-12-19' },
  { name: 'Spring 2026', starts: '2026-01-20', ends: '2026-05-15' },
  { name: 'Summer 2026', starts: '2026-05-26', ends: '2026-08-14' },
  { name: 'Fall 2026', starts: '2026-08-24', ends: '2026-12-18', current: true, reg: '2026-04-06', add: '2026-09-04', drop: '2026-10-30', begin: '2026-08-24' },
  { name: 'Spring 2027', starts: '2027-01-20', ends: '2027-05-14', reg: '2026-11-03', add: '2027-01-29', drop: '2027-03-12', begin: '2027-01-20' },
  { name: 'Summer 2027', starts: '2027-05-25', ends: '2027-08-13', reg: '2027-03-15' },
]

const COURSES = [
  ['CS 501', 'Foundations of Computer Science', 'Foundation'],
  ['CS 502', 'Discrete Structures', 'Foundation'],
  ['CS 610', 'Software Engineering', 'Core'],
  ['CS 612', 'Operating Systems', 'Core', false],
  ['CS 620', 'Database Systems', 'Core'],
  ['CS 630', 'Computer Networks', 'Core'],
  ['CS 608', 'Algorithms & Computing Theory', 'Elective'],
  ['CS 640', 'Machine Learning', 'Elective'],
  ['CS 645', 'Cloud Computing', 'Elective'],
  ['CS 650', 'Human-Computer Interaction', 'Elective'],
  ['CS 661', 'Python Programming', 'Elective'],
  ['CS 675', 'Data Science', 'Elective'],
  ['CS 680', 'Natural Language Processing', 'Elective'],
  ['CS 691', 'Capstone Project', 'Capstone'],
]
const PREREQS = [['CS 691', 'CS 610'], ['CS 640', 'CS 502'], ['CS 680', 'CS 640']]

// Fall 2026 and Spring 2027 sections: [code, instructor, days, start, end, room, office hours]
const SECTIONS = {
  'Fall 2026': [
    ['CS 675', 'Prof. Hannah Brooks', ['Thu'], '10:00', '12:45', 'Room 1201', 'Wed 2–3 pm'],
    ['CS 661', 'Prof. Ravi Iyer', ['Thu'], '18:10', '20:55', 'Room 318', 'Thu 5–6 pm'],
    ['CS 608', 'Prof. Daniel Fischer', ['Mon'], '18:10', '20:55', 'Room 214', 'Mon 4–5 pm'],
    ['CS 640', 'Prof. Mei Chen', ['Tue'], '18:10', '20:55', 'Room 410', 'Tue 4–5 pm'],
    ['CS 645', 'Prof. Omar Haddad', ['Wed'], '18:10', '20:55', 'Room 220', 'Wed 5–6 pm'],
    ['CS 691', 'Dr. Elena Ramirez', ['Fri'], '15:00', '17:45', 'Room 502', 'Fri 1–2 pm'],
    ['CS 650', 'Prof. Grace Liu', ['Tue'], '10:00', '12:45', 'Room 115', 'Tue 1–2 pm'],
  ],
  'Spring 2027': [
    ['CS 691', 'Dr. Elena Ramirez', ['Mon'], '18:10', '20:55', 'Room 502', 'Mon 4–5 pm'],
    ['CS 640', 'Prof. Mei Chen', ['Wed'], '18:10', '20:55', 'Room 410', 'Wed 4–5 pm'],
    ['CS 645', 'Prof. Omar Haddad', ['Tue'], '18:10', '20:55', 'Room 220', 'Tue 5–6 pm'],
    ['CS 680', 'Prof. Mei Chen', ['Thu'], '18:10', '20:55', 'Room 410', 'Thu 4–5 pm'],
    ['CS 650', 'Prof. Grace Liu', ['Thu'], '10:00', '12:45', 'Room 115', 'Thu 1–2 pm'],
    ['CS 608', 'Prof. Daniel Fischer', ['Mon'], '18:10', '20:55', 'Room 214', 'Mon 4–5 pm'],
  ],
}

const STAFF = [
  { key: 'ramirez', name: 'Dr. Elena Ramirez', email: 'eramirez', role: 'advisor', title: 'Faculty advisor, Computer Science', dept: 'Computer Science', office: 'Science Hall, Room 410', capacity: 45, helps: 'Degree plan, capstone, course approvals' },
  { key: 'chen', name: 'Dr. Mei Chen', email: 'mchen', role: 'advisor', title: 'Faculty advisor, Data Science', dept: 'Data Science', office: 'Science Hall, Room 412', capacity: 45, helps: 'Data Science plans and electives' },
  { key: 'patel', name: 'Dr. Sanjay Patel', email: 'spatel', role: 'advisor', title: 'Faculty advisor, Information Systems', dept: 'Information Systems', office: 'Business Hall, Room 210', capacity: 40, helps: 'Information Systems plans' },
  { key: 'adeyemi', name: 'Dr. Lola Adeyemi', email: 'ladeyemi', role: 'advisor', title: 'Faculty advisor, Cybersecurity', dept: 'Cybersecurity', office: 'Science Hall, Room 305', capacity: 40, helps: 'Cybersecurity plans' },
  { key: 'career', name: 'Jordan Lee', email: 'jlee', role: 'advisor', title: 'Career advisor', dept: 'Career services', office: 'Student Center, Room 120', capacity: 0, helps: 'Internships, CPT, résumé reviews' },
  { key: 'gradoffice', name: 'Graduate Office', email: 'gradoffice', role: 'advisor', title: 'Student services', dept: 'Graduate Office', office: 'Admin Building, Room 100', capacity: 0, helps: 'Graduation application, records' },
  { key: 'fischer', name: 'Prof. Daniel Fischer', email: 'dfischer', role: 'advisor', title: 'CS 608 · Algorithms', dept: 'Computer Science', office: 'Science Hall, Room 214', capacity: 0, helps: 'CS 608 questions', bookable: false },
  { key: 'admin', name: 'Alex Morgan', email: 'admin', role: 'admin', title: 'Administrator', dept: 'IT services', office: 'Admin Building, Room 001', capacity: 0, bookable: false },
]

// completed: [code, term, grade]; current: [code, grade, progress, absences]; planned: [code, plan status, note]
const STUDENTS = [
  {
    key: 'amara', name: 'Amara Okafor', preferred: 'Amara', email: 'amara', program: 0, advisor: 'ramirez', lastLogin: 0, classTime: 'Evening classes',
    completed: [['CS 501', 'Fall 2025', 'A-'], ['CS 502', 'Fall 2025', 'A-'], ['CS 610', 'Fall 2025', 'A'], ['CS 620', 'Spring 2026', 'B+'], ['CS 630', 'Spring 2026', 'A'], ['CS 612', 'Summer 2026', 'A'], ['CS 650', 'Summer 2026', 'A']],
    current: [['CS 675', 'A-', 45, 0], ['CS 661', 'A', 50, 0], ['CS 608', 'B+', 40, 1]],
    planned: [['CS 691', 'Needs approval', 'Required to graduate. Your pre-approval form is not submitted yet.'], ['CS 640', 'Needs approval', 'Builds on Data Science and Python. Fits an open evening slot in your Spring schedule.']],
  },
  {
    key: 'daniel', name: 'Daniel Kowalski', email: 'dkowalski', program: 0, advisor: 'ramirez', lastLogin: 1,
    completed: [['CS 501', 'Fall 2025', 'B+'], ['CS 502', 'Fall 2025', 'A-'], ['CS 610', 'Fall 2025', 'B+'], ['CS 620', 'Spring 2026', 'A-'], ['CS 630', 'Spring 2026', 'B'], ['CS 612', 'Summer 2026', 'B+'], ['CS 640', 'Summer 2026', 'A-'], ['CS 650', 'Summer 2026', 'B+']],
    current: [['CS 675', 'B+', 45, 1], ['CS 645', 'A-', 40, 0], ['CS 608', 'B', 40, 0]],
    planned: [['CS 691', 'Needs approval', 'Capstone after the pre-approval form is signed.']],
  },
  {
    key: 'priya', name: 'Priya Shah', email: 'pshah', program: 1, advisor: 'ramirez', lastLogin: 0,
    completed: [['CS 501', 'Fall 2025', 'A'], ['CS 502', 'Fall 2025', 'A'], ['CS 610', 'Fall 2025', 'A'], ['CS 620', 'Spring 2026', 'A'], ['CS 630', 'Spring 2026', 'A-'], ['CS 612', 'Spring 2026', 'A'], ['CS 675', 'Summer 2026', 'A'], ['CS 661', 'Summer 2026', 'A-']],
    current: [['CS 691', 'A', 35, 0]],
    planned: [['CS 640', 'Needs approval', ''], ['CS 645', 'Needs approval', ''], ['CS 680', 'Needs approval', '']],
  },
  {
    key: 'marcus', name: 'Marcus Thompson', email: 'mthompson', program: 0, advisor: 'ramirez', lastLogin: 2,
    completed: [['CS 501', 'Fall 2025', 'A-'], ['CS 502', 'Fall 2025', 'B+'], ['CS 610', 'Spring 2026', 'B+'], ['CS 620', 'Spring 2026', 'B'], ['CS 630', 'Summer 2026', 'A-'], ['CS 650', 'Summer 2026', 'B+']],
    current: [['CS 608', 'C+', 35, 2], ['CS 661', 'B-', 40, 1], ['CS 645', 'C+', 35, 2]],
    planned: [],
  },
  {
    key: 'lina', name: 'Lina Haddad', email: 'lhaddad', program: 2, advisor: 'ramirez', lastLogin: 41,
    completed: [['CS 501', 'Fall 2025', 'B+'], ['CS 502', 'Fall 2025', 'B'], ['CS 620', 'Spring 2026', 'B+'], ['CS 630', 'Spring 2026', 'B'], ['CS 612', 'Summer 2026', 'B+'], ['CS 650', 'Summer 2026', 'A-'], ['CS 645', 'Summer 2026', 'B'], ['CS 661', 'Summer 2026', 'B+']],
    current: [['CS 675', 'B', 40, 2], ['CS 640', 'B-', 35, 1]],
    planned: [['CS 691', 'Needs approval', '']],
    missesWork: true,
  },
  {
    key: 'jonah', name: 'Jonah Park', email: 'jpark', program: 0, advisor: 'ramirez', lastLogin: 0,
    completed: [['CS 501', 'Spring 2026', 'A-'], ['CS 502', 'Spring 2026', 'A'], ['CS 610', 'Summer 2026', 'A-'], ['CS 620', 'Summer 2026', 'B+']],
    current: [['CS 630', 'A-', 45, 0], ['CS 661', 'A', 50, 0], ['CS 675', 'B+', 45, 0]],
    planned: [['CS 612', 'Approved', ''], ['CS 640', 'Approved', ''], ['CS 645', 'Approved', '']],
  },
  {
    key: 'sofia', name: 'Sofia Rossi', email: 'srossi', program: 0, advisor: 'ramirez', lastLogin: 3,
    completed: [['CS 501', 'Fall 2025', 'A'], ['CS 502', 'Fall 2025', 'A-'], ['CS 610', 'Fall 2025', 'A'], ['CS 620', 'Spring 2026', 'A-'], ['CS 630', 'Spring 2026', 'A'], ['CS 612', 'Spring 2026', 'B+'], ['CS 640', 'Summer 2026', 'A'], ['CS 650', 'Summer 2026', 'A'], ['CS 661', 'Summer 2026', 'A-'], ['CS 645', 'Summer 2026', 'A'], ['CS 680', 'Summer 2026', 'B+']],
    current: [['CS 691', 'A-', 40, 0]],
    planned: [],
  },
  {
    key: 'kwame', name: 'Kwame Asante', email: 'kasante', program: 1, advisor: 'ramirez', lastLogin: 5,
    completed: [['CS 501', 'Fall 2025', 'B+'], ['CS 502', 'Fall 2025', 'A-'], ['CS 610', 'Fall 2025', 'B+'], ['CS 620', 'Spring 2026', 'A-'], ['CS 630', 'Spring 2026', 'B+'], ['CS 612', 'Spring 2026', 'B'], ['CS 640', 'Summer 2026', 'A-'], ['CS 650', 'Summer 2026', 'B+'], ['CS 661', 'Summer 2026', 'A'], ['CS 645', 'Summer 2026', 'B+']],
    current: [['CS 675', 'A-', 45, 0], ['CS 691', 'B+', 40, 0]],
    planned: [],
  },
  {
    key: 'noah', name: 'Noah Kim', email: 'nkim', program: 1, advisor: 'chen', lastLogin: 1,
    completed: [['CS 501', 'Fall 2025', 'A'], ['CS 502', 'Fall 2025', 'A'], ['CS 610', 'Spring 2026', 'A-'], ['CS 620', 'Spring 2026', 'A']],
    current: [['CS 675', 'A', 45, 0], ['CS 630', 'A-', 45, 0]],
    planned: [],
  },
  {
    key: 'grace', name: 'Grace Liu', email: 'gliu', program: 1, advisor: 'chen', lastLogin: 2,
    completed: [['CS 501', 'Fall 2025', 'B+'], ['CS 502', 'Fall 2025', 'A-'], ['CS 610', 'Spring 2026', 'B+']],
    current: [['CS 675', 'A-', 45, 0], ['CS 620', 'B+', 40, 0]],
    planned: [],
  },
  { key: 'sam', name: 'Sam Rivera', email: 'srivera', program: 2, advisor: 'patel', status: 'invited', completed: [], current: [], planned: [] },
]

// Fall 2026 course work: [course, title, type, weight, due offset (days from today), description, steps]
const WORK = [
  ['CS 675', 'Lab 3: Data cleaning', 'Individual', 5, -16, 'Clean and document the course dataset.', ['Load the data', 'Handle missing values', 'Submit the notebook']],
  ['CS 675', 'Lab 4: Exploratory analysis', 'Individual', 5, -2, 'Explore the dataset and summarize findings with plots.', ['Plot distributions', 'Write findings', 'Submit']],
  ['CS 675', 'Project topic proposal', 'Team', 5, 2, 'One-page team proposal: problem statement, chosen dataset, planned methods in R and Python, and each member’s role.', ['Agree on the topic with the team', 'Write the problem statement and dataset section', 'Outline supervised and unsupervised models', 'Proofread and submit']],
  ['CS 661', 'Week 4 tutorial', 'Individual', 4, -10, 'Complete the week 4 tutorial exercises.', ['Work through the exercises', 'Upload the notebook']],
  ['CS 661', 'Week 5 tutorial', 'Individual', 4, -3, 'Complete the week 5 tutorial exercises.', ['Work through the exercises', 'Upload the notebook']],
  ['CS 661', 'Week 6 tutorial', 'Individual', 4, 4, 'Complete this week’s tutorial exercises and upload your notebook.', ['Work through the exercises', 'Test every function', 'Upload the notebook']],
  ['CS 661', 'Project 2 checkpoint', 'Individual', 10, 15, 'Submit a working first version of Project 2 with a short README.', ['Set up the project structure', 'Build the core features', 'Write the README']],
  ['CS 608', 'Problem set 3', 'Individual', 7, -12, 'Greedy algorithms and amortized analysis.', ['Solve each problem', 'Write proofs']],
  ['CS 608', 'Dynamic programming set', 'Individual', 7, -3, 'Graded. Feedback is available on the course site.', ['Read the grader’s feedback', 'Fix mistakes before the midterm']],
  ['CS 608', 'Problem set 4', 'Individual', 7, 8, 'Dynamic programming and greedy algorithms. Show recurrences and prove correctness where asked.', ['Review lecture notes on DP', 'Draft recurrences for each problem', 'Write proofs', 'Check answers at office hours']],
  ['CS 640', 'Homework 3: Regression', 'Individual', 8, -6, 'Linear and logistic regression exercises.', ['Implement models', 'Report results']],
  ['CS 640', 'Homework 4: Trees', 'Individual', 8, -1, 'Decision trees and ensembles.', ['Implement models', 'Report results']],
  ['CS 645', 'Lab 2: Containers', 'Individual', 6, -4, 'Containerize the sample service.', ['Write a Dockerfile', 'Deploy']],
  ['CS 691', 'Capstone milestone 1', 'Individual', 10, -5, 'Project charter and requirements.', ['Write the charter', 'Review with advisor']],
  ['CS 630', 'Lab 3: Routing', 'Individual', 6, -7, 'Configure routing in the simulator.', ['Configure', 'Submit report']],
  ['CS 620', 'Assignment 2: SQL', 'Individual', 6, -5, 'Write the queries in the handout.', ['Write queries', 'Submit']],
]

// What each student has done on Fall 2026 work: title -> [status, score, days late]
const PROGRESS = {
  amara: {
    'Lab 3: Data cleaning': ['Graded', 93, 0], 'Lab 4: Exploratory analysis': ['Submitted', null, 0], 'Project topic proposal': ['In progress', null, 0, [0]],
    'Week 4 tutorial': ['Graded', 95, 0], 'Week 5 tutorial': ['Graded', 98, 0], 'Week 6 tutorial': ['In progress', null, 0, [0]],
    'Problem set 3': ['Graded', 88, 1], 'Dynamic programming set': ['Graded', 84, 0],
  },
  lina: { 'Lab 3: Data cleaning': ['Graded', 81, 0] },
}

async function insert(db, sql, params) {
  const { rows } = await db.query(sql, params)
  return rows[0]
}

export async function seed({ now = new Date(), log = console.log } = {}) {
  const password = config.seedPassword
  if (!password || password.length < 8) throw new Error('Set SEED_PASSWORD (8+ characters) in backend/.env before seeding.')
  const passwordHash = await hashPassword(password)
  const today = localDate(now, TZ)
  const monday = mondayOf(today)
  const at = (date, time) => zonedTime(date, time, TZ)
  const day = (offset) => addDays(today, offset)
  const hoursAgo = (h) => new Date(now.getTime() - h * 3_600_000)
  // Next date on or after `from` that falls on a weekday (Mon–Fri).
  const weekdayFrom = (from) => { let d = from; while (['Sat', 'Sun'].includes(weekday(d))) d = addDays(d, 1); return d }

  await transaction(async (db) => {
    const tables = (await db.query(`SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'schema_migrations'`)).rows
    await db.query(`TRUNCATE ${tables.map((t) => `"${t.tablename}"`).join(', ')} RESTART IDENTITY CASCADE`)

    // ---- settings & catalog
    await db.query(`INSERT INTO app_settings (key, value) VALUES ('institution', $1), ('security', $2), ('retention', $3), ('branding', $4), ('ai', $5)`, [
      JSON.stringify({ name: 'Acadmate University', emailDomain: DOMAIN, supportEmail: `acadmate-help@${DOMAIN}`, timeZone: 'Eastern' }),
      JSON.stringify(DEFAULT_SETTINGS.security), JSON.stringify(DEFAULT_SETTINGS.retention), JSON.stringify(DEFAULT_SETTINGS.branding), JSON.stringify(DEFAULT_SETTINGS.ai),
    ])
    const programIds = []
    for (const name of PROGRAMS) {
      const program = await insert(db, 'INSERT INTO programs (name) VALUES ($1) RETURNING id', [name])
      programIds.push(program.id)
      for (const [i, [label, type, count]] of REQUIREMENTS.entries()) {
        await db.query('INSERT INTO requirement_groups (program_id, name, course_type, required_count, sort_order) VALUES ($1, $2, $3, $4, $5)', [program.id, label, type, count, i])
      }
    }
    const termIds = {}
    const termRows = {}
    for (const t of TERMS) {
      const row = await insert(db,
        `INSERT INTO terms (name, starts_on, ends_on, is_current, registration_opens, last_add, last_drop, classes_begin)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING *`,
        [t.name, t.starts, t.ends, Boolean(t.current), t.reg ?? null, t.add ?? null, t.drop ?? null, t.begin ?? t.starts])
      termIds[t.name] = row.id
      termRows[t.name] = row
    }
    const courseIds = {}
    for (const [code, name, type, offered = true] of COURSES) {
      courseIds[code] = (await insert(db, 'INSERT INTO courses (code, name, type, offered, offer_term) VALUES ($1, $2, $3, $4, $5) RETURNING id',
        [code, name, type, offered, offered ? 'Spring 2027' : null])).id
    }
    for (const [course, prereq] of PREREQS) await db.query('INSERT INTO course_prerequisites (course_id, prereq_id) VALUES ($1, $2)', [courseIds[course], courseIds[prereq]])
    for (const [term, sections] of Object.entries(SECTIONS)) {
      for (const [code, instructor, days, start, end, room, office] of sections) {
        await db.query('INSERT INTO sections (course_id, term_id, instructor, days, start_time, end_time, room, office_hours) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)',
          [courseIds[code], termIds[term], instructor, days, start, end, room, office])
      }
    }

    // ---- people
    const users = {}
    for (const s of STAFF) {
      users[s.key] = await insert(db,
        `INSERT INTO users (email, password_hash, full_name, role, status, last_login_at) VALUES ($1, $2, $3, $4, 'active', $5) RETURNING *`,
        [`${s.email}@${DOMAIN}`, passwordHash, s.name, s.role, hoursAgo(3)])
      await db.query(
        `INSERT INTO staff_profiles (user_id, title, department, office, capacity, helps, bookable, settings) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`,
        [users[s.key].id, s.title, s.dept, s.office, s.capacity, s.helps ?? null, s.bookable ?? s.role === 'advisor',
          JSON.stringify({ videoLink: s.role === 'advisor' ? `https://meet.${DOMAIN}/${s.email}` : '' })])
    }
    await db.query(`INSERT INTO office_hours (staff_id, day, start_time, end_time, location) VALUES ($1, 'Wed', '16:30', '17:30', 'Science Hall, Room 410')`, [users.ramirez.id])

    for (const [i, s] of STUDENTS.entries()) {
      const status = s.status ?? 'active'
      users[s.key] = await insert(db,
        `INSERT INTO users (email, password_hash, full_name, preferred_name, role, status, last_login_at, preferences)
         VALUES ($1, $2, $3, $4, 'student', $5, $6, $7) RETURNING *`,
        [`${s.email}@${DOMAIN}`, status === 'active' ? passwordHash : null, s.name, s.preferred ?? null, status,
          s.lastLogin == null ? null : hoursAgo(s.lastLogin * 24 + 2), JSON.stringify(s.classTime ? { classTime: s.classTime } : {})])
      await db.query('INSERT INTO student_profiles (user_id, student_number, program_id, advisor_id) VALUES ($1, $2, $3, $4)',
        [users[s.key].id, `S${String(10241 + i).padStart(6, '0')}`, programIds[s.program], users[s.advisor].id])
      for (const [code, term, grade] of s.completed) {
        await db.query(`INSERT INTO enrollments (student_id, course_id, term_id, status, grade, progress_pct) VALUES ($1, $2, $3, 'completed', $4, 100)`,
          [users[s.key].id, courseIds[code], termIds[term], grade])
      }
      for (const [code, grade, progress, absences] of s.current) {
        await db.query(`INSERT INTO enrollments (student_id, course_id, term_id, status, grade, progress_pct, absences) VALUES ($1, $2, $3, 'current', $4, $5, $6)`,
          [users[s.key].id, courseIds[code], termIds['Fall 2026'], grade, progress, absences])
      }
      for (const [code, planStatus, note] of s.planned) {
        await db.query(`INSERT INTO enrollments (student_id, course_id, term_id, status, plan_status, plan_note) VALUES ($1, $2, $3, 'planned', $4, $5)`,
          [users[s.key].id, courseIds[code], termIds['Spring 2027'], planStatus, note || null])
      }
    }

    // Grade breakdowns for Amara's current courses (from the My courses prototype).
    const parts = {
      'CS 675': [['Team project', 40, null, null], ['Labs', 25, 92, null], ['Midterm', 20, null, day(12)], ['Participation', 15, 95, null]],
      'CS 661': [['Weekly tutorials', 40, 96, null], ['Projects', 30, 94, null], ['Final exam', 20, null, '2026-12-10'], ['Participation', 10, 100, null]],
      'CS 608': [['Problem sets', 35, 86, null], ['Midterm', 30, null, day(9)], ['Final exam', 30, null, '2026-12-14'], ['Participation', 5, 100, null]],
    }
    for (const [code, list] of Object.entries(parts)) {
      const enrollment = await insert(db, `SELECT id FROM enrollments WHERE student_id = $1 AND course_id = $2 AND status = 'current'`, [users.amara.id, courseIds[code]])
      for (const [i, [label, weight, score, due]] of list.entries()) {
        await db.query('INSERT INTO grade_components (enrollment_id, label, weight, score, due_on, sort_order) VALUES ($1, $2, $3, $4, $5, $6)', [enrollment.id, label, weight, score, due, i])
      }
    }

    // ---- course work and submissions
    const enrolledIn = (code) => STUDENTS.filter((s) => s.current.some(([c]) => c === code))
    const workIds = {}
    for (const [code, title, type, weight, offset, description, steps] of WORK) {
      const dueAt = at(day(offset), '23:59')
      const row = await insert(db,
        `INSERT INTO assignments (course_id, term_id, title, description, type, weight_pct, due_at, steps) VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING id`,
        [courseIds[code], termIds['Fall 2026'], title, description, type, weight, dueAt, JSON.stringify(steps)])
      workIds[title] = row.id
      for (const s of enrolledIn(code)) {
        const custom = PROGRESS[s.key]?.[title]
        let status = custom?.[0]
        let score = custom?.[1] ?? null
        const late = custom?.[2] ?? 0
        const stepsDone = custom?.[3] ?? []
        if (!custom) {
          if (offset >= 0) continue // future work not started yet
          if (s.missesWork && offset > -14) continue // Lina: missed deadlines in the last two weeks
          status = offset < -2 ? 'Graded' : 'Submitted'
          score = status === 'Graded' ? 80 + ((s.name.length * 7 + title.length) % 19) : null
        }
        const submittedAt = ['Submitted', 'Graded'].includes(status) ? new Date(dueAt.getTime() + (late ? late * 86_400_000 : -36 * 3_600_000)) : null
        await db.query(
          `INSERT INTO submissions (assignment_id, student_id, status, score, submitted_at, steps_done) VALUES ($1, $2, $3, $4, $5, $6)`,
          [row.id, users[s.key].id, status, score, submittedAt, stepsDone])
      }
    }
    // Per-student advising forms.
    const formDue = at(day(19), '23:59')
    workIds.amaraForm = (await insert(db,
      `INSERT INTO assignments (student_id, term_id, title, description, type, due_at, steps) VALUES ($1, $2, 'Capstone pre-approval form', $3, 'Form', $4, $5) RETURNING id`,
      [users.amara.id, termIds['Fall 2026'], 'Your advisor must sign this form before you can register for the capstone in Spring 2027.', formDue,
        JSON.stringify(['Pick two or three capstone ideas', 'Discuss them at your capstone meeting', 'Fill in and send the form'])])).id
    const danielForm = await insert(db,
      `INSERT INTO assignments (student_id, term_id, title, description, type, due_at, steps) VALUES ($1, $2, 'Capstone pre-approval form', $3, 'Form', $4, $5) RETURNING id`,
      [users.daniel.id, termIds['Fall 2026'], 'Your advisor must sign this form before you can register for the capstone.', formDue, JSON.stringify(['Fill in and send the form'])])
    await db.query(`INSERT INTO submissions (assignment_id, student_id, status, submitted_at) VALUES ($1, $2, 'Submitted', $3)`, [danielForm.id, users.daniel.id, hoursAgo(30)])

    // ---- Amara's calendar: study blocks and team meetings for last, this and next week
    for (const weekStart of [addDays(monday, -7), monday, addDays(monday, 7)]) {
      const d = (dow) => addDays(weekStart, WEEKDAYS.indexOf(dow))
      const events = [
        ['Study · CS 675 labs', 'Study', d('Mon'), '13:00', '15:00', 'Library, 3rd floor', 'Personal study block for lab work.'],
        ['Study · CS 661', 'Study', d('Tue'), '12:00', '13:00', 'Online', 'Work on the weekly tutorial.'],
        ['CS 675 office hours', 'Office hours', d('Wed'), '14:00', '15:00', 'Prof. Brooks’s office', 'Optional. Bring questions about the project proposal.'],
        ['Study · CS 608', 'Study', d('Wed'), '18:00', '20:00', 'Library', 'Problem set practice.'],
        ['Team project sync', 'Team', d('Thu'), '13:30', '14:15', 'Study room 3', 'Finalize the topic proposal.'],
        ['Study · CS 675 reading', 'Study', d('Thu'), '15:30', '17:30', 'Library', 'Read the assigned chapter.'],
        ['CS 608 study group', 'Team', d('Fri'), '16:00', '17:30', 'Study room 1', 'Review dynamic programming.'],
        ['Study · proposal edits', 'Study', d('Sat'), '10:00', '12:00', 'Home', 'Final read-through before submitting.'],
        ['Study · weekly review', 'Study', d('Sun'), '15:00', '16:30', 'Home', 'Plan the week ahead.'],
      ]
      for (const [title, type, date, start, end, location, note] of events) {
        await db.query('INSERT INTO events (owner_id, title, type, starts_at, ends_at, location, note) VALUES ($1, $2, $3, $4, $5, $6, $7)',
          [users.amara.id, title, type, at(date, start), at(date, end), location, note])
      }
    }

    // ---- meetings with Dr. Ramirez
    const meeting = (student, date, time, minutes, format, topic, status = 'confirmed', extra = {}) => db.query(
      `INSERT INTO meetings (student_id, staff_id, starts_at, ends_at, format, topic, status, location, video_link, student_note, attach_plan, created_at)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)`,
      [student ? users[student].id : null, users.ramirez.id, at(date, time), new Date(at(date, time).getTime() + minutes * 60_000), format, topic, status,
        format === 'In person' ? 'Science Hall, Room 410' : null, format === 'Online' ? `https://meet.${DOMAIN}/eramirez` : null,
        extra.note ?? null, extra.attachPlan ?? false, extra.createdAt ?? hoursAgo(72)])
    await meeting('jonah', today, '10:00', 30, 'In person', 'Course change: swap one elective')
    await meeting('priya', today, '13:00', 30, 'Online', 'Review Spring 2027 plan')
    await meeting('amara', today, '15:00', 30, 'Online', 'Advising check-in: Spring plan from Acadmate', 'confirmed', { attachPlan: true })
    const capstoneDay = weekdayFrom(day(5))
    await meeting('amara', capstoneDay, '15:00', 30, 'In person', 'Capstone topics', 'confirmed', { note: 'I will bring three capstone ideas.', attachPlan: true })
    await meeting('lina', weekdayFrom(day(3)), '14:00', 30, 'Online', 'Capstone prerequisite question', 'requested')
    await meeting('sofia', weekdayFrom(day(6)), '10:00', 30, 'In person', 'Final graduation audit', 'requested')
    // Past meetings for the reports chart.
    const pastStudents = ['amara', 'daniel', 'priya', 'marcus', 'jonah', 'sofia', 'kwame']
    for (let week = 1; week <= 6; week++) {
      for (let k = 0; k < 4 + ((week * 3) % 5); k++) {
        const date = weekdayFrom(addDays(monday, -7 * week + (k % 5)))
        await meeting(pastStudents[(week + k) % pastStudents.length], date, ['09:00', '10:00', '11:00', '13:00', '14:00', '15:00', '16:00'][k % 7], 30, k % 2 ? 'Online' : 'In person', 'Advising check-in', 'confirmed', { createdAt: addDaysTime(at(date, '09:00'), -3) })
      }
    }

    // ---- approvals (pre-checks are computed by the same rules the API uses)
    const contexts = await loadStudents(STUDENTS.filter((s) => s.status !== 'invited').map((s) => users[s.key].id), db)
    const ctxOf = (key) => contexts.get(users[key].id)
    const planned = (key) => ctxOf(key).enrollments.filter((e) => e.status === 'planned')
    const approval = async (key, a, createdHoursAgo, decided = null) => {
      const check = await precheck(ctxOf(key), a, { tz: TZ, db })
      await db.query(
        `INSERT INTO approvals (student_id, advisor_id, type, title, lines, payload, precheck_ok, precheck_text, status, comment, decided_by, decided_at, created_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)`,
        [users[key].id, users.ramirez.id, a.type, a.title, JSON.stringify(a.lines), JSON.stringify({ ...a.payload, checks: check.checks }), check.ok, check.text,
          decided?.status ?? 'Pending', decided?.comment ?? null, decided ? users.ramirez.id : null, decided ? hoursAgo(createdHoursAgo - decided.afterHours) : null, hoursAgo(createdHoursAgo)])
    }
    const coursePlan = (key, label, lines) => {
      const list = planned(key)
      return {
        type: 'Course plan', title: `Spring 2027 plan · ${label}`, lines,
        payload: { courseIds: list.map((e) => e.course_id), enrollmentIds: list.map((e) => e.id), termId: termIds['Spring 2027'], termEndsOn: termRows['Spring 2027'].ends_on },
      }
    }
    await approval('amara', coursePlan('amara', 'Capstone Project + Machine Learning', [{ a: 'CS 691 Capstone Project', b: 'Mon 18:10 · 3 cr' }, { a: 'CS 640 Machine Learning', b: 'Wed 18:10 · 3 cr' }]), 26)
    await approval('daniel', { type: 'Form', title: 'Capstone pre-approval form', lines: [{ a: 'Proposed topic', b: 'Federated learning for small clinics' }, { a: 'Project summary', b: 'Missing' }], payload: { assignmentId: danielForm.id, fields: { 'Proposed topic': 'Federated learning for small clinics', 'Project summary': '' } } }, 30)
    await approval('priya', coursePlan('priya', '3 electives', [{ a: 'CS 640 Machine Learning', b: '3 cr' }, { a: 'CS 645 Cloud Computing', b: '3 cr' }, { a: 'CS 680 Natural Language Processing', b: '3 cr' }]), 32)
    const marcus608 = ctxOf('marcus').enrollments.find((e) => e.code === 'CS 608')
    await approval('marcus', { type: 'Request', title: 'Drop CS 608 Algorithms & Computing Theory', lines: [{ a: 'Drop', b: 'CS 608 · 3 cr' }, { a: 'Credits after drop', b: '6' }], payload: { action: 'drop', courseId: marcus608.course_id, enrollmentId: marcus608.id, reason: 'My work hours changed this month.' } }, 50)
    await approval('lina', coursePlan('lina', 'Capstone Project', [{ a: 'CS 691 Capstone Project', b: 'Mon 18:10 · 3 cr' }]), 75)
    // Decided earlier this term (feeds the response-time report).
    await approval('jonah', coursePlan('jonah', 'Operating Systems + 2 electives', [{ a: 'CS 612 Operating Systems', b: '3 cr' }, { a: 'CS 640 Machine Learning', b: '3 cr' }, { a: 'CS 645 Cloud Computing', b: '3 cr' }]), 24 * 20, { status: 'Approved', afterHours: 30 })
    await approval('sofia', { type: 'Form', title: 'Graduation audit request', lines: [{ a: 'Expected term', b: 'Fall 2026' }], payload: { fields: { 'Expected term': 'Fall 2026' } } }, 24 * 30, { status: 'Approved', afterHours: 20 })
    await db.query(`UPDATE enrollments SET plan_status = 'Pending approval' WHERE status = 'planned' AND plan_status = 'Needs approval' AND student_id = ANY($1)`,
      [['amara', 'priya', 'lina'].map((k) => users[k].id)])

    await db.query('INSERT INTO advisor_notes (student_id, author_id, body, created_at) VALUES ($1, $2, $3, $4)',
      [users.amara.id, users.ramirez.id, 'Strong in data science; consider recommending her for the research assistant opening.', hoursAgo(24 * 28)])

    // ---- conversations
    const conversation = async (kind, title, members, messages) => {
      const c = await insert(db, 'INSERT INTO conversations (kind, title) VALUES ($1, $2) RETURNING id', [kind, title])
      for (const m of members) {
        await db.query('INSERT INTO conversation_members (conversation_id, user_id, last_read_at) VALUES ($1, $2, $3)', [c.id, users[m].id, m === members[0] ? now : '-infinity'])
      }
      for (const [from, body, hours] of messages) {
        await db.query('INSERT INTO messages (conversation_id, sender_id, sender_name, body, created_at) VALUES ($1, $2, $3, $4, $5)',
          [c.id, from ? users[from].id : null, from ? users[from].full_name : 'Acadmate', body, hoursAgo(hours)])
      }
      return c.id
    }
    const markRead = (id, key) => db.query('UPDATE conversation_members SET last_read_at = $3 WHERE conversation_id = $1 AND user_id = $2', [id, users[key].id, now])
    const advChat = await conversation('direct', null, ['amara', 'ramirez'], [
      ['ramirez', 'Hi Amara, I looked at the Spring plan Acadmate put together. Capstone plus one AI elective works for May 2027.', 20],
      ['amara', 'Thank you! Could we go over capstone topics at our meeting next week?', 18],
      ['ramirez', 'Yes. Bring two or three ideas, and please send the capstone pre-approval form before it is due.', 2],
    ])
    await markRead(advChat, 'ramirez')
    await db.query(`UPDATE conversation_members SET last_read_at = $3 WHERE conversation_id = $1 AND user_id = $2`, [advChat, users.amara.id, hoursAgo(3)])
    await conversation('group', 'CS 675 project team', ['amara', 'noah', 'grace'], [
      ['noah', 'Proposal draft is in the shared folder. Can someone write the dataset section?', 26],
      ['amara', 'I’ll take the dataset section tonight.', 25],
      ['grace', 'Can we meet Thursday at 13:30 to finalize before we submit?', 24],
    ]).then((id) => db.query('UPDATE conversation_members SET last_read_at = $3 WHERE conversation_id = $1 AND user_id = $2', [id, users.amara.id, hoursAgo(25)]))
    await conversation('direct', null, ['amara', 'fischer'], [['fischer', 'Office hours move to Monday 4–5 pm this week. Bring questions on Problem set 4.', 24 * 4]])
    await conversation('direct', null, ['amara', 'gradoffice'], [['gradoffice', 'Students graduating in May 2027 should file a graduation application by March 1.', 24 * 12]])
    await conversation('direct', null, ['ramirez', 'marcus'], [
      ['marcus', 'I’d like to drop CS 608. My work hours changed this month.', 3],
      ['marcus', 'Is there a way to stay full-time if I drop it?', 2.9],
    ]).then((id) => markRead(id, 'marcus'))
    await conversation('direct', null, ['ramirez', 'daniel'], [['daniel', 'I submitted my capstone form. Do you need anything else from me?', 22]])
      .then(async (id) => { await markRead(id, 'daniel'); await db.query(`UPDATE conversation_members SET last_read_at = '-infinity' WHERE conversation_id = $1 AND user_id = $2`, [id, users.ramirez.id]) })
    await conversation('group', 'CS advising team', ['ramirez', 'chen', 'patel', 'adeyemi'], [
      ['chen', 'Reminder: Spring registration opens Nov 3. Let’s clear plan approvals by Oct 30.', 24 * 4],
      ['patel', 'I can cover drop-in hours on Friday if anyone needs it.', 24 * 4 - 1],
    ])
    for (const [key, notes] of [
      ['amara', [['Your Spring 2027 plan is waiting for advisor approval.', 26], ['Reminder: Spring 2027 registration opens Nov 3.', 48]]],
      ['ramirez', [['5 course plans and requests are waiting for your approval.', 24]]],
    ]) {
      const id = await conversation('system', 'Acadmate', [key], notes.map(([text, hours]) => [null, text, hours]))
      await db.query(`UPDATE conversation_members SET last_read_at = $2 WHERE conversation_id = $1`, [id, hoursAgo(1)])
    }

    // ---- administration
    for (const [q, issue, source, hours] of [
      ['Is CS 612 offered in Spring?', 'Answer listed a course that isn’t on the Spring 2027 schedule.', 'Reported by student', 3],
      ['Can I skip the advanced theory prerequisite?', 'Advisor says the waiver rule quoted is out of date.', 'Reported by Dr. Mei Chen', 26],
      ['How many credits make me full-time?', 'Gave the undergraduate threshold, not the graduate one.', 'Auto-check', 24 * 3],
      ['When is the graduation application due?', 'No date in the catalog, so the answer guessed.', 'Auto-check', 24 * 4],
    ]) {
      await db.query('INSERT INTO ai_flags (question, issue, source, created_at) VALUES ($1, $2, $3, $4)', [q, issue, source, hoursAgo(hours)])
    }
    await db.query(`INSERT INTO ai_flags (question, issue, source, status, resolved_by, resolved_at, created_at) VALUES ($1, $2, 'Auto-check', 'Resolved', $3, $4, $5)`,
      ['Can I take CS 691 without the prerequisite?', 'Answer contradicted the catalog.', users.admin.id, hoursAgo(24 * 6), hoursAgo(24 * 8)])
    const integrations = [
      ['csv', 'CSV data import', 'Upload courses, enrollments and grades exported from your school’s systems.', true, [['Imported 2026–27 catalog', hoursAgo(24 * 39)]]],
      ['mail', 'Email (SMTP)', 'Sends meeting confirmations, reminders and invites.', false, []],
      ['gcal', 'Google Calendar', 'Students subscribe to their Acadmate calendar feed from Google Calendar.', false, []],
      ['outlook', 'Outlook Calendar', 'Students subscribe to their Acadmate calendar feed from Outlook.', false, []],
    ]
    for (const [id, name, description, connected, log] of integrations) {
      await db.query('INSERT INTO integrations (id, name, description, connected, last_sync_at, log) VALUES ($1, $2, $3, $4, $5, $6)',
        [id, name, description, connected, log[0]?.[1] ?? null, JSON.stringify(log.map(([a, b]) => ({ a, b })))])
    }

    const auditRows = [
      ['ramirez', 'Advisor', 'Approved Operating Systems + 2 electives plan for Jonah P.', 24 * 19, 'jonah'],
      [null, 'System', 'Flagged an answer about visa rules for human review', 3],
      ['admin', 'Admin', 'Turned on grade-based insights', 4],
      ['amara', 'Student', 'Signed in', 2, 'amara'],
      ['amara', 'Student', 'Booked a meeting with Dr. Elena Ramirez', 70, 'amara'],
      ['admin', 'Admin', 'Invited 1 student', 24 * 2, 'sam'],
      ['admin', 'Admin', 'Changed CS 612 (offered → not offered)', 24 * 3],
      ['admin', 'Admin', 'Reassigned 5 advisees from Dr. Sanjay Patel to Dr. Lola Adeyemi', 24 * 5],
      ['admin', 'Admin', 'Published catalog version 1', 24 * 19],
      ['marcus', 'Student', 'Signed in', 24 * 2, 'marcus'],
      ['marcus', 'Student', 'Requested to drop CS 608', 50, 'marcus'],
      ['amara', 'Student', 'Shared their Spring 2027 plan for approval', 26, 'amara'],
      ['amara', 'Student', 'Completed the CS 608 dynamic programming set (84%)', 24 * 3, 'amara'],
    ]
    for (const s of STUDENTS.filter((x) => x.lastLogin != null)) {
      for (let w = 0; w < 6; w++) auditRows.push([s.key, 'Student', 'Signed in', 24 * 7 * w + s.lastLogin * 24 + 2, s.key])
    }
    for (const [actor, role, action, hours, subject] of auditRows) {
      await db.query(
        `INSERT INTO audit_log (actor_id, actor_name, actor_role, action, subject_user_id, ip, created_at) VALUES ($1, $2, $3, $4, $5, $6, $7)`,
        [actor ? users[actor].id : null, actor ? users[actor].full_name : 'Acadmate', role, action, subject ? users[subject].id : null, actor ? '192.0.2.10' : null, hoursAgo(hours)])
    }
  })

  // Publish the catalog once so students can read it.
  await pool.query(
    `INSERT INTO catalog_versions (snapshot, published_at) SELECT jsonb_build_object('courses', jsonb_agg(jsonb_build_object('code', code, 'name', name, 'type', type, 'credits', credits, 'offered', offered) ORDER BY code)), now() FROM courses`)

  await seedAiConversation(`amara@${DOMAIN}`, now)

  log(`Seeded demo data. Every demo account uses the SEED_PASSWORD from backend/.env:
  student  amara@${DOMAIN}      (also dkowalski, pshah, mthompson, lhaddad, jpark, srossi, kasante, nkim, gliu)
  advisor  eramirez@${DOMAIN}   (also mchen, spatel, ladeyemi, jlee, gradoffice, dfischer)
  admin    admin@${DOMAIN}
Advisors and admins enrol an authenticator app on first sign-in (two-step sign-in is on).`)
}

// One AI advisor conversation, answered by the rule-based engine from the seeded records (never Claude,
// so seeding needs no API key and sends nothing out).
async function seedAiConversation(email, now) {
  const { id } = (await pool.query('SELECT id FROM users WHERE email = $1', [email])).rows[0]
  const ctx = await loadStudent(id)
  const tz = TZ
  const settings = { ...(await getSetting('ai')), engine: 'Rules' }
  const started = new Date(now.getTime() - 26 * 3_600_000)
  const thread = (await pool.query(
    `INSERT INTO ai_threads (student_id, title, created_at, updated_at) VALUES ($1, $2, $3, $3) RETURNING id`, [id, 'Am I on track to graduate?', started])).rows[0]
  const history = []
  for (const [i, text] of ['Am I on track to graduate?', 'Compare my elective options'].entries()) {
    const at = new Date(started.getTime() + i * 120_000)
    const reply = await answer({ ctx, text, history, settings, tz, today: localDate(now, tz) })
    await pool.query(`INSERT INTO ai_messages (thread_id, role, body, created_at) VALUES ($1, 'user', $2, $3)`, [thread.id, text, at])
    await pool.query(
      `INSERT INTO ai_messages (thread_id, role, body, kind, attachments, engine, created_at) VALUES ($1, 'ai', $2, $3, $4, 'rules', $5)`,
      [thread.id, reply.text, reply.kind, JSON.stringify({ plan: reply.plan, follow: reply.follow, sources: reply.sources, actions: reply.actions }), new Date(at.getTime() + 2000)])
    history.push({ role: 'user', body: text }, { role: 'ai', body: reply.text })
  }
  await pool.query('UPDATE ai_threads SET updated_at = $2 WHERE id = $1', [thread.id, new Date(started.getTime() + 122_000)])
}

function addDaysTime(date, days) {
  return new Date(date.getTime() + days * 86_400_000)
}

export async function resetDemo(options) {
  await migrate({ reset: true, log: () => {} })
  await seed(options)
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  if (config.isProd) {
    console.error('Refusing to seed demo data with NODE_ENV=production.')
    process.exit(1)
  }
  migrate()
    .then(() => seed())
    .then(() => pool.end())
    .catch((err) => {
      console.error(err.message)
      process.exitCode = 1
      return pool.end()
    })
}
