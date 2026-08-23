# -*- coding: utf-8 -*-
import tkinter as tk, sys, traceback
sys.path.insert(0, '.')
import claude_continue_gui as m
root = tk.Tk(); root.withdraw()
try:
    app = m.App(root)
    root.update_idletasks()
    app._set_theme('light')
    root.update()
    print('OK')
except Exception:
    traceback.print_exc()
app.root.after(30, app.root.destroy)
root.update()
