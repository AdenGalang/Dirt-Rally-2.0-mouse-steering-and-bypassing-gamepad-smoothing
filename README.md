# Dirt-Rally-2.0-mouse-steering-and-bypassing-gamepad-smoothing
DR2 with mouse steering and bypassing input smoothing
# Requirement
- ViGEm Bus
- python and the following packages
```
pip install vgamepad pynput pywin32
```
# Dirt Rally 2 gamepad thing
normally gamepad will receive a smoothing and also a bit of assist to keep the car straight etc, which make the wheel feels speed dependent(the faster you go the less the sensitivity applied), while not neccecarily add much of a latency, it can feel really annoying when counter steering with input that in this case weren't actually a gamepad, to fix this you can manually add ViGem's VID and PID into Dirt rally 2's input xml and set your input to wheel or custom generic device(which can be toggeled for gamepad as normal but bypasses smoothing)

- *Note: you need to fire the source of the input device or it wont appear, as obvious as it sounds, just in case some poor soul forgot abt it*
# Adding your own Input xml
you can nativage to the game root folder and find input folder "DiRT Rally 2.0\input\", within input folder there would be 3 folder actionmaps, devices, and libraries:

<img width="160" height="113" alt="image" src="https://github.com/user-attachments/assets/1c79229c-3886-4115-8f26-704d6c8043a9" />

 you will be focusing on devices and actionmaps folder, inside devices there would be a xml file named device_defines.xml, for the game to recognize and overwrite ViGem gamepad and to add your own
 you have to add your own Device ID and its Name inside device_defines.xml, upon opening you can see:
 ```
<device_list>
 <!--
   Device configuration file.
   This file is used to define device definitions and their usage in the game.
   ......
   The hardware id for PC devices is essentially '{PID#VID#-0000-0000-0000-504944564944}'
   ....

   (blah blah stuff ∨∨∨∨∨∨)
   --!>

  <device id="{038E0EB7-0000-0000-0000-504944564944}" name="ftec_clubsport_v1" priority="100" type="wheel" />
</device_list>
 ```
how to add your own?
-
- copy paste the first device id= and its entire line < line /> that is already exist in device_defines.xml e.g ```<device id="{038E0EB7-0000-0000-0000-504944564944}" name="ftec_clubsport_v1" priority="100" type="wheel" />```
- get your virtual/physical gamepad VID and PID, if its physical USB devicem you should able to get it from device manager, but if you're using virtual gamepad(e.g ViGEm) you can use Joystick Gremlin to view its properties, note you only need VID and PID, then paste it using format explained in the device_defines.xml said above "PID#VID#" e.g 05C4054C if you're using my script which uses DS4 and identified as a Wireless Controller, the name= is your choice, but remember this will be used in actionmaps e.g name="wireless_controller"....
- the final line should look something similar to this  ```<device id="{05C4054C-0000-0000-0000-504944564944}" name="wireless_controller" priority="100" type="wheel" official="false" /> ```
- now we move on to actionmaps folder
  inside there would be bunch of respective action map for each device that is listed in the device_defines.xml, the name are the only identifier used for the game to see the respective file so make sure you name your new xml the same as name= in device_defines.xml, you dont need to make actionmap from scratch you can easily copy paste and rename other compatible file say ```"ftec_clubsport_bmw.xml"```, note: as long as X and Y axis are defined clearly it should be fine, once open the header should be self explanatory ```<action_map name="ftec_clubsport_bmw" device_name="ftec_clubsport" library="lib_direct_input" version="18">```, action_map name is the default keybind in game that you can load(i think used for resetting your keybind if you messed up or smth) your naming choice, device_name= is the important one, because it had to match your previous added device in device_defines.xml, once matched, you should see something like:
  
  <img width="972" height="174" alt="image" src="https://github.com/user-attachments/assets/7836c49f-5bd7-4ef9-b450-878a280ad60a" />
- now you can test launching the game, and see if the game recognize your newly added device configuration xml
  if you do use ```official="false"``` in device_defines.xml, you could choose what your input do since the flag makes your device appear as generic input device, you could set this parameter in game setting as wheel, gamepad, or even unknown etc in input, your input device then advance option, i recommend you to set it to wheel


# Using ViGem script to map mouse axis
  
 Script Usage
 *launch it using CMD*
```
python gameinput.py
```
### Input Logic

This script translates raw mouse/keyboard deltas into a virtual gamepad stream as throttle, brake and steering.


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
# Debugging
remove "#" in line 178, this will dump data to terminal every update
```
print(f"vx={virtual_x:.0f} vy={virtual_y:.0f} thr={throttle_target:.2f} brk={brake_target:.2f}")
```
# Extras
this script technically works in other games too, such as Assetto Corsa(with Content Manager), personally i prefer this input method far better compared to any controller, the amount of small and very accurate steering adjustment with a proper visual feedback make up for the lack of feedback, the only downside is throttle and brakes require tons of muscle memory to learn and adapt to, and partial braking/throttle can be difficult while actively steering, tho if you just drive at somepoint it would click, for a rally game, using gamepad is just a psychopath thing to do, idk maybe its just skill issue on my end, but i go to this extent just to avoid using my gamepad so maybe you can relate?  
