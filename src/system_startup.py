"""System startup registration module"""
import os
import platform
import sys

try:
	import winreg
except ImportError:
	winreg = None


class StartupManager:
	"""Manages startup registration"""
	
	@staticmethod
	def register_startup(enable: bool):
		"""Register or unregister application from startup
		
		Args:
			enable: True to register, False to unregister
		
		Raises:
			RuntimeError: If not on Windows or winreg not available
		"""
		if platform.system() != 'Windows' or winreg is None:
			raise RuntimeError('Startup registration is only supported on Windows')
		
		key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
		if getattr(sys, 'frozen', False):
			exe = f'"{sys.executable}"'
		else:
			exe = f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'
		
		with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS) as key:
			if enable:
				winreg.SetValueEx(key, 'ProcessPriorityManager', 0, winreg.REG_SZ, exe)
			else:
				try:
					winreg.DeleteValue(key, 'ProcessPriorityManager')
				except FileNotFoundError:
					pass
