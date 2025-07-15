"""Functions that subprocess MAME to get info, etc"""

import asyncio
import asyncio.subprocess
import dataclasses
import logging
import re
import subprocess
from collections.abc import AsyncIterator, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from functools import cache, cached_property
from pathlib import Path
from typing import TYPE_CHECKING

from async_lru import alru_cache

from .xml_wrapper import XMLElement, XMLElementType_co, XMLReader, get_xml_reader

if TYPE_CHECKING:
	from pymame.settings import MAMESettings

	from .typedefs import Basename, SoftwareBasename, SoftwareListBasename

logger = logging.getLogger(__name__)

# put some stuff in functions outside MAMEExecutable, so it can be cached more easily


def _listxml_all_unsafe(
	path: Path, reader: XMLReader[XMLElementType_co], *, capture_stderr: bool = False
):
	# For some reason it breaks sometimes if capturing stderr??
	with subprocess.Popen(
		[path, '-listxml'],
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE if capture_stderr else None,
	) as proc:
		try:
			assert proc.stdout is not None, 'Somehow proc.stdout is None'
			# naughty because I don't wait for it to end and the docs tell you not to do that
			for element in reader.iterparse(proc.stdout, 'machine'):
				yield element.attrib['name'], element
			if capture_stderr:
				_, stderr = proc.communicate()
				if stderr:
					logger.info(stderr)
		finally:
			proc.kill()


def listxml_all(
	mame_path: Path,
	reader: XMLReader[XMLElementType_co],
	*,
	unsafe: bool = False,
	capture_stderr: bool = False,
) -> Iterator[tuple['Basename', XMLElement]]:
	if unsafe:
		yield from _listxml_all_unsafe(mame_path, reader, capture_stderr=capture_stderr)
	else:
		proc = subprocess.run(
			[mame_path, '-listxml'],
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE if capture_stderr else None,
			check=True,
			# timeout=60,
		)
		for element in reader.iterparse(proc.stdout, 'machine'):
			yield element.attrib['name'], element
		if proc.stderr:
			logger.info(proc.stderr)


async def listxml_all_async(
	mame_path: Path, reader: XMLReader[XMLElementType_co], *, capture_stderr: bool = False
) -> AsyncIterator[tuple['Basename', XMLElement]]:
	# I should use asyncio.subprocess here, but meh
	sentinel = object()

	iterator = await asyncio.to_thread(
		listxml_all, mame_path, reader, capture_stderr=capture_stderr
	)
	while (element := await asyncio.to_thread(next, iterator, sentinel)) is not sentinel:
		assert isinstance(element, tuple)
		yield element


@cache
def listxml_as_dict(
	path: Path, reader: XMLReader[XMLElementType_co], *, unsafe: bool = False
) -> Mapping['Basename', XMLElement]:
	return dict(listxml_all(path, reader, unsafe=unsafe))


@cache
def _listxml(path: Path, reader: XMLReader[XMLElementType_co], basename: 'Basename') -> XMLElement:
	proc = subprocess.run([path, '-listxml', basename], check=True, capture_output=True)
	if proc.stderr:
		logger.info(proc.stderr)
	machine = reader.read(proc.stdout).find_first('machine')
	if not machine:
		raise KeyError(basename)
	return machine


@alru_cache
async def _listxml_async(
	path: Path, reader: XMLReader[XMLElementType_co], basename: 'Basename'
) -> XMLElement:
	proc = await asyncio.subprocess.create_subprocess_exec(
		path, '-listxml', basename, stdout=subprocess.PIPE, stderr=subprocess.PIPE
	)
	stdout, stderr = await proc.communicate()
	if stderr:
		logger.info(stderr)
	xml = await asyncio.to_thread(reader.read, stdout)
	machine = xml.find_first('machine')
	if not machine:
		raise KeyError(basename)
	return machine


@cache
def _listxml_with_devices(
	path: Path, reader: XMLReader[XMLElementType_co], basename: 'Basename'
) -> dict['Basename', XMLElement]:
	proc = subprocess.run([path, '-listxml', basename], check=True, capture_output=True)
	if proc.stderr:
		logger.info(proc.stderr)
	return {xml.attrib['name']: xml for xml in reader.read(proc.stdout).iter('machine')}


def _parse_verifysoftlist_output(
	output: str,
) -> Iterator[tuple['SoftwareListBasename', 'SoftwareBasename']]:
	"""This doesn't capture any specific details of what goes on with bad software, just if it is there or not

	Yields:
		(Software list basename, software basename)"""
	for line in output.splitlines():
		line = line.strip()
		match = re.fullmatch(
			r'^romset (?P<listname>.+?):(?P<softwarename>.+?) is (?:best available|good)$', line
		)
		if match:
			yield match['listname'], match['softwarename']


@dataclass
class VerifyromsOutput:
	basename: 'Basename'
	romof: 'Basename | None'
	status: str
	info: Sequence[str] = dataclasses.field(default_factory=tuple)
	"""Anything printed for this romset about what particular ROMs are bad/have no good dump etc"""

	@property
	def is_okay(self) -> bool:
		return self.status in {'good', 'best available'}


def _parse_verifyroms_output(lines: Iterable[str]) -> Iterator[VerifyromsOutput]:
	current_info_lines = []

	for line in lines:
		line = line.strip()
		match = re.fullmatch(
			r'romset (?P<basename>\w+)(?:\s+\[(?P<romof>\w+)\]\s*)? is (?P<status>best available|good|bad)$',
			line,
		)
		if match:
			# info for each basename is printed before the line for that basename, not after it
			yield VerifyromsOutput(
				match['basename'], match['romof'], match['status'], current_info_lines
			)
			current_info_lines.clear()
		elif 'were OK' not in line:
			current_info_lines.append(line)


@cache
def get_software_list(path: Path, name: 'SoftwareListBasename'):
	proc = subprocess.run([path, '-getsoftlist', name], capture_output=True, check=True)
	stderr = proc.stderr.strip()
	if stderr == b'No such software lists found':
		# It seems it will still return 0 in this case
		raise KeyError(name)
	if stderr:
		logger.warning('MAME printed to stderr when getting %s software list: %s', name, stderr)
	return get_xml_reader().read(proc.stdout)


async def get_software_list_async(path: Path, name: 'SoftwareListBasename'):
	proc = await asyncio.subprocess.create_subprocess_exec(
		path, '-getsoftlist', name, stdout=subprocess.PIPE, stderr=subprocess.PIPE
	)
	stdout, stderr = await proc.communicate()
	stderr = stderr.strip()
	if stderr == b'No such software lists found':
		# It seems it will still return 0 in this case
		raise KeyError(name)
	if stderr:
		logger.warning('MAME printed to stderr when getting %s software list: %s', name, stderr)
	return get_xml_reader().read(stdout)


class MAMEExecutable:
	def __init__(self, settings: 'MAMESettings'):
		self.path = settings.mame_executable_path
		self.unsafe_listxml = settings.use_unsafe_listxml

	def listxml_as_dict(self) -> Mapping['Basename', XMLElement]:
		return listxml_as_dict(self, get_xml_reader(), unsafe=self.unsafe_listxml)

	def verifyroms(self, basename: 'Basename') -> bool:
		try:
			subprocess.run(
				[self.path, '-verifyroms', basename],
				stdout=subprocess.DEVNULL,
				stderr=subprocess.DEVNULL,
				check=True,
			)
		except subprocess.CalledProcessError:
			return False
		else:
			return True

	async def verifyroms_async(self, basename: 'Basename') -> bool:
		proc = await asyncio.subprocess.create_subprocess_exec(
			self.path,
			'-verifyroms',
			basename,
			stdout=asyncio.subprocess.DEVNULL,
			stderr=asyncio.subprocess.DEVNULL,
		)
		return_code = await proc.wait()
		return return_code == 0

	def _verifyroms_with_info_single(self, basename: 'Basename') -> VerifyromsOutput:
		proc = subprocess.run(
			[self.path, '-verifyroms', basename], capture_output=True, text=True, check=False
		)
		if proc.stderr.endswith('has no roms!\n'):
			# Devices do this, romless machines still just say "best available"
			# If more than one basename it will just not display it, and it will not be added to the count of "found" at the end
			return VerifyromsOutput(basename, None, 'no roms!')
		if proc.stderr.endswith('not found!\n'):
			# If more than one basename it will just not display it, and it will not be added to the count of "found" at the end
			return VerifyromsOutput(basename, None, 'not found!')
		return next(_parse_verifyroms_output(proc.stdout.splitlines()))

	def _verifyroms_with_info(self, basenames: Iterable['Basename']) -> Iterator[VerifyromsOutput]:
		proc = subprocess.run(
			[self.path, '-verifyroms', *basenames], capture_output=True, text=True, check=False
		)
		yield from _parse_verifyroms_output(proc.stdout.splitlines())

	def verifyroms_with_info(self, basename: 'Basename'):
		result = self._verifyroms_with_info_single(basename)
		return result.is_okay, '\n'.join(result.info)

	def verifyroms_multiple(self, basenames: Iterable['Basename']) -> Sequence['Basename']:
		"""Note that if basenames is empty, this will check all of them, which might take a while

		Returns:
			Basenames that were verified as okay"""
		return tuple(
			result.basename for result in self._verifyroms_with_info(basenames) if result.is_okay
		)

	def verifysamples(self, basename: 'Basename') -> bool:
		try:
			subprocess.run(
				[self.path, '-verifysamples', basename],
				stdout=subprocess.DEVNULL,
				stderr=subprocess.DEVNULL,
				check=True,
			)
		except subprocess.CalledProcessError:
			return False
		else:
			return True

	async def verifysamples_async(self, basename: 'Basename') -> bool:
		proc = await asyncio.subprocess.create_subprocess_exec(
			self.path,
			'-verifysamples',
			basename,
			stdout=subprocess.DEVNULL,
			stderr=subprocess.DEVNULL,
		)
		return_code = await proc.wait()
		return return_code == 0

	def verifysoftlist_all(self) -> Iterator[tuple['SoftwareListBasename', 'SoftwareBasename']]:
		proc = subprocess.run(
			[self.path, '-verifysoftlist'], capture_output=True, check=False, encoding='utf8'
		)
		# We don't actually care about the "no romsets found for software list "name"" message from stderr
		yield from _parse_verifysoftlist_output(proc.stdout)

	def verifysoftlist(self, basename: 'SoftwareListBasename') -> Iterator['SoftwareBasename']:
		proc = subprocess.run(
			[self.path, '-verifysoftlist', basename],
			capture_output=True,
			check=False,
			encoding='utf8',
		)
		# We don't actually care about the "no romsets found for software list "name"" message from stderr
		for _, software_basename in _parse_verifysoftlist_output(proc.stdout):
			yield software_basename

	def getsoftlist(self, name: 'SoftwareListBasename') -> XMLElement:
		return get_software_list(self.path, name)

	async def getsoftlist_async(self, name: 'SoftwareListBasename') -> XMLElement:
		return await get_software_list_async(self.path, name)

	def iter_all_xml(self) -> Iterator[tuple['Basename', XMLElement]]:
		yield from listxml_all(self.path, get_xml_reader(), unsafe=self.unsafe_listxml)

	def listxml(self, name: 'Basename') -> XMLElement:
		"""Lists just one machine, or raises KeyError if it was not found

		Returns:
			XMLElement
		"""
		return _listxml(self.path, get_xml_reader(), name)

	async def listxml_async(self, name: 'Basename') -> XMLElement:
		"""Lists just one machine, or raises KeyError if it was not found

		Returns:
			XMLElement
		"""
		return await _listxml_async(self.path, get_xml_reader(), name)

	def listxml_with_devices(self, name: 'Basename') -> Mapping['Basename', XMLElement]:
		"""Lists just one machine and its associated devices

		Returns:
			{basename: <machine> element}
		"""
		return _listxml_with_devices(self.path, get_xml_reader(), name)

	def iter_software_list_names(self) -> Iterator['SoftwareListBasename']:
		with subprocess.Popen(
			[self.path, '-listsoftware', '-nodtd'], stdout=subprocess.PIPE, stderr=subprocess.PIPE
		) as proc:
			assert proc.stdout is not None
			for element in get_xml_reader().iterparse(proc.stdout, 'softwarelist'):
				yield element.attrib['name']
			_, stderr = proc.communicate()
			if stderr:
				logger.info(stderr)

	@cached_property
	def software_list_names(self) -> Sequence['SoftwareListBasename']:
		return tuple(self.iter_software_list_names())

	@cached_property
	def version(self) -> str:
		return subprocess.check_output([self.path, '-version'], encoding='utf8')

	# other frontend commands:
	# listfull, listsource: could be possible to parse but not straightforward, maybe faster than getting the info manually with listxml and MachineElement
	# listclones, listbrothers: also just use listxml and MachineElement probably
	# listcrc
	# listroms
	# listsamples
	# TODO: romident - now this could be interesting instead of relying on software_finder, would it be faster if MAME is doing the work (including decompressing zip/7z)?
	# prints "Identifying <path>" and then takes a bit and prints (inner filename = ROM name <tab> software ID <tab> software name) for each file inside the archive or folder, and then "Out of X files, Y matched, Z did not match" or "No roms matched." if some weren't recognized
	# listdevices: <root> and machine full name, and tag + full name on each device, which is interesting because it's not actually the device basename and that doesn't seem to be in listxml I guess (e.g. pacman has a mainlatch, which is only in the device_ref in XML as ls259)
	# listslots, listbios, listmedia: don't think that would be worth parsing over just getting the info from MachineElement
	# listsoftware: This is just -getsoftlist for all of the machine's <softwarelist>s
	# verifysoftware: This is just -verifysoftlist for all of the machine's <softwarelist>s
	# listmidi, listnetwork if you are into that sort of thing I guess (but does it just list anything compiled in, whether you personally have it or not?)
	# validate if you are _really_ into that sort of thing but now we're just listing every single thing that doesn't start a machine
