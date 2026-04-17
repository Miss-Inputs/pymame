import asyncio
import asyncio.subprocess
import logging
import subprocess
from collections.abc import AsyncIterator, Iterator, Mapping
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

from async_lru import alru_cache

if TYPE_CHECKING:
	from pymame.typedefs import Basename
	from pymame.xml_wrapper import XMLElement, XMLElementType_co, XMLReader

logger = logging.getLogger(__name__)


def _listxml_all_unsafe(
	mame_path: Path, reader: 'XMLReader[XMLElementType_co]', *, capture_stderr: bool = False
):
	# For some reason it breaks sometimes if capturing stderr??
	with subprocess.Popen(
		[mame_path, '-listxml'],
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
	reader: 'XMLReader[XMLElementType_co]',
	*,
	unsafe: bool = False,
	capture_stderr: bool = False,
) -> Iterator[tuple['Basename', 'XMLElement']]:
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
	mame_path: Path, reader: 'XMLReader[XMLElementType_co]', *, capture_stderr: bool = False
) -> AsyncIterator[tuple['Basename', 'XMLElement']]:
	# I should use asyncio.subprocess here, but meh
	# TODO: Yeah nah you should
	# TODO: This isn't actually used right now, figure out where we want to use it
	sentinel = object()

	iterator = await asyncio.to_thread(
		listxml_all, mame_path, reader, capture_stderr=capture_stderr
	)
	while (element := await asyncio.to_thread(next, iterator, sentinel)) is not sentinel:
		assert isinstance(element, tuple)
		yield element


@cache
def listxml_as_dict(
	mame_path: Path, reader: 'XMLReader[XMLElementType_co]', *, unsafe: bool = False
) -> Mapping['Basename', 'XMLElement']:
	return dict(listxml_all(mame_path, reader, unsafe=unsafe))


@cache
def listxml(
	mame_path: Path, reader: 'XMLReader[XMLElementType_co]', basename: 'Basename'
) -> 'XMLElement':
	proc = subprocess.run([mame_path, '-listxml', basename], check=True, capture_output=True)
	if proc.stderr:
		logger.info(proc.stderr)
	machine = reader.read(proc.stdout).find_first('machine')
	if not machine:
		raise KeyError(basename)
	return machine


@alru_cache
async def listxml_async(
	mame_path: Path, reader: 'XMLReader[XMLElementType_co]', basename: 'Basename'
) -> 'XMLElement':
	proc = await asyncio.subprocess.create_subprocess_exec(
		mame_path, '-listxml', basename, stdout=subprocess.PIPE, stderr=subprocess.PIPE
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
def listxml_with_devices(
	mame_path: Path, reader: 'XMLReader[XMLElementType_co]', basename: 'Basename'
) -> dict['Basename', 'XMLElement']:
	proc = subprocess.run([mame_path, '-listxml', basename], check=True, capture_output=True)
	if proc.stderr:
		logger.info(proc.stderr)
	return {xml.attrib['name']: xml for xml in reader.read(proc.stdout).iter('machine')}
