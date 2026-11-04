import test from 'node:test'
import assert from 'node:assert/strict'
import { cutoffTimestamp, formatProbability, requestJSON } from '../src/research/api.js'
test('UTC cutoff and missing versus zero probability', () => {
  assert.equal(cutoffTimestamp('2027-02-08'),'2027-02-08T23:59:59.999999Z')
  assert.throws(() => cutoffTimestamp('bad'))
  assert.equal(formatProbability(null),'Not scored');assert.equal(formatProbability(0),'0.0%')
})
test('API response and error propagation', async () => {
  const original = globalThis.fetch
  try {
    globalThis.fetch = async path => { assert.equal(path,'/api/v1/research/database/students'); return { ok:true,json:async () => ({students:[]}) } }
    assert.deepEqual(await requestJSON('/students'),{students:[]})
    globalThis.fetch = async () => ({ok:false,status:503,json:async () => ({error:{message:'Unavailable'}})})
    await assert.rejects(requestJSON('/students'),/Unavailable/)
    globalThis.fetch = async () => ({ok:true,json:async () => {throw new Error('HTML')}})
    await assert.rejects(requestJSON('/students'),/Invalid API response/)
  } finally { globalThis.fetch = original }
})

test('multi-enrollment assessment preserves successful courses on partial failure', async () => {
  const { assessEnrollments, formatChange } = await import('../src/research/api.js')
  const original = globalThis.fetch
  try {
    globalThis.fetch = async path => path.includes('/1/') ? {ok:true,json:async () => ({status:'scored_research_demo',research_risk_probability:.2})} : {ok:false,status:503,json:async () => ({error:{message:'Missing artifact'}})}
    const results = await assessEnrollments([{enrollment_id:1},{enrollment_id:2}], '2027-02-08')
    assert.equal(results[1].research_risk_probability,.2)
    assert.equal(results[2].status,'request_error');assert.equal(results[2].reason,'Missing artifact')
    assert.equal(formatChange(10),'+10');assert.equal(formatChange(-2),'-2');assert.equal(formatChange(null),'Unknown')
  } finally { globalThis.fetch=original }
})

test('FastAPI validation details become a readable error', async () => {
  const original=globalThis.fetch
  try {
    globalThis.fetch=async()=>({ok:false,status:422,json:async()=>({detail:[{msg:'Invalid cutoff timestamp'}]})})
    await assert.rejects(requestJSON('/enrollments/1/risk-assessment'),/Invalid cutoff timestamp/)
  } finally {globalThis.fetch=original}
})
