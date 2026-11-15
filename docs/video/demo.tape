# The terminal part of the demo video: bin/switchboard --demo over the bundled sample data.
# Run it from docs/video (see README.md): `vhs demo.tape` writes out/terminal.mp4.
#
# The footage is recorded at twice the size it is shown (3600x1760, shown at 1800x880) so
# that the camera zooms in the video stay sharp. 15 frames per second on purpose: at 30, VHS
# dropped frames (even at 1920x930) and the MP4 came out shorter than the tape's real time,
# which shifts every beat that schedule.py cuts. `python3 check.py footage` measures it.
#
# The comments below say what each part shows, not when: `python3 check.py live` prints the
# time at which every change shows up in out/terminal.mp4, and BEATS in schedule.py are cut at
# those times. A Sleep here does not end where a sum of the Sleeps says: each key adds the
# typing delay, and in the footage a key shows about 0.1 s before that sum.
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

# The list: every machine, blocked first.
Sleep 3.5s

# Moving changes the live preview.
Down
Sleep 1.3s
Down
Sleep 2.7s

# The demo's timeline turns a working agent into done while the popup is open, with no key:
# 8 s after the demo starts, about 7.3 s into the footage.
Sleep 4.3s

# Type to filter by machine, then narrow to one pane.
Type "workstation"
Sleep 1.6s
Type " landing"
Sleep 1.4s

# ctrl-y copies the agent's last reply.
Ctrl+Y
Sleep 3.3s

# The same screen while the caption and the narration say what Enter does. No key is sent:
# the video tells what Enter does, it does not show it. The install line is on the end card,
# which the composition draws.
Sleep 5.2s

Hide
Escape
Sleep 1.5s
