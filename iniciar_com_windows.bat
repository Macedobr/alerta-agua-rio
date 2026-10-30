@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set "INICIAR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "ATALHO=%INICIAR%\Alerta Agua RJ.lnk"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('%ATALHO%');" ^
  "$s.TargetPath = '%~dp0run.bat';" ^
  "$s.WorkingDirectory = '%~dp0';" ^
  "$s.WindowStyle = 7;" ^
  "$s.Description = 'Monitor de abastecimento de agua do Rio de Janeiro';" ^
  "$s.Save()"

if exist "%ATALHO%" (
    echo.
    echo  Pronto: o Alerta Agua RJ vai iniciar junto com o Windows.
    echo  Atalho criado em:
    echo    %ATALHO%
    echo.
    echo  Para desfazer, apague esse atalho.
) else (
    echo.
    echo  Nao consegui criar o atalho. Crie manualmente um atalho para run.bat
    echo  em: %INICIAR%
)
echo.
pause
