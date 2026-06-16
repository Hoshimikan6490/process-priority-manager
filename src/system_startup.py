"""System startup registration module"""
import platform
import sys
import os

try:
	import winreg
except Exception:
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
		
		key_path = r"Software\\Microsoft\\Windows\\CurrentVersion\\Run"
		exe = f'"{sys.executable}" "{os.path.abspath(__file__)}"'
		
		with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS) as key:
			if enable:
				winreg.SetValueEx(key, 'ProcessPriorityManager', 0, winreg.REG_SZ, exe)
			else:
				try:
					winreg.DeleteValue(key, 'ProcessPriorityManager')
				except FileNotFoundError:
					pass
	
	@staticmethod
	def is_supported():
		"""Check if startup registration is supported
		
		Returns:
			True if supported on this system
		"""
		return platform.system() == 'Windows' and winreg is not None
