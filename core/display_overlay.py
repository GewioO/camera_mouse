import cv2


class DisplayOverlay:
    def __init__(self, scale_controller):
        self.scale_controller = scale_controller
        self.ui_commands = []

    def add_ui_command(self, text, position, color, duration=20):
        self.ui_commands.append({"text": text, "pos": position, "color": color, "frames": duration})

    def draw(self, frame):
        current_scale = self.scale_controller.get()
        cv2.putText(frame, f"ZOOM: {current_scale:.2f}x [+/-]", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.9, (200, 200, 255), 2)
        for cmd in self.ui_commands[:]:
            cv2.putText(frame, cmd["text"], cmd["pos"],
                       cv2.FONT_HERSHEY_SIMPLEX, 1.1, cmd["color"], 3)
            cmd["frames"] -= 1
            if cmd["frames"] <= 0:
                self.ui_commands.remove(cmd)
