import vgamepad as vg
import ctypes, ctypes.wintypes
import time
import threading
import queue
from pynput import keyboard

# ── Config ──────────────────────────────────────────────
STEER_RANGE    = 1900   # raw mouse counts
THROTTLE_RANGE = 310    # raw mouse counts
SMOOTHING      = 0.5    # higher = smoother, max 0.99
POLL_RATE      = 0.002  # hz/cycle

KB_W = dict(MAX_POWER=1.0, RAMP_UP=2.5, RAMP_DOWN=4.0, CURVE=1.8)  # throttle
KB_S = dict(MAX_POWER=0.9, RAMP_UP=4.0, RAMP_DOWN=6.0, CURVE=1.4)  # brake
KB_A = dict(MAX_POWER=0.8, RAMP_UP=3.0, RAMP_DOWN=5.0, CURVE=1.6)  # steer left
KB_D = dict(MAX_POWER=0.8, RAMP_UP=3.0, RAMP_DOWN=5.0, CURVE=1.6)  # steer right
# ────────────────────────────────────────────────────────

#gamepad = vg.VX360Gamepad() #idk, i just use DS4 cuz it got longer name i guess
gamepad = vg.VDS4Gamepad()

steering_out = 0.0
throttle_out = 0.0
brake_out    = 0.0

virtual_x = 0.0
virtual_y = 0.0

active  = False
running = True

delta_queue = queue.Queue()

keys_held = {'w': False, 's': False, 'a': False, 'd': False}
kb_ramp   = {'w': 0.0,   's': 0.0,   'a': 0.0,   'd': 0.0}

# ── Raw Input structs ────────────────────────────────────
class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [("usUsagePage", ctypes.c_ushort),
                ("usUsage",     ctypes.c_ushort),
                ("dwFlags",     ctypes.c_ulong),
                ("hwndTarget",  ctypes.wintypes.HWND)]

class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [("dwType",  ctypes.c_ulong),
                ("dwSize",  ctypes.c_ulong),
                ("hDevice", ctypes.wintypes.HANDLE),
                ("wParam",  ctypes.wintypes.WPARAM)]

class _BUTTONS_STRUCT(ctypes.Structure):
    _fields_ = [("usButtonFlags", ctypes.c_ushort),
                ("usButtonData",  ctypes.c_ushort)]

class _BUTTONS_UNION(ctypes.Union):
    _fields_ = [("ulButtons",     ctypes.c_ulong),
                ("_buttonStruct", _BUTTONS_STRUCT)]

class RAWMOUSE(ctypes.Structure):
    _fields_ = [("usFlags",            ctypes.c_ushort),
                ("_buttons",           _BUTTONS_UNION),
                ("ulRawButtons",       ctypes.c_ulong),
                ("lLastX",             ctypes.c_long),
                ("lLastY",             ctypes.c_long),
                ("ulExtraInformation", ctypes.c_ulong)]

class RAWINPUT(ctypes.Structure):
    _fields_ = [("header", RAWINPUTHEADER),
                ("mouse",  RAWMOUSE)]

# ── Raw Input window ─────────────────────────────────────
import win32api, win32con, win32gui

def wnd_proc(hwnd, msg, wparam, lparam):
    global active, virtual_x, virtual_y
    if msg == 0x00FF:  # WM_INPUT
        size = ctypes.c_uint(0)
        ctypes.windll.user32.GetRawInputData(
            lparam, 0x10000003, None,
            ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER))
        buf = (ctypes.c_byte * size.value)()
        ctypes.windll.user32.GetRawInputData(
            lparam, 0x10000003, buf,
            ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER))
        ri = ctypes.cast(buf, ctypes.POINTER(RAWINPUT)).contents
        if ri.header.dwType == 0:  # RIM_TYPEMOUSE
            # movement
            dx = ri.mouse.lLastX
            dy = ri.mouse.lLastY
            if dx != 0 or dy != 0:
                delta_queue.put((dx, dy))
            # middle mouse button toggle
            if ri.mouse._buttons._buttonStruct.usButtonFlags & 0x0010:
                active = not active
                if active:
                    virtual_x = 0.0
                    virtual_y = 0.0
                print(f"Mouse steering: {'ON' if active else 'OFF'}")
    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

def raw_input_window():
    wndclass = win32gui.WNDCLASS()
    wndclass.lpfnWndProc = wnd_proc
    wndclass.lpszClassName = "RawInputWindow"
    win32gui.RegisterClass(wndclass)
    hwnd = win32gui.CreateWindow(
        "RawInputWindow", "", 0, 0, 0, 0, 0,
        win32con.HWND_MESSAGE, None, None, None)
    rid = RAWINPUTDEVICE()
    rid.usUsagePage = 0x01
    rid.usUsage     = 0x02
    rid.dwFlags     = 0x00000100  # RIDEV_INPUTSINK
    rid.hwndTarget  = hwnd
    ctypes.windll.user32.RegisterRawInputDevices(
        ctypes.byref(rid), 1, ctypes.sizeof(rid))
    win32gui.PumpMessages()

# ── Cursor ───────────────────────────────────────────────
def hide_cursor():
    ctypes.windll.user32.SetCursorPos(0, 0)

# ── Helpers ──────────────────────────────────────────────
def lerp(a, b, t):
    return a + (b - a) * t

def apply_curve(value, curve):
    return value ** curve

def update_ramp(key, cfg, dt):
    global kb_ramp
    if keys_held[key]:
        kb_ramp[key] = min(1.0, kb_ramp[key] + cfg['RAMP_UP'] * dt)
    else:
        kb_ramp[key] = max(0.0, kb_ramp[key] - cfg['RAMP_DOWN'] * dt)
    curved = apply_curve(kb_ramp[key], cfg['CURVE'])
    return curved * cfg['MAX_POWER']

# ── Main loop ────────────────────────────────────────────
def main_loop():
    global steering_out, throttle_out, brake_out
    global virtual_x, virtual_y, running

    last_time = time.perf_counter()

    while running:
        now = time.perf_counter()
        dt  = now - last_time
        last_time = now

        if active:
            hide_cursor()

            while not delta_queue.empty():
                dx, dy = delta_queue.get()
                virtual_x = max(-STEER_RANGE,    min(STEER_RANGE,    virtual_x + dx))
                virtual_y = max(-THROTTLE_RANGE, min(THROTTLE_RANGE, virtual_y + dy))

            # mouse: up = throttle (negative y), down = brake (positive y)
            mouse_steer    =  virtual_x / STEER_RANGE
            vertical_norm  =  virtual_y / THROTTLE_RANGE
            mouse_throttle =  max(0.0, -vertical_norm)
            mouse_brake    =  max(0.0,  vertical_norm)

            # keyboard ramps
            kb_throttle = update_ramp('w', KB_W, dt)
            kb_brake    = update_ramp('s', KB_S, dt)
            kb_left     = update_ramp('a', KB_A, dt)
            kb_right    = update_ramp('d', KB_D, dt)

            kb_steer_left  = -kb_left
            kb_steer_right =  kb_right
            kb_steer = kb_steer_left if abs(kb_steer_left) >= abs(kb_steer_right) else kb_steer_right

            # max() combine
            steering_target = mouse_steer if abs(mouse_steer) >= abs(kb_steer) else kb_steer
            throttle_target = max(mouse_throttle, kb_throttle)
            brake_target    = max(mouse_brake,    kb_brake)
            #print(f"vx={virtual_x:.0f} vy={virtual_y:.0f} thr={throttle_target:.2f} brk={brake_target:.2f}")

            steering_out = lerp(steering_out, steering_target, 1.0 - SMOOTHING)
            throttle_out = lerp(throttle_out, throttle_target, 1.0 - SMOOTHING)
            brake_out    = lerp(brake_out,    brake_target,    1.0 - SMOOTHING)

            gamepad.left_joystick_float(x_value_float=float(steering_out), y_value_float=0.0)
            gamepad.right_trigger_float(value_float=float(throttle_out))
            gamepad.left_trigger_float(value_float=float(brake_out))
            gamepad.update()

        time.sleep(POLL_RATE)

# ── Keyboard listener ────────────────────────────────────
# char-based buttons (key.char matches these)
KB_CHAR_BUTTONS = {
    'q': vg.XUSB_BUTTON.XUSB_GAMEPAD_A,   # clutch
    'e': vg.XUSB_BUTTON.XUSB_GAMEPAD_B,   # headlight
}

# special key buttons (pynput Key enum)
KB_SPECIAL_BUTTONS = {
    keyboard.Key.space: vg.XUSB_BUTTON.XUSB_GAMEPAD_X,        # handbrake
    keyboard.Key.tab:   vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,        # camera
    keyboard.Key.shift_l: vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,  # gear up
    keyboard.Key.ctrl_l:  vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,   # gear down
}

WASD_MAP = {'w': 'w', 's': 's', 'a': 'a', 'd': 'd'}

def on_press(key):
    global running
    # char keys
    try:
        ch = key.char.lower() if hasattr(key, 'char') and key.char else None
        if ch in WASD_MAP:
            keys_held[ch] = True
            return
        if ch in KB_CHAR_BUTTONS:
            gamepad.press_button(button=KB_CHAR_BUTTONS[ch])
            gamepad.update()
            return
    except AttributeError:
        pass
    # special keys
    if key in KB_SPECIAL_BUTTONS:
        gamepad.press_button(button=KB_SPECIAL_BUTTONS[key])
        gamepad.update()
        return
    if key == keyboard.Key.shift_r:
        running = False
        return False

def on_release(key):
    try:
        ch = key.char.lower() if hasattr(key, 'char') and key.char else None
        if ch in WASD_MAP:
            keys_held[ch] = False
            return
        if ch in KB_CHAR_BUTTONS:
            gamepad.release_button(button=KB_CHAR_BUTTONS[ch])
            gamepad.update()
            return
    except AttributeError:
        pass
    if key in KB_SPECIAL_BUTTONS:
        gamepad.release_button(button=KB_SPECIAL_BUTTONS[key])
        gamepad.update()

print("─────────────────────────────────────")
print(" ")
print("  Mid Click → toggle ON/OFF")
print("  WASD      → throttle / brake / steer")
print("  Q         → clutch")
print("  Space     → handbrake")
print("  Tab       → camera")
print("  E         → headlight")
print("  L.Shift   → gear up")
print("  L.Ctrl    → gear down")
print("  R.Shift   → quit")
print(" ")
print("────── Made By SmiCondctr5200 ──────")

threading.Thread(target=raw_input_window, daemon=True).start()
threading.Thread(target=main_loop, daemon=True).start()

kl = keyboard.Listener(on_press=on_press, on_release=on_release)
kl.start()
kl.join()
running = False
