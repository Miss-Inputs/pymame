"""Wraps -verifyroms, -verifysoftlist, and -verifysamples"""

import asyncio
import dataclasses
import logging
import re
import subprocess
from collections.abc import AsyncIterator, Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from pymame.typedefs import Basename, SoftwareBasename, SoftwareListBasename

logger = logging.getLogger(__name__)


def verifyroms(mame_path: Path, basename: 'Basename') -> bool:
	try:
		subprocess.run(
			[mame_path, '-verifyroms', basename],
			stdout=subprocess.DEVNULL,
			stderr=subprocess.DEVNULL,
			check=True,
		)
	except subprocess.CalledProcessError:
		return False
	else:
		return True


async def verifyroms_async(mame_path: Path, basename: 'Basename') -> bool:
	proc = await asyncio.subprocess.create_subprocess_exec(
		mame_path,
		'-verifyroms',
		basename,
		stdout=asyncio.subprocess.DEVNULL,
		stderr=asyncio.subprocess.DEVNULL,
	)
	return_code = await proc.wait()
	return return_code == 0


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


def _parse_verifyroms_single(basename: 'Basename', stdout: str, stderr: str):
	if stderr.endswith('has no roms!\n'):
		# Devices do this, romless machines still just say "best available"
		# If more than one basename it will just not display it, and it will not be added to the count of "found" at the end
		return VerifyromsOutput(basename, None, 'no roms!')
	if stderr.endswith('not found!\n'):
		# If more than one basename it will just not display it, and it will not be added to the count of "found" at the end
		return VerifyromsOutput(basename, None, 'not found!')
	return next(_parse_verifyroms_output(stdout.splitlines()))


def verifyroms_with_info(mame_path: Path, basename: 'Basename') -> VerifyromsOutput:
	proc = subprocess.run(
		[mame_path, '-verifyroms', basename], capture_output=True, text=True, check=False
	)
	return _parse_verifyroms_single(basename, proc.stdout, proc.stderr)


async def verifyroms_with_info_async(mame_path: Path, basename: 'Basename'):
	proc = await asyncio.subprocess.create_subprocess_exec(
		mame_path, '-verifyroms', basename, stdout=subprocess.PIPE, stderr=subprocess.PIPE
	)
	stdout, stderr = await proc.communicate()
	return _parse_verifyroms_single(basename, stdout.decode('utf-8'), stderr.decode('utf-8'))


def verifyroms_multiple(
	mame_path: Path, basenames: Iterable['Basename']
) -> Iterator[VerifyromsOutput]:
	proc = subprocess.run(
		[mame_path, '-verifyroms', *basenames], capture_output=True, text=True, check=False
	)
	yield from _parse_verifyroms_output(proc.stdout.splitlines())


async def verifyroms_multiple_async(
	mame_path: Path, basenames: Iterable['Basename']
) -> AsyncIterator[VerifyromsOutput]:
	proc = await asyncio.subprocess.create_subprocess_exec(
		mame_path, '-verifyroms', *basenames, stdout=subprocess.PIPE, stderr=subprocess.PIPE
	)
	stdout, stderr = await proc.communicate()
	if proc.returncode:
		# This probably won't matter, as it just does this if one of the basenames is not recognized
		logger.warning('MAME -verifyroms returned %d: %s', proc.returncode, stderr.decode('utf-8'))
	for output in _parse_verifyroms_output(stdout.decode('utf-8').splitlines()):
		yield output


def verifysamples(mame_path: Path, basename: 'Basename') -> bool:
	try:
		subprocess.run(
			[mame_path, '-verifysamples', basename],
			stdout=subprocess.DEVNULL,
			stderr=subprocess.DEVNULL,
			check=True,
		)
	except subprocess.CalledProcessError:
		return False
	else:
		return True


async def verifysamples_async(mame_path: Path, basename: 'Basename') -> bool:
	proc = await asyncio.subprocess.create_subprocess_exec(
		mame_path, '-verifysamples', basename, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
	)
	return_code = await proc.wait()
	return return_code == 0


# TODO: Could parse the -verifysamples output perchance


def _parse_verifysoftlist_output(
	output: str,
) -> Iterator[tuple['SoftwareListBasename', 'SoftwareBasename']]:
	"""This doesn't capture any specific details of what goes on with bad software, just if it is there or not

	Yields:
		(Software list basename, software basename)"""
	# TODO: maybe it should parse that output
	for line in output.splitlines():
		line = line.strip()
		match = re.fullmatch(
			r'^romset (?P<listname>.+?):(?P<softwarename>.+?) is (?:best available|good)$', line
		)
		if match:
			yield match['listname'], match['softwarename']


# TODO: async versions of these, I guess
def verifysoftlist(
	mame_path: Path, softlist_names: Iterable['SoftwareListBasename']
) -> Iterator[tuple['SoftwareListBasename', 'SoftwareBasename']]:
	"""Yields all available software as tuples of (softlist basename, software basename)"""
	proc = subprocess.run(
		[mame_path, '-verifysoftlist', *softlist_names],
		capture_output=True,
		check=False,
		encoding='utf8',
	)
	# We don't actually care about the "no romsets found for software list "name"" message from stderr
	yield from _parse_verifysoftlist_output(proc.stdout)


def verifysoftlist_single(
	mame_path: Path, softlist_name: 'SoftwareListBasename'
) -> Iterator['SoftwareBasename']:
	for _, software_basename in verifysoftlist(mame_path, (softlist_name,)):
		yield software_basename
