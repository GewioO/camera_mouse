import cv2
import mediapipe as mp
import numpy as np

class HandTracker:
    def __init__(self, max_hands=2, detection_confidence=0.7, tracking_confidence=0.7):
        """
        param max_hands: max hands count
        param detection_confidence: (0-1)
        param tracking_confidence: (0-1)
        """
        self.max_hands = max_hands
        
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            max_num_hands=max_hands,
            min_detection_confidence=detection_confidence,
            min_tracking_confidence=tracking_confidence
        )
        
        self.mp_draw = mp.solutions.drawing_utils
        
    def find_hands(self, frame, draw=True):
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        self.results = self.hands.process(frame_rgb)
        
        if self.results.multi_hand_landmarks and draw:
            for hand_landmarks in self.results.multi_hand_landmarks:
                self.mp_draw.draw_landmarks(
                    frame, 
                    hand_landmarks, 
                    self.mp_hands.HAND_CONNECTIONS
                )
        
        return frame
    
    def get_hand_landmarks(self, hand_index=0):
        if not self.results.multi_hand_landmarks:
            return None
            
        if hand_index >= len(self.results.multi_hand_landmarks):
            return None
            
        hand_landmarks = self.results.multi_hand_landmarks[hand_index]
        landmarks = []
        
        for id, landmark in enumerate(hand_landmarks.landmark):
            landmarks.append((id, landmark.x, landmark.y, landmark.z))
            
        return landmarks
    
    def get_finger_positions(self, frame_width, frame_height, hand_index=0):
        landmarks = self.get_hand_landmarks(hand_index)
        
        if landmarks is None:
            return None
        
        finger_tips = {
            'thumb': 4,      
            'index': 8,      
            'middle': 12,    
            'ring': 16,      
            'pinky': 20      
        }
        
        positions = {}
        for name, tip_id in finger_tips.items():
            landmark = landmarks[tip_id]
            x = int(landmark[1] * frame_width)
            y = int(landmark[2] * frame_height)
            positions[name] = (x, y)
            
        return positions
    
    def get_hand_center(self, frame_width, frame_height, hand_index=0):
        landmarks = self.get_hand_landmarks(hand_index)
        if landmarks is None:
            return None
        xs = [landmark[1] for landmark in landmarks]
        ys = [landmark[2] for landmark in landmarks]
        center_x = int(np.mean(xs) * frame_width)
        center_y = int(np.mean(ys) * frame_height)
        return (center_x, center_y)

    
    def close(self):
        self.hands.close()

    
