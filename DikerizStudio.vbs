Option Explicit
Dim sh, fso, dir, pyw, q
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = dir
q = Chr(34)
pyw = dir & "\.venv\Scripts\pythonw.exe"

If fso.FileExists(pyw) And SameText(dir & "\requirements.txt", dir & "\.venv\.requirements.txt") Then
  sh.Run q & pyw & q & " " & q & dir & "\dikeriz_studio.py" & q, 0, False
Else
  sh.Run q & dir & "\DikerizStudio.bat" & q, 1, False
End If

Function ReadAll(p)
  ReadAll = ""
  If fso.FileExists(p) Then
    If fso.GetFile(p).Size > 0 Then ReadAll = fso.OpenTextFile(p, 1).ReadAll
  End If
End Function

Function SameText(a, b)
  SameText = False
  If fso.FileExists(a) And fso.FileExists(b) Then SameText = (ReadAll(a) = ReadAll(b))
End Function
