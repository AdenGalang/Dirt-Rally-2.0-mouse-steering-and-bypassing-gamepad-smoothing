# Dirt-Rally-2.0-mouse-steering-and-bypassing-gamepad-smoothing
DR2 with mouse steering and bypassing input smoothing
# Requirement
```
python and ViGEm Bus
```
# Dirt Rally 2 gamepad thing
normally gamepad will receive a smoothing and also a bit of assist to keep the car straight etc, which make the wheel feels speed dependent(the faster you go the less the sensitivity applied), while not neccecarily add much of a latency, it can feel really annoying when counter steering with input that in this case weren't actually a gamepad, to fix this you can manually add ViGem's VID and PID into Dirt rally 2's input xml
# Adding your own Input xml
you can nativage to the game root folder and find input folder "DiRT Rally 2.0\input\", within input folder there would be 3 folder actionmaps, devices, and libraries:

<img width="160" height="113" alt="image" src="https://github.com/user-attachments/assets/1c79229c-3886-4115-8f26-704d6c8043a9" />

 you will be focusing on devices and actionmaps folder, inside devices there would be a xml file named device_defines.xml
# Using ViGem script to map mouse axis
  
 Script Usage
 *launch it using CMD*
```
python gameinput.py
```
### Input Logic

This script translates raw mouse/keyboard deltas into a virtual gamepad stream.


# 1. Delta Integration & Clamping
# Converts relative movement into an absolute position within set ranges
```
while not delta_queue.empty():
    dx, dy = delta_queue.get()
    virtual_x = max(-STEER_RANGE, min(STEER_RANGE, virtual_x + dx))
    virtual_y = max(-THROTTLE_RANGE, min(THROTTLE_RANGE, virtual_y + dy))
```
# 2. Normalization
# Maps raw values to 0.0 - 1.0 float range for gamepad output
```
mouse_steer    = virtual_x / STEER_RANGE
vertical_norm  = virtual_y / THROTTLE_RANGE
mouse_throttle = max(0.0, -vertical_norm)
mouse_brake    = max(0.0, vertical_norm)
```
# 3. Blending (Mouse + Keyboard)
# Combines inputs using a max() priority strategy
```
steering_target = mouse_steer if abs(mouse_steer) >= abs(kb_steer) else kb_steer
throttle_target = max(mouse_throttle, kb_throttle)
brake_target    = max(mouse_brake, kb_brake)
```
# 4. Smoothing & Dispatch
# Applies linear interpolation and pushes to the virtual gamepad
```
steering_out = lerp(steering_out, steering_target, 1.0 - SMOOTHING)
gamepad.left_joystick_float(x_value_float=float(steering_out), y_value_float=0.0)
gamepad.right_trigger_float(value_float=float(throttle_target))
gamepad.left_trigger_float(value_float=float(brake_out))
gamepad.update()
```
### Raw Input Handler

#This section implements a hidden window using the Windows API to capture mouse data directly from the HID stack, bypassing OS-level cursor acceleration or game-engine interference.


# 1. Message Processing (WndProc)
# Intercepts WM_INPUT (0x00FF) messages to read hardware-level movement
```
def wnd_proc(hwnd, msg, wparam, lparam):
    global active, virtual_x, virtual_y
    if msg == 0x00FF: 
        # Retrieve raw mouse packets
        # ... [GetRawInputData implementation]
        if ri.header.dwType == 0:  # RIM_TYPEMOUSE
            dx, dy = ri.mouse.lLastX, ri.mouse.lLastY
            if dx != 0 or dy != 0:
                delta_queue.put((dx, dy)) # Buffer movement for integrator
            
            # Toggle logic: Middle Mouse Button (0x0010)
            if ri.mouse._buttons._buttonStruct.usButtonFlags & 0x0010:
                active = not active
                if active: virtual_x, virtual_y = 0.0, 0.0
```
# 2. Raw Input Registration
# Creates a message-only window to listen for device input
```
def raw_input_window():
    # ... [RegisterClass/CreateWindow setup]
    rid = RAWINPUTDEVICE()
    rid.usUsagePage = 0x01
    rid.usUsage     = 0x02
    rid.dwFlags     = 0x00000100  # RIDEV_INPUTSINK (capture even when backgrounded)
    rid.hwndTarget  = hwnd
    ctypes.windll.user32.RegisterRawInputDevices(ctypes.byref(rid), 1, ctypes.sizeof(rid))
    win32gui.PumpMessages()
```
