"""Type hinted/convenience wrapper around XML elements, from -listxml DTD"""

import asyncio
import logging
from collections.abc import Iterator, Mapping, Sequence
from enum import StrEnum
from functools import cache, cached_property
from pathlib import Path, PurePath
from typing import IO, TYPE_CHECKING

from async_lru import alru_cache

from pymame.utils import try_parse_hexbytes, try_parse_int, try_parse_strenum
from pymame.xml_wrapper import ElementWrapper, XMLElementType_co, XMLReader, get_xml_reader

from .common_elements import DipswitchValueElement, DumpStatus, NamedElement

if TYPE_CHECKING:
	from pymame.typedefs import Basename, SoftwareListBasename

logger = logging.getLogger(__name__)


class BIOSSetElement(ElementWrapper):
	@property
	def name(self) -> str:
		return self.xml.attrib['name']

	@property
	def description(self) -> str:
		"""Human readable name"""
		return self.xml.attrib['description']

	@property
	def is_default(self) -> bool:
		return self.xml.attrib.get('default', 'no') == 'yes'


class ROMElement(ElementWrapper):
	"""<rom> element inside machine"""

	@property
	def name(self) -> str:
		return self.xml.attrib['name']

	@property
	def size(self) -> int | None:
		# I think this is always decimal?
		return try_parse_int(self.xml.attrib['size'])

	@property
	def part_of_bios(self) -> str | None:
		return self.xml.attrib.get('bios')

	@property
	def crc(self) -> int | None:
		return try_parse_int(self.xml.attrib.get('crc'), 16)

	@property
	def sha1(self) -> bytes | None:
		return try_parse_hexbytes(self.xml.attrib.get('sha1'))

	@property
	def merge(self) -> str | None:
		# Need to remember if this is the name of the file in the child and name is the one in the parent, or the other way around
		return self.xml.attrib.get('merge')

	@property
	def region(self) -> str | None:
		return self.xml.attrib.get('region')

	@property
	def offset(self) -> int:
		return try_parse_int(self.xml.attrib.get('offset')) or 0

	@property
	def status(self) -> DumpStatus:
		return DumpStatus(self.xml.attrib.get('status', 'good'))

	@property
	def is_optional(self) -> bool:
		return self.xml.attrib.get('optional', 'no') == 'yes'


class DiskElement(ElementWrapper):
	@property
	def name(self) -> str:
		return self.xml.attrib['name']

	@property
	def sha1(self) -> bytes | None:
		return try_parse_hexbytes(self.xml.attrib.get('sha1'))

	@property
	def merge(self) -> str | None:
		# Need to remember if this is the name of the file in the child and name is the one in the parent, or the other way around
		return self.xml.attrib.get('merge')

	@property
	def region(self) -> str | None:
		return self.xml.attrib.get('region')

	@property
	def index(self) -> int | None:
		# Should this default to 0?
		return try_parse_int(self.xml.attrib.get('index'))

	@property
	def is_writable(self) -> bool:
		return self.xml.attrib.get('writable', 'no') == 'yes'

	@property
	def status(self) -> DumpStatus:
		return DumpStatus(self.xml.attrib.get('status', 'good'))

	@property
	def is_optional(self) -> bool:
		return self.xml.attrib.get('optional', 'no') == 'yes'


class ChipType(StrEnum):
	CPU = 'cpu'
	Audio = 'audio'


class ChipElement(ElementWrapper):
	@property
	def name(self) -> str:
		return self.xml.attrib['name']

	@property
	def tag(self) -> str | None:
		return self.xml.attrib.get('tag')

	@property
	def type(self) -> ChipType:
		return ChipType(self.xml.attrib['type'])

	@property
	def clock_speed(self) -> int | None:
		"""Hz"""
		return try_parse_int(self.xml.attrib.get('clock'))


class DisplayType(StrEnum):
	Raster = 'raster'
	Vector = 'vector'
	LCD = 'lcd'
	SVG = 'svg'
	Unknown = 'unknown'


class DisplayElement(ElementWrapper):
	@property
	def tag(self) -> str | None:
		return self.xml.attrib.get('tag')

	@property
	def type(self) -> DisplayType:
		"""raster, vector, lcd, svg, unknown"""
		return DisplayType(self.xml.attrib['type'])

	@property
	def rotation(self) -> int | None:
		"""Always one of 0, 90, 180, 270 (or none)"""
		return try_parse_int(self.xml.attrib.get('rotate'))

	@property
	def flip_x(self) -> bool:
		return self.xml.attrib.get('flipx', 'no') == 'yes'

	@property
	def width(self) -> int | None:
		"""Pixels"""
		return try_parse_int(self.xml.attrib.get('width'))

	@property
	def height(self) -> int | None:
		"""Pixels"""
		return try_parse_int(self.xml.attrib.get('height'))

	@property
	def refresh_rate(self) -> float:
		"""Hz"""
		return float(self.xml.attrib['refresh'])

	@property
	def pixel_clock(self) -> int | None:
		return try_parse_int(self.xml.attrib.get('pixclock'))

	@property
	def horizontal_total(self) -> int | None:
		return try_parse_int(self.xml.attrib.get('htotal'))

	@property
	def horizontal_bend(self) -> int | None:
		return try_parse_int(self.xml.attrib.get('hbend'))

	@property
	def horizontal_blank_start(self) -> int | None:
		return try_parse_int(self.xml.attrib.get('hbstart'))

	@property
	def vertical_total(self) -> int | None:
		return try_parse_int(self.xml.attrib.get('vtotal'))

	@property
	def vertical_bend(self) -> int | None:
		return try_parse_int(self.xml.attrib.get('vbend'))

	@property
	def vertical_blank_start(self) -> int | None:
		return try_parse_int(self.xml.attrib.get('vbstart'))


class SoundElement(ElementWrapper):
	@property
	def number_of_channels(self) -> int:
		return int(self.xml.attrib['channels'])


class ConditionRelation(StrEnum):
	Eq = 'eq'
	Ne = 'ne'
	Gt = 'gt'
	Lt = 'lt'
	Le = 'le'
	Ge = 'ge'


class ConditionElement(ElementWrapper):
	@property
	def tag(self) -> str:
		return self.xml.attrib['tag']

	@property
	def mask(self) -> str:
		return self.xml.attrib['mask']

	@property
	def relation(self) -> ConditionRelation:
		return ConditionRelation(self.xml.attrib['relation'])

	@property
	def value(self) -> int:
		return int(self.xml.attrib['value'])


class StickWays(StrEnum):
	"""Which ways a joystick goes"""

	FourWay = '4'
	"""The normal way"""
	EightWay = '8'
	"""Including diagonal"""
	LeftRight = '2'
	UpDown = 'vertical2'
	OneWay = '1'
	ThreeWay = '3 (half4)'
	"""Missing one direction, e.g. just up + left + right"""
	FiveWay = '5 (half8)'
	Strange = 'strange2'


class ControlElement(ElementWrapper):
	@property
	def type(self) -> str:
		# The DTD does not define a list of control types, so we also shall not
		return self.xml.attrib['type']

	@property
	def number_of_buttons(self) -> int:
		return try_parse_int(self.xml.attrib.get('buttons')) or 0

	@property
	def joystick_ways(self) -> int | None:
		return try_parse_int(self.xml.attrib.get('ways'))

	@property
	def player_num(self) -> int:
		"""Which player this control is for, starting at player 1"""
		return try_parse_int(self.xml.attrib.get('player')) or 1

	@property
	def is_reversed(self) -> bool:
		return self.xml.attrib.get('reverse', 'no') == 'yes'

	@property
	def minimum_analog_value(self) -> int | None:
		return try_parse_int(self.xml.attrib.get('minimum'))

	@property
	def maximum_analog_value(self) -> int | None:
		return try_parse_int(self.xml.attrib.get('maximum'))

	@property
	def sensitivity(self) -> int | None:
		return try_parse_int(self.xml.attrib.get('sensitivity'))

	@property
	def keydelta(self) -> int | None:
		"""Something for analog controls?"""
		return try_parse_int(self.xml.attrib.get('keydelta'))

	@property
	def required_buttons(self) -> int:
		return try_parse_int(self.xml.attrib.get('reqbuttons')) or 0

	@property
	def stick_ways(self) -> StickWays | None:
		"""How many directions the main joystick goes in"""
		ways = self.xml.attrib.get('ways')
		if ways is None:
			return None
		return StickWays(ways)

	@property
	def all_stick_ways(self) -> Sequence[StickWays]:
		return [StickWays(ways) for key, ways in self.xml.attrib.items() if key.startswith('ways')]


class InputElement(ElementWrapper):
	@cached_property
	def controls(self) -> Sequence[ControlElement]:
		return tuple(ControlElement(control) for control in self.xml.iter('control'))

	@property
	def coin_slots(self) -> int | None:
		return try_parse_int(self.xml.attrib.get('coins'))

	@property
	def number_of_players(self) -> int | None:
		return try_parse_int(self.xml.attrib.get('players'))

	@property
	def control_types(self) -> set[str]:
		return {control.type for control in self.controls}

	@property
	def has_service(self) -> bool:
		return self.xml.attrib.get('service', 'no') == 'yes'

	@property
	def has_tilt(self) -> bool:
		return self.xml.attrib.get('tilt', 'no') == 'yes'


class DipswitchLocationElement(ElementWrapper):
	@property
	def name(self) -> str:
		return self.xml.attrib['name']

	@property
	def number(self) -> str:
		return self.xml.attrib['number']

	@property
	def is_inverted(self) -> bool:
		return self.xml.attrib.get('inverted', 'no') == 'yes'


class DipswitchElement(ElementWrapper):
	@cached_property
	def locations(self) -> Sequence[DipswitchLocationElement]:
		return tuple(
			DipswitchLocationElement(diplocation) for diplocation in self.xml.iter('diplocation')
		)

	@cached_property
	def values(self) -> Sequence[DipswitchValueElement]:
		return tuple(DipswitchValueElement(dipvalue) for dipvalue in self.xml.iter('dipvalue'))

	@property
	def name(self) -> str:
		return self.xml.attrib['name']

	@property
	def tag(self) -> str:
		return self.xml.attrib['tag']

	@property
	def mask(self) -> str:
		"""always numeric?"""
		return self.xml.attrib['mask']

	@property
	def default_value(self) -> DipswitchValueElement | None:
		return next((value for value in self.values if value.is_default), None)

	@property
	def condition(self) -> ConditionElement | None:
		element = self.xml.find_first('condition')
		if element is None:
			return None
		return ConditionElement(element)


class ConfigLocationElement(ElementWrapper):
	@property
	def name(self) -> str:
		return self.xml.attrib['name']

	@property
	def number(self) -> str:
		"""Presumably numeric, but I havne't seen one in the wild"""
		return self.xml.attrib['name']

	@property
	def inverted(self) -> bool:
		return self.xml.attrib.get('inverted', 'no') == 'yes'


class ConfigSettingElement(ElementWrapper):
	@property
	def name(self) -> str:
		return self.xml.attrib['name']

	@property
	def value(self) -> str:
		"""Seemingly always numeric?"""
		return self.xml.attrib['value']

	@property
	def is_default(self) -> bool:
		return self.xml.attrib.get('default', 'no') == 'yes'


class ConfigurationElement(ElementWrapper):
	@property
	def name(self) -> str:
		return self.xml.attrib['name']

	@property
	def tag(self) -> str:
		return self.xml.attrib['tag']

	@property
	def mask(self) -> str:
		"""always numeric?"""
		return self.xml.attrib['mask']

	@cached_property
	def locations(self) -> Sequence[ConfigLocationElement]:
		return tuple(
			ConfigLocationElement(conflocation) for conflocation in self.xml.iter('conflocation')
		)

	@cached_property
	def settings(self) -> Sequence[ConfigSettingElement]:
		return tuple(
			ConfigSettingElement(confsetting) for confsetting in self.xml.iter('confsetting')
		)


class AnalogElement(ElementWrapper):
	@property
	def mask(self) -> str:
		"""always numeric?"""
		return self.xml.attrib['mask']


class PortElement(ElementWrapper):
	@property
	def tag(self) -> str:
		return self.xml.attrib['tag']

	@cached_property
	def analog(self) -> Sequence[AnalogElement]:
		return tuple(AnalogElement(analog) for analog in self.xml.iter('analog'))


class AdjusterElement(ElementWrapper):
	"""Adjustable things like monitor sync, sound volume, etc"""

	@property
	def name(self) -> str:
		"""Human readable"""
		return self.xml.attrib['name']

	@property
	def default(self) -> int:
		return int(self.xml.attrib['default'])


class DriverStatus(StrEnum):
	Good = 'good'
	Imperfect = 'imperfect'
	Preliminary = 'preliminary'


class DriverElement(ElementWrapper):
	@property
	def status(self) -> DriverStatus:
		return DriverStatus(self.xml.attrib['status'])

	@property
	def emulation_status(self) -> DriverStatus:
		return DriverStatus(self.xml.attrib['emulation'])

	@property
	def savestate_supported(self) -> bool:
		return self.xml.attrib['savestate'] == 'supported'

	@property
	def cocktail_status(self) -> DriverStatus | None:
		return try_parse_strenum(self.xml.attrib.get('cocktail'), DriverStatus)

	@property
	def requires_artwork(self) -> bool:
		"""Added in MAME 0.229, we assume nothing before then requires artwork, since it is assumed that if the element is missing in newer versions it does not require artwork"""
		return self.xml.attrib.get('requiresartwork', 'no') == 'yes'

	@property
	def is_unofficial(self) -> bool:
		"""Added in MAME 0.229, we assume everything before then is official"""
		return self.xml.attrib.get('unofficial', 'no') == 'yes'

	@property
	def no_sound_hardware(self) -> bool:
		"""Added in MAME 0.229, we assume everything before then has sound hardware"""
		return self.xml.attrib.get('nosoundhardware', 'no') == 'yes'

	@property
	def is_incomplete(self) -> bool:
		"""Added in MAME 0.229, we assume everything before then is complete"""
		return self.xml.attrib.get('incomplete', 'no') == 'yes'


class FeatureStatus(StrEnum):
	"""There is no "good" value, if a feature is good, then it doesn't get mentioned"""

	Imperfect = 'imperfect'
	Unemulated = 'unemulated'


class FeatureElement(ElementWrapper):
	@property
	def type(self) -> str:
		# valid types are specified in the dtd, but maybe we don't want to impose that requirement as stuff is added in new MAME versions
		# <!ATTLIST feature type (protection|timing|graphics|palette|sound|capture|camera|microphone|controls|keyboard|mouse|media|disk|printer|tape|punch|drum|rom|comms|lan|wan) #REQUIRED>
		return self.xml.attrib['type']

	@property
	def status(self) -> FeatureStatus | None:
		# Not sure what the difference between status and overall is? But it seems to only have one or the other
		return try_parse_strenum(
			self.xml.attrib.get('status', self.xml.attrib.get('overall')), FeatureStatus
		)


class DeviceInstanceElement(ElementWrapper):
	@property
	def name(self) -> str:
		return self.xml.attrib['name']

	@property
	def briefname(self) -> str:
		return self.xml.attrib['briefname']


class MediaDeviceElement(ElementWrapper):
	"""Not a machine which is a device, but <device> underneath <machine>, which is used for media slots and has a weird name"""

	@cached_property
	def instance(self):
		instance_xml = self.xml.find_first('instance')
		return DeviceInstanceElement(instance_xml) if instance_xml is not None else None

	@property
	def type(self) -> str:
		return self.xml.attrib['type']

	@property
	def tag(self) -> str | None:
		return self.xml.attrib.get('tag')

	@property
	def is_fixed_image(self) -> bool:
		return self.xml.attrib.get('fixed_image') == '1'

	@property
	def is_mandatory(self) -> bool:
		# no default specified in DTD?
		return self.xml.attrib.get('mandatory') == '1'

	@property
	def interface(self) -> str | None:
		# Might be comma separated?
		return self.xml.attrib.get('interface')

	@property
	def extensions(self) -> set[str]:
		"""File extensions intended to be used"""
		return {extension.attrib['name'] for extension in self.xml.iter('extension')}


class SlotOptionElement(ElementWrapper):
	@property
	def name(self) -> str:
		return self.xml.attrib['name']

	@property
	def device_name(self) -> 'Basename':
		"""Basename of device for this option"""
		return self.xml.attrib['devname']

	@property
	def is_default(self) -> bool:
		return self.xml.attrib.get('default', 'no') == 'yes'


class SlotElement(ElementWrapper):
	"""For peripherals etc, as with -listslots"""

	@cached_property
	def options(self) -> Sequence[SlotOptionElement]:
		return tuple(SlotOptionElement(slotoption) for slotoption in self.xml.iter('slotoption'))

	@property
	def name(self) -> str:
		return self.xml.attrib['name']

	@property
	def default_option(self) -> SlotOptionElement | None:
		# should only be one? but maybe not always any
		# In fact it might not have any options at all, if this is for a media slot (self.name is equal to the tag of a DeviceElement, seemingly)
		return next((option for option in self.options if option.is_default), None)


class SoftwareListType(StrEnum):
	Original = 'original'
	Compatible = 'compatible'


class MachineSoftwareListElement(ElementWrapper):
	"""<softwarelist> element in <machine> which has info about what software the machine can use"""

	@property
	def tag(self) -> str:
		return self.xml.attrib['tag']

	@property
	def name(self) -> 'SoftwareListBasename':
		return self.xml.attrib['name']

	@property
	def type(self) -> SoftwareListType:
		"""The element is called <status> but type seems more like what it actually is"""
		return SoftwareListType(self.xml.attrib['status'])

	@property
	def filter(self) -> str | None:
		"""Software must have this in compatibility, or if this starts with !, must not have this value"""
		return self.xml.attrib.get('filter')


class RAMOptionElement(ElementWrapper):
	@property
	def name(self) -> str:
		return self.xml.attrib['name']

	@property
	def is_default(self) -> bool:
		return self.xml.attrib.get('default', 'no') == 'yes'

	@property
	def size(self) -> int:
		return int(self.xml.text or '0')


class MachineElement(ElementWrapper):
	@property
	def basename(self) -> 'Basename':
		return self.xml.attrib['name']

	@property
	def parent_basename(self) -> 'Basename | None':
		return self.xml.attrib.get('cloneof')

	@property
	def is_mechanical(self) -> bool:
		return self.xml.attrib.get('ismechanical', 'no') == 'yes'

	@property
	def is_bios(self) -> bool:
		return self.xml.attrib.get('isbios', 'no') == 'yes'

	@property
	def is_device(self) -> bool:
		return self.xml.attrib.get('isdevice', 'no') == 'yes'

	@property
	def is_runnable(self) -> bool:
		return self.xml.attrib.get('runnable', 'no') == 'yes'

	@property
	def source_file(self) -> PurePath:
		return PurePath(self.xml.attrib['sourcefile'])

	@property
	def bios_basename(self) -> 'Basename | None':
		"""Note! If this is a clone set, this will be the parent basename, so you should look up the parent machine instead"""
		return self.xml.attrib.get('romof')

	@property
	def sample_set_basename(self) -> 'Basename | None':
		return self.xml.attrib.get('sampleof')

	@property
	def name(self) -> str:
		# Missing name should never happen
		description = self.xml.find_text('description')
		if description is None:
			logger.warning('<machine> element %s has missing description', self.basename)
			return self.basename
		return description

	@property
	def raw_year(self) -> str | None:
		"""May include ? or x or whatever, not necessarily present on devices"""
		return self.xml.find_text('year')

	@property
	def year(self) -> int | None:
		return try_parse_int(self.raw_year)

	@property
	def manufacturer(self) -> str | None:
		"""Manufacturer of the machine, not necessarily present on devices"""
		return self.xml.find_text('manufacturer')

	@cached_property
	def bios_options(self) -> Sequence[BIOSSetElement]:
		return tuple(BIOSSetElement(biosset) for biosset in self.xml.iter('biosset'))

	@property
	def default_bios(self) -> BIOSSetElement | None:
		return next((bios for bios in self.bios_options if bios.is_default), None)

	@cached_property
	def roms(self) -> Sequence[ROMElement]:
		return tuple(ROMElement(xml) for xml in self.xml.iter('rom'))

	@cached_property
	def disks(self) -> Sequence[DiskElement]:
		return tuple(DiskElement(xml) for xml in self.xml.iter('disk'))

	@cached_property
	def device_refs(self) -> Sequence[NamedElement]:
		return tuple(NamedElement(xml) for xml in self.xml.iter('device_ref'))

	@cached_property
	def samples(self) -> Sequence[NamedElement]:
		return tuple(NamedElement(xml) for xml in self.xml.iter('sample'))

	@cached_property
	def chips(self) -> Sequence[ChipElement]:
		return tuple(ChipElement(xml) for xml in self.xml.iter('chip'))

	@cached_property
	def displays(self) -> Sequence[DisplayElement]:
		return tuple(DisplayElement(e) for e in self.xml.iter('display'))

	@cached_property
	def sound(self) -> SoundElement | None:
		sound = self.xml.find_first('sound')
		return SoundElement(sound) if sound else None

	@property
	def number_of_sound_channels(self):
		return self.sound.number_of_channels if self.sound else 0

	@cached_property
	def input(self) -> InputElement | None:
		input_element = self.xml.find_first('input')
		return InputElement(input_element) if input_element else None

	@property
	def number_of_coin_slots(self) -> int:
		if self.input and self.input.coin_slots:
			return self.input.coin_slots
		return 0

	@cached_property
	def dipswitches(self) -> Sequence[DipswitchElement]:
		return tuple(DipswitchElement(dipswitch) for dipswitch in self.xml.iter('dipswitch'))

	@cached_property
	def configuration_options(self) -> Sequence[ConfigurationElement]:
		return tuple(
			ConfigurationElement(configuration) for configuration in self.xml.iter('configuration')
		)

	@cached_property
	def ports(self) -> Sequence[PortElement]:
		return tuple(PortElement(port) for port in self.xml.iter('port'))

	@cached_property
	def adjusters(self) -> Sequence[AdjusterElement]:
		return tuple(AdjusterElement(adjuster) for adjuster in self.xml.iter('adjuster'))

	@cached_property
	def driver(self) -> DriverElement | None:
		driver = self.xml.find_first('driver')
		return None if driver is None else DriverElement(driver)

	@property
	def overall_status(self) -> DriverStatus | None:
		"""Hmm, so how this works according to https://github.com/mamedev/mame/blob/master/src/frontend/mame/info.cpp: if any particular feature is preliminary, this is preliminary, if any feature is imperfect this is imperfect, unless protection = imperfect then this is preliminary
		It even says it's for the convenience of frontend developers, but since I'm an ungrateful piece of shit and I always feel the need to take matters into my own hands, I'm gonna get the other parts of the emulation too"""
		if self.driver is None:
			return None
		return self.driver.status

	@property
	def emulation_status(self) -> DriverStatus | None:
		if self.driver is None:
			return None
		return self.driver.emulation_status

	@property
	def cocktail_status(self) -> DriverStatus | None:
		if self.driver is None:
			return None
		return self.driver.cocktail_status

	@cached_property
	def features(self) -> Sequence[FeatureElement]:
		return tuple(FeatureElement(feature) for feature in self.xml.iter('feature'))

	@property
	def feature_statuses(self) -> Mapping[str, FeatureStatus]:
		statuses: dict[str, FeatureStatus] = {}
		for feature in self.features:
			if not feature.status:
				continue

			statuses[feature.type] = feature.status
		return statuses

	@cached_property
	def media_slots(self) -> Sequence[MediaDeviceElement]:
		return tuple(MediaDeviceElement(device) for device in self.xml.iter('device'))

	@cached_property
	def slots(self) -> Sequence[SlotElement]:
		return tuple(SlotElement(slot) for slot in self.xml.iter('slot'))

	@property
	def has_mandatory_slots(self) -> bool:
		return any(slot.is_mandatory for slot in self.media_slots)

	@cached_property
	def software_lists(self) -> Sequence[MachineSoftwareListElement]:
		return tuple(
			MachineSoftwareListElement(softwarelist)
			for softwarelist in self.xml.iter('softwarelist')
		)

	@cached_property
	def ram_options(self) -> Sequence[RAMOptionElement]:
		return tuple(RAMOptionElement(ramoption) for ramoption in self.xml.iter('ramoption'))


def iter_machine_elements_from_file(
	file: Path | IO[bytes], reader: XMLReader[XMLElementType_co]
) -> Iterator[MachineElement]:
	if isinstance(file, Path):
		with file.open('rb') as f:
			yield from iter_machine_elements_from_file(f, reader)
	else:
		for xml in reader.iterparse(file, 'machine'):
			yield MachineElement(xml)


@cache
def get_machine_elements_from_file_as_dict(
	file: Path | IO[bytes],
) -> Mapping['Basename', MachineElement]:
	return {
		element.basename: element
		for element in iter_machine_elements_from_file(file, get_xml_reader())
	}


@alru_cache
async def get_machine_elements_from_file_as_dict_async(
	file: Path | IO[bytes],
) -> Mapping['Basename', MachineElement]:
	sentinel = object()
	iterator = await asyncio.to_thread(iter_machine_elements_from_file, file, get_xml_reader())
	d = {}
	while (element := await asyncio.to_thread(next, iterator, sentinel)) is not sentinel:
		assert isinstance(element, MachineElement)
		d[element.basename] = element
	return d
