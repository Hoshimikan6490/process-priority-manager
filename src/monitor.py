"""Auto-monitoring module for continuous priority management"""
import threading
import time
import psutil
from .priority_manager import PriorityManager


class ProcessMonitor:
	"""Monitors and maintains process priority"""
	
	def __init__(self):
		self.monitoring = False
		self.monitor_thread = None
	
	def start(self, get_selected_pid, get_desired_priority, get_update_interval):
		"""Start monitoring process
		
		Args:
			get_selected_pid: Callable that returns current selected PID
			get_desired_priority: Callable that returns desired priority name
			get_update_interval: Callable that returns update interval in seconds
		"""
		if self.monitoring:
			return
		
		self.monitoring = True
		self.monitor_thread = threading.Thread(
			target=self._monitor_loop,
			args=(get_selected_pid, get_desired_priority, get_update_interval),
			daemon=True
		)
		self.monitor_thread.start()
	
	def stop(self):
		"""Stop monitoring process"""
		self.monitoring = False
	
	def _monitor_loop(self, get_selected_pid, get_desired_priority, get_update_interval):
		"""Main monitoring loop"""
		mapping = PriorityManager.get_priority_mapping()
		
		while self.monitoring:
			try:
				pid = get_selected_pid()
				if pid:
					try:
						p = psutil.Process(pid)
						desired_priority = get_desired_priority()
						desired_value = mapping.get(desired_priority)
						
						try:
							current = p.nice()
						except Exception:
							current = None
						
						if current != desired_value:
							try:
								p.nice(desired_value)
							except Exception:
								pass
					except (psutil.NoSuchProcess, psutil.AccessDenied):
						pass
				
				# Sleep according to update interval
				secs = get_update_interval()
				if secs <= 0:
					secs = 1
				
				for _ in range(int(max(1, secs))):
					if not self.monitoring:
						break
					time.sleep(1)
			
			except Exception:
				time.sleep(1)
