FFmpeg Toolkit for Linux
========================

Made for: Linux Mint, Ubuntu, Debian (anything that uses apt).


INSTALL (once)
--------------
1. Copy this whole folder to your home folder, for example:
       /home/yourname/FFmpeg Toolkit
   (Keep everything together. The app saves its settings in this folder.)

2. Open the folder in the file manager, right-click an empty space and choose
   "Open in Terminal". Then run:

       bash install.sh

   It asks for your password, installs ffmpeg and a few Python parts, and adds
   "FFmpeg Toolkit" to the applications menu and the desktop.
   Takes a few minutes. It's safe to run again at any time.


START THE APP
-------------
- Applications menu -> Sound & Video -> FFmpeg Toolkit, or
- double-click the FFmpeg Toolkit icon on the desktop, or
- in a terminal in this folder:   ./run.sh


NEW VERSIONS
------------
Drop the new ffmpeg_toolkit_v….py into this folder. The launcher always runs
the newest version, so nothing else needs changing. You can delete old ones.


DIFFERENCES FROM WINDOWS
------------------------
- The video preview plays in its own window instead of inside the app.
- "Open Log in Text Editor" opens your system's text editor instead of Notepad.
- The folder browser starts at / (the top of the file system) instead of drive letters.


BUILD A LINUX PROGRAM (OPTIONAL)
--------------------------------
Not needed to use the app -- run.sh runs the .py file directly. To make a
single self-contained program instead, in a terminal in this folder:

    .venv/bin/python -m pip install pyinstaller
    sudo apt install -y binutils
    .venv/bin/python -m PyInstaller --noconfirm --onefile --windowed \
        --name ffmpeg_toolkit_v10-0-L --collect-data customtkinter \
        ffmpeg_toolkit_v10-0-L.py

The result is dist/ffmpeg_toolkit_v10-0-L (Linux programs have no .exe).
- It uses the ffmpeg that install.sh installed; ffmpeg isn't bundled inside it.
- A program built on one Mint/Ubuntu version runs on that version and newer,
  so build on the oldest version you want to support.
- The menu and desktop icons still start run.sh, not the built program.


PROBLEMS?
---------
When the app is started from the menu or desktop, any error messages are saved to:
    ~/.cache/ffmpeg-toolkit.log
Start it with ./run.sh in a terminal to see them live instead.


UNINSTALL
---------
Delete this folder, plus:
    ~/.local/share/applications/ffmpeg-toolkit.desktop
    the ffmpeg-toolkit.desktop icon on your desktop
ffmpeg itself can stay (other programs use it), or remove it with:
    sudo apt remove ffmpeg
