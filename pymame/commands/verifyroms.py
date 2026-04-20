"""Wraps -verifyroms, -verifysoftlist, and -verifysamples"""

import asyncio
import logging
import re
import subprocess
from collections.abc import AsyncIterator, Iterable, Iterator, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePath
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


class AuditSubstatus(StrEnum):
	NeedsRedump = 'NEEDS REDUMP'
	NoGoodDump = 'NOT FOUND - NO GOOD DUMP KNOWN'
	NoGoodDumpButFound = 'NO GOOD DUMP KNOWN'
	BadChecksum = 'INCORRECT CHECKSUM'
	BadLength = 'INCORRECT LENGTH'
	NotFound = 'NOT FOUND'
	Optional = 'NOT FOUND BUT OPTIONAL'


@dataclass
class ROMStatus:
	basename: 'Basename'
	"""romset the missing ROM is from, which is usually but not always the basename passed in as an argument (or that is being checked here)"""
	filename: PurePath
	size: int | None
	"""The size the ROM is supposed to be (can be None for disks)"""
	status: AuditSubstatus
	found_size: int | None = None
	"""If status == BadLength, this is the incorrect size of the ROM that was found"""

	# Nah I'm not going to convert all these CRC32s/SHA1s to bytes, I'll just say they're for display purposes
	expected_crc32: str | None = None
	"""If status == BadChecksum, this is what the CRC32 is supposed to be"""
	expected_sha1: str | None = None
	"""If status == BadChecksum, this is what the SHA1 is supposed to be"""
	expected_bad_dump: bool | None = None
	"""If status == BadChecksum, this is True if this ROM is expected to be a known bad dump, otherwise False"""
	found_crc32: str | None = None
	found_sha1: str | None = None

	@property
	def is_best_available(self) -> bool:
		"""If it is known to be bad or missing, not a lot we can do about it"""
		return self.status in {
			AuditSubstatus.NoGoodDump,
			AuditSubstatus.NoGoodDumpButFound,
			AuditSubstatus.NeedsRedump,
		}


class AuditStatus(StrEnum):
	Good = 'good'
	BestAvailable = 'best available'
	Bad = 'bad'
	NotFound = 'not found'
	NoRoms = 'has no roms'


@dataclass
class VerifyromsOutput:
	basename: 'Basename'
	romof: 'Basename | None'
	"""Parent set/BIOS/etc if any"""
	status: AuditStatus
	bad_roms: Sequence[ROMStatus]
	"""Anything printed for this romset about what particular ROMs are bad/have no good dump etc"""

	@property
	def is_okay(self) -> bool:
		return self.status in {AuditStatus.Good, AuditStatus.BestAvailable, AuditStatus.NoRoms}


# These regexes are why I regret doing this and feel like I should just be reimplementing the command in Python manually… oh well
_verifyroms_rom_line_reg = re.compile(
	r'(?P<basename>\w+)\s*:\s*(?P<filename>.+?)(?:\s+\((?P<size>\d+) bytes\))? - (?P<status>[^()]+)(?:$|( \((?P<parent>\w+?)\)))'
)
_verifyroms_checksum_line_reg = re.compile(
	r'\s*(?:EXPECTED|FOUND):\s*(?:CRC\((?P<crc32>\w{8})\))?(?:\s*SHA1\((?P<sha1>\w+)\))?\s*(?P<flag>BAD_DUMP)?$'
)
# I can't even be bothered counting how many characters are supposed to be in a SHA1 anymore
_verifyroms_line_reg = re.compile(
	r'romset (?P<basename>\w+)(?:\s+\[(?P<romof>\w+)\]\s*)? is (?P<status>best available|good|bad)$'
)


def _parse_rom_info_lines(lines: Iterable[str]):
	it = iter(lines)
	for line in it:
		line = line.strip()
		m = _verifyroms_rom_line_reg.match(line)
		if not m:
			logger.info('Unrecognized ROM line from -verifyroms: %s', line)
			continue
		filename = PurePath(m['filename'])
		size = int(m['size']) if m['size'] else None
		parent = m['parent'] or None
		basename = parent or m['basename']
		found_size = None
		found_crc = found_sha = expected_crc = expected_sha = expected_bad = None

		status_raw, _, extra = m['status'].partition(':')
		status = AuditSubstatus(status_raw)
		if extra:
			if status == AuditSubstatus.BadLength:
				found_size = int(extra.strip().removesuffix(' bytes'))
			else:
				logger.info('Unhandled extra info in line %s: "%s"', line, extra)
		if status == AuditSubstatus.BadChecksum:
			expected_line = next(it)
			m = _verifyroms_checksum_line_reg.fullmatch(expected_line)
			if m:
				expected_crc = m['crc32'] or None
				expected_sha = m['sha1'] or None
				expected_bad = m['flag'] == 'BAD_DUMP'
			else:
				logger.info(
					'Unrecognized expected checksum line from -verifyroms: %s', expected_line
				)
			found_line = next(it)
			m = _verifyroms_checksum_line_reg.fullmatch(found_line)
			if m:
				found_crc = m['crc32'] or None
				found_sha = m['sha1'] or None
			else:
				logger.info('Unrecognized found checksum line from -verifyroms: %s', found_line)

		yield ROMStatus(
			basename,
			filename,
			size,
			status,
			found_size,
			expected_crc,
			expected_sha,
			expected_bad,
			found_crc,
			found_sha,
		)


def _parse_verifyroms_output(lines: Iterable[str]) -> Iterator[VerifyromsOutput]:
	current_info_lines = []

	for line in lines:
		line = line.strip()
		match = _verifyroms_line_reg.fullmatch(line)
		if match:
			# info for each basename is printed before the line for that basename, not after it
			roms = list(_parse_rom_info_lines(current_info_lines))
			current_info_lines.clear()
			status = AuditStatus(match['status'])
			yield VerifyromsOutput(match['basename'], match['romof'] or None, status, roms)
		elif 'were OK' not in line:
			current_info_lines.append(line)
		else:
			logger.info('Unrecognized line from -verifyroms: %s', line)


def _parse_verifyroms_single(basename: 'Basename', stdout: str, stderr: str):
	if stderr.endswith('has no roms!\n'):
		# Devices do this, romless machines still just say "best available"
		# If more than one basename it will just not display it, and it will not be added to the count of "found" at the end
		return VerifyromsOutput(basename, None, AuditStatus.NoRoms, ())
	if stderr.endswith('not found!\n'):
		# If more than one basename it will just not display it, and it will not be added to the count of "found" at the end
		return VerifyromsOutput(basename, None, AuditStatus.NotFound, ())
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
		(Software list basename, software basename) for every software basename that is okay (good or best available)"""
	# TODO: maybe it should parse that output
	for line in output.splitlines():
		line = line.strip()
		match = re.fullmatch(
			r'^romset (?P<listname>.+?):(?P<softwarename>.+?) is (?:best available|good)$', line
		)
		if match:
			yield match['listname'], match['softwarename']


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
	# We don't necessarily care about the "no romsets found for software list "name"" message from stderr (at least for now), and the return code is 5 = any softlist name was not recognized or 2 = any romset was bad
	yield from _parse_verifysoftlist_output(proc.stdout)


async def verifysoftlist_async(
	mame_path: Path, softlist_names: Iterable['SoftwareListBasename']
) -> AsyncIterator[tuple['SoftwareListBasename', 'SoftwareBasename']]:
	"""Yields all available software as tuples of (softlist basename, software basename)"""
	proc = await asyncio.subprocess.create_subprocess_exec(
		mame_path,
		'-verifysoftlist',
		*softlist_names,
		stdout=subprocess.PIPE,
		stderr=subprocess.DEVNULL,
	)
	stdout, _ = await proc.communicate()
	for basename in _parse_verifysoftlist_output(stdout.decode('utf8')):
		yield basename


def verifysoftlist_single(
	mame_path: Path, softlist_name: 'SoftwareListBasename'
) -> Iterator['SoftwareBasename']:
	for _, software_basename in verifysoftlist(mame_path, (softlist_name,)):
		yield software_basename


async def verifysoftlist_single_async(
	mame_path: Path, softlist_name: 'SoftwareListBasename'
) -> AsyncIterator['SoftwareBasename']:
	async for _, software_basename in verifysoftlist_async(mame_path, (softlist_name,)):
		yield software_basename
