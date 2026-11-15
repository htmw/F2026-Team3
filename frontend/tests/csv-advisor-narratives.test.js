import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import {createServer} from 'vite'

test('every audited CSV course narrative preserves facts without turning resource counts into an intervention flag', {skip:!process.env.ACADMATE_MAIN_SNAPSHOT}, async()=>{
 const root=path.join(process.env.ACADMATE_MAIN_SNAPSHOT,'frontend')
 const auditDir=process.env.ACADMATE_ADVISOR_AUDIT_DIR ?? process.env.ACADMATE_MAIN_SNAPSHOT
 const vite=await createServer({root,server:{middlewareMode:true,hmr:false},appType:'custom',logLevel:'silent'})
 try{
  const {explanationParagraph}=await vite.ssrLoadModule('/src/components/research/MainResearchRisk.jsx')
  let students=0,courses=0,resourceOnly=0
  for(const id of [201,10200,10201,10202]){
   const audit=JSON.parse(fs.readFileSync(path.join(auditDir,`advisor-${id}-audit.json`),'utf8'))
   assert.equal(audit.passed,true);assert.equal(audit.students,25)
   students+=audit.records.length
   for(const student of audit.records)for(const course of student.courses){
    const text=explanationParagraph(course.explanation,course.evidence)
    assert.ok(text.length>0 && text.length<1300)
    assert.doesNotMatch(text,/undefined|NaN|SHAP|log-odds|pushed the risk|0 days earlier|will fail|will improve/)
    assert.doesNotMatch(text,/(?:^|\.\s+)The student is disengaged\./)
    const chosen=course.explanation.contributions.filter(c=>!['course_day','course_progress','window_days_28d','assessments_due'].includes(c.feature)&&Math.abs(c.raw_log_odds_contribution)>1e-12).sort((a,b)=>Math.abs(b.raw_log_odds_contribution)-Math.abs(a.raw_log_odds_contribution)).slice(0,2)
    const positive=chosen.filter(c=>c.raw_log_odds_contribution>0)
    if(positive.length && positive.every(c=>c.feature.startsWith('clicks_'))){
     assert.match(text,/Resource-use counts point the other way/)
     assert.match(text,/does not mean that using learning resources is harmful/)
     assert.doesNotMatch(text,/concern highlighted|need follow-up|overdue/)
     resourceOnly++
    }
    if(positive.some(c=>c.feature==='overdue_assessments' && c.input_value>0)){
     assert.match(text,/overdue/);if(course.evidence.received_submissions !== 0) assert.match(text,/outstanding/);assert.match(text,/catch-up plan/)
    }
    if(chosen.some(c=>c.feature==='late_submission_rate') && course.evidence.received_submissions>0){
     assert.doesNotMatch(text,/\d+% of the observed submissions/)
     assert.match(text,/received submission/)
    }
    courses++
   }
  }
  assert.equal(students,100);assert.equal(courses,179);assert.ok(resourceOnly>0)
  const none=explanationParagraph({status:'available',contributions:[
    {feature:'overdue_assessments',input_value:4,raw_log_odds_contribution:2},
    {feature:'late_submission_rate',input_value:null,raw_log_odds_contribution:-.4}]},{received_submissions:0,late_submissions:0})
  assert.match(none,/no submissions have been received/i)
  assert.match(none,/catch-up plan/)
  assert.doesNotMatch(none,/Missing records|is missing|reassuring parts/)
  const one=explanationParagraph({status:'available',contributions:[{feature:'late_submission_rate',input_value:0,raw_log_odds_contribution:-.3}]},{received_submissions:1,late_submissions:0})
  assert.match(one,/The received submission was on time/);assert.doesNotMatch(one,/All 1/)
  console.log(`Verified ${students} students, ${courses} real current explanations; ${resourceOnly} resource-count-only counterpoints remain neutral.`)
 }finally{await vite.close()}
})
