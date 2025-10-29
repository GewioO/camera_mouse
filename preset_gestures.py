import numpy as np

class PresetGestures:
    def __init__(self, landmarks, frame_width, frame_height, threshold=40):
        """
        landmarks - list cntain 21 cortage (id, x, y, z), mediapipe like
        frame_width, frame_height - for coords to pixels
        threshold - distance between fingers
        """
        self.lm = landmarks
        self.w = frame_width
        self.h = frame_height
        self.th = threshold
        
        self.tips = {
            'thumb': 4,
            'index': 8,
            'middle': 12,
            'ring': 16,
            'pinky': 20
        }
    
    def _distance(self, p1, p2):
        x1 = int(self.lm[p1][1] * self.w)
        y1 = int(self.lm[p1][2] * self.h)
        x2 = int(self.lm[p2][1] * self.w)
        y2 = int(self.lm[p2][2] * self.h)
        return np.sqrt((x1 - x2)**2 + (y1 - y2)**2)
    
    def _group_touch(self, group):
        # group = ['thumb', 'index', ...]
        return all(self._distance(self.tips[f], self.tips['thumb']) < self.th for f in group if f != "thumb")

    # 1. Fist, but index up
    def is_fist_and_index_up(self):
        if not self.lm or len(self.lm) < 21:
            return False
        index_extended = (self.lm[8][2] < self.lm[6][2] - 0.03)
        others = [12, 16, 20]
        others_folded = all(self.lm[tid][2] > self.lm[tid-2][2]+0.015 for tid in others)
        return index_extended and others_folded

    # 2. Thumb + middle + ring
    def is_thumb_middle_ring(self):
        return self._group_touch(['middle', 'ring'])

    # 3. Thumb + index
    def is_thumb_and_index(self):
        return self._group_touch(['index'])

    # 4. Thumb + middle
    def is_thumb_and_middle(self):
        return self._group_touch(['middle'])

    # 5. Thumb + ring
    def is_thumb_and_ring(self):
        return self._group_touch(['ring'])

    # 6. Thumb + pinky
    def is_thumb_and_pinky(self):
        return self._group_touch(['pinky'])

    # 7. Thumb + index + middle
    def is_thumb_index_middle(self):
        return (
            self._group_touch(['index', 'middle'])
        )

    # 8. Thumb + ring + pinky
    def is_thumb_ring_pinky(self):
        return self._group_touch(['ring', 'pinky'])

