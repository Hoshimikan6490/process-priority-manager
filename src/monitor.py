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
	
	def start(self, get_priority_rules, get_update_interval):
		"""Start monitoring process
		
		Args:
			get_priority_rules: Callable that returns active priority rules
			get_update_interval: Callable that returns update interval in seconds
		"""
		if self.monitoring:
			return
		
		self.monitoring = True
		self.monitor_thread = threading.Thread(
			target=self._monitor_loop,
			args=(get_priority_rules, get_update_interval),
			daemon=True
		)
		self.monitor_thread.start()
	
	def stop(self):
		"""Stop monitoring process"""
		self.monitoring = False
	
	def _monitor_loop(self, get_priority_rules, get_update_interval):
		"""Main monitoring loop"""
		mapping = PriorityManager.get_priority_mapping()
		
		while self.monitoring:
			try:
				rules = get_priority_rules() or []
				normalized_rules = []
				for rule in rules:
					if not rule.get('enabled', True):
						continue
					keyword = str(rule.get('keyword', '')).strip().lower()
					priority_name = str(rule.get('priority', '')).strip()
					if not keyword or priority_name not in mapping:
						continue
					normalized_rules.append((keyword, mapping[priority_name]))

				if normalized_rules:
					try:
						for p in psutil.process_iter(['pid', 'name']):
							try:
								name = (p.info.get('name') or '').lower()
								pid_text = str(p.info.get('pid'))

								for keyword, desired_value in normalized_rules:
									if keyword not in name and keyword not in pid_text:
										continue

									try:
										current = p.nice()
									except Exception:
										current = None

									if current != desired_value:
										try:
											p.nice(desired_value)
										except Exception:
											pass
									break
							except (psutil.NoSuchProcess, psutil.AccessDenied):
								continue
					except Exception:
						pass
				
				# Sleep according to update interval
				secs = get_update_interval()
				if secs <= 0:
					self.monitoring = False
					break
				
				for _ in range(int(max(1, secs))):
					if not self.monitoring:
						break
					time.sleep(1)
			
			except Exception:
				time.sleep(1)
