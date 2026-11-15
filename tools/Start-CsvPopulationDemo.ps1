param([switch]$RestartApi)
$ErrorActionPreference='Stop'
$repo=Split-Path $PSScriptRoot -Parent
$snapshot=Join-Path $repo 'ml\outputs\main-integration\8c4b0843368b'
$manifest=Get-Content (Join-Path $snapshot 'csv-population-manifest.json') -Raw | ConvertFrom-Json
if($manifest.state -ne 'complete' -or $manifest.database -ne 'acadmate_risk_csv_sprint2'){throw 'Verified CSV-population database required'}
$apiListener=Get-NetTCPConnection -LocalPort 8004 -State Listen -ErrorAction SilentlyContinue
if($apiListener){
 $apiProcess=Get-CimInstance Win32_Process -Filter "ProcessId=$($apiListener.OwningProcess)"
 if($apiProcess.CommandLine -notlike '*risk_mvp.main_host:app*' -or $apiProcess.CommandLine -notlike '*8004*'){throw 'Unexpected process on port 8004'}
 if($RestartApi){Stop-Process -Id $apiListener.OwningProcess;$apiListener=$null}
}
$env:PYTHONPATH="$snapshot\backend;$repo\backend;$repo\ml\src"
$env:DATABASE_URL='postgresql+psycopg://acadmate_demo@127.0.0.1:55439/acadmate_risk_csv_sprint2'
$env:ACADMATE_RISK_MVP_ENABLED='true'
$env:ACADMATE_TODAY=$manifest.demo_day
$env:SESSION_COOKIE='acadmate_csv_session'
$env:FRONTEND_ORIGIN='http://127.0.0.1:5178'
$env:OMP_NUM_THREADS='2'
$env:PYTHONDONTWRITEBYTECODE='1'
if(-not $apiListener){Start-Process "$snapshot\.venv\Scripts\python.exe" -ArgumentList '-m','uvicorn','risk_mvp.main_host:app','--host','127.0.0.1','--port','8004' -WorkingDirectory "$snapshot\backend" -WindowStyle Hidden -RedirectStandardOutput "$snapshot\api-csv.out.log" -RedirectStandardError "$snapshot\api-csv.err.log"}
$frontListener=Get-NetTCPConnection -LocalPort 5178 -State Listen -ErrorAction SilentlyContinue
if($frontListener){
 $frontProcess=Get-CimInstance Win32_Process -Filter "ProcessId=$($frontListener.OwningProcess)"
 if($frontProcess.CommandLine -notlike '*vite*' -or $frontProcess.CommandLine -notlike '*5178*'){throw 'Unexpected process on port 5178'}
}else{
 $env:API_PROXY_TARGET='http://127.0.0.1:8004';$env:VITE_API_URL='/api/v1'
 Start-Process 'C:\Program Files\nodejs\node.exe' -ArgumentList 'node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5178','--strictPort' -WorkingDirectory "$snapshot\frontend" -WindowStyle Hidden -RedirectStandardOutput "$snapshot\vite-csv.out.log" -RedirectStandardError "$snapshot\vite-csv.err.log"
}
Write-Output 'CSV population demo: http://127.0.0.1:5178 (API 8004). Original demo on 5177/8003 preserved.'
