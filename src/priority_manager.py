"""Process priority management module"""
import platform

import psutil


class PriorityManager:
	"""Manages process priority operations"""
	
	@staticmethod
	def get_priority_mapping():
		"""Get OS-specific priority mapping
		
		Returns:
			Dictionary mapping priority names to values
		"""
		if platform.system() == 'Windows':
			return {
				'Idle': psutil.IDLE_PRIORITY_CLASS,
				'Below Normal': psutil.BELOW_NORMAL_PRIORITY_CLASS,
				'Normal': psutil.NORMAL_PRIORITY_CLASS,
				'Above Normal': psutil.ABOVE_NORMAL_PRIORITY_CLASS,
				'High': psutil.HIGH_PRIORITY_CLASS,
				'RealTime': psutil.REALTIME_PRIORITY_CLASS,
			}
		else:
			# Map to nice values on POSIX
			return {
				'Idle': 19,
				'Below Normal': 10,
				'Normal': 0,
				'Above Normal': -5,
				'High': -10,
				'RealTime': -20,
			}
	
	@staticmethod
	def set_priority(pid, priority_name):
		"""Set process priority
		
		Args:
			pid: Process ID
			priority_name: Priority name (e.g., 'High', 'Normal')
		
		Raises:
			psutil.NoSuchProcess: If process not found
			psutil.AccessDenied: If permission denied
		"""
		mapping = PriorityManager.get_priority_mapping()
		priority_value = mapping.get(priority_name)
		
		if priority_value is None:
			raise ValueError(f"Unknown priority: {priority_name}")
		
		p = psutil.Process(pid)
		p.nice(priority_value)
