import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { hashPassword, verifyPassword } from '../src/lib/crypto.js'
import { parseCsv, toCsv } from '../src/lib/csv.js'
import { addDays, localDate, localTime, mondayOf, weekday, zonedTime } from '../src/lib/time.js'
import { base32Decode, base32Encode, generateCode, verifyCode } from '../src/lib/totp.js'
import { replyStyle } from '../src/lib/preferences.js'
import { gpa, graduation, taskStatus } from '../src/services/academics.js'
import { matchBlockedTopic } from '../src/services/ai/guard.js'
import { threadTitle } from '../src/services/ai/index.js'
import { classify } from '../src/services/ai/rulesEngine.js'
import { courseCode } from '../src/services/ai/tools.js'

describe('totp', () => {
  it('matches the RFC 6238 SHA-1 test vector', () => {
    const secret = base32Encode(Buffer.from('12345678901234567890'))
    // RFC 6238 Appendix B: T = 59 s -> 94287082 (8 digits); the 6-digit code is the last six.
    assert.equal(generateCode(secret, 59_000), '287082')
    assert.equal(generateCode(secret, 1_111_111_109_000), '081804')
  })
  it('round-trips base32 and tolerates one step of drift', () => {
    const secret = base32Encode(Buffer.from('hello world!'))
    assert.equal(base32Decode(secret).toString(), 'hello world!')
    const now = Date.now()
    assert.ok(verifyCode(secret, generateCode(secret, now - 30_000), now))
    assert.ok(!verifyCode(secret, generateCode(secret, now - 120_000), now))
    assert.ok(!verifyCode(secret, 'abcdef', now))
  })
})

describe('passwords', () => {
  it('hashes with a salt and verifies', async () => {
    const a = await hashPassword('correct horse')
    const b = await hashPassword('correct horse')
    assert.notEqual(a, b)
    assert.ok(await verifyPassword('correct horse', a))
    assert.ok(!(await verifyPassword('wrong', a)))
  })
})

describe('time helpers', () => {
  it('converts wall-clock time in a zone to an instant and back, across DST', () => {
    const summer = zonedTime('2026-07-01', '09:30', 'America/New_York')
    assert.equal(summer.toISOString(), '2026-07-01T13:30:00.000Z')
    const winter = zonedTime('2026-12-01', '09:30', 'America/New_York')
    assert.equal(winter.toISOString(), '2026-12-01T14:30:00.000Z')
    assert.equal(localDate(winter, 'America/New_York'), '2026-12-01')
    assert.equal(localTime(winter, 'America/New_York'), '09:30')
  })
  it('does calendar arithmetic on date strings', () => {
    assert.equal(addDays('2026-12-31', 1), '2027-01-01')
    assert.equal(weekday('2026-10-10'), 'Sat')
    assert.equal(mondayOf('2026-10-11'), '2026-10-05')
  })
})

describe('csv', () => {
  it('parses quoted fields and escapes formulas on export', () => {
    const rows = parseCsv('email,name\r\na@x.edu,"Doe, Jane"\nb@x.edu,"Say ""hi"""\n')
    assert.deepEqual(rows, [{ email: 'a@x.edu', name: 'Doe, Jane' }, { email: 'b@x.edu', name: 'Say "hi"' }])
    assert.equal(toCsv(['a'], [['=SUM(A1)']]), "a\r\n'=SUM(A1)\r\n")
  })
})

describe('academic rules', () => {
  it('computes credit-weighted GPA', () => {
    assert.equal(gpa([{ grade: 'A', credits: 3 }, { grade: 'B', credits: 3 }]), 3.5)
    assert.equal(gpa([{ grade: null, credits: 3 }]), null)
  })
  it('labels deadlines', () => {
    const now = new Date('2026-10-10T12:00:00Z')
    assert.equal(taskStatus({ status: 'Graded', due_at: new Date('2026-10-01') }, now), 'Done')
    assert.equal(taskStatus({ status: 'To do', due_at: new Date('2026-10-11T12:00:00Z') }, now), 'Due soon')
    assert.equal(taskStatus({ status: 'In progress', due_at: new Date('2026-10-30') }, now), 'In progress')
    assert.equal(taskStatus({ status: 'To do', due_at: new Date('2026-10-01') }, now), 'Overdue')
  })
  it('works out graduation from the plan', () => {
    const req = (course_type, required_count) => ({ name: course_type, course_type, required_count })
    const ctx = {
      requirements: [req('Core', 1), req('Capstone', 1)],
      enrollments: [
        { id: 1, course_id: 1, type: 'Core', status: 'completed', credits: 3, ends_on: '2026-05-15' },
        { id: 2, course_id: 2, type: 'Capstone', status: 'planned', credits: 3, ends_on: '2027-05-14', plan_status: 'Pending approval', code: 'CS 691' },
      ],
    }
    assert.deepEqual(
      { label: graduation(ctx).label, confirmed: graduation(ctx).confirmed },
      { label: 'May 2027', confirmed: false })
    ctx.enrollments[1].plan_status = 'Approved'
    assert.equal(graduation(ctx).confirmed, true)
    ctx.enrollments.pop()
    assert.equal(graduation(ctx).label, 'Not planned yet')
  })
})

describe('AI advisor rules', () => {
  const defaults = ['Visa and immigration', 'Mental health', 'Financial aid', 'Grade appeals']
  it('matches blocked topics on whole words', () => {
    assert.equal(matchBlockedTopic('Can I work on OPT after graduating?', defaults), 'Visa and immigration')
    assert.equal(matchBlockedTopic("I'm really stressed about exams", defaults), 'Mental health')
    assert.equal(matchBlockedTopic('Will my scholarship cover this?', defaults), 'Financial aid')
    assert.equal(matchBlockedTopic('How do I appeal my grade in CS 612?', defaults), 'Grade appeals')
    assert.equal(matchBlockedTopic('My advisor said I need one more elective', defaults), null) // "said" is not "aid"
    assert.equal(matchBlockedTopic('What are my options for electives?', defaults), null) // "options" is not "opt"
    assert.equal(matchBlockedTopic('Questions about thesis funding', ['Thesis funding']), 'Thesis funding')
    assert.equal(matchBlockedTopic('anything', []), null)
  })
  it('classifies common questions', () => {
    assert.equal(classify('Am I on track to graduate?'), 'on_track')
    assert.equal(classify('Plan my Spring semester'), 'plan_term')
    assert.equal(classify('Which electives fit my schedule?'), 'electives')
    assert.equal(classify('Compare my elective options'), 'electives')
    assert.equal(classify('What do I still need?'), 'remaining')
    assert.equal(classify('What are the prerequisites for CS 640?'), 'prerequisites')
    assert.equal(classify("What's my GPA?"), 'gpa')
    assert.equal(classify('What is on my calendar tomorrow?'), 'schedule')
    assert.equal(classify('What if I fail a course?'), 'what_if_fail')
    assert.equal(classify('hello'), 'help')
    assert.equal(classify('Tell me a joke about cats'), 'fallback')
  })
  it('reads course codes and builds thread titles', () => {
    assert.equal(courseCode('can I take cs640 next term'), 'CS 640')
    assert.equal(courseCode('MATH-101'), 'MATH 101')
    assert.equal(courseCode('no code here'), null)
    assert.equal(threadTitle('  Am I   on track?  '), 'Am I on track?')
    const long = threadTitle('Could you please compare all of the elective options that fit around my evening work schedule next spring')
    assert.ok(long.length <= 61 && long.endsWith('…'))
  })
  it("prefers the student's reply style over the school's", () => {
    assert.equal(replyStyle({}, 'Balanced'), 'Balanced')
    assert.equal(replyStyle({ aiStyle: 'Detailed' }, 'Concise'), 'Detailed')
    assert.equal(replyStyle(null, undefined), 'Balanced')
  })
})
