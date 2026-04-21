"""meow
Loader/parser for category .ini files"""

import asyncio
import logging
from collections import defaultdict
from collections.abc import Collection, Mapping
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

from async_lru import alru_cache

from pymame.utils import NoNonsenseConfigParser, listdir_async

if TYPE_CHECKING:
	from pymame.typedefs import Basename

logger = logging.getLogger(__name__)

type CatName = str
"""Type alias for string that is the stem of an .ini file (e.g. version, catlist, etc)"""
type CatMapping = Mapping[str, Collection[Basename]]
"""Section in .ini file -> basenames within that file"""


def read_key_value_cat_ini(cat_path: Path, section_name: str | None = None) -> CatMapping:
	"""
	Parses a category ini file which contains key/value pairs instead of the usual format (such as nplayers).
	If `section_name` is blank or None, it will use the first one.
	"""
	p = NoNonsenseConfigParser(strict=False, comment_prefixes=';')
	# Maybe we could have an encoding parameter here, but it's not super necessary
	p.read(filenames=cat_path)
	section_name = section_name or p.sections()[0]
	assert section_name is not None, 'section_name should not be None'

	if not p.has_section(section_name):
		return {}

	d: defaultdict[str, list[Basename]] = defaultdict(list)
	for item, value in p.items(section_name, raw=True):
		d[value].append(item)
	return d


async def read_key_value_cat_ini_async(
	cat_path: Path, section_name: str | None = None
) -> CatMapping:
	return await asyncio.to_thread(read_key_value_cat_ini, cat_path, section_name)


def read_mame_cat_ini(path: Path, encoding: str = 'ascii') -> CatMapping:
	"""Parses a category ini (the usual kind with several sections, and basenames as keys + empty values which can appear in multiple sections) into a {section name -> basenames} dict.
	Using ASCII by default because series.ini has borked utf-8 before…
	"""
	with path.open('rt', encoding=encoding) as f:
		d: defaultdict[str, set[Basename]] = defaultdict(set)
		current_section = None
		for line in f:
			# Not sure if it's better to just use RawConfigParser with allow_no_value = True here
			line = line.strip()
			# Don't need to worry about FOLDER_SETTINGS or ROOT_FOLDER sections though I guess this code is gonna put them in there as categories with no basenames in them but eh, that's probably fine
			if line.startswith(';'):
				continue
			if line.startswith('['):
				current_section = line[1:-1]
			elif current_section:
				d[current_section].add(line)
		return d


async def read_mame_cat_ini_async(path: Path, encoding: str = 'ascii') -> CatMapping:
	return await asyncio.to_thread(read_mame_cat_ini, path, encoding)


def _read_ini_auto(path: Path, encoding: str = 'ascii'):
	"""Automatically parses a category file and chooses the right format depending on what it is.
	`encoding` is only used for standard categories for now."""
	# TODO: Should be smarter about this and autodetect based on attempting to load key/values first, or having a single section (though catver has 2), or something
	if path.name == 'nplayers.ini':
		return read_key_value_cat_ini(path, 'NPlayers')
	return read_mame_cat_ini(path, encoding)


async def _read_ini_auto_async(path: Path, encoding: str = 'ascii'):
	if path.name == 'nplayers.ini':
		return path, await read_key_value_cat_ini_async(path, 'NPlayers')
	return path, await read_mame_cat_ini_async(path, encoding)


@cache
def read_cat_folder(cat_folder_path: Path):
	"""Reads an entire directory of category ini files. nplayers is treated specially due to the key/value format."""
	cats: dict[CatName, CatMapping] = {}  # meow

	for file in cat_folder_path.iterdir():
		if file.suffix[1:].lower() != 'ini':
			continue
		cats[file.stem] = _read_ini_auto(file)
	return cats


@alru_cache
async def read_cat_folder_async(cat_folder_path: Path):
	"""Reads an entire directory of category ini files. nplayers is treated specially due to the key/value format."""
	files = await listdir_async(cat_folder_path)
	tasks = [
		asyncio.create_task(_read_ini_auto_async(cat_path))
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
