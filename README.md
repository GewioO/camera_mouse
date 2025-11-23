## Non-commercial use only, see LICENSE.

This tool allows users to control the mouse cursor, perform scrolling actions, and interact with desktop elements using hand gestures detected via a webcam.

## Dependencies:
You can use pip for all dependencies.
* python 3.11
* opencv 4.12.0.88: pip install opencv-python
* pip install numpy
* pip opencv-contrib-python
* pip mediapipe
* pip pynput

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
