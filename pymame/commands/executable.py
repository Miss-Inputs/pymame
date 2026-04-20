"""Wrapper for subprocessed MAME frontend commands."""

import subprocess
from collections.abc import AsyncIterator, Iterable, Iterator, Mapping, Sequence
from functools import cached_property
from typing import TYPE_CHECKING

from pymame.xml_wrapper import XMLElement, get_xml_reader

from .listxml import listxml, listxml_all, listxml_as_dict, listxml_async, listxml_with_devices
from .software import getsoftlist, getsoftlist_async, iter_software_list_names
from .verifyroms import (
	VerifyromsOutput,
	verifyroms,
	verifyroms_async,
	verifyroms_multiple,
	verifyroms_multiple_async,
	verifyroms_with_info,
	verifyroms_with_info_async,
	verifysamples,
	verifysamples_async,
	verifysoftlist,
	verifysoftlist_async,
	verifysoftlist_single,
	verifysoftlist_single_async,
)

if TYPE_CHECKING:
	from pymame.settings import MAMESettings
	from pymame.typedefs import Basename, SoftwareBasename, SoftwareListBasename


class MAMEExecutable:
	def __init__(self, settings: 'MAMESettings'):
		self.path = settings.mame_executable_path
		self.unsafe_listxml = settings.use_unsafe_listxml

	@cached_property
	def version(self) -> str:
		return subprocess.check_output([self.path, '-version'], encoding='utf8')

	# listxml stuff
	def listxml(self, name: 'Basename') -> XMLElement:
		"""Lists just one machine, or raises KeyError if it was not found

		Returns:
			XMLElement
		"""
		return listxml(self.path, get_xml_reader(), name)

	async def listxml_async(self, name: 'Basename') -> XMLElement:
		"""Lists just one machine, or raises KeyError if it was not found

		Returns:
			XMLElement
		"""
		return await listxml_async(self.path, get_xml_reader(), name)

	def listxml_with_devices(self, name: 'Basename') -> Mapping['Basename', XMLElement]:
		"""Lists just one machine and its associated devices

		Returns:
			{basename: <machine> element}
		"""
		return listxml_with_devices(self.path, get_xml_reader(), name)

	def listxml_as_dict(self) -> Mapping['Basename', XMLElement]:
		return listxml_as_dict(self, get_xml_reader(), unsafe=self.unsafe_listxml)

	def iter_all_xml(self) -> Iterator[tuple['Basename', XMLElement]]:
		yield from listxml_all(self.path, get_xml_reader(), unsafe=self.unsafe_listxml)

	# verifyroms stuff

	def verifyroms(self, basename: 'Basename') -> bool:
		return verifyroms(self.path, basename)

	async def verifyroms_async(self, basename: 'Basename') -> bool:
		return await verifyroms_async(self.path, basename)

	def verifyroms_with_info(self, basename: 'Basename') -> VerifyromsOutput:
		"""Verifies if a romset is present and valid, but returns info about what files are missing etc if not"""
		return verifyroms_with_info(self.path, basename)

	async def verifyroms_with_info_async(self, basename: 'Basename') -> VerifyromsOutput:
		return await verifyroms_with_info_async(self.path, basename)

	def verifyroms_multiple_with_info(
		self, basenames: Iterable['Basename']
	) -> Iterator[VerifyromsOutput]:
		yield from verifyroms_multiple(self.path, basenames)

	def verifyroms_multiple(self, basenames: Iterable['Basename']) -> Sequence['Basename']:
		"""Note that if basenames is empty, this will check all known machines, which might take a while, and might be what you want but might not be

		Returns:
			Basenames that were verified as okay"""
		return tuple(
			result.basename
			for result in self.verifyroms_multiple_with_info(basenames)
			if result.is_okay
		)

	async def verifyroms_multiple_with_info_async(
		self, basenames: Iterable['Basename']
	) -> AsyncIterator[VerifyromsOutput]:
		async for output in verifyroms_multiple_async(self.path, basenames):
			yield output

	# verifysamples
	def verifysamples(self, basename: 'Basename') -> bool:
		return verifysamples(self.path, basename)

	async def verifysamples_async(self, basename: 'Basename') -> bool:
		return await verifysamples_async(self.path, basename)

	# verifysoftlist
	def verifysoftlists(self, *softlist_names: 'SoftwareListBasename') -> Iterator[tuple['SoftwareListBasename', 'SoftwareBasename']]:
		"""If no softlist_names are provided, this will verify all known software lists."""
		return verifysoftlist(self.path, softlist_names)

	def verifysoftlist(self, softlist_name: 'SoftwareListBasename') -> Iterator['SoftwareBasename']:
		return verifysoftlist_single(self.path, softlist_name)
	
	async def verifysoftlists_async(self, *softlist_names: 'SoftwareListBasename') -> AsyncIterator[tuple['SoftwareListBasename', 'SoftwareBasename']]:
		"""If no softlist_names are provided, this will verify all known software lists."""
		return verifysoftlist_async(self.path, softlist_names)

	async def verifysoftlist_async(self, softlist_name: 'SoftwareListBasename') -> AsyncIterator['SoftwareBasename']:
		return verifysoftlist_single_async(self.path, softlist_name)

	# listsoftware
	def getsoftlist(self, name: 'SoftwareListBasename') -> XMLElement:
		return getsoftlist(self.path, name)

	async def getsoftlist_async(self, name: 'SoftwareListBasename') -> XMLElement:
		return await getsoftlist_async(self.path, name)

	def iter_software_list_names(self) -> Iterator['SoftwareListBasename']:
		yield from iter_software_list_names(self.path)

	@cached_property
	def software_list_names(self) -> Sequence['SoftwareListBasename']:
		return tuple(self.iter_software_list_names())

	# TODO: romident - now this could be interesting instead of relying on software_finder, would it be faster if MAME is doing the work (including decompressing zip/7z)?
	# prints "Identifying <path>" and then takes a bit and prints (inner filename = ROM name <tab> software ID <tab> software name) for each file inside the archive or folder, and then "Out of X files, Y matched, Z did not match" or "No roms matched." if some weren't recognized

	# other frontend commands which could be implemented through -listxml and processing MachineElement objects instead:
	# TODO: Maybe benchmark at some point if any of these would actually be significantly faster
	# listsource (source files of all, or specified machines)
	# listclones (machines with cloneof = specified machine)
	# listbrothers (machines with same source file as specified)
	# listcrc (ROM names and CRC32s for specified machine(s))
	# listroms (ROM names and printout of checksum, probably don't bother parsing this one)
	# listsamples (list of samples required for machine, if any)
	# listslots (slots and things you can plug into them, e.g. for computers)
	# listbios (list of BIOS options that can be selected for machine, not the BIOS machine it uses)
	# listmedia (list of media slots)

	# Others:
	# listdevices: <root> and machine full name, and tag + full name on each device, which is interesting because it's not actually the device basename and that doesn't seem to be in listxml I guess (e.g. pacman has a mainlatch, which is only in the device_ref in XML as ls259)
	# listsoftware {machine}: This is just -getsoftlist for all of the machine's <softwarelist>s, though we do already do this without an argument to get all software
	# verifysoftware: This is just -verifysoftlist for all of the machine's <softwarelist>s
	# listmidi, listnetwork if you are into that sort of thing I guess (but does it just list anything compiled in, whether you personally have it or not?)
	# validate if you are _really_ into that sort of thing but now we're just listing every single thing that doesn't start a machine
