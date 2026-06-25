import logging
import os
from typing import Optional
from evdev import UInput, ecodes, AbsInfo
log=logging.getLogger("input")

#https://developer.mozilla.org/en-US/docs/Web/API/UI_Events/Keyboard_event_code_values

#i used AI for this keymap because its insanely long
KEY_MAP={
    "KeyA": ecodes.KEY_A, "KeyB": ecodes.KEY_B, "KeyC": ecodes.KEY_C,
    "KeyD": ecodes.KEY_D, "KeyE": ecodes.KEY_E, "KeyF": ecodes.KEY_F,
    "KeyG": ecodes.KEY_G, "KeyH": ecodes.KEY_H, "KeyI": ecodes.KEY_I,
    "KeyJ": ecodes.KEY_J, "KeyK": ecodes.KEY_K, "KeyL": ecodes.KEY_L,
    "KeyM": ecodes.KEY_M, "KeyN": ecodes.KEY_N, "KeyO": ecodes.KEY_O,
    "KeyP": ecodes.KEY_P, "KeyQ": ecodes.KEY_Q, "KeyR": ecodes.KEY_R,
    "KeyS": ecodes.KEY_S, "KeyT": ecodes.KEY_T, "KeyU": ecodes.KEY_U,
    "KeyV": ecodes.KEY_V, "KeyW": ecodes.KEY_W, "KeyX": ecodes.KEY_X,
    "KeyY": ecodes.KEY_Y, "KeyZ": ecodes.KEY_Z,
    "Digit1": ecodes.KEY_1, "Digit2": ecodes.KEY_2, "Digit3": ecodes.KEY_3,
    "Digit4": ecodes.KEY_4, "Digit5": ecodes.KEY_5, "Digit6": ecodes.KEY_6,
    "Digit7": ecodes.KEY_7, "Digit8": ecodes.KEY_8, "Digit9": ecodes.KEY_9,
    "Digit0": ecodes.KEY_0,
    "F1": ecodes.KEY_F1,   "F2": ecodes.KEY_F2,   "F3": ecodes.KEY_F3,
    "F4": ecodes.KEY_F4,   "F5": ecodes.KEY_F5,   "F6": ecodes.KEY_F6,
    "F7": ecodes.KEY_F7,   "F8": ecodes.KEY_F8,   "F9": ecodes.KEY_F9,
    "F10": ecodes.KEY_F10, "F11": ecodes.KEY_F11, "F12": ecodes.KEY_F12,
    "ShiftLeft": ecodes.KEY_LEFTSHIFT,   "ShiftRight": ecodes.KEY_RIGHTSHIFT,
    "ControlLeft": ecodes.KEY_LEFTCTRL,  "ControlRight": ecodes.KEY_RIGHTCTRL,
    "AltLeft": ecodes.KEY_LEFTALT,       "AltRight": ecodes.KEY_RIGHTALT,
    "MetaLeft": ecodes.KEY_LEFTMETA,     "MetaRight": ecodes.KEY_RIGHTMETA,
    "ArrowUp": ecodes.KEY_UP,     "ArrowDown": ecodes.KEY_DOWN,
    "ArrowLeft": ecodes.KEY_LEFT, "ArrowRight": ecodes.KEY_RIGHT,
    "Home": ecodes.KEY_HOME,      "End": ecodes.KEY_END,
    "PageUp": ecodes.KEY_PAGEUP,  "PageDown": ecodes.KEY_PAGEDOWN,
    "Insert": ecodes.KEY_INSERT,  "Delete": ecodes.KEY_DELETE,
    "Space": ecodes.KEY_SPACE,
    "Enter": ecodes.KEY_ENTER,
    "NumpadEnter": ecodes.KEY_KPENTER,
    "Backspace": ecodes.KEY_BACKSPACE,
    "Tab": ecodes.KEY_TAB,
    "Escape": ecodes.KEY_ESC,
    "CapsLock": ecodes.KEY_CAPSLOCK,
    "Minus": ecodes.KEY_MINUS,          "Equal": ecodes.KEY_EQUAL,
    "BracketLeft": ecodes.KEY_LEFTBRACE, "BracketRight": ecodes.KEY_RIGHTBRACE,
    "Backslash": ecodes.KEY_BACKSLASH,   "Semicolon": ecodes.KEY_SEMICOLON,
    "Quote": ecodes.KEY_APOSTROPHE,      "Backquote": ecodes.KEY_GRAVE,
    "Comma": ecodes.KEY_COMMA,           "Period": ecodes.KEY_DOT,
    "Slash": ecodes.KEY_SLASH,
    "Numpad0": ecodes.KEY_KP0, "Numpad1": ecodes.KEY_KP1,
    "Numpad2": ecodes.KEY_KP2, "Numpad3": ecodes.KEY_KP3,
    "Numpad4": ecodes.KEY_KP4, "Numpad5": ecodes.KEY_KP5,
    "Numpad6": ecodes.KEY_KP6, "Numpad7": ecodes.KEY_KP7,
    "Numpad8": ecodes.KEY_KP8, "Numpad9": ecodes.KEY_KP9,
    "NumpadDecimal": ecodes.KEY_KPDOT,
    "NumpadAdd": ecodes.KEY_KPPLUS,      "NumpadSubtract": ecodes.KEY_KPMINUS,
    "NumpadMultiply": ecodes.KEY_KPASTERISK, "NumpadDivide": ecodes.KEY_KPSLASH,
    "NumLock": ecodes.KEY_NUMLOCK,
    "PrintScreen": ecodes.KEY_SYSRQ,
    "ScrollLock": ecodes.KEY_SCROLLLOCK,
    "Pause": ecodes.KEY_PAUSE,
}

MOUSE_BUTTON_MAP={
    0:ecodes.BTN_LEFT,
    1:ecodes.BTN_MIDDLE,
    2:ecodes.BTN_RIGHT
}

GAMEPAD_BUTTON_MAP={
    0:ecodes.BTN_SOUTH,
    1:ecodes.BTN_EAST,
    2:ecodes.BTN_WEST,
    3:ecodes.BTN_NORTH,
    4:ecodes.BTN_TL,
    5:ecodes.BTN_TR,
    6:ecodes.BTN_TL2,
    7:ecodes.BTN_TR2,
    8:ecodes.BTN_SELECT,
    9:ecodes.BTN_START,
    10:ecodes.BTN_THUMBL,
    11:ecodes.BTN_THUMBR,
    12:ecodes.BTN_DPAD_UP,
    13:ecodes.BTN_DPAD_DOWN,
    14:ecodes.BTN_DPAD_LEFT,
    15:ecodes.BTN_DPAD_RIGHT,
    16:ecodes.BTN_MODE
}
ABS_RANGE=32767
ABS_TRIGGER_MAX=255

class InputDevices:
    def __init__(self):
        self._keyboard:Optional[UInput]=None
        self._mouse:Optional[UInput]=None
        self._gamepad:Optional[UInput]=None 
    
    def keyboard(self)->UInput:
        if self._keyboard is None:
            self._keyboard=UInput(
                {ecodes.EV_KEY:list(KEY_MAP.values())},
                name="webstream-keyboard",
                version=0x1,
            )
            log.info("vkeyboard created")
        return self._keyboard 
    
    def mouse(self)->UInput:
        if self._mouse is None:
            self._mouse=UInput(
                {
                    ecodes.EV_KEY:[ecodes.BTN_LEFT,ecodes.BTN_MIDDLE,ecodes.BTN_RIGHT],
                    ecodes.EV_REL:[ecodes.REL_X,ecodes.REL_Y,ecodes.REL_WHEEL],
                },
                name="webstream-mouse",
                version=0x1,
            )
            log.info("vmouse created")
        return self._mouse
    
    def gamepad(self)->UInput:
        if self._gamepad is None:
            abs_capabilities={
                ecodes.ABS_X:AbsInfo(value=0,min=-ABS_RANGE,max=ABS_RANGE,fuzz=0,flat=128,resolution=0),
                ecodes.ABS_Y:AbsInfo(value=0,min=-ABS_RANGE,max=ABS_RANGE,fuzz=0,flat=128,resolution=0),
                ecodes.ABS_RX:AbsInfo(value=0,min=-ABS_RANGE,max=ABS_RANGE,fuzz=0,flat=128,resolution=0),
                ecodes.ABS_RY:AbsInfo(value=0,min=-ABS_RANGE,max=ABS_RANGE,fuzz=0,flat=128,resolution=0),
                ecodes.ABS_Z:AbsInfo(value=0,min=0,max=ABS_TRIGGER_MAX,fuzz=0,flat=0,resolution=0),
                ecodes.ABS_RZ:AbsInfo(value=0,min=0,max=ABS_TRIGGER_MAX,fuzz=0,flat=0,resolution=0),
                ecodes.ABS_HAT0X:AbsInfo(value=0,min=-1,max=1,fuzz=0,flat=0,resolution=0),
                ecodes.ABS_HAT0Y:AbsInfo(value=0,min=-1,max=1,fuzz=0,flat=0,resolution=0)
            }
            self._gamepad=UInput(
                {
                    ecodes.EV_KEY:list(GAMEPAD_BUTTON_MAP.values()),
                    ecodes.EV_ABS:abs_capabilities,
                },
                name="webstream-gamepad",
                version=0x1,
            )
            log.info("vgamepad created")
        return self._gamepad
    
    def close(self):
        for dev in [self._keyboard,self._mouse,self._gamepad]:
            if dev:
                try:
                    dev.close()
                except Exception:
                    pass

_devices=InputDevices()

def _get_screen_size()->tuple[int,int]:
    #simply returns width,height of the captured display
    w=os.environ.get("CAPTURE_WIDTH")
    h=os.environ.get("CAPTURE_HEIGHT")
    if w and h:
        return int(w),int(h)
    try:
        import subprocess
        out=subprocess.check_output(["xdpyinfo"],text=True)
        for line in out.splitlines():
            if "dimensions:" in line:
                dims=line.split()[1]
                sw,sh=dims.split("x")
                return int(sw),int(sh)
    except Exception:
        pass
    return 1920, 1080

_screen_w,_screen_h=None,None

def _screen()->tuple[int,int]:
    global _screen_w,_screen_h
    if _screen_w is None:
        _screen_w, _screen_h=_get_screen_size()
        log.info("screen size %dx%d",_screen_w,_screen_h)
    return _screen_w,_screen_h

_prev_gamepad_buttons:dict[int,list[bool]]={}

def inject_event(event:dict):
    t=event.get("type")
    try:
        if t=="keydown":
            _inject_key(event.get("code",""),1)
        elif t=="keyup":
            _inject_key(event.get("code",""),0)
        elif t=="mousemove":
            _inject_mousemove(event.get("x",0.5),event.get("y",0.5))
        elif t=="mousedown":
            _inject_mousebutton(event.get("button",0),1)
        elif t=="mouseup":
            _inject_mousebutton(event.get("button",0),0)
        elif t=="wheel":
            _inject_wheel(event.get("deltaY",0))
        elif t=="gamepad":
            _inject_wheel(event.get("deltaY",0))
        elif t=="gamepad":
            _inject_gamepad(
                event.get("index",0),
                event.get("buttons",[]),
                event.get("axes",[]),
            )
    except Exception as e:
        log.warning("inject_event error %s: %s",t,e)

def _inject_key(code:str,value:int):
    keycode=KEY_MAP.get(code)
    if keycode is None:
        log.debug("unmapped key code %s",code)
        return
    kb=_devices.keyboard()
    kb.write(ecodes.EV_KEY,keycode,value)
    kb.syn()

def _inject_mousemove(x:float,y:float):
    sw,sh=_screen()
    abs_x=int(x*sw)
    abs_y=int(y*sh)
    prev=getattr(_inject_mousemove,"_prev",(sw//2,sh//2))
    dx=abs_x-prev[0]
    dy=abs_y-prev[1]
    _inject_mousemove._prev=(abs_x,abs_y)
    if dx==0 and dy==0:
        return 
    m=_devices.mouse()
    if dx!=0:
        m.write(ecodes.EV_REL,ecodes.REL_X,dx)
    if dy!=0:
        m.write(ecodes.EV_REL,ecodes.REL_Y,dy)
    m.syn()
    
def _inject_mousebutton(button:int,value:int):
    btn=MOUSE_BUTTON_MAP.get(button)
    if btn is None:
        return
    m=_devices.mouse()
    m.write(ecodes.EV_KEY,btn,value)
    m.syn()

def _inject_wheel(delta_y:float):
    if abs(delta_y)<1:
        return
    direction=-1 if delta_y>0 else 1
    m=_devices.mouse()
    m.write(ecodes.EV_REL,ecodes.REL_WHEEL,direction)
    m.syn()

def _inject_gamepad(index:int,buttons:list,axes:list):
    gp=_devices.gamepad()
    prev_buttons=_prev_gamepad_buttons.get(index,[])
    for i,pressed in enumerate(buttons):
        btn=GAMEPAD_BUTTON_MAP.get(i)
        if btn is None:
            continue
        prev=prev_buttons[i] if i <len(prev_buttons) else False
        if pressed!=prev:
            gp.write(ecodes.EV_KEY,btn,1 if pressed else 0)
    _prev_gamepad_buttons[index]=list(buttons)
    axis_map=[
        (0,ecodes.ABS_X),
        (1,ecodes.ABS_Y),
        (2,ecodes.ABS_RX),
        (3,ecodes.ABS_RY),
    ]
    for i,abs_code in axis_map:
        if i <len(axes):
            val=int(axes[i]*ABS_RANGE)
            gp.write(ecodes.EV_ABS,abs_code,val)
    if 6<len(buttons):
        lt=int(buttons[6]*ABS_TRIGGER_MAX) if isinstance(buttons[6],float) else (ABS_TRIGGER_MAX if buttons[6] else 0)
        gp.write(ecodes.EV_ABS,ecodes.ABS_Z,lt)
    if 7<len(buttons):
        rt=int(buttons[7]*ABS_TRIGGER_MAX) if ininstance(buttons[7],float) else (ABS_TRIGGER_MAX if buttons[7] else 0)
        gp.write(ecodes.EV_ABS,ecodes.ABS_RZ,rt)
    gp.syn()

def close():
    #cleanly closes uinput
    _devices.close()