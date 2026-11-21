"""System tray management module"""
import threading

from .resources import load_logo

try:
	import pystray
	from PIL import Image, ImageDraw
except ImportError:
	pystray = None


class TrayManager:
	"""Manages system tray icon and menu"""

	def __init__(self, app_title, callbacks=None):
		"""Initialize tray manager

		Args:
			app_title: Application title for tray
			callbacks: Dictionary with 'show' and 'exit' callback functions
				(called from the tray thread) and optional menu labels
		"""
		self.app_title = app_title
		self.tray_icon = None
		self.callbacks = callbacks or {}

	def is_available(self):
		"""Check if pystray is available"""
		return pystray is not None

	@property
	def running(self):
		return self.tray_icon is not None

	@staticmethod
	def _build_image():
		image = load_logo(64)
		if image is not None:
			return image
		# Fallback when the logo file is missing.
		image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
		ImageDraw.Draw(image).ellipse((4, 4, 60, 60), fill=(74, 144, 217, 255))
		return image

	def start(self):
		"""Create the tray icon and run it in a background thread."""
		if pystray is None or self.tray_icon is not None:
			return

		menu = pystray.Menu(
			# default=True: left-click / double-click on the icon shows the window
			pystray.MenuItem(self.callbacks.get('show_label') or 'Show', self._on_show_click, default=True),
			pystray.MenuItem(self.callbacks.get('exit_label') or 'Exit', self._on_exit_click),
		)
		self.tray_icon = pystray.Icon('ppm', self._build_image(), self.app_title, menu)
		threading.Thread(target=self.tray_icon.run, daemon=True).start()

	def _on_show_click(self, icon, item):
		"""Handle show menu item click"""
		if self.callbacks.get('show'):
			self.callbacks['show']()

	def _on_exit_click(self, icon, item):
		"""Handle exit menu item click"""
		if self.callbacks.get('exit'):
			self.callbacks['exit']()

	def stop(self):
		"""Remove the tray icon"""
		icon, self.tray_icon = self.tray_icon, None
		try:
			if icon:
				icon.stop()
		except (AttributeError, RuntimeError):
			# Icon was never started or is already stopped.
			pass
