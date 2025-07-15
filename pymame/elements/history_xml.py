from collections.abc import Collection, Iterator
from functools import cached_property
from typing import TYPE_CHECKING

from pymame.xml_wrapper import ElementWrapper

from .common_elements import NamedElement

if TYPE_CHECKING:
	from pymame.typedefs import Basename, SoftwareBasename, SoftwareListBasename


class HistorySoftwareItem(ElementWrapper):
	"""<item> element in <software>, shows which software this history is applicable to"""

	@property
	def list_name(self) -> 'SoftwareListBasename':
		return self.xml.attrib['list']

	@property
	def name(self) -> 'SoftwareBasename':
		return self.xml.attrib['name']


class HistorySoftware(ElementWrapper):
	@cached_property
	def items(self) -> Collection[HistorySoftwareItem]:
		return {HistorySoftwareItem(item) for item in self.xml.iter('item')}


class HistorySystems(ElementWrapper):
	"""<systems> element in <software>, designates which arcade system this history is applicable to"""

	@cached_property
	def systems(self) -> Collection['Basename']:
		return {NamedElement(system).name for system in self.xml.iter('system')}


class HistoryEntryElement(ElementWrapper):
	# Note that it is possible for an entry to apply to both systems and softwares, e.g. ST-V games are for the appropriate arcade game and also the stv software list
	@cached_property
	def text(self):
		return self.xml.find_text('text')

	@cached_property
	def systems(self) -> Collection['Basename']:
		systems_element = self.xml.find_first('systems')
		if not systems_element:
			return ()
		return HistorySystems(systems_element).systems

	@cached_property
	def softwares(self) -> Collection[tuple['SoftwareListBasename', 'SoftwareBasename']]:
		software_element = self.xml.find_first('software')
		if software_element is None:
			return ()
		return {(item.list_name, item.name) for item in HistorySoftware(software_element).items}


class HistoryXML(ElementWrapper):
	def _iter_elements(self) -> Iterator[HistoryEntryElement]:
		for entry in self.xml.iter('entry'):
			yield HistoryEntryElement(entry)

	def iter_system_histories(self) -> Iterator[tuple['Basename', str]]:
		for entry in self._iter_elements():
			if not entry.text:
				continue
			for system in entry.systems:
				yield (system, entry.text)

	def iter_software_histories(
		self,
	) -> Iterator[tuple['SoftwareListBasename', 'SoftwareBasename', str]]:
		for entry in self._iter_elements():
			if not entry.text:
				continue
			for software_list, software in entry.softwares:
				yield (software_list, software, entry.text)
