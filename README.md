## Non-commercial use only, see LICENSE.

This tool allows users to control the mouse cursor, perform scrolling actions, and interact with desktop elements using hand gestures detected via a webcam.

## Dependencies:
You can use pip for all dependencies.
* python 3.11
* pip install opencv-python
* pip install numpy
* pip install opencv-contrib-python
* pip install mediapipe
* pip install pynput
* pip install autopy
* pip install sv-ttk

Only for Windows (optional, for camera names):
* pip install pygrabber

## CLI
# Modes:
* default: Mouse movement, scroll down, scroll up.
* touch: Mouse movement, click (thumb+index), double click (thumb+middle), drag-n-drop (thumb+ring).
* scroll: Scroll down and up only.
* help: Show a help message listing all available CLI commands and modes.
* configuration: Reserved for future settings (not implemented yet).

# Localization:
Use --lang en for English, --lang uk for Ukrainian output.
For example: python main.py help --lang en

## UI
You can start programm with UI mode. Now the UI mode a little bit poor :D
Just use: python main.py or double click on main file.