import datetime
from collections.abc import Collection, Iterator, Mapping, Sequence
from functools import cached_property
from typing import TYPE_CHECKING

from pymame.commands import MAMEExecutable
from pymame.elements.software_list_element import (
	SoftwareListElement,
	get_software_list_element_from_file,
	get_software_list_element_from_file_async,
)
from pymame.support_files.dat import get_dat_folder
from pymame.user_data import TimerDBRow, try_load_timer_db
from pymame.utils import multidict

if TYPE_CHECKING:
	from pymame.elements import PartElement, SoftwareElement
	from pymame.settings import MAMESettings
	from pymame.support_files.history import HistoryEntry
	from pymame.typedefs import SoftwareBasename


class SoftwareList:
	def __init__(self, element: SoftwareListElement, settings: 'MAMESettings'):
		self.element = element
		self.basename = element.basename
		grouping, has_underscore, software_type = self.basename.partition('_')
		self.grouping = grouping
		self.type = software_type if has_underscore else None

		self.settings = settings

	@property
	def name(self) -> str:
		return self.element.name

	@property
	def software_count(self) -> int:
		return len(self.element.software)

	def iter_software(self) -> Iterator['Software']:
		return (
			Software(self, element, self.settings) for element in self.element.software.values()
		)


class Software:
	def __init__(
		self, software_list: SoftwareList, element: 'SoftwareElement', settings: 'MAMESettings'
	):
		self.list = software_list
		self.element = element

		self.settings = settings
		self._dat_folder = get_dat_folder(settings.dats_path) if settings.dats_path else None

	@property
	def id(self) -> str:
		"""Combination of software list basename and basename"""
		return f'{self.list.basename}:{self.basename}'

	@property
	def name(self) -> str:
		"""Human readable name"""
		return self.element.name

	@property
	def basename(self) -> 'SoftwareBasename':
		"""Short name"""
		return self.element.basename

	@property
	def parent_basename(self) -> 'SoftwareBasename | None':
		return self.element.parent_basename

	@property
	def publisher(self) -> str | None:
		# TODO: Handle <doujin> or <homebrew> or other stuff which isn't quite right, albeit I'm not sure what should go there instead, or just None but surely we use the information somehow
		return self.element.publisher

	@property
	def notes(self) -> str | None:
		"""Compatibility notes for the current state of running the software in MAME"""
		notes = self.element.notes
		return notes.strip() if notes else None

	@property
	def info_as_dict(self) -> Mapping[str, Sequence[str | None]]:
		return multidict((info.name, info.value) for info in self.element.infos)

	def get_info(self, name: str) -> str | None:
		return next((info.value for info in self.element.infos if info.name == name), None)

	@property
	def shared_features_as_dict(self) -> Mapping[str, Sequence[str | None]]:
		return multidict(
			(shared_feature.name, shared_feature.value)
			for shared_feature in self.element.shared_features
		)

	def get_shared_feature(self, name: str) -> str | None:
		return next(
			(
				shared_feature.value
				for shared_feature in self.element.shared_features
				if shared_feature.name == name
			),
			None,
		)

	def get_part(self, name: str) -> 'SoftwarePart':
		part_element = self.element.parts_by_name[name]
		return SoftwarePart(self, part_element)

	def get_only_part(self) -> 'SoftwarePart | None':
		parts = self.element.parts
		if len(parts) == 1:
			return SoftwarePart(self, parts[0])
		return None

	def iter_parts(self) -> Iterator['SoftwarePart']:
		return (SoftwarePart(self, element) for element in self.element.parts)

	@property
	def part_names(self) -> Collection[str]:
		return frozenset(part.name for part in self.element.parts)

	@property
	def part_interfaces(self) -> Collection[str]:
		return frozenset(part.interface for part in self.element.parts)

	@cached_property
	def parent(self) -> 'Software | None':
		return (
			get_software(self.list, self.parent_basename, self.settings)
			if self.parent_basename
			else None
		)

	@property
	def parent_name(self) -> str | None:
		parent = self.parent
		return parent.name if parent else None

	@property
	def history(self) -> 'HistoryEntry | None':
		if not self._dat_folder:
			return None
		history = self._dat_folder.get_software_history(self.list.basename, self.basename)
		if not history and self.parent_basename:
			history = self._dat_folder.get_software_history(
				self.list.basename, self.parent_basename
			)
		return history

	@property
	async def history_async(self) -> 'HistoryEntry | None':
		if not self._dat_folder:
			return None
		history = await self._dat_folder.get_software_history_async(
			self.list.basename, self.basename
		)
		if not history and self.parent_basename:
			history = await self._dat_folder.get_software_history_async(
				self.list.basename, self.parent_basename
			)
		return history

	@cached_property
	def _timer_db_row(self) -> TimerDBRow | None:
		if not self.settings.timer_db_path:
			return None
		db = try_load_timer_db(self.settings.timer_db_path)
		if not db:
			return None
		return db.software.get((self.list.basename, self.basename))

	@property
	def total_time_played(self) -> datetime.timedelta:
		time_played = self._timer_db_row
		return time_played.total_time if time_played else datetime.timedelta(0)

	@property
	def play_count(self) -> int:
		time_played = self._timer_db_row
		return time_played.play_count if time_played else 0

	@property
	def total_time_emulated(self) -> datetime.timedelta:
		time_played = self._timer_db_row
		return time_played.emulated_time if time_played else datetime.timedelta(0)


def get_software_list(element: str | SoftwareListElement, settings: 'MAMESettings') -> SoftwareList:
	if isinstance(element, str):
		if settings.list_software_from_file and settings.hash_paths:
			element = get_software_list_element_from_file(settings.hash_paths, element)
		else:
			xml = MAMEExecutable(settings).getsoftlist(element)
			element = SoftwareListElement(xml)
	return SoftwareList(element, settings)


async def get_software_list_async(
	element: str | SoftwareListElement, settings: 'MAMESettings'
) -> SoftwareList:
	if isinstance(element, str):
		if settings.list_software_from_file and settings.hash_paths:
			element = await get_software_list_element_from_file_async(settings.hash_paths, element)
		else:
			xml = await MAMEExecutable(settings).getsoftlist_async(element)
			element = SoftwareListElement(xml)
	return SoftwareList(element, settings)


class SoftwarePart:
	def __init__(self, software: Software, element: 'PartElement'):
		self.software = software
		self.element = element

	@property
	def features_as_dict(self) -> Mapping[str, Sequence[str | None]]:
		return multidict((feature.name, feature.value) for feature in self.element.features)

	def get_feature(self, name: str) -> str | None:
		return next(feature.value for feature in self.element.features if feature.name == name)

	@property
	def dipswitch_names(self) -> Collection[str]:
		return frozenset(dipswitch.name for dipswitch in self.element.dipswitches)


def get_software(
	software_list: str | SoftwareList | SoftwareListElement,
	software: 'str | SoftwareElement',
	settings: 'MAMESettings',
):
	if isinstance(software_list, str):
		software_list = get_software_list(software_list, settings)
	if isinstance(software_list, SoftwareListElement):
		software_list = SoftwareList(software_list, settings)

	if isinstance(software, str):
		return Software(software_list, software_list.element.software[software], settings)
	return Software(software_list, software, settings)

async def get_software_async(
	software_list: str | SoftwareList | SoftwareListElement,
	software: 'str | SoftwareElement',
	settings: 'MAMESettings',
):
	if isinstance(software_list, str):
		software_list = await get_software_list_async(software_list, settings)
	if isinstance(software_list, SoftwareListElement):
		software_list = SoftwareList(software_list, settings)

	if isinstance(software, str):
		return Software(software_list, software_list.element.software[software], settings)
	return Software(software_list, software, settings)
