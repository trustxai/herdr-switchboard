# The terminal part of the demo video: bin/switchboard --demo over the bundled sample data.
# Run it from docs/video (see README.md): `vhs demo.tape` writes out/terminal.mp4.
#
# The footage is recorded at twice the size it is shown (3600x1760, shown at 1800x880) so
# that the camera zooms in the video stay sharp. 15 frames per second on purpose: at 30, VHS
# dropped frames (even at 1920x930) and the MP4 came out shorter than the tape's real time,
# which shifts every beat that schedule.py cuts. `python3 check.py footage` measures it.
Output out/terminal.mp4

Require python3
Require fzf

Set Shell "bash"
Set FontFamily "DejaVu Sans Mono"
Set FontSize 52
Set Width 3600
Set Height 1760
Set Padding 44
Set Theme "TokyoNight"
Set TypingSpeed 85ms
Set Framerate 15
Set CursorBlink false

# Launch off camera, from the root of the repository; the video starts on the loaded popup.
Hide
Type "cd ../.. && clear && python3 bin/switchboard --demo"
Enter
Wait+Screen@20s /18 agents/
Sleep 1.5s
Show

# 0.0  The list: every machine, blocked first.
Sleep 3.5s

# 3.5  Moving changes the live preview.
Down
Sleep 1.3s
Down
Sleep 2.7s

# 7.5  The sample timeline turns a working agent into done while the popup is open.
Sleep 4.3s

# 11.8 Type to filter by machine, then narrow to one pane.
Type "workstation"
Sleep 1.6s
Type " landing"
Sleep 1.4s

# 16.5 ctrl-y copies the agent's last reply.
Ctrl+Y
Sleep 3.3s

# 19.8 Enter and the install line.
Sleep 5.2s

Hide
Escape
Sleep 1.5s
