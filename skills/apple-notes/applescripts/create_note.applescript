on run argv
  set acct to item 1 of argv
  set parentName to item 2 of argv
  set proj to item 3 of argv
  set theStatus to item 4 of argv
  set t to item 5 of argv
  set b to item 6 of argv
  tell application "Notes"
    try
      set sf to folder theStatus of folder proj of folder parentName of account acct
    on error
      return "ERR:status folder missing: " & theStatus & " in " & proj & " (run: apple-notes init " & proj & ")"
    end try
    make new note at sf with properties {body:"<div>" & t & "</div>" & b}
  end tell
  return "OK"
end run
