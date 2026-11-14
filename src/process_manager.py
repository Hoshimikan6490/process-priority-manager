"""Process management module for searching and listing processes"""
import psutil


class ProcessManager:
	"""Manages process listing and searching"""
	
	@staticmethod
	def get_processes_by_keyword(keyword=''):
		"""Get list of processes matching keyword
		
		Args:
			keyword: Search string (matches process name or PID)
		
		Returns:
			List of tuples: (display_text, pid, name)
		"""
		keyword = keyword.lower()
		procs = []
		
		for p in psutil.process_iter(['pid', 'name']):
			try:
				name = p.info.get('name') or ''
				pid = p.info.get('pid')
				display = f"{pid} - {name}"
				
				if keyword in name.lower() or keyword in str(pid):
					procs.append((display, pid, name))
			except (psutil.NoSuchProcess, psutil.AccessDenied):
				continue
		
		# Sort by process name
		procs.sort(key=lambda x: x[2].lower())
		return procs
