@echo off
chcp 65001 >nul
setlocal
set PYTHONUTF8=1
title QUANT_NQ - Inventory (read-only)
echo ==============================================================
echo   QUANT_NQ - JARD AL-NUSKHA (qira'a faqat - read only)
echo   Hat hatha al-malaf dakhl mujallad al-nuskha (jidhr al mashrou3)
echo   w double-click. Nataija: inventory_*.zip bl majallad nafso.
echo   Ma b3ddel wla bams7 ay shi - qira'a 100 ya3ni 100.
echo ==============================================================
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='SilentlyContinue'; $root=(Get-Location).Path; $stamp=Get-Date -Format 'yyyyMMdd_HHmm'; $skip='\\(venv|node_modules|__pycache__|\.git|\.cache|\.pytest_cache|\.venv|\.next)(\\|$)'; Write-Host '[1/4] Jam3 listat al malafat... (bila5ad dakaeq 3ala mashrou3 kabir)'; $all=@(Get-ChildItem -LiteralPath $root -Recurse -File -Force | Where-Object {$_.FullName -notmatch $skip}); $csv=Join-Path $root ('inventory_files_'+$stamp+'.csv'); $all | ForEach-Object { [pscustomobject]@{ Path=$_.FullName.Substring($root.Length+1); Bytes=$_.Length; ModifiedUTC=$_.LastWriteTimeUtc.ToString('yyyy-MM-dd HH:mm:ss') } } | Export-Csv -LiteralPath $csv -NoTypeInformation -Encoding UTF8; Write-Host '[2/4] Malakhas al mujalladat...'; function DirSum($p){ if(Test-Path -LiteralPath $p){ $f=@(Get-ChildItem -LiteralPath $p -Recurse -File -Force); $s=($f|Measure-Object Length -Sum).Sum; if(-not $s){$s=0}; '' + $f.Count + ' files, ' + [math]::Round($s/1MB,1) + ' MB' } else { 'missing' } }; $sum=Join-Path $root ('inventory_summary_'+$stamp+'.txt'); @('ROOT: '+$root, 'Generated: '+(Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), '', ('TOTAL scanned (excl junk): '+$all.Count+' files, '+[math]::Round((($all|Measure-Object Length -Sum).Sum)/1MB,1)+' MB'), ('venv : '+(DirSum (Join-Path $root 'venv'))), ('.git : '+(DirSum (Join-Path $root '.git'))), ('var  : '+(DirSum (Join-Path $root 'var'))), '', '--- Top-level folders (excl junk) ---') | Set-Content -LiteralPath $sum -Encoding UTF8; $tops=@(Get-ChildItem -LiteralPath $root -Directory -Force | Where-Object {$_.Name -notmatch '^(venv|node_modules|\.git|\.cache|__pycache__)$'}); foreach($d in $tops){ $f=@(Get-ChildItem -LiteralPath $d.FullName -Recurse -File -Force); $s=($f|Measure-Object Length -Sum).Sum; if(-not $s){$s=0}; Add-Content -LiteralPath $sum -Value ($d.Name + [char]9 + [string][math]::Round($s/1MB,1) + ' MB' + [char]9 + $f.Count + ' files') }; Write-Host '[3/4] Daghst...'; $zip=Join-Path $root ('inventory_'+$stamp+'.zip'); Compress-Archive -LiteralPath $csv,$sum -DestinationPath $zip -Force; Remove-Item -LiteralPath $csv,$sum -Force; Write-Host '[4/4] KHALAS: '+$zip "
echo.
echo ==============================================================
echo   KHALAS - hath al malaf bl majallad:  inventory_*.zip
echo   Ab3atho ll muhawara (chat).
echo ==============================================================
pause