import autopy
from pynput.mouse import Controller
import numpy as np

class MouseController:
    def __init__(self, frame_width, frame_height, smoothing=7):
        self.pynput_mouse = Controller()
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.smoothing = smoothing
        
        self.screen_width, self.screen_height = autopy.screen.size()
        
        self.prev_x = 0
        self.prev_y = 0
        
        self.margin = 100
        
        self.is_dragging = False
        
    def convert_coordinates(self, x, y):
        x_clamped = np.clip(x, self.margin, self.frame_width - self.margin)
        y_clamped = np.clip(y, self.margin, self.frame_height - self.margin)
        
        x_normalized = (x_clamped - self.margin) / (self.frame_width - 2 * self.margin)
        y_normalized = (y_clamped - self.margin) / (self.frame_height - 2 * self.margin)
        
        screen_x = int(x_normalized * self.screen_width)
        screen_y = int(y_normalized * self.screen_height)
        
        return screen_x, screen_y
    
    def smooth_move(self, x, y):
        screen_x, screen_y = self.convert_coordinates(x, y)
        
        smooth_x = self.prev_x + (screen_x - self.prev_x) / self.smoothing
        smooth_y = self.prev_y + (screen_y - self.prev_y) / self.smoothing
        
        self.prev_x = smooth_x
        self.prev_y = smooth_y
        
        try:
            autopy.mouse.move(int(smooth_x), int(smooth_y))
        except Exception as e:
            print(f"Mouse moving error: {e}")
    
    def click(self, button='left'):
        try:
            if button == 'left':
                autopy.mouse.click()
            elif button == 'right':
                autopy.mouse.click(autopy.mouse.Button.RIGHT)
        except Exception as e:
            print(f"Click error: {e}")
    
    def double_click(self):
        try:
            autopy.mouse.click()
            autopy.mouse.click()
        except Exception as e:
            print(f"Double click error: {e}")
    
    def toggle_drag(self, start=True):
        try:
            if start and not self.is_dragging:
                autopy.mouse.toggle(down=True)
                self.is_dragging = True
            elif not start and self.is_dragging:
                autopy.mouse.toggle(down=False)
                self.is_dragging = False
        except Exception as e:
            print(f"Drag error: {e}")
    
    def scroll(self, direction, amount=3):
        try:
            if direction == 'up':
                self.pynput_mouse.scroll(0, amount)
            elif direction == 'down':
                self.pynput_mouse.scroll(0, -amount)
        except Exception as e:
            print(f"Scroll error: {e}")
    
    def get_distance(self, point1, point2):
        x1, y1 = point1
        x2, y2 = point2
        return np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
