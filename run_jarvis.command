' Run Jarvis with no console window
' Double-click this file to start Jarvis

Dim shell, fso, jarvisDir

Set shell = CreateObject("WScript.Shell")
Set fso   = CreateObject("Scripting.FileSystemObject")

' Get the directory where this script lives
jarvisDir = fso.GetParentFolderName(WScript.ScriptFullName)

' Check if setup has been run
If Not fso.FileExists(jarvisDir & "\.venv\Scripts\python.exe") Then
    shell.Popup "Jarvis is not set up yet." & vbCrLf & vbCrLf & _
                "Please run setup.py first:" & vbCrLf & _
                "  python setup.py", _
                0, "Jarvis Setup Required", 64
    WScript.Quit
End If

' Check if Ollama is running, start it if not
On Error Resume Next
shell.Run "ollama serve", 0, False
On Error GoTo 0

WScript.Sleep 1000

' Start Jarvis Python backend (no window)
shell.Run """" & jarvisDir & "\.venv\Scripts\python.exe"" """ & jarvisDir & "\main.py""", 0, False

' Wait for WebSocket bridge
WScript.Sleep 3000

' Start Electron UI
shell.CurrentDirectory = jarvisDir & "\ui"
shell.Run "cmd /c npm start", 0, False