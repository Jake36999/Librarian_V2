@echo off
REM Use a free local port so stale app or picker processes cannot shadow this launch.
REM If a vault was opened before it relaunches there; otherwise it opens the picker.
resource-librarian app --open --port 0
