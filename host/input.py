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