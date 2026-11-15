import test from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import {createRequire} from 'node:module'
import {createServer} from 'vite'

test('project-help answers remain plain text without displaying citation links',async()=>{
 const snapshot=process.env.ACADMATE_MAIN_SNAPSHOT
 assert.ok(snapshot,'Set ACADMATE_MAIN_SNAPSHOT')
 const require=createRequire(path.resolve(snapshot,'frontend/package.json'))
 const React=require('react');const {renderToStaticMarkup}=require('react-dom/server')
 const vite=await createServer({root:path.join(snapshot,'frontend'),server:{middlewareMode:true,hmr:false},appType:'custom',logLevel:'silent'})
 try{
  const Message=(await vite.ssrLoadModule('/src/components/ai/AiMessage.jsx')).default
  const citation={documentId:'project-help-plan',title:'Submitting and reviewing a degree plan',version:'1.0',startLine:3,endLine:3,path:'/help/documents/project-help-plan'}
  const html=renderToStaticMarkup(React.createElement(Message,{message:{kind:'answer',text:'Project help',citations:[citation],sources:[]}}))
  assert.match(html,/Project help/)
  assert.doesNotMatch(html,/View guide:|href=|v1.0, lines|Submitting and reviewing/)
  const ordinary=renderToStaticMarkup(React.createElement(Message,{message:{kind:'answer',text:'Existing record answer',sources:['Degree audit']}}))
  assert.match(ordinary,/Existing record answer/);assert.match(ordinary,/Degree audit/);assert.doesNotMatch(ordinary,/View guide:/)
  const unsafe=renderToStaticMarkup(React.createElement(Message,{message:{kind:'answer',text:'Example',citations:[{...citation,documentId:'javascript:alert(1)'}]}}))
  assert.doesNotMatch(unsafe,/href=|javascript:/)
 }finally{await vite.close()}
})
