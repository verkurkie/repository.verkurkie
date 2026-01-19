@echo off
if @%1 == @ goto usage
git add .
git commit  -m %1
git push -u origin main
goto done
:usage
echo %0 "commit message"
:done
