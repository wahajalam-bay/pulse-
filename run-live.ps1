# Launch ZD PULSE detached on 127.0.0.1:4010 and leave it running.
$d = "$PSScriptRoot"
$env:PORT = '4010'; $env:MOUNT = '/zd'; $env:HOST = '127.0.0.1'
Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalPort -eq 4010 } |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
$p = Start-Process -FilePath 'python' -ArgumentList 'server.py' -WorkingDirectory $d -RedirectStandardOutput "$d\logs\server.out" -RedirectStandardError "$d\logs\server.err" -WindowStyle Hidden -PassThru
Start-Sleep -Seconds 2
Write-Output "PID=$($p.Id)"
