import test from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { readFile } from 'node:fs/promises'
import { createServer } from 'vite'
import { JSDOM } from 'jsdom'
import { createRequire } from 'node:module'

test('student roadmap shows returned feedback and clears it after approval while preserving graduation status', async()=>{
  const snapshot=process.env.ACADMATE_MAIN_SNAPSHOT;assert.ok(snapshot,'Set ACADMATE_MAIN_SNAPSHOT')
  // Render with the same React installation as the team frontend loaded by Vite.
  const require=createRequire(path.resolve(snapshot,'frontend/package.json'))
  const React=require('react')
  const {act}=React
  const {createRoot}=require('react-dom/client')
  const {MemoryRouter}=require('react-router-dom')
  // Version-controlled synthetic API responses; never read saved local demo state.
  const fixture=JSON.parse(await readFile(new URL('./fixtures/plan-feedback.json',import.meta.url),'utf8'))
  const feedback=fixture.plan.terms.find(t=>t.name==='Fall 2027').advisorFeedback
  assert.ok(feedback)
  const dom=new JSDOM('<!doctype html><div id="host"></div>',{url:'http://localhost/student/degree-plan'})
  globalThis.window=dom.window;globalThis.document=dom.window.document
  Object.defineProperty(globalThis,'navigator',{value:dom.window.navigator,configurable:true})
  globalThis.HTMLElement=dom.window.HTMLElement;globalThis.IS_REACT_ACT_ENVIRONMENT=true
  const original=globalThis.fetch
  globalThis.fetch=async url=>{
    const route=new URL(url,'http://localhost').pathname.replace(/^\/api(?:\/v1)?/,'')
    const responses={'/students/me/plan':fixture.plan,'/students/me/degree-audit':fixture.audit,'/students/me/degree-progress':fixture.progress,'/auth/me':{user:{role:'student',initials:'SS'}},'/auth/config':{accent:'#0F766E'},'/users/me/badges':{badges:{}}}
    assert.ok(route in responses,'Unexpected API '+route)
    return new Response(JSON.stringify(responses[route]),{status:200,headers:{'Content-Type':'application/json'}})
  }
  const vite=await createServer({root:path.join(snapshot,'frontend'),server:{middlewareMode:true,hmr:false},appType:'custom',logLevel:'silent'})
  let root
  try{
    const Page=(await vite.ssrLoadModule('/src/pages/student/DegreePlan.jsx')).default
    const {AuthProvider}=await vite.ssrLoadModule('/src/auth/AuthContext.jsx')
    const {ToastProvider}=await vite.ssrLoadModule('/src/components/ui/Toast.jsx')
    const host=document.getElementById('host');root=createRoot(host)
    await act(async()=>root.render(React.createElement(MemoryRouter,null,React.createElement(AuthProvider,null,React.createElement(ToastProvider,null,React.createElement(Page))))))
    for(let i=0;i<80&&!host.textContent.includes(feedback);i++)await act(async()=>new Promise(r=>setTimeout(r,15)))
    if(process.env.ACADMATE_EXPECT_DEGREE_PROGRESS==='true'){
      assert.match(host.textContent,/Degree progress/)
      const summary=host.querySelector('[aria-label="Degree summary"]')
      assert.ok(summary)
      assert.match(summary.textContent,/Credits completed21 \/ 30/)
      assert.match(summary.textContent,/9 credits remaining now/)
      assert.match(summary.textContent,/In progress3/)
      assert.match(summary.textContent,/Remaining after this term6/)
      assert.match(summary.textContent,/If you pass your current courses/)
      assert.equal((host.textContent.match(/21 \/ 30/g)||[]).length,1,'Do not repeat the completed-credit summary')
      assert.equal((host.textContent.match(/December 2027/g)||[]).length,1,'Keep the graduation date in its summary tile')
      assert.equal(host.querySelector('[role="progressbar"][aria-label="Expected graduation"]'),null,'A date is not a completion percentage')
      assert.ok(host.textContent.includes(fixture.audit.graduation.estimateNote))
    }
    assert.match(host.textContent,/Changes requested for Fall 2027/)
    assert.ok(host.textContent.includes(feedback))
    assert.match(host.textContent,/December 2027/)
    assert.match(host.textContent,/Plan changes requested/)
    assert.doesNotMatch(host.textContent,/On track/)
    const roadmap=[...host.querySelectorAll('h2')].find(h=>h.textContent==='Semester roadmap').closest('.bg-surface')
    assert.ok(roadmap.textContent.includes(feedback),'Feedback must be beside the roadmap')
    assert.equal([...host.querySelectorAll('button')].find(b=>b.textContent==='Send plan to advisor').disabled,false,'Returned plans must be resubmittable')
    const fall=fixture.plan.terms.find(t=>t.name==='Fall 2027')
    fall.advisorFeedback=null
    for(const c of fall.courses)c.planStatus='Approved'
    for(const group of fixture.audit.groups)for(const item of group.items)if(item.status==='Changes requested')item.status='Approved'
    fixture.audit.graduation.status='On track'
    for(const stat of fixture.audit.stats)if(stat.label==='Expected graduation')stat.note='On track'
    await act(async()=>root.render(React.createElement(MemoryRouter,null,React.createElement(AuthProvider,null,React.createElement(ToastProvider,null,React.createElement(Page,{key:'approved'}))))))
    for(let i=0;i<80&&!host.textContent.includes('Semester roadmap');i++)await act(async()=>new Promise(r=>setTimeout(r,15)))
    assert.ok(!host.textContent.includes(feedback),'Old feedback must not remain current')
    const approvedRoadmap=[...host.querySelectorAll('h2')].find(h=>h.textContent==='Semester roadmap').closest('.bg-surface')
    assert.equal((approvedRoadmap.textContent.match(/Approved/g)||[]).length,2,'Both approved roadmap courses keep their decision label')
    assert.equal([...host.querySelectorAll('button')].find(b=>b.textContent==='Send plan to advisor').disabled,true,'Approved plans must not be submitted again')

  }finally{
    if(root)await act(async()=>root.unmount())
    globalThis.fetch=original;await vite.close();dom.window.close()
  }
})
