FFmpeg Toolkit — Setup Instructions
====================================

REQUIREMENTS
------------
- ffmpeg.exe placed in the SAME folder as FFmpeg_Toolkit.exe
- icon_source.jpg placed in the SAME folder (for the welcome splash image)
  (No Python or other installation required on the target machine.)

Download ffmpeg.exe from: https://ffmpeg.org/download.html
  -> Windows builds -> pick a static build -> extract ffmpeg.exe


HOW TO BUILD THE EXE (developers only)
---------------------------------------
1. Make sure Python 3.9+ is installed and on your PATH.
2. Open a Command Prompt in this folder (where build.bat lives).
3. Run:
       build.bat
4. When it finishes the exe is at:
       dist\FFmpeg_Toolkit.exe


HOW TO RUN
----------
1. Copy FFmpeg_Toolkit.exe to any folder on the target machine.
2. Place ffmpeg.exe in that SAME folder.
3. Place icon_source.jpg in that SAME folder (optional — for welcome splash).
4. Double-click FFmpeg_Toolkit.exe — no installation needed.


NOTES
-----
- Settings are saved as settings.json next to the exe.
- All output files default to the folder of your input file
  unless you configure a default output folder in the app.
