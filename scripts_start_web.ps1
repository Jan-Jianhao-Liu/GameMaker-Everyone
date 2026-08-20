$env:UV_INDEX_URL = "https://mirrors.aliyun.com/pypi/simple/"
Set-Location "H:\Code\Github\GameMaker-Everyone"
$proc = Start-Process -FilePath "D:\Anaconda\Scripts\uv.exe" `
    -ArgumentList "run","uvicorn","web.server:app","--host","127.0.0.1","--port","8080" `
    -WorkingDirectory "H:\Code\Github\GameMaker-Everyone" `
    -WindowStyle Hidden -PassThru
Write-Output "PID=$($proc.Id)"
Start-Sleep -Seconds 12
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8080/api/health" -UseBasicParsing -TimeoutSec 5
    Write-Output "HEALTH_OK=$($r.Content)"
} catch {
    Write-Output "HEALTH_FAIL=$($_.Exception.Message)"
    Write-Output "PROCESS_EXITED=$($proc.HasExited)"
    if ($proc.HasExited) { Write-Output "EXIT_CODE=$($proc.ExitCode)" }
}