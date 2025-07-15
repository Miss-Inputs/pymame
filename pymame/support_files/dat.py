"""Parser for text file .dats, and wrapper around a folder containing dats"""

import asyncio
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

from async_lru import alru_cache

from .history import HistoryDB, HistoryEntry, read_history_xml, read_history_xml_async

if TYPE_CHECKING:
	from pymame.typedefs import Basename, SoftwareBasename, SoftwareListBasename


def _parse_dat_raw(path: Path):
	# Not at all sure if any .dat files have software info in them?
	d = {}
	current_name = None
	current_info: list[str] = []
	with path.open('rt', encoding='utf8') as f:
		for line in f.readlines():
			line = line.strip()
			if line.startswith('$info'):
				current_name = line.split('=', 1)[1]
				current_info = []
			elif current_name:
				if line == '$end':
					d[current_name] = '\n'.join(current_info[1:])
					current_name = None
					continue
				current_info.append(line)
	return d


parse_dat = cache(_parse_dat_raw)


@alru_cache
async def parse_dat_async(path: Path) -> Mapping['Basename', str]:
	return await asyncio.to_thread(_parse_dat_raw, path)


class DatsFolder:
	def __init__(self, path: Path) -> None:
		self.path = path
		self._history_db: HistoryDB | None = None
		self._history_db_lock = asyncio.Lock()

	def get_dat_info(self, name: str, basename: 'Basename') -> str | None:
		dat_path = self.path / f'{name}.dat'
		return parse_dat(dat_path).get(basename)

	async def get_dat_info_async(self, name: str, basename: 'Basename') -> str | None:
		dat_path = self.path / f'{name}.dat'
		dat = await parse_dat_async(dat_path)
		return dat.get(basename)

	@property
	def history_db(self) -> HistoryDB | None:
		if self._history_db:
			return self._history_db
		xml = read_history_xml(self.path / 'history.xml')
		if not xml:
			return None
		self._history_db = HistoryDB(xml)
		return self._history_db

	@property
	async def history_db_async(self) -> HistoryDB | None:
		async with self._history_db_lock:
			if self._history_db:
				return self._history_db
			xml = await read_history_xml_async(self.path / 'history.xml')
			if not xml:
				return None
			self._history_db = HistoryDB(xml)
			return self._history_db

	def get_history(self, basename: 'Basename') -> HistoryEntry | None:
		db = self.history_db
		return db.get_history(basename) if db else None

	async def get_history_async(self, basename: 'Basename') -> HistoryEntry | None:
		db = await self.history_db_async
		return db.get_history(basename) if db else None

	def get_software_history(
		self, software_list_name: 'SoftwareListBasename', software_name: 'SoftwareBasename'
	) -> HistoryEntry | None:
		db = self.history_db
		return db.get_software_history(software_list_name, software_name) if db else None

	async def get_software_history_async(
		self, software_list_name: 'SoftwareListBasename', software_name: 'SoftwareBasename'
	) -> HistoryEntry | None:
		db = await self.history_db_async
		return db.get_software_history(software_list_name, software_name) if db else None


@cache
def get_dat_folder(path: Path):
	return DatsFolder(path)
