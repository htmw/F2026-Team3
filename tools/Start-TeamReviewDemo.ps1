$ErrorActionPreference='Stop'
$repo=Split-Path $PSScriptRoot -Parent
$snapshot=Join-Path $repo 'ml\outputs\main-integration\team-review-9dba938-a0c1930'
$manifest=Get-Content (Join-Path $snapshot 'team-demo-manifest.json') -Raw | ConvertFrom-Json
if($manifest.state -ne 'complete' -or $manifest.database -ne 'acadmate_risk_team_review_sprint2'){throw 'Verified team-review clone required'}
foreach($port in @(8005,5179)){
 if(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue){throw "Port $port already in use; inspect before starting another demo"}
}
$env:PYTHONPATH="$snapshot\backend;$repo\backend;$repo\ml\src"
$env:DATABASE_URL='postgresql+psycopg://acadmate_demo@127.0.0.1:55439/acadmate_risk_team_review_sprint2'
$env:ACADMATE_RISK_MVP_ENABLED='true'
$env:ACADMATE_TODAY=$manifest.demo_day
$env:SESSION_COOKIE='acadmate_team_review_session'
$env:FRONTEND_ORIGIN='http://127.0.0.1:5179'
$env:OMP_NUM_THREADS='2'
$env:PYTHONDONTWRITEBYTECODE='1'
$python=Join-Path $repo 'ml\outputs\handoff-venv-v1\Scripts\python.exe'
if(-not (Test-Path -LiteralPath $python)){throw 'Create the reviewed combined-candidate environment first; see backend/ML_EXPLANATION_SETUP.md'}
Start-Process $python -ArgumentList '-m','uvicorn','risk_mvp.team_host:app','--host','127.0.0.1','--port','8005' -WorkingDirectory "$snapshot\backend" -WindowStyle Hidden -RedirectStandardOutput "$snapshot\api-team.out.log" -RedirectStandardError "$snapshot\api-team.err.log"
$env:API_PROXY_TARGET='http://127.0.0.1:8005';$env:VITE_API_URL='/api/v1'
Start-Process 'C:\Program Files\nodejs\node.exe' -ArgumentList 'node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5179','--strictPort' -WorkingDirectory "$snapshot\frontend" -WindowStyle Hidden -RedirectStandardOutput "$snapshot\vite-team.out.log" -RedirectStandardError "$snapshot\vite-team.err.log"
Write-Output 'Team review demo: http://127.0.0.1:5179 (API 8005). Existing demos/databases preserved.'
