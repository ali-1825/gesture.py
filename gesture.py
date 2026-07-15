import cv2
import mediapipe as mp
import pyautogui
import numpy as np
import math
import webbrowser
import keyboard
import subprocess  # <--- Keyboard open karne ke liye ye add kiya hai
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from comtypes import CLSCTX_ALL

pyautogui.FAILSAFE = False

# ---------- Screen aur Camera Setup ----------
screen_w, screen_h = pyautogui.size()
cap = cv2.VideoCapture(0)
cap.set(3, 640)
cap.set(4, 480)

# ---------- MediaPipe Hands ----------
mp_hands = mp.solutions.hands # type: ignore
hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7, min_tracking_confidence=0.5)
mp_draw = mp.solutions.drawing_utils # pyright: ignore[reportAttributeAccessIssue]

# ---------- Volume Control (Error free) ----------
try:
    speakers = AudioUtilities.GetSpeakers()
    if isinstance(speakers, (list, tuple)):
        device = speakers[0]
    else:
        device = speakers
    
    interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None) # pyright: ignore[reportAttributeAccessIssue, reportOptionalMemberAccess]
    volume = interface.QueryInterface(IAudioEndpointVolume)
    vol_range = volume.GetVolumeRange()
    min_vol, max_vol = vol_range[0], vol_range[1]
    volume_available = True
except Exception as e:
    print(f"Volume Control Error: {e}. Volume gestures will be disabled.")
    volume = None
    min_vol, max_vol = -65, 0
    volume_available = False

# ---------- Flags ----------
left_click_done = False
right_click_done = False
double_click_done = False
alt_tab_triggered = False
desktop_triggered = False
media_triggered = False
chrome_triggered = False
drag_active = False
osk_triggered = False  # <--- Keyboard flag add kiya

# ---------- Mouse Smoothing ----------
prev_mouse_x, prev_mouse_y = screen_w // 2, screen_h // 2
SMOOTHING = 5  # Smoothness: 5 = balance. 7 ya 8 kar do agar aur smooth chahiye.

def get_finger_status(lm_list):
    fingers = []
    # Thumb (Right hand)
    if lm_list[4][0] > lm_list[3][0]:
        fingers.append(1)
    else:
        fingers.append(0)
    # Index, Middle, Ring, Pinky
    tips = [8, 12, 16, 20]
    pips = [6, 10, 14, 18]
    for tip, pip in zip(tips, pips):
        if lm_list[tip][1] < lm_list[pip][1]:
            fingers.append(1)
        else:
            fingers.append(0)
    return fingers

# ---------- Main Loop ----------
while True:
    success, frame = cap.read()
    if not success:
        break

    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb)
    h, w, _ = frame.shape

    gesture_text = "Waiting for hand..."

    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

            lm_list = []
            for id, lm in enumerate(hand_landmarks.landmark):
                cx, cy = int(lm.x * w), int(lm.y * h)
                lm_list.append((cx, cy))

            if len(lm_list) != 0:
                fingers = get_finger_status(lm_list)
                f_thumb, f_index, f_middle, f_ring, f_pinky = fingers

                x4, y4 = lm_list[4]
                x8, y8 = lm_list[8]
                x12, y12 = lm_list[12]
                x16, y16 = lm_list[16]
                x20, y20 = lm_list[20]

                dist_click = math.hypot(x8 - x4, y8 - y4)    # thumb-index
                dist_right = math.hypot(x12 - x4, y12 - y4)  # thumb-middle
                dist_double = math.hypot(x16 - x4, y16 - y4) # thumb-ring
                dist_vol = math.hypot(x20 - x4, y20 - y4)    # thumb-pinky

                # ----- 1. MOUSE MOVE (Sirf Index) -----
                if f_index == 1 and f_middle == 0 and f_ring == 0 and f_pinky == 0:
                    target_x = np.interp(x8, [50, w - 50], [0, screen_w])
                    target_y = np.interp(y8, [50, h - 50], [0, screen_h])
                    mouse_x = prev_mouse_x + (target_x - prev_mouse_x) / SMOOTHING
                    mouse_y = prev_mouse_y + (target_y - prev_mouse_y) / SMOOTHING
                    pyautogui.moveTo(mouse_x, mouse_y)
                    prev_mouse_x, prev_mouse_y = mouse_x, mouse_y
                    gesture_text = "Mouse Move"

                # ----- 2. LEFT CLICK (Thumb + Index Pinch) -----
                if dist_click < 30 and f_index == 1:
                    if not left_click_done:
                        pyautogui.click()
                        left_click_done = True
                        gesture_text = "LEFT CLICK"
                else:
                    left_click_done = False

                # ----- 3. RIGHT CLICK (Thumb + Middle Pinch) -----
                if dist_right < 30 and f_middle == 1:
                    if not right_click_done:
                        pyautogui.rightClick()
                        right_click_done = True
                        gesture_text = "RIGHT CLICK"
                else:
                    right_click_done = False

                # ----- 4. DOUBLE CLICK (Thumb + Ring Pinch) -----
                if dist_double < 30 and f_ring == 1:
                    if not double_click_done:
                        pyautogui.doubleClick()
                        double_click_done = True
                        gesture_text = "DOUBLE CLICK"
                else:
                    double_click_done = False

                # ----- 5. SCROLL (Index + Middle upar) -----
                if f_index == 1 and f_middle == 1 and f_ring == 0 and f_pinky == 0:
                    scroll_y = np.interp(y12, [50, h - 50], [-5, 5])
                    if scroll_y > 2:
                        pyautogui.scroll(-1)
                        gesture_text = "Scroll Down"
                    elif scroll_y < -2:
                        pyautogui.scroll(1)
                        gesture_text = "Scroll Up"

                # ----- 6. ALT+TAB (Teen ungli: Index+Middle+Ring) -----
                if f_index == 1 and f_middle == 1 and f_ring == 1 and f_pinky == 0:
                    if x8 < 200 and not alt_tab_triggered:
                        keyboard.press_and_release('alt+tab')
                        alt_tab_triggered = True
                        gesture_text = "ALT+TAB (Next)"
                    elif x8 > 440 and not alt_tab_triggered:
                        keyboard.press_and_release('alt+shift+tab')
                        alt_tab_triggered = True
                        gesture_text = "ALT+TAB (Previous)"
                    elif 200 <= x8 <= 440:
                        alt_tab_triggered = False
                else:
                    alt_tab_triggered = False

                # ----- 7. SHOW DESKTOP (4 ungliyaan upar, thumb down) -----
                if f_thumb == 0 and f_index == 1 and f_middle == 1 and f_ring == 1 and f_pinky == 1:
                    if not desktop_triggered:
                        keyboard.press_and_release('win+d')
                        desktop_triggered = True
                        gesture_text = "SHOW DESKTOP"
                else:
                    desktop_triggered = False

                # ----- 8. DRAG & DROP (Mukki / Sab band) -----
                if f_thumb == 0 and f_index == 0 and f_middle == 0 and f_ring == 0 and f_pinky == 0:
                    if not drag_active:
                        pyautogui.mouseDown()
                        drag_active = True
                        gesture_text = "DRAG START"
                    else:
                        cx_hand = int(np.mean([lm_list[i][0] for i in range(21)]))
                        cy_hand = int(np.mean([lm_list[i][1] for i in range(21)]))
                        mouse_x = np.interp(cx_hand, [50, w - 50], [0, screen_w])
                        mouse_y = np.interp(cy_hand, [50, h - 50], [0, screen_h])
                        pyautogui.moveTo(mouse_x, mouse_y, duration=0.05)
                        gesture_text = "DRAGGING..."
                else:
                    if drag_active:
                        pyautogui.mouseUp()
                        drag_active = False
                        gesture_text = "DROP"

                # ----- 9. PLAY/PAUSE (Thumbs Up) -----
                if f_thumb == 1 and f_index == 0 and f_middle == 0 and f_ring == 0 and f_pinky == 0:
                    if not media_triggered:
                        keyboard.press_and_release('play/pause media')
                        media_triggered = True
                        gesture_text = "PLAY / PAUSE"
                else:
                    media_triggered = False

                # ----- 10. YOUTUBE (Shaka sign: Thumb + Pinky) -----
                if f_thumb == 1 and f_index == 0 and f_middle == 0 and f_ring == 0 and f_pinky == 1:
                    if not chrome_triggered:
                        webbrowser.open("https://www.youtube.com")
                        chrome_triggered = True
                        gesture_text = "OPENING YOUTUBE"
                else:
                    chrome_triggered = False

                # ----- 11. VOLUME (Thumb + Pinky + Index upar, Middle aur Ring band) -----
                if volume_available and f_thumb == 1 and f_pinky == 1 and f_index == 1 and f_middle == 0 and f_ring == 0:
                    vol_norm = np.interp(dist_vol, [20, 150], [0.0, 1.0])
                    vol_level = min_vol + (max_vol - min_vol) * vol_norm
                    volume.SetMasterVolumeLevel(vol_level, None) # type: ignore
                    gesture_text = f"VOLUME: {int(vol_norm * 100)}%"

                # ----- 12. ON-SCREEN KEYBOARD (Ring + Pinky upar, baaki sab band) -----
                # (Anamika + Chhoti ungli upar karo, baaki sab neeche rakho)
                if f_thumb == 0 and f_index == 0 and f_middle == 0 and f_ring == 1 and f_pinky == 1:
                    if not osk_triggered:
                        subprocess.Popen("osk.exe")  # Windows ka On-Screen Keyboard
                        osk_triggered = True
                        gesture_text = "KEYBOARD OPEN"
                else:
                    osk_triggered = False

    # ---------- Screen par dikhao ----------
    cv2.putText(frame, gesture_text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 3)
    cv2.putText(frame, "Press 'Q' to quit", (50, h - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.imshow("Har Cheez Control", frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()