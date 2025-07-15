"""meow"""

import asyncio
import logging
from collections import defaultdict
from collections.abc import Collection, Mapping
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

from async_lru import alru_cache

from pymame.utils import NoNonsenseConfigParser

if TYPE_CHECKING:
	from pymame.typedefs import Basename

logger = logging.getLogger(__name__)

CatName = str
"""Type alias for string that is the stem of an .ini file (e.g. version, catlist, etc)"""
CatMapping = Mapping[str, Collection['Basename']]
"""Section in .ini file -> basenames within that file"""


def _get_nplayers(cat_path: Path) -> CatMapping:
	p = NoNonsenseConfigParser(strict=False, comment_prefixes=';')
	p.read(filenames=cat_path)
	if not p.has_section('NPlayers'):
		return {}

	d = defaultdict(list)
	for item, value in p.items('NPlayers', raw=True):
		d[value].append(item)
	return d


def parse_mame_cat_ini(path: Path) -> CatMapping:
	# using ASCII because series.ini has borked utf-8 before…
	with path.open('rt', encoding='ascii') as f:
		d: defaultdict[str, set[Basename]] = defaultdict(set)
		current_section = None
		for line in f:
			line = line.strip()
			# Don't need to worry about FOLDER_SETTINGS or ROOT_FOLDER sections though I guess this code is gonna put them in there
			if line.startswith(';'):
				continue
			if line.startswith('['):
				current_section = line[1:-1]
			elif current_section:
				d[current_section].add(line)
		return d


@cache
def read_cat_folder(cat_folder_path: Path):
	cats: dict[str, Mapping[str, Collection[Basename]]] = {}  # meow

	for file in cat_folder_path.iterdir():
		if file.suffix[1:].lower() != 'ini':
			continue
		if file.name == 'nplayers.ini':
			cats['nplayers'] = _get_nplayers(file)
		else:
			cats[file.stem] = parse_mame_cat_ini(file)
	return cats


def _listdir_sync(path: Path):
	return list(path.iterdir())


async def _listdir_async(path: Path):
	return await asyncio.to_thread(_listdir_sync, path)


@alru_cache
async def _read_cat_file_async(path: Path):
	if path.name == 'nplayers.ini':
		return path, await asyncio.to_thread(_get_nplayers, path)
	return path, await asyncio.to_thread(parse_mame_cat_ini, path)


async def read_cat_folder_async(cat_folder_path: Path):
	files = await _listdir_async(cat_folder_path)
	tasks = [
		asyncio.create_task(_read_cat_file_async(cat_path))
		for cat_path in files
		if cat_path.suffix[1:].lower() == 'ini'
	]

	cats: dict[CatName, CatMapping] = {}  # meow

	for result in asyncio.as_completed(tasks):
		path, cat = await result
		cats[path.stem] = cat
	return cats


class CategoryFolder:
	"""Holds .ini category/folder/whatever they're called files, after reading them all into memory."""

	def __init__(self, cats: dict[CatName, CatMapping]) -> None:
		self.cats = cats

	@classmethod
	def load_from_folder(cls, path: Path):
		return cls(read_cat_folder(path))

	@classmethod
	async def load_from_folder_async(cls, path: Path):
		return cls(await read_cat_folder_async(path))

	def get_cats(self, cat_name: CatName, basename: 'Basename') -> Collection[str]:
		"""Gets all values for a category for `basename`

		Returns:
			Collection of section names"""
		cat = self.cats.get(cat_name)
		if not cat:
			return ()
		return {section for section, names in cat.items() if basename in names}

	def get_cat(self, cat_name: CatName, basename: 'Basename') -> str | None:
		"""Gets a single value for a category for `basename`, where only one is expected

		Returns:
			Section name or None"""
		sections = self.get_cats(cat_name, basename)
		if not sections:
			return None
		if len(sections) > 1:
			logger.warning('More than one %s for %s, using first', cat_name, basename)
		return next(iter(sections))
