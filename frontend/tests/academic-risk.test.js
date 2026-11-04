import test, { before, after } from 'node:test'
import assert from 'node:assert/strict'
import { fileURLToPath } from 'node:url'
import { JSDOM } from 'jsdom'
import React, { act } from 'react'
import { createServer } from 'vite'
let vite, Component, createRoot
before(async () => {
  const dom = new JSDOM('<!doctype html><html><body></body></html>', {url:'http://localhost/'})
  globalThis.window=dom.window; globalThis.document=dom.window.document
  Object.defineProperty(globalThis,'navigator',{value:dom.window.navigator,configurable:true})
  globalThis.HTMLElement=dom.window.HTMLElement; globalThis.IS_REACT_ACT_ENVIRONMENT=true
  createRoot=(await import('react-dom/client')).createRoot
  vite=await createServer({root:fileURLToPath(new URL('..',import.meta.url)),server:{middlewareMode:true,hmr:false},appType:'custom',logLevel:'silent'})
  Component=(await vite.ssrLoadModule('/src/pages/advisor/AcademicRisk.jsx')).default
})
after(async()=>{await vite?.close()})
const summary={student_id:10001,name:'Synthetic Example',recorded_gpa:3.2,completed_credits:12,failed_courses:['CS1'],withdrawn_courses:[],gpa_policy:'Policy unconfirmed',active_enrollments:[{enrollment_id:1,course_code:'CS1',term:'Spring 2027'},{enrollment_id:2,course_code:'CS2',term:'Spring 2027'}]}
const prediction={status:'scored_research_demo',research_risk_probability:.42,as_of_day:28,cutoff:'2027-02-08T23:59:59.999999Z',model_version:'final-experiment-v1',coverage:{activity:{complete:true}},evidence:{assessments_due:3,submissions:2,overdue_assignments:1,active_days_7d:4,engagement_change:-10,assessment_completion_rate:2/3,released_scores:[]}}
function api(failure=false){return async path=>{
  if(path.endsWith('/students'))return {ok:true,json:async()=>({students:[{student_id:10001,name:'Synthetic Example'}]})}
  if(path.includes('/insights'))return {ok:true,json:async()=>summary}
  if(path.includes('/enrollments/1/'))return {ok:true,json:async()=>prediction}
  if(failure)return {ok:false,status:503,json:async()=>({error:{message:'Second course unavailable'}})}
  return {ok:true,json:async()=>({...prediction,status:'unavailable',research_risk_probability:null,reason:'Incomplete activity coverage',evidence:{},coverage:{activity:{complete:false}}})}
}}
async function mount(fetcher){
  globalThis.fetch=fetcher
  const host=document.createElement('div');document.body.append(host);const root=createRoot(host)
  await act(async()=>root.render(React.createElement(Component)));return {host,root}
}
async function selectStudent(host){const select=host.querySelector('select');await act(async()=>{select.value='10001';select.dispatchEvent(new window.Event('change',{bubbles:true}))})}
async function cleanup(root,host){await act(async()=>root.unmount());host.remove()}
test('student selection and multiple course scored/unavailable states',async()=>{
  const original=globalThis.fetch;const {host,root}=await mount(api())
  try{
    await selectStudent(host);assert.match(host.textContent,/Active enrollments \(2\)/);assert.match(host.textContent,/3.2/)
    await act(async()=>host.querySelector('button').click())
    for(const expected of [/42.0%/,/Incomplete activity coverage/,/Not scored/,/-10/,/67%/,/Research demonstration only/])assert.match(host.textContent,expected)
    assert.equal(host.querySelectorAll('article').length,2)
  }finally{await cleanup(root,host);globalThis.fetch=original}
})
test('failed course request preserves successful course prediction',async()=>{
  const original=globalThis.fetch;const {host,root}=await mount(api(true))
  try{await selectStudent(host);await act(async()=>host.querySelector('button').click());assert.match(host.textContent,/42.0%/);assert.match(host.querySelector('[role="alert"]').textContent,/Second course unavailable/)}
  finally{await cleanup(root,host);globalThis.fetch=original}
})
test('backend startup error is visible and assessment is disabled',async()=>{
  const original=globalThis.fetch;const {host,root}=await mount(async()=>({ok:false,status:503,json:async()=>({detail:'Database unavailable'})}))
  try{
    assert.match(host.textContent,/Database unavailable/);assert.equal(host.querySelector('button').disabled,true)
    globalThis.fetch=api()
    const retry=Array.from(host.querySelectorAll('button')).find(b=>b.textContent==='Retry loading students')
    await act(async()=>retry.click())
    assert.match(host.querySelector('select').textContent,/Synthetic Example/)
    assert.doesNotMatch(host.textContent,/Database unavailable/)
  }
  finally{await cleanup(root,host);globalThis.fetch=original}
})

test('live advisor component uses frontend proxy, PostgreSQL and real model for multiple courses', {skip:process.env.RUN_LIVE_ADVISOR_TEST!=='true'}, async()=>{
  const original=globalThis.fetch
  const base='http://127.0.0.1:5175'
  async function get(path){const r=await original(base+'/api/v1/research/database'+path);assert.equal(r.status,200);return r.json()}
  const listing=await get('/students');assert.equal(listing.students.length,100)
  let chosen
  for(const student of listing.students){
    const s=await get(`/students/${student.student_id}/insights`)
    if(s.active_enrollments.length>1){
      const r=await get(`/enrollments/${s.active_enrollments[0].enrollment_id}/risk-assessment?cutoff=2027-02-08T23%3A59%3A59.999999Z`)
      if(r.status==='scored_research_demo'){chosen=s;break}
    }
  }
  assert.ok(chosen,'Need an eligible multiple-course synthetic student')
  async function waitFor(predicate){for(let i=0;i<120;i++){await act(async()=>new Promise(resolve=>setTimeout(resolve,25)));if(predicate())return}throw new Error('Component did not settle')}
  const {host,root}=await mount((path,options)=>original(new URL(path,base),options))
  try{
    await waitFor(()=>host.querySelector('select').options.length===101)
    await act(async()=>{const select=host.querySelector('select');select.value=String(chosen.student_id);select.dispatchEvent(new window.Event('change',{bubbles:true}))})
    await waitFor(()=>host.querySelectorAll('article').length===chosen.active_enrollments.length)
    await act(async()=>host.querySelector('button').click())
    await waitFor(()=>!host.textContent.includes('Assessing')&&!host.textContent.includes('Not requested'))
    assert.match(host.textContent,/%/);assert.match(host.textContent,/final-experiment-v1/)
    assert.match(host.textContent,/Assessment scores are not inputs/)
    assert.equal(host.querySelectorAll('article').length,chosen.active_enrollments.length)
    console.log('Live React/PostgreSQL/model verification:',chosen.student_id,chosen.active_enrollments.length,'courses')
  }finally{await cleanup(root,host);globalThis.fetch=original}
})
