"""Custom Tk widgets."""

import tkinter as tk


class ToggleSwitch(tk.Canvas):
    """Slide switch (iOS-style) that calls command(new_value) when clicked."""

    WIDTH = 40
    HEIGHT = 20

    def __init__(
        self,
        master,
        value=False,
        command=None,
        bg=None,
        on_color="#4a90d9",
        off_color="#9a9a9a",
    ):
        super().__init__(
            master,
            width=self.WIDTH,
            height=self.HEIGHT,
            bg=bg,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self._value = bool(value)
        self._command = command
        self._on_color = on_color
        self._off_color = off_color
        self.bind("<Button-1>", self._on_click)
        self._draw()

    @property
    def value(self):
        return self._value

    def _on_click(self, _event):
        self._value = not self._value
        self._draw()
        if self._command:
            self._command(self._value)

    def _draw(self):
        self.delete("all")
        w, h = self.WIDTH, self.HEIGHT
        color = self._on_color if self._value else self._off_color
        r = h // 2
        # Pill-shaped track: two end caps plus a body rectangle.
        self.create_oval(0, 0, h, h, fill=color, outline=color)
        self.create_oval(w - h, 0, w, h, fill=color, outline=color)
        self.create_rectangle(r, 0, w - r, h, fill=color, outline=color)
        pad = 3
        knob_x = w - h + pad if self._value else pad
        self.create_oval(knob_x, pad, knob_x + h - 2 * pad, h - pad, fill="white", outline="white")
