from collections.abc import Sequence
from enum import StrEnum
from functools import cached_property
from typing import TYPE_CHECKING

from pymame.elements.common_elements import DipswitchValueElement, DumpStatus
from pymame.utils import try_parse_hexbytes, try_parse_int, try_parse_strenum
from pymame.xml_wrapper import ElementWrapper

if TYPE_CHECKING:
	from pymame.typedefs import SoftwareBasename


class InfoElement(ElementWrapper):
	"""We cheat a bit and reuse this for sharedfeat and feature"""

	@property
	def name(self):
		return self.xml.attrib['name']

	@property
	def value(self):
		return self.xml.attrib.get('value')


class LoadFlag(StrEnum):
	"""I dunno what most of this means, sorry"""

	Load16Byte = 'load16_byte'
	Load16Word = 'load16_word'
	Load16WordSwap = 'load16_word_swap'
	Load32Byte = 'load_32_byte'
	Load32Word = 'load_32_word'
	Load32WordSwap = 'load_32_word_swap'
	Load32DWord = 'load_32_dword'
	Load64Word = 'load_64_word'
	Load64WordSwap = 'load_64_word_swap'
	Reload = 'reload'
	Fill = 'fill'
	"""This ROM is just filled with the same byte (specified by value)"""
	Continue = 'continue'
	ReloadPlain = 'reload_plain'
	Ignore = 'ignore'
	"""Ignore this ROM"""


class ROMElement(ElementWrapper):
	@property
	def name(self):
		return self.xml.attrib.get('name')

	@property
	def size(self):
		return try_parse_int(self.xml.attrib.get('size'))

	@property
	def crc(self):
		return try_parse_int(self.xml.attrib.get('crc'), 16)

	@property
	def sha1(self):
		return try_parse_hexbytes(self.xml.attrib.get('sha1'))

	@property
	def offset(self):
		"""Offset where this file is loaded into the overall ROM
		Should this default to 0?"""
		return try_parse_int(self.xml.attrib.get('offset'))

	@property
	def value(self):
		"""Not often present, but used with certain load flags e.g. fill"""
		return self.xml.attrib.get('value')

	@property
	def status(self):
		return DumpStatus(self.xml.attrib.get('status', 'good'))

	@property
	def load_flag(self):
		return try_parse_strenum(self.xml.attrib.get('loadflag'), LoadFlag)


class Endianness(StrEnum):
	Big = 'big'
	Little = 'little'


class DataAreaElement(ElementWrapper):
	@property
	def name(self):
		return self.xml.attrib['name']

	@cached_property
	def roms(self):
		return tuple(ROMElement(rom) for rom in self.xml.iter('rom'))

	@property
	def size(self):
		return int(self.xml.attrib['size'])

	@property
	def width(self):
		"""Must be 8, 16, 32, or 64"""
		return int(self.xml.attrib.get('width', '8'))

	@property
	def endianness(self):
		return Endianness(self.xml.attrib.get('endianness', 'little'))


class DiskElement(ElementWrapper):
	@property
	def name(self):
		return self.xml.attrib['name']

	@property
	def sha1(self):
		return try_parse_hexbytes(self.xml.attrib.get('sha1'))

	@property
	def status(self):
		return DumpStatus(self.xml.attrib.get('status', 'good'))

	@property
	def is_writeable(self):
		return self.xml.attrib.get('writeable', 'no') == 'yes'


class DiskAreaElement(ElementWrapper):
	@property
	def name(self):
		return self.xml.attrib['name']

	@cached_property
	def disks(self):
		return tuple(DiskElement(disk) for disk in self.xml.iter('disk'))


class SoftwareDipswitchElement(DiskElement):
	"""Found in for example bootleg NES carts (e.g. nes/chessac). Unlike machine <dipswitch> it has no diplocation which surely warrants making a separate class hmm maybe I should refactor all this"""

	@cached_property
	def values(self) -> Sequence[DipswitchValueElement]:
		return tuple(DipswitchValueElement(dipvalue) for dipvalue in self.xml.iter('dipvalue'))

	@property
	def name(self):
		return self.xml.attrib['name']

	@property
	def tag(self):
		return self.xml.attrib['tag']

	@property
	def mask(self):
		"""always numeric?"""
		return self.xml.attrib['mask']

	@property
	def default_value(self):
		return next((value for value in self.values if value.is_default), None)


class PartElement(ElementWrapper):
	@property
	def name(self):
		return self.xml.attrib['name']

	@property
	def interface(self):
		return self.xml.attrib['interface']

	@cached_property
	def features(self) -> Sequence[InfoElement]:
		return tuple(InfoElement(feature) for feature in self.xml.iter('feature'))

	@cached_property
	def data_areas(self) -> Sequence[DataAreaElement]:
		return tuple(DataAreaElement(dataarea) for dataarea in self.xml.iter('dataarea'))

	@cached_property
	def disk_areas(self) -> Sequence[DiskAreaElement]:
		return tuple(DiskAreaElement(diskarea) for diskarea in self.xml.iter('diskarea'))

	@cached_property
	def dipswitches(self):
		return tuple(
			SoftwareDipswitchElement(dipswitch) for dipswitch in self.xml.iter('dipswitch')
		)


class SoftwareStatus(StrEnum):
	Supported = 'yes'
	PartialSupport = 'partial'
	NotSupported = 'no'


class SoftwareElement(ElementWrapper):
	@property
	def basename(self) -> 'SoftwareBasename':
		return self.xml.attrib['name']

	@property
	def parent_basename(self):
		return self.xml.attrib.get('cloneof')

	@property
	def supported(self):
		return SoftwareStatus(self.xml.attrib.get('supported', 'yes'))

	@property
	def name(self):
		# TODO: Warn if <description> is not there, because that's odd
		return self.xml.find_text('description') or self.basename

	@property
	def raw_year(self):
		return self.xml.find_text('year')

	@property
	def year(self):
		return try_parse_int(self.raw_year)

	@property
	def publisher(self):
		return self.xml.find_text('publisher')

	@property
	def notes(self):
		"""Not in softwarelist.dtd because it's in <softwarelist> instead"""
		return self.xml.find_text('notes')

	@cached_property
	def infos(self):
		"""Note that you can have multiple infos with the same name"""
		return tuple(InfoElement(info) for info in self.xml.iter('info'))

	@cached_property
	def shared_features(self):
		# presume you can have multiple sharedfeats with same name too?
		# Cheating a bit by just reusing InfoElement because it does the same thing
		return tuple(InfoElement(sharedfeat) for sharedfeat in self.xml.iter('sharedfeat'))

	@cached_property
	def parts(self):
		return tuple(PartElement(part) for part in self.xml.iter('part'))

	@property
	def parts_by_name(self):
		return {part.name: part for part in self.parts}
