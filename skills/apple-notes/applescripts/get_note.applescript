on run argv
  set acct to item 1 of argv
  set parentName to item 2 of argv
  set proj to item 3 of argv
  set theStatus to item 4 of argv
  set t to item 5 of argv
  tell application "Notes"
    set sf to folder theStatus of folder proj of folder parentName of account acct
    set matches to (notes of sf whose name is t)
    if (count of matches) = 0 then return "ERR:race condition"
    return body of (item 1 of matches)
  end tell
end run
