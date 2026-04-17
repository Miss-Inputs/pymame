"""Wraps -getsoftlist, -listsoftware"""

import asyncio.subprocess
import logging
import subprocess
from collections.abc import Iterator
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

from async_lru import alru_cache

from pymame.xml_wrapper import get_xml_reader

if TYPE_CHECKING:
	from pymame.typedefs import SoftwareListBasename

logger = logging.getLogger(__name__)


@cache
def getsoftlist(mame_path: Path, name: 'SoftwareListBasename'):
	proc = subprocess.run([mame_path, '-getsoftlist', name], capture_output=True, check=True)
	stderr = proc.stderr.strip()
	if stderr == b'No such software lists found':
		# It seems it will still return 0 in this case
		raise KeyError(name)
	if stderr:
		logger.warning('MAME printed to stderr when getting %s software list: %s', name, stderr)
	return get_xml_reader().read(proc.stdout)


@alru_cache
async def getsoftlist_async(mame_path: Path, name: 'SoftwareListBasename'):
	proc = await asyncio.subprocess.create_subprocess_exec(
		mame_path, '-getsoftlist', name, stdout=subprocess.PIPE, stderr=subprocess.PIPE
	)
	stdout, stderr = await proc.communicate()
	stderr = stderr.strip()
	if stderr == b'No such software lists found':
		# It seems it will still return 0 in this case
		raise KeyError(name)
	if stderr:
		logger.warning('MAME printed to stderr when getting %s software list: %s', name, stderr)
	return get_xml_reader().read(stdout)


def iter_software_list_names(mame_path: Path) -> Iterator['SoftwareListBasename']:
	with subprocess.Popen(
		[mame_path, '-listsoftware', '-nodtd'], stdout=subprocess.PIPE, stderr=subprocess.PIPE
	) as proc:
		assert proc.stdout is not None
		for element in get_xml_reader().iterparse(proc.stdout, 'softwarelist'):
			yield element.attrib['name']
		_, stderr = proc.communicate()
		if stderr:
			logger.info(stderr)
