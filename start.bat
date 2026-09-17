@echo off
cd /d "%~dp0"
if not exist web\dist\index.html (
  echo 正在构建新界面...
  pushd web
  call npm install
  if errorlevel 1 goto :fail
  call npm run build
  if errorlevel 1 goto :fail
  popd
)
echo 正在启动选股服务 http://127.0.0.1:8765/
python server.py
pause
goto :eof
:fail
echo 界面构建失败，请先安装 Node.js，然后在 web 目录执行 npm install 与 npm run build。
pause
