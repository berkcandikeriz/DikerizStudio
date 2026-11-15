Option Explicit
Dim sh, fso, dir, places, p, lnk, q
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
q = Chr(34)
places = Array(sh.SpecialFolders("Desktop"), sh.SpecialFolders("Programs"))
For Each p In places
  Set lnk = sh.CreateShortcut(p & "\Dikeriz Studio.lnk")
  lnk.TargetPath = sh.ExpandEnvironmentStrings("%SystemRoot%\System32\wscript.exe")
  lnk.Arguments = q & dir & "\DikerizStudio.vbs" & q
  lnk.WorkingDirectory = dir
  lnk.IconLocation = dir & "\assets\dikeriz.ico, 0"
  lnk.Description = "Dikeriz Studio - yatay videodan dikey kisa video"
  lnk.Save
Next
MsgBox "Kisayollar olusturuldu:" & vbCrLf & "- Masaustu" & vbCrLf & "- Baslat menusu" & vbCrLf & vbCrLf & _
       "Programi artik 'Dikeriz Studio' kisayolundan acabilirsin.", vbInformation, "Dikeriz Studio"
