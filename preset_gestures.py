import numpy as np
from json_manager import JsonManager
from constants import FINGER_TIPS

class PresetGestures:
    def __init__(
        self,
        landmarks,
        frame_width: int,
        frame_height: int,
        json_manager: JsonManager | None = None
    ):
        self.landmarks = landmarks
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.finger_tips = FINGER_TIPS
        self.json_manager = json_manager or JsonManager()
        gesture_definitions = self.json_manager.load_gestures()
        self.gesture_definitions = {gesture['name']: gesture for gesture in gesture_definitions}

    def detect(self, gesture_name: str) -> bool:
        if gesture_name == "dummy":
            return True
            
        gesture = self.gesture_definitions.get(gesture_name)
        if not gesture:
            return False

        check_type = gesture.get('check')

        if check_type == "touch":
            fingers = gesture["fingers"]
            threshold = gesture["args"].get("distance_threshold", 40)
            if "thumb" not in fingers or len(fingers) != 2:
                return False
            other_finger = [f for f in fingers if f != "thumb"][0]
            distance = self._distance(self.finger_tips['thumb'], self.finger_tips[other_finger])
            return distance < threshold

        if check_type == "group_touch":
            fingers = gesture["fingers"]
            threshold = gesture["args"].get("distance_threshold", 40)
            group_fingers = [f for f in fingers if f != "thumb"]
            return all(
                self._distance(self.finger_tips[f], self.finger_tips['thumb']) < threshold
                for f in group_fingers
            )

        if check_type == "fist_index_up":
            args = gesture["args"]
            if len(self.landmarks) < 21:
                return False
            index_tip_y = self.landmarks[args["tip_ids"][0]][2]
            index_pip_y = self.landmarks[args["pip_ids"][0]][2]
            index_extended = index_tip_y < index_pip_y - args["index_tip_to_pip_offset"]

            folded_status = []
            for tip_id, pip_id in zip(args["fold_ids"], args["pip_ids"][1:]):
                folded_status.append(
                    self.landmarks[tip_id][2] > self.landmarks[pip_id][2] + args["others_folded_offset"]
                )
            others_folded = all(folded_status)
            return index_extended and others_folded

        if check_type == "fist_fingers_up":
            args = gesture["args"]
            if len(self.landmarks) < 21:
                return False
            extended_offset = args.get("extended_offset", 0.03)
            folded_offset = args.get("folded_offset", 0.015)
            for tip_id, pip_id in zip(args["extended_tip_ids"], args["extended_pip_ids"]):
                if self.landmarks[tip_id][2] >= self.landmarks[pip_id][2] - extended_offset:
                    return False
            for tip_id, pip_id in zip(args["folded_tip_ids"], args["folded_pip_ids"]):
                if self.landmarks[tip_id][2] <= self.landmarks[pip_id][2] + folded_offset:
                    return False
            return True

        if check_type == "landmark_distance":
            args = gesture["args"]
            ids = args["landmark_ids"]
            if len(self.landmarks) < 21 or len(ids) < 2:
                return False
            threshold = args.get("distance_threshold", 40)
            return self._distance(ids[0], ids[1]) < threshold

        if check_type == "group_landmark_distance":
            args = gesture["args"]
            ids = args["landmark_ids"]
            if len(self.landmarks) < 21 or len(ids) < 2:
                return False
            threshold = args.get("distance_threshold", 40)
            anchor = ids[0]
            return all(self._distance(anchor, ids[i]) < threshold for i in range(1, len(ids)))

        return False

    def _distance(self, tip1_id: int, tip2_id: int) -> float:
        x1 = int(self.landmarks[tip1_id][1] * self.frame_width)
        y1 = int(self.landmarks[tip1_id][2] * self.frame_height)
        x2 = int(self.landmarks[tip2_id][1] * self.frame_width)
        y2 = int(self.landmarks[tip2_id][2] * self.frame_height)
        return float(np.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2))
