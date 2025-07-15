import asyncio
from collections.abc import Iterable
from functools import cache, cached_property
from pathlib import Path
from typing import TYPE_CHECKING

from pymame.xml_wrapper import ElementWrapper, XMLElement, get_xml_reader

from .software_element import SoftwareElement

if TYPE_CHECKING:
	from pymame.typedefs import SoftwareListBasename


class SoftwareListElement(ElementWrapper):
	@property
	def basename(self) -> 'SoftwareListBasename':
		return self.xml.attrib['name']

	@property
	def name(self):
		return self.xml.attrib.get('description', self.basename)

	@property
	def notes(self):
		"""I'm not sure this is ever actually there or if it's just the DTD misplacing the notes element on software"""
		return self.xml.find_text('notes')

	@cached_property
	def software(self):
		# name should always be unique
		return {
			software.attrib['name']: SoftwareElement(software)
			for software in self.xml.iter('software')
		}


def _get_software_list_from_file(
	hash_paths: Iterable[Path], name: 'SoftwareListBasename'
) -> XMLElement:
	for hash_path in hash_paths:
		xml_path = hash_path / f'{name}.xml'
		try:
			with xml_path.open('rb') as f:
				return get_xml_reader().read_from_file(f)
		except FileNotFoundError:
			continue
	raise KeyError(name)


def get_software_list_element_from_file(
	hash_paths: Iterable[Path], name: 'SoftwareListBasename'
) -> SoftwareListElement:
	xml = _get_software_list_from_file(hash_paths, name)
	return SoftwareListElement(xml)


async def get_software_list_element_from_file_async(
	hash_paths: Iterable[Path], name: 'SoftwareListBasename'
) -> SoftwareListElement:
	xml = await asyncio.to_thread(_get_software_list_from_file, hash_paths, name)
	return SoftwareListElement(xml)


@cache
def get_software_element_from_file(
	hash_paths: Iterable[Path], software_list: str | SoftwareListElement, name: str
) -> 'SoftwareElement':
	if isinstance(software_list, str):
		software_list = get_software_list_element_from_file(hash_paths, software_list)
	return software_list.software[name]
