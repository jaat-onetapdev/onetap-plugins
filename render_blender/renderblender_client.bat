@echo off

REM Cliente Render 


REM SETEO
SET "PROYECTO_DIR=%USERPROFILE%\Documents\blenderprojs"
SET "SERVIDOR_USUARIO=onetapdev"
SET "SERVIDOR_IP=192.168.0.8"
SET "SERVIDOR_PROYECTO_DIR=/home/onetapdev/proyecto"
SET "ARCHIVO_RENDERIZADO=output/render_final.mp4"
SET "RUTA_LOCAL_SALIDA=%PROYECTO_DIR%\renderizados"

REM CREAR CARPETAS
IF NOT EXIST "%PROYECTO_DIR%" mkdir "%PROYECTO_DIR%"
IF NOT EXIST "%RUTA_LOCAL_SALIDA%" mkdir "%RUTA_LOCAL_SALIDA%"

REM PUSH GIT
cd /d "%PROYECTO_DIR%"
git add .
git commit -m "Auto: backup antes de render"
git push origin main

REM EMPEZAR RENDER
echo Solicitando render al servidor...
ssh %SERVIDOR_USUARIO%@%SERVIDOR_IP% "bash -s" < "%PROYECTO_DIR%\render_server.sh"

REM DEVOLVER RESULTADO
echo Descargando...
REM Se asume que tienes SCP disponible en Windows
scp %SERVIDOR_USUARIO%@%SERVIDOR_IP%:%SERVIDOR_PROYECTO_DIR%/%ARCHIVO_RENDERIZADO% "%RUTA_LOCAL_SALIDA%"

echo Render completado y archivo descargado en: %RUTA_LOCAL_SALIDA%
pause

