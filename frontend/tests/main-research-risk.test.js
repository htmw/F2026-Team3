import test from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { createServer } from 'vite'
import { JSDOM } from 'jsdom'
import { createRequire } from 'node:module'

function renderingRuntime() {
  const require = createRequire(path.resolve(process.env.ACADMATE_MAIN_SNAPSHOT, 'frontend/package.json'))
  const React = require('react')
  return { React, act: React.act, createRoot: require('react-dom/client').createRoot }
}

// Opt-in requires the isolated main API and Vite proxy. No production source or credentials.
test('main advisor panel renders every enrollment and automatically loaded current-snapshot results', {skip:process.env.RUN_MAIN_RISK_UI_TEST !== 'true'}, async () => {
  const { React, act, createRoot } = renderingRuntime()
  const studentId = Number(process.env.MAIN_DEMO_STUDENT_ID || 101)
  const expectedName = process.env.MAIN_DEMO_STUDENT_NAME || 'Amara Okafor'
  const base = process.env.MAIN_RISK_FRONTEND_URL || 'http://127.0.0.1:5177'
  const original = globalThis.fetch
  const login = await original(base+'/api/v1/auth/login', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({email:process.env.MAIN_DEMO_EMAIL,password:process.env.MAIN_DEMO_PASSWORD})})
  assert.equal(login.status,200)
  const cookie=login.headers.get('set-cookie').split(';')[0]
  const dom=new JSDOM('<!doctype html><html><body></body></html>',{url:base})
  globalThis.window=dom.window;globalThis.document=dom.window.document
  Object.defineProperty(globalThis,'navigator',{value:dom.window.navigator,configurable:true})
  globalThis.HTMLElement=dom.window.HTMLElement;globalThis.IS_REACT_ACT_ENVIRONMENT=true
  const vite=await createServer({root:path.join(process.env.ACADMATE_MAIN_SNAPSHOT,'frontend'),server:{middlewareMode:true,hmr:false},appType:'custom',logLevel:'silent'})
  let root
  try {
    const Component=(await vite.ssrLoadModule('/src/components/research/MainResearchRisk.jsx')).default
    const expectedResponse=await original(base+`/api/v1/advisor/research/students/${studentId}/insights`,{headers:{Cookie:cookie}})
    assert.equal(expectedResponse.status,200)
    const expected=await expectedResponse.json();assert.equal(expected.name,expectedName);assert.equal(expected.student_id,studentId)
    globalThis.fetch=(url,options={})=>original(new URL(url,base),{...options,headers:{...options.headers,Cookie:cookie}})
    const host=document.createElement('div');document.body.append(host);root=createRoot(host)
    await act(async()=>root.render(React.createElement(Component,{studentId})))
    async function wait(predicate){for(let i=0;i<500;i++){await act(async()=>new Promise(r=>setTimeout(r,30)));if(predicate())return}throw new Error('Panel did not settle')}
    await wait(()=>host.querySelectorAll('article').length===expected.enrollments.length)
    assert.ok(expected.enrollments.length>expected.active_enrollments.length)
    assert.match(host.textContent,/synthetic learning activity/i)
    assert.match(host.textContent,/failure or withdrawal/i)
    assert.match(host.textContent,/OULAD/)
    const history=[...host.querySelectorAll('details')].find(d=>d.querySelector('summary')?.textContent.startsWith('Historical enrollments'))
    assert.ok(history);assert.equal(history.open,false)
    assert.match(host.querySelector('article').textContent,/In progress/)
    assert.doesNotMatch(host.textContent,/in_progress/)
    const buttons=()=>[...host.querySelectorAll('button')]
    await wait(()=>host.querySelectorAll('article').length>0 && !host.textContent.includes('Loading assessment') && !host.textContent.includes('Updating'))
    assert.match(host.textContent,/Estimated risk/i);assert.match(host.textContent,/Course ended/)
    assert.doesNotMatch(host.textContent,/Request failed/)
    assert.doesNotMatch(host.textContent,/T23:59:59/)
    assert.doesNotMatch(host.textContent,/Assessed through|Assessment date|Choose another|2026-10-01/)
    assert.equal(host.querySelector('input[type=date]'),null)
    assert.match(host.textContent,/outstanding|rather than proof|reassuring parts|Resource-use counts/)
    assert.doesNotMatch(host.textContent,/research|What influenced this estimate/)
    assert.doesNotMatch(host.textContent,/SHAP|log-odds|raw model score|reference day|Supporting data and source coverage|day-28 replay|All contributions and reference/)
    console.log('Main live panel:',expected.enrollments.length,'enrollments; automatic assessment verified')
  } finally {
    if(root)await act(async()=>root.unmount())
    globalThis.fetch=original;await vite.close();dom.window.close()
  }
})


test('panel preserves zero, incomplete-data reasons and partial failures without technical clutter', {skip:!process.env.ACADMATE_MAIN_SNAPSHOT}, async () => {
  const { React, act, createRoot } = renderingRuntime()
  const original=globalThis.fetch
  const dom=new JSDOM('<!doctype html><html><body></body></html>',{url:'http://localhost/'})
  globalThis.window=dom.window;globalThis.document=dom.window.document
  Object.defineProperty(globalThis,'navigator',{value:dom.window.navigator,configurable:true})
  globalThis.HTMLElement=dom.window.HTMLElement;globalThis.IS_REACT_ACT_ENVIRONMENT=true
  const vite=await createServer({root:path.join(process.env.ACADMATE_MAIN_SNAPSHOT,'frontend'),server:{middlewareMode:true,hmr:false},appType:'custom',logLevel:'silent'})
  let root
  const enrollments=[{enrollment_id:1,course_code:'CS1',term:'Fall',status:'in_progress',starts_at:'2026-08-24T00:00:00Z'},
                     {enrollment_id:2,course_code:'CS2',term:'Fall',status:'completed',starts_at:'2026-08-24T00:00:00Z'},
                     {enrollment_id:3,course_code:'CS3',term:'Fall',status:'in_progress',starts_at:'2026-08-24T00:00:00Z'}]
  let first=true;let explanationAvailable=true;let wrongSnapshot=false
  const timerDelays=[];const interval=window.setInterval.bind(window)
  window.setInterval=(fn,delay)=>{timerDelays.push(delay);return interval(fn,delay)}
  const assessmentUrls=[]
  globalThis.fetch=async url=>{
    if(url.includes('/insights')){
      if(first){first=false;return {ok:false,status:503,json:async()=>({error:{message:'Unavailable for test'}})}}
      return {ok:true,json:async()=>({demo_cutoff:'2026-10-01T23:59:59.999999Z',enrollments})}
    }
    assessmentUrls.push(url)
    if(url.includes('/enrollments/2/'))return {ok:false,status:503,json:async()=>({error:{message:'Course request failed'}})}
    const incomplete=url.includes('/enrollments/3/')
    return {ok:true,json:async()=>({status:incomplete?'unavailable':'scored_research_demo',research_risk_probability:incomplete?null:0,
      reason:incomplete?'Incomplete source coverage: activity':null,
      evidence:{clicks_7d:incomplete?null:0,active_days_7d:incomplete?null:0,assessments_due:0,submissions:0,overdue_assignments:null,assessment_completion_rate:null,late_submission_rate:null},
      explanation:explanationAvailable?{status:'available',background_reference:{prediction_day:38,reference_day:35,actual_size:128},baseline_raw_log_odds:0,raw_log_odds:0,contributions:[{feature:'overdue_assessments',raw_log_odds_contribution:.2},{feature:'clicks_7d',raw_log_odds_contribution:-.2}]}:{status:'unavailable'},
      coverage:{activity:{complete:!incomplete},submissions:{complete:true}},cutoff:wrongSnapshot?'2026-09-30T23:59:59.999999Z':'2026-10-01T23:59:59.999999Z',as_of_day:38,model_version:'final-experiment-v1',calibration_method:'sigmoid'})}
  }
  try{
    const Component=(await vite.ssrLoadModule('/src/components/research/MainResearchRisk.jsx')).default
    const host=document.createElement('div');document.body.append(host);root=createRoot(host)
    await act(async()=>root.render(React.createElement(Component,{studentId:101})))
    async function wait(predicate){for(let i=0;i<80;i++){await act(async()=>new Promise(r=>setTimeout(r,20)));if(predicate())return}throw new Error('Panel did not settle')}
    await wait(()=>host.textContent.includes('Please try again'))
    await act(async()=>[...host.querySelectorAll('button')].find(b=>b.textContent==='Refresh assessment').click())
    await wait(()=>host.querySelectorAll('article').length===3)
    assert.equal(host.querySelector('article h3').textContent,'CS1 \u00b7 Fall')
    assert.equal(host.querySelectorAll('article')[1].querySelector('h3').textContent,'CS3 \u00b7 Fall')
    await wait(()=>!host.textContent.includes('Updating'))
    const cards=[...host.querySelectorAll('article')]
    assert.match(cards[0].textContent,/0.0%/)
    assert.match(cards[1].textContent,/Assessment unavailable/)
    assert.match(cards[1].textContent,/A current assessment is not available/)
    assert.doesNotMatch(cards[1].textContent,/0.0%/)
    assert.match(cards[2].textContent,/Course ended/)
    assert.doesNotMatch(host.textContent,/NaN|Invalid Date/)
    assert.match(cards[0].textContent,/failure or withdrawal/i)
    assert.match(cards[0].textContent,/Missing records affect this assessment/)
    assert.match(cards[0].textContent,/missing information is not reassuring evidence/)
    assert.doesNotMatch(host.textContent,/SHAP|log-odds|raw model score|Supporting data and source coverage|day-28 replay|[+-]0\.200/)
    assert.match(cards[0].textContent,/Information about overdue assessments is missing/)
    assert.match(cards[0].textContent,/information about learning-resource activity over the past week is missing/i)
    explanationAvailable=false
    await act(async()=>[...host.querySelectorAll('button')].find(b=>b.textContent==='Refresh assessment').click())
    await wait(()=>!host.textContent.includes('Updating'))
    assert.match(host.querySelector('article').textContent,/0.0%/)
    assert.match(host.querySelector('article').textContent,/An explanation is not available for this assessment/)
    assert.ok(timerDelays.length>0 && timerDelays.every(delay=>delay===12*60*60*1000))
    assert.ok(assessmentUrls.some(url=>url.includes('force_refresh=true')))
    await act(async()=>window.dispatchEvent(new window.Event('offline')))
    assert.doesNotMatch(host.textContent,/0.0%/)
    assert.match(host.textContent,/A current assessment is not available/)
    wrongSnapshot=true
    await act(async()=>window.dispatchEvent(new window.Event('online')))
    await wait(()=>!host.textContent.includes('Updating'))
    assert.doesNotMatch(host.textContent,/0.0%/)
    assert.match(host.querySelector('article').textContent,/Assessment unavailable/)
    // Moving to another student clears the old student's view before new data arrives.
    let release
    globalThis.fetch=()=>new Promise(resolve=>{release=resolve})
    await act(async()=>root.render(React.createElement(Component,{studentId:999})))
    assert.equal(host.querySelectorAll('article').length,0)
    assert.match(host.textContent,/Loading current assessments/)

  }finally{
    if(root)await act(async()=>root.unmount())
    globalThis.fetch=original;await vite.close();dom.window.close()
  }
})

// Test narrative fidelity: observed values, unusual signs, missing inputs, and no causal claims.
test('course narrative follows observed facts and actual model directions', {skip:!process.env.ACADMATE_MAIN_SNAPSHOT}, async () => {
  const vite=await createServer({root:path.join(process.env.ACADMATE_MAIN_SNAPSHOT,'frontend'),server:{middlewareMode:true,hmr:false},appType:'custom',logLevel:'silent'})
  try {
    const {explanationParagraph,orderActiveEnrollments}=await vite.ssrLoadModule('/src/components/research/MainResearchRisk.jsx')
    const text=explanationParagraph({status:'available',contributions:[
      {feature:'overdue_assessments',input_value:1,raw_log_odds_contribution:.4},
      {feature:'late_submission_rate',input_value:0,raw_log_odds_contribution:-.3},
      {feature:'clicks_7d',input_value:20,raw_log_odds_contribution:.1}]})
    assert.match(text,/1 assessment was overdue/)
    assert.match(text,/Alongside this, none of the observed submissions were late/)
    assert.doesNotMatch(text,/20|SHAP|log-odds|caused|will improve|pushed the|higher estimate|lower estimate/)
    assert.match(text,/what is getting in the way of completing the overdue work/)
    assert.match(text,/assessment still outstanding/)
    assert.match(explanationParagraph({status:'available',contributions:[{feature:'active_days_7d',input_value:1,raw_log_odds_contribution:.2}]}),/on 1 day over the past week/)
    assert.match(explanationParagraph({status:'available',contributions:[{feature:'overdue_assessments',input_value:null,raw_log_odds_contribution:.2}]}),/is missing/)
    assert.equal(explanationParagraph({status:'available',contributions:[]}), 'No individual factor stood out in this assessment.')
    assert.match(explanationParagraph(null),/not available/)
    assert.match(explanationParagraph({status:'available',contributions:[{feature:'clicks_28d',input_value:530,raw_log_odds_contribution:.2}]}),/does not mean that using learning resources is harmful/)
    const contextual=explanationParagraph({status:'available',contributions:[
      {feature:'assessments_due',input_value:5,raw_log_odds_contribution:-2},
      {feature:'overdue_assessments',input_value:4,raw_log_odds_contribution:.8},
      {feature:'active_days_7d',input_value:3,raw_log_odds_contribution:-.1}]})
    assert.match(contextual,/4 assessments were overdue/)
    assert.match(contextual,/on 3 days over the past week/)
    assert.doesNotMatch(contextual,/reached.*deadline/)
    const onlyTiming=explanationParagraph({status:'available',contributions:[{feature:'course_progress',input_value:.4,raw_log_odds_contribution:-.3}]})
    assert.match(onlyTiming,/No clear learning-activity or submission explanation/)
    assert.doesNotMatch(onlyTiming,/lower estimate/)
    const lowConcern=explanationParagraph({status:'available',contributions:[
      {feature:'late_submission_rate',input_value:0,raw_log_odds_contribution:-.36},
      {feature:'active_days_28d',input_value:19,raw_log_odds_contribution:-.33},
      {feature:'clicks_28d',input_value:530,raw_log_odds_contribution:.02}]})
    assert.match(lowConcern,/None of the observed submissions were late/)
    assert.match(lowConcern,/on 19 days/)
    assert.doesNotMatch(lowConcern,/530|concern highlighted here|useful next step|check-in/)
    assert.match(lowConcern,/do not guarantee a successful outcome/)
    const limitedActivity=explanationParagraph({status:'available',contributions:[
      {feature:'overdue_assessments',input_value:3,raw_log_odds_contribution:1.5},
      {feature:'active_days_28d',input_value:4,raw_log_odds_contribution:.46},
      {feature:'late_submission_rate',input_value:0,raw_log_odds_contribution:-.36}]})
    assert.match(limitedActivity,/3 assessments were overdue, and learning activity was recorded on 4 days/)
    assert.doesNotMatch(limitedActivity,/declining|disengaged|reassur|Alongside this/)
    const resourceOnly=explanationParagraph({status:'available',contributions:[
      {feature:'active_days_28d',input_value:24,raw_log_odds_contribution:-.6},
      {feature:'clicks_28d',input_value:948,raw_log_odds_contribution:.3}]})
    assert.match(resourceOnly,/on 24 days/)
    assert.match(resourceOnly,/Resource-use counts point the other way/)
    assert.doesNotMatch(resourceOnly,/concern highlighted|need follow-up|overdue|948/)
    const submissionCounts=explanationParagraph({status:'available',contributions:[
      {feature:'late_submission_rate',input_value:1,raw_log_odds_contribution:.8},
      {feature:'overdue_assessments',input_value:1,raw_log_odds_contribution:.4}]}, {received_submissions:3,late_submissions:3})
    assert.match(submissionCounts,/All 3 received submissions were late/)
    assert.match(submissionCounts,/Both late submissions and outstanding work/)
    assert.doesNotMatch(submissionCounts,/100%|main concern/)
    const inconsistentCounts=explanationParagraph({status:'available',contributions:[
      {feature:'late_submission_rate',input_value:.5,raw_log_odds_contribution:.8}]}, {received_submissions:2,late_submissions:2})
    assert.match(inconsistentCounts,/50%/)
    assert.doesNotMatch(inconsistentCounts,/All 2/)
    const recent=explanationParagraph({status:'available',contributions:[
      {feature:'days_since_submission',input_value:0,raw_log_odds_contribution:-.3}]})
    assert.match(recent,/on the day covered by this assessment/)
    assert.doesNotMatch(recent,/0 days earlier/)
    const change=explanationParagraph({status:'available',contributions:[
      {feature:'engagement_change',input_value:-100,raw_log_odds_contribution:.3}]})
    assert.match(change,/Fewer.*past week.*previous week/)
    const enrollments=[1,2,3,4].map(enrollment_id=>({enrollment_id,status:'in_progress'}))
    const ordered=orderActiveEnrollments(enrollments,{
      1:{status:'scored_research_demo',research_risk_probability:0},
      2:{status:'unavailable',research_risk_probability:null},
      3:{status:'scored_research_demo',research_risk_probability:.9},
      4:{status:'scored_research_demo',research_risk_probability:.3}})
    assert.deepEqual(ordered.map(e=>e.enrollment_id),[3,4,1,2])
    assert.deepEqual(enrollments.map(e=>e.enrollment_id),[1,2,3,4])

  } finally {await vite.close()}
})
