"""Auto-monitoring module for continuous priority management"""
import logging
import threading

import psutil

from .priority_manager import PriorityManager

logger = logging.getLogger(__name__)


class ProcessMonitor:
	"""Monitors and maintains process priority"""

	def __init__(self):
		self.monitor_thread = None
		self._stop_event = None

	@property
	def monitoring(self):
		return self.monitor_thread is not None and self.monitor_thread.is_alive()

	def start(self, get_priority_rules, get_update_interval):
		"""Start monitoring process

		Args:
			get_priority_rules: Callable that returns priority rules
			get_update_interval: Callable that returns update interval in seconds
		"""
		if self.monitoring:
			return

		self._stop_event = threading.Event()
		self.monitor_thread = threading.Thread(
			target=self._monitor_loop,
			args=(get_priority_rules, get_update_interval, self._stop_event),
			daemon=True
		)
		self.monitor_thread.start()

	def stop(self):
		"""Stop monitoring process"""
		if self._stop_event is not None:
			self._stop_event.set()
		self.monitor_thread = None

	def restart(self, get_priority_rules, get_update_interval):
		"""Stop the current loop (if any) and start a fresh one.

		Each loop owns its own stop event, so an old loop that is still
		finishing its wait can never be revived by the new start().
		"""
		self.stop()
		self.start(get_priority_rules, get_update_interval)

	def _monitor_loop(self, get_priority_rules, get_update_interval, stop_event):
		"""Main monitoring loop"""
		mapping = PriorityManager.get_priority_mapping()

		while not stop_event.is_set():
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
					self._apply_rules(normalized_rules)

				# Sleep according to update interval ("first only" ends the loop)
				secs = get_update_interval()
				if secs <= 0:
					break

				for _ in range(int(max(1, secs))):
					if stop_event.wait(1):
						break

			except Exception:
				# Keep the monitor thread alive on unexpected errors.
				logger.exception('Priority monitor loop failed')
				stop_event.wait(1)

	@staticmethod
	def _apply_rules(normalized_rules):
		try:
			for p in psutil.process_iter(['pid', 'name']):
				try:
					name = (p.info.get('name') or '').lower()
					pid_text = str(p.info.get('pid'))

					for keyword, desired_value in normalized_rules:
						if keyword not in name and keyword not in pid_text:
							continue

						try:
							if p.nice() != desired_value:
								p.nice(desired_value)
						except psutil.Error:
							# Process exited or access denied; skip it.
							pass
						break
				except psutil.Error:
					continue
		except psutil.Error:
			# Process enumeration failed; retry on the next cycle.
			pass
