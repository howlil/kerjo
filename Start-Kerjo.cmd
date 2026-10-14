@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
  echo Python 3.12+ belum terpasang atau tidak ada di PATH.
  pause
  exit /b 1
)
where npm >nul 2>&1
if errorlevel 1 (
  echo Node.js 22+ dan npm dibutuhkan untuk membangun antarmuka Kerjo.
  pause
  exit /b 1
)

pushd apps\web
if not exist node_modules\.package-lock.json (
  call npm ci
  if errorlevel 1 goto build_error
)
call npm run build
if errorlevel 1 goto build_error
popd

set "PYTHONPATH=apps\api"
echo Menjalankan Kerjo pada http://127.0.0.1:8000
python -c "import webbrowser; from jobhunt.server import create_server; s=create_server('127.0.0.1',8000); webbrowser.open('http://127.0.0.1:8000'); s.serve_forever()"
if errorlevel 1 (
  echo Kerjo gagal dijalankan. Pastikan port 8000 tersedia.
  pause
)
exit /b 0

:build_error
popd
echo Gagal membangun antarmuka Kerjo.
pause
exit /b 1
