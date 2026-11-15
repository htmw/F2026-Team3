import test from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { createServer } from 'vite'
import { JSDOM } from 'jsdom'
import { createRequire } from 'node:module'

test('approvals preserve disabled prechecks, update counts, and undo a decision', async () => {
  assert.ok(process.env.ACADMATE_MAIN_SNAPSHOT,'Set ACADMATE_MAIN_SNAPSHOT')
  const require=createRequire(path.resolve(process.env.ACADMATE_MAIN_SNAPSHOT,'frontend/package.json'))
  const React=require('react')
  const {act}=React
  const {createRoot}=require('react-dom/client')
  const {MemoryRouter}=require('react-router-dom')
  const dom=new JSDOM('<!doctype html><div id="host"></div>',{url:'http://localhost/advisor/approvals'})
  globalThis.window=dom.window;globalThis.document=dom.window.document
  Object.defineProperty(globalThis,'navigator',{value:dom.window.navigator,configurable:true})
  globalThis.HTMLElement=dom.window.HTMLElement;globalThis.IS_REACT_ACT_ENVIRONMENT=true
  const original=globalThis.fetch
  const rows=[1,2].map(id=>({id,studentId:100+id,name:'Student '+id,firstName:'Student',type:'Course plan',item:'Plan '+id,when:'Today',status:'Pending',ok:true,check:'Ready',lines:[],canUndo:false}))
  let prechecks=false
  rows[0].warnings=["CS706 has no recorded offering in Fall 2027."]
  const calls=[]
  globalThis.fetch=async(url,options={})=>{
    const route=new URL(url,'http://localhost').pathname;calls.push([route,options.method||'GET'])
    let data
    if(route.endsWith('/auth/me'))data={user:{role:'advisor',initials:'SS'}}
    else if(route.endsWith('/auth/config'))data={accent:'#0F766E'}
    else if(route.endsWith('/badges'))data={badges:{approvals:rows.filter(r=>r.status==='Pending').length}}
    else if(route.endsWith('/approve')){rows[0]={...rows[0],status:'Approved',canUndo:true};data=rows[0]}
    else if(route.endsWith('/reopen')){rows[0]={...rows[0],status:'Pending',canUndo:false};data=rows[0]}
    else if(route.endsWith('/approvals')){
      const tab=new URL(url,'http://localhost').searchParams.get('status')||'Pending'
      data={prechecks,tabs:['Pending','Approved','Changes requested'].map(label=>({label,count:rows.filter(r=>r.status===label).length})),rows:rows.filter(r=>r.status===tab)}
    }else if(/approvals\/\d+$/.test(route))data=rows.find(r=>route.endsWith('/'+r.id))
    else throw new Error('Unexpected API request '+route)
    return new Response(JSON.stringify(data),{status:200,headers:{'Content-Type':'application/json'}})
  }
  const vite=await createServer({root:path.join(process.env.ACADMATE_MAIN_SNAPSHOT,'frontend'),server:{middlewareMode:true,hmr:false},appType:'custom',logLevel:'silent'})
  let root
  try{
    const Page=(await vite.ssrLoadModule('/src/pages/advisor/Approvals.jsx')).default
    const {AuthProvider}=await vite.ssrLoadModule('/src/auth/AuthContext.jsx')
    const {ToastProvider}=await vite.ssrLoadModule('/src/components/ui/Toast.jsx')
    const host=document.getElementById('host');root=createRoot(host)
    await act(async()=>root.render(React.createElement(MemoryRouter,{initialEntries:['/advisor/approvals']},React.createElement(AuthProvider,null,React.createElement(ToastProvider,null,React.createElement(Page))))))
    async function wait(fn){for(let i=0;i<80;i++){await act(async()=>new Promise(r=>setTimeout(r,15)));if(fn())return}throw new Error('Page did not settle')}
    const button=text=>[...host.querySelectorAll('button')].find(b=>b.textContent===text)
    await wait(()=>button('Approve'))
    assert.doesNotMatch(host.textContent,/Pre-check passed|Acadmate pre-check/)
    await act(async()=>button('Approve').click())
    await wait(()=>host.querySelector('#request-title')?.textContent==='Plan 2')
    assert.doesNotMatch(host.textContent,/Pre-check passed|Acadmate pre-check/)
    assert.equal(rows.filter(r=>r.status==='Pending').length,1)
    assert.ok(button('Undo'))
    await act(async()=>button('Undo').click())
    await wait(()=>rows[0].status==='Pending'&&host.textContent.includes('Plan 1'))
    assert.doesNotMatch(host.textContent,/Pre-check passed|Acadmate pre-check/)
    assert.ok(calls.some(([url])=>url.endsWith('/1/approve')))
    assert.ok(calls.some(([url])=>url.endsWith('/1/reopen')))
    await act(async()=>[...host.querySelectorAll('button')].find(b=>b.textContent.startsWith('Approved')).click())
    await wait(()=>host.textContent.includes('No approved requests yet'))
    assert.doesNotMatch(host.textContent,/Select a request to see its details/)
    await act(async()=>[...host.querySelectorAll('button')].find(b=>b.textContent.startsWith('Changes requested')).click())
    await wait(()=>host.textContent.includes('No requests returned for changes'))
    prechecks=true
    await act(async()=>[...host.querySelectorAll('button')].find(b=>b.textContent.startsWith('Pending')).click())
    await wait(()=>host.textContent.includes('CS706 has no recorded offering in Fall 2027.'))
    assert.match(host.textContent,/Review warnings/)

    assert.doesNotMatch(host.textContent,/Select a request to see its details/)

  }finally{
    if(root)await act(async()=>root.unmount())
    globalThis.fetch=original;await vite.close();dom.window.close()
  }
})
