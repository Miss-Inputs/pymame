import asyncio
import datetime
import logging
from collections.abc import Collection, Mapping, Sequence
from fractions import Fraction
from functools import cached_property
from typing import TYPE_CHECKING

from pymame.commands import MAMEExecutable
from pymame.elements.common_elements import DumpStatus
from pymame.elements.config import Counters
from pymame.elements.machine_element import (
	ChipElement,
	ChipType,
	DisplayElement,
	MachineElement,
	get_machine_elements_from_file_as_dict,
	get_machine_elements_from_file_as_dict_async,
)
from pymame.support_files import CategoryFolder, HistoryEntry, MAMEInfoEntry
from pymame.support_files.dat import get_dat_folder
from pymame.user_data import (
	TimerDBRow,
	get_counters,
	get_counters_async,
	get_favourites,
	get_favourites_async,
	try_load_timer_db,
)
from pymame.utils import try_parse_int

from .catlist import CatlistCategory, MachineType

if TYPE_CHECKING:
	from pymame.elements.config import Counters
	from pymame.settings import MAMESettings
	from pymame.typedefs import Basename, SoftwareListBasename

logger = logging.getLogger(__name__)


class Display:
	def __init__(self, element: 'DisplayElement'):
		self.element = element

	@property
	def resolution(self):
		if self.element.width is None or self.element.height is None:
			return None
		return self.element.width * self.element.height

	@property
	def aspect_ratio(self):
		if self.element.width is None or self.element.height is None:
			return None
		return Fraction(self.element.width, self.element.height)


def _get_machine_element(
	settings: 'MAMESettings', basename: 'Basename | MachineElement'
) -> MachineElement:
	if isinstance(basename, MachineElement):
		return basename
	if settings.xml_path:
		return get_machine_elements_from_file_as_dict(settings.xml_path)[basename]
	executable = MAMEExecutable(settings)
	xml = executable.listxml(basename)
	return MachineElement(xml)


async def _get_machine_element_async(
	settings: 'MAMESettings', basename: 'Basename | MachineElement'
) -> MachineElement:
	if isinstance(basename, MachineElement):
		return basename
	if settings.xml_path:
		elements = await get_machine_elements_from_file_as_dict_async(settings.xml_path)
		return elements[basename]

	executable = MAMEExecutable(settings)
	xml = await executable.listxml_async(basename)
	return MachineElement(xml)


class Machine:
	"""Machine element and all info related to it, and any method that might be remotely convenient."""

	# Should these methods be sorted/organized in some way? Probably! Oh well
	def __init__(
		self,
		element: 'MachineElement',
		settings: 'MAMESettings',
		category_folder: CategoryFolder | None,
		parent: 'Machine | None',
		bios: 'Machine | None',
	) -> None:
		"""Constructor not necessarily intended to be called normally, because it's a bit wacky
		We get the machine's parent and bios at initialization so it can work with both sync and async, instead of having to call get_machine later which would then potentially be in an async loop"""
		self.element = element
		self.settings = settings
		self.category_folder = category_folder

		self.parent = parent
		self.bios = bios

		self._executable = MAMEExecutable(settings)
		self._dat_folder = get_dat_folder(settings.dats_path) if settings.dats_path else None
		self._counters: Counters | None = None
		self._lock = asyncio.Lock()

	@property
	def name(self) -> str:
		"""Human readable name"""
		return self.element.name

	@property
	def basename(self) -> 'Basename':
		return self.element.basename

	def __str__(self) -> str:
		return f'{self.basename} ({self.name})'

	@property
	def parent_basename(self) -> 'Basename | None':
		return self.element.parent_basename

	@cached_property
	def catlist_full(self) -> str | None:
		"""raw section name from catlist before we parse it with CatlistCategory"""
		if not self.category_folder:
			return None
		catlist = self.category_folder.get_cat('catlist', self.basename)
		if catlist is None and self.parent_basename:
			# Presumably, any clone set (that is newer than the catlist file but the parent set is in there) is the same sort of thing
			catlist = self.category_folder.get_cat('catlist', self.parent_basename)
		return catlist

	@cached_property
	def catlist(self) -> CatlistCategory | None:
		return CatlistCategory(self.catlist_full) if self.catlist_full else None

	@property
	def genre(self) -> str | None:
		return self.catlist.genre if self.catlist else None

	@property
	def subgenre(self) -> str | None:
		return self.catlist.subgenre if self.catlist else None

	@property
	def parent_name(self) -> str | None:
		parent = self.parent
		return parent.name if parent else None

	@property
	def manufacturer(self) -> str | None:
		return self.element.manufacturer

	platform_prefixes: Mapping[str, MachineType] = {
		'Game & Watch': MachineType.LCDHandheld,
		'R-Zone': MachineType.ConsoleCartridge,
	}
	"""Prefixes to machine name that indicate this is a different machine type, and a particular platform"""
	platform_suffixes: Mapping[str, MachineType] = {
		'XaviXPORT': MachineType.ConsoleCartridge,
		'CPS Changer': MachineType.ConsoleCartridge,
		'Domyos Interactive System': MachineType.ConsoleCartridge,
	}
	"""Suffixes in parentheses to machine name that indicate this is a different machine type, and a particular platform"""

	@property
	def _is_arcade(self) -> bool:
		if self.catlist and self.catlist.machine_type == MachineType.Arcade:
			return True
		return self.element.number_of_coin_slots > 0

	@property
	def _platform_prefix(self) -> tuple[str, MachineType] | None:
		for prefix, machine_type in self.platform_prefixes.items():
			if self.name.startswith(f'{prefix}: '):
				return prefix, machine_type
		return None

	@property
	def _platform_suffix(self) -> tuple[str, MachineType] | None:
		for suffix, machine_type in self.platform_suffixes.items():
			if ' (' in self.name and suffix in self.name.split(' (', 1)[1]:
				return suffix, machine_type
		return None

	@property
	def machine_type(self) -> MachineType:
		if self._platform_prefix:
			return self._platform_prefix[1]
		if self._platform_suffix:
			return self._platform_suffix[1]
		if self.element.is_bios:
			return MachineType.BIOS
		if self.catlist:
			return self.catlist.machine_type

		if self._is_arcade:
			return MachineType.Arcade
		if self.is_mechanical:
			return MachineType.Mechanical

		return MachineType.Other

	@property
	def platform(self) -> str | None:
		if self._platform_prefix:
			return self._platform_prefix[0]
		if self._platform_suffix:
			return self._platform_suffix[0]
		# TODO: More advanced platform parsing:
		# If Game Console, Plug & Play if it has no media slots, or if it is Vii or has JAKKS in the name?
		# MultiGame / Compilation and Music Game / Dance are probably misplaced plug & play games?
		if self.machine_type == MachineType.PlugAndPlay:
			return 'Plug & Play'
		if self.machine_type == MachineType.MedalGame:
			return 'Medal Game'
		return self.machine_type.name

	@property
	def is_mechanical(self) -> bool:
		return self.element.is_mechanical

	@property
	def requires_artwork(self) -> bool:
		return self.element.driver.requires_artwork if self.element.driver else False

	@property
	def is_incomplete(self) -> bool:
		return self.element.driver.is_incomplete if self.element.driver else False

	@property
	def is_unofficial(self) -> bool:
		return self.element.driver.is_unofficial if self.element.driver else False

	@property
	def no_sound_hardware(self) -> bool:
		return self.element.driver.no_sound_hardware if self.element.driver else False

	@property
	def requires_chds(self) -> bool:
		"""Hmm... should this include where all <disk> has status == "nodump"? e.g. Dragon's Lair has no CHD dump, would it be useful to say that it requires CHDs because it's supposed to have one but doesn't, or not, because you have a good romset without one
		I guess I should have a look at how the MAME inbuilt UI does this"""
		return any(not disk.is_optional for disk in self.element.disks)

	@property
	def is_romless(self) -> bool:
		if self.requires_chds:
			return False

		return not any(rom.status != DumpStatus.NoDump for rom in self.element.roms)

	@cached_property
	def bios_basename(self) -> 'Basename | None':
		if self.element.bios_basename and (self.element.bios_basename == self.parent_basename):
			assert self.parent, f'wtf {self} has no parent but it has a parent basename?'
			return self.parent.bios_basename
		return self.element.bios_basename

	@cached_property
	def bios_name(self) -> str | None:
		return self.bios.name if self.bios else None

	def find_if_have_artwork(self) -> bool:
		if self.settings.artwork_paths:
			return any(
				self.basename in (item.stem for item in path.iterdir())
				for path in self.settings.artwork_paths
			)
		# Assume we don't have artwork if our artwork dir is unknown/not configured
		return False

	async def find_if_have_artwork_async(self) -> bool:
		return await asyncio.to_thread(self.find_if_have_artwork)

	def get_messinfo_summary(self) -> str | None:
		if not self._dat_folder:
			return None
		messinfo = self._dat_folder.get_dat_info('messinfo', self.basename)
		if not messinfo:
			return None
		return messinfo.split('\nDRIVER:', 1)[0]

	async def get_messinfo_summary_async(self) -> str | None:
		if not self._dat_folder:
			return None
		messinfo = await self._dat_folder.get_dat_info_async('messinfo', self.basename)
		if not messinfo:
			return None
		return messinfo.split('\nDRIVER:', 1)[0]

	def get_mameinfo(self) -> MAMEInfoEntry | None:
		if not self._dat_folder:
			return None
		entry = self._dat_folder.get_dat_info('mameinfo', self.basename)
		if not entry:
			return None
		return MAMEInfoEntry(entry)

	async def get_mameinfo_async(self) -> MAMEInfoEntry | None:
		if not self._dat_folder:
			return None
		entry = await self._dat_folder.get_dat_info_async('mameinfo', self.basename)
		if not entry:
			return None
		return MAMEInfoEntry(entry)

	@property
	def media_slot_tags(self) -> Collection[str]:
		return {
			media_slot.tag
			for media_slot in self.element.media_slots
			if media_slot.tag and not media_slot.is_fixed_image
		}

	@property
	def media_slot_types(self) -> Collection[str]:
		return {
			media_slot.type
			for media_slot in self.element.media_slots
			if media_slot.tag and not media_slot.is_fixed_image
		}

	@property
	def slot_names(self) -> Collection[str]:
		return {slot.name for slot in self.element.slots}

	@property
	def software_list_names(self) -> Collection['SoftwareListBasename']:
		return {software_list.name for software_list in self.element.software_lists}

	@property
	def control_types(self) -> Collection[str]:
		# could also get_cats('Control')
		return self.element.input.control_types if self.element.input else set()

	@cached_property
	def devices(self) -> 'Sequence[Machine]':
		return [
			get_machine(self.settings, device_ref.name) for device_ref in self.element.device_refs
		]

	async def get_devices_async(self) -> 'Sequence[Machine]':
		return [
			await get_machine_async(self.settings, device_ref.name, self.category_folder)
			for device_ref in self.element.device_refs
		]

	def get_device_names(self) -> Sequence[str]:
		return [
			_get_machine_element(self.settings, device_ref.name).name
			for device_ref in self.element.device_refs
		]

	async def get_device_names_async(self) -> Sequence[str]:
		return [
			(await _get_machine_element_async(self.settings, device_ref.name)).name
			for device_ref in self.element.device_refs
		]

	@cached_property
	def _timer_db_row(self) -> TimerDBRow | None:
		if not self.settings.timer_db_path:
			return None
		db = try_load_timer_db(self.settings.timer_db_path)
		if not db:
			return None
		return db.systems.get(self.basename)

	@property
	def total_time_played(self):
		time_played = self._timer_db_row
		return time_played.total_time if time_played else datetime.timedelta(0)

	@property
	def play_count(self):
		time_played = self._timer_db_row
		return time_played.play_count if time_played else 0

	@property
	def total_time_emulated(self):
		time_played = self._timer_db_row
		return time_played.emulated_time if time_played else datetime.timedelta(0)

	def _get_cats(self, cat: str, *, fallback_parent: bool = False) -> Collection[str]:
		if not self.category_folder:
			return ()
		cats = self.category_folder.get_cats(cat, self.basename)
		if not cats and fallback_parent and self.parent_basename:
			return self.category_folder.get_cats(cat, self.parent_basename)
		return cats

	def _get_cat(self, cat: str, *, fallback_parent: bool = False) -> str | None:
		if not self.category_folder:
			return None
		cat_value = self.category_folder.get_cat(cat, self.basename)
		if not cat_value and fallback_parent and self.parent_basename:
			return self.category_folder.get_cat(cat, self.parent_basename)
		return cat_value

	@property
	def series(self):
		return self._get_cats('series', fallback_parent=True)

	@property
	def is_mature(self) -> bool | None:
		"""Returns None if unsure"""
		in_mature = self._get_cat('mature', fallback_parent=True)
		if in_mature:
			return True
		in_not_mature = self._get_cat('not_mature', fallback_parent=True)
		if in_not_mature:
			return False
		if self.catlist:
			return self.catlist.is_mature
		return None

	def get_is_favourite(self) -> bool:
		if not self.settings.ui_path:
			return False
		return self.basename in get_favourites(self.settings.ui_path)

	async def get_is_favourite_async(self) -> bool:
		if not self.settings.ui_path:
			return False
		return self.basename in await get_favourites_async(self.settings.ui_path)

	@property
	def cabinet_types(self):
		return self._get_cats('cabinets')

	@property
	def languages(self):
		return self._get_cats('languages')

	@property
	def has_free_play(self) -> bool:
		# TODO: Also detect by dipswitches or something
		return bool(self._get_cat('freeplay'))

	@property
	def monochrome_type(self) -> str | None:
		return self._get_cat('monochrome')

	def _get_counters(self) -> 'Counters | None':
		if self._counters is None:
			self._counters = get_counters(self.settings, self.basename)
		return self._counters

	async def _get_counters_async(self) -> 'Counters | None':
		async with self._lock:
			if self._counters:
				return self._counters
			self._counters = await get_counters_async(self.settings, self.basename)
			return self._counters

	def get_tickets_dispensed(self) -> int | None:
		counters = self._get_counters()
		return counters.tickets if counters else None

	async def get_tickets_dispensed_async(self) -> int | None:
		counters = await self._get_counters_async()
		return counters.tickets if counters else None

	@property
	def number_of_players_description(self):
		if self.category_folder:
			nplayers = self.category_folder.get_cat('nplayers', self.basename)
			if nplayers:
				return nplayers
		return str(self.number_of_players)

	@property
	def version_added(self) -> str | None:
		return self._get_cat('version')

	@property
	def bestgames_rating_name(self) -> str | None:
		return self._get_cat('bestgames')

	@property
	def bestgames_rating(self) -> int | None:
		bestgames = self.bestgames_rating_name
		if bestgames:
			return int(bestgames.split(' ', 1)[0]) + 10
		return None

	def get_history(self) -> HistoryEntry | None:
		return self._dat_folder.get_history(self.basename) if self._dat_folder else None

	async def get_history_async(self) -> HistoryEntry | None:
		return await self._dat_folder.get_history_async(self.basename) if self._dat_folder else None

	@property
	def number_of_players(self) -> int:
		return (self.element.input.number_of_players or 0) if self.element.input else 0

	@property
	def decade(self) -> int | None:
		"""Decade this machine was released in, even if the exact year is unknown (as an int of the start year, e.g. 1990)"""
		# I think this is also in Alltime.ini? But that's not needed
		if not self.element.raw_year:
			return None
		i = try_parse_int(self.element.raw_year[:3])
		return None if i is None else i * 10

	@property
	def century(self) -> int | None:
		if not self.element.raw_year:
			return None
		i = try_parse_int(self.element.raw_year[:2])
		return None if i is None else i * 100

	@property
	def cpus(self) -> Sequence[ChipElement]:
		return tuple(chip for chip in self.element.chips if chip.type == ChipType.CPU)

	@property
	def audio_chips(self) -> Sequence[ChipElement]:
		return tuple(chip for chip in self.element.chips if chip.type == ChipType.Audio)

	@property
	def display_count(self):
		return len(self.element.displays)

	@property
	def displays(self) -> Sequence[Display]:
		return tuple(Display(disp) for disp in self.element.displays)


def get_machine(
	settings: 'MAMESettings',
	basename_or_element: 'Basename | MachineElement',
	category_folder: CategoryFolder | None = None,
) -> Machine:
	if category_folder is None:
		category_folder = (
			CategoryFolder.load_from_folder(settings.cat_path) if settings.cat_path else None
		)
	element = _get_machine_element(settings, basename_or_element)
	parent = (
		get_machine(settings, element.parent_basename, category_folder)
		if element.parent_basename
		else None
	)
	bios = (
		get_machine(settings, element.bios_basename, category_folder)
		if element.bios_basename
		else None
	)
	return Machine(element, settings, category_folder, parent, bios)


async def get_machine_async(
	settings: 'MAMESettings',
	basename_or_element: 'Basename | MachineElement',
	category_folder: CategoryFolder | None = None,
) -> Machine:
	if category_folder is None:
		category_folder = (
			await CategoryFolder.load_from_folder_async(settings.cat_path)
			if settings.cat_path
			else None
		)

	element = await _get_machine_element_async(settings, basename_or_element)
	parent = (
		await get_machine_async(settings, element.parent_basename, category_folder)
		if element.parent_basename
		else None
	)
	bios_basename = parent.bios_basename if parent else element.bios_basename
	bios = (
		await get_machine_async(settings, bios_basename, category_folder) if bios_basename else None
	)
	return Machine(element, settings, category_folder, parent, bios)
