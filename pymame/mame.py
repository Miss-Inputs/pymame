import asyncio
from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING

from pymame.commands import MAMEExecutable
from pymame.elements.machine_element import MachineElement, iter_machine_elements_from_file
from pymame.support_files.cats import CategoryFolder
from pymame.wrappers.machine import Machine
from pymame.wrappers.machine import get_machine as _get_machine
from pymame.wrappers.machine import get_machine_async as _get_machine_async
from pymame.xml_wrapper import get_xml_reader

if TYPE_CHECKING:
	from pymame.settings import MAMESettings
	from pymame.typedefs import Basename


class MAME:
	"""need to write documentation that makes sense here. Basically utility methods once we have a MAMESettings"""

	def __init__(self, settings: 'MAMESettings') -> None:
		self.settings = settings
		self.executable = MAMEExecutable(settings)

	def iter_machine_elements(self) -> Iterator[MachineElement]:
		if self.settings.xml_path:
			yield from iter_machine_elements_from_file(self.settings.xml_path, get_xml_reader())
		else:
			yield from (MachineElement(xml) for _, xml in self.executable.iter_all_xml())

	async def iter_machine_elements_async(self) -> AsyncIterator[MachineElement]:
		# not sure if this way is actually correct/performant?
		sentinel = object()
		iterator = await asyncio.to_thread(self.iter_machine_elements)
		while (element := await asyncio.to_thread(next, iterator, sentinel)) is not sentinel:
			assert isinstance(element, MachineElement)
			yield element

	def _get_category_folder(self) -> CategoryFolder | None:
		if not self.settings.cat_path:
			return None
		return CategoryFolder.load_from_folder(self.settings.cat_path)

	async def _get_category_folder_async(self) -> CategoryFolder | None:
		if not self.settings.cat_path:
			return None
		return await CategoryFolder.load_from_folder_async(self.settings.cat_path)

	def iter_machines(self) -> Iterator[Machine]:
		category_folder = self._get_category_folder()
		yield from (
			_get_machine(self.settings, element, category_folder)
			for element in self.iter_machine_elements()
		)

	async def iter_machines_async(self) -> AsyncIterator[Machine]:
		category_folder = await self._get_category_folder_async()
		async for element in self.iter_machine_elements_async():
			yield await _get_machine_async(self.settings, element, category_folder)

	def iter_runnable_machines(self) -> Iterator[Machine]:
		category_folder = self._get_category_folder()
		yield from (
			_get_machine(self.settings, element, category_folder)
			for element in self.iter_machine_elements()
			if element.is_runnable and not element.is_device
		)

	async def iter_runnable_machines_async(self) -> AsyncIterator[Machine]:
		category_folder = await self._get_category_folder_async()
		async for element in self.iter_machine_elements_async():
			if element.is_runnable and not element.is_device:
				yield await _get_machine_async(self.settings, element, category_folder)

	def get_machine(self, basename: 'Basename') -> Machine:
		return _get_machine(self.settings, basename)

	async def get_machine_async(self, basename: 'Basename') -> Machine:
		return await _get_machine_async(self.settings, basename)
