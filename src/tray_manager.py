"""System tray management module"""
import threading

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
		"""
		self.app_title = app_title
		self.tray_icon = None
		self.callbacks = callbacks or {}
	
	def is_available(self):
		"""Check if pystray is available"""
		return pystray is not None
	
	def create_icon(self):
		"""Create system tray icon"""
		if pystray is None:
			return
		
		# Create simple icon image
		image = Image.new('RGB', (64, 64), color=(0, 0, 0))
		d = ImageDraw.Draw(image)
		d.ellipse((8, 8, 56, 56), fill=(255, 255, 255))
		
		# Create menu
		menu_items = [
			pystray.MenuItem(self.callbacks.get('show_label') or 'Show', self._on_show_click),
			pystray.MenuItem(self.callbacks.get('exit_label') or 'Exit', self._on_exit_click),
		]
		
		self.tray_icon = pystray.Icon('ppm', image, self.app_title, pystray.Menu(*menu_items))
	
	def _on_show_click(self, icon, item):
		"""Handle show menu item click"""
		if self.callbacks.get('show'):
			self.callbacks['show']()
	
	def _on_exit_click(self, icon, item):
		"""Handle exit menu item click"""
		if self.callbacks.get('exit'):
			self.callbacks['exit']()
	
	def start(self):
		"""Start tray icon (runs in background thread)"""
		if pystray is None or not self.tray_icon:
			return
		
		thread = threading.Thread(target=self.tray_icon.run, daemon=True)
		thread.start()
	
	def stop(self):
		"""Stop tray icon"""
		try:
			if self.tray_icon:
				self.tray_icon.stop()
		except (AttributeError, RuntimeError):
			# Icon was never started or is already stopped.
			pass
