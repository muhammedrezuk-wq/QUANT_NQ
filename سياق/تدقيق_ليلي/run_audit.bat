@echo off
setlocal
cd /d C:\Users\NQ\QUANT_NQ
set "STAMP=%~1"
for /f "usebackq tokens=*" %%R in (`powershell -NoProfile -Command "$f='C:\Users\NQ\QUANT_NQ\????\?????_????\_round.txt'; if(Test-Path $f){$n=[int](Get-Content $f)+1}else{$n=1}; if($n -gt 8){$n=8}; Set-Content -Path $f -Value $n -Encoding ascii; $n"`) do set "RND=%%R"
"C:\Users\NQ\QUANT_NQ\vendor\python\runtime\python.exe" "C:\Users\NQ\QUANT_NQ\governance\scripts\night_audit.py" --round %RND%
endlocal