import asyncio
import re
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

from pymame.elements import HistoryXML
from pymame.utils import try_parse_int
from pymame.xml_wrapper import get_xml_reader

if TYPE_CHECKING:
	from pymame.typedefs import Basename, SoftwareBasename, SoftwareListBasename


def read_history_xml(path: Path) -> HistoryXML | None:
	try:
		with path.open('rb') as f:
			return HistoryXML(get_xml_reader().read_from_file(f))
	except FileNotFoundError:
		return None


async def read_history_xml_async(path: Path) -> HistoryXML | None:
	return await asyncio.to_thread(read_history_xml, path)


_line_pattern = re.compile(r'\n- (.+) -\n')


def parse_info_sections(text: str) -> dict[str, str]:
	"""Parses the actual text from history.xml, etc. into sections, delimited by - SECTION -.

	Returns:
		dict of {section: contents}, the start is stored with a key of an empty string.
	"""
	sections = {}
	section = ''
	for i, group in enumerate(_line_pattern.split(text)):
		if i % 2:
			# Every second element from the split will be a section header
			section = group
		else:
			sections[section] = group.strip()

	return sections


_start_line_pattern = re.compile(r'(?P<type>.+) published (?P<age>.+) years ago:')


class HistoryEntry:
	"""Wrapper around the actual text of a history entry, to make getting sections easier."""

	def __init__(self, text: str) -> None:
		self.sections = parse_info_sections(text)

	@cached_property
	def _start(self) -> tuple[str | None, str | None, str | None]:
		# Returns type, age, the rest of the text
		start = self.sections.get('')
		if start is None:
			# Shouldn't happen, but might as well handle this case
			return None, None, None
		start_match = _start_line_pattern.match(start)
		if start_match is None:
			return None, None, start
		return start_match['type'], start_match['age'], start[start_match.end() + 1 :].strip()

	@property
	def entry_type(self):
		return self._start[0]

	@property
	def age(self):
		"""Years ago (since the history file was updated)"""
		return try_parse_int(self._start[1])

	@property
	def description(self):
		return self._start[2]

	@property
	def technical_info(self):
		return self.sections.get('TECHNICAL')

	@property
	def trivia(self):
		return self.sections.get('TRIVIA')

	@property
	def tips_and_tricks(self):
		return self.sections.get('TIPS AND TRICKS')

	@property
	def updates(self):
		return self.sections.get('UPDATES')

	@property
	def scoring(self):
		return self.sections.get('SCORING')

	@property
	def series_info(self):
		return self.sections.get('SERIES')

	@property
	def staff(self):
		return self.sections.get('STAFF')

	@property
	def ports(self):
		return self.sections.get('PORTS')

	@property
	def cast(self):
		# maybe also appears as CAST OF ELEMENTS?
		return self.sections.get('CAST OF CHARACTERS')

	@property
	def other_sections(self):
		return {
			k: v
			for k, v in self.sections.items()
			if k
			not in {
				'',
				'TECHNICAL',
				'TRIVIA',
				'TIPS AND TRICKS',
				'UPDATES',
				'SCORING',
				'SERIES',
				'STAFF',
				'PORTS',
				'CAST OF CHARACTERS',
			}
		}


class HistoryDB:
	"""Wrapper for history.xml. No I/O here, as it takes as an argument a HistoryXML that has already been loaded."""

	def __init__(self, xml: HistoryXML) -> None:
		self.xml = xml
		self.system_histories = tuple(self.xml.iter_system_histories())
		self.software_histories = tuple(self.xml.iter_software_histories())

	def get_history(self, basename: 'Basename'):
		for entry_basename, entry in self.system_histories:
			if basename == entry_basename:
				return HistoryEntry(entry)
		return None

	def get_software_history(
		self, software_list_name: 'SoftwareListBasename', software_basename: 'SoftwareBasename'
	):
		for entry_softlist_name, entry_software_name, entry in self.software_histories:
			if (
				software_list_name == entry_softlist_name
				and software_basename == entry_software_name
			):
				return HistoryEntry(entry)
		return None
