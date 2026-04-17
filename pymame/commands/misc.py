"""MAME CLI commands that could be implemented with listxml() but could also just be called directly and then parsed"""

import asyncio
import logging
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from pymame.typedefs import Basename


logger = logging.getLogger(__name__)


def _parse_listfull(stdout: str) -> Iterator[tuple['Basename', str]]:
	lines = stdout.splitlines()
	for line in lines[1:]:
		# ignore line that just says "Name:" "Description:" at the top
		try:
			basename, full_name = line.split(maxsplit=1)
		except ValueError:
			logger.info('-listfull was unable to parse line: %s', line)
		else:
			full_name = full_name.strip('"')
			yield basename, full_name


def listfull(mame_path: Path, *basenames: str) -> dict['Basename', str]:
	proc = subprocess.run(
		[mame_path, '-listfull', *basenames], capture_output=True, text=True, check=True
	)
	return dict(_parse_listfull(proc.stdout))


async def listfull_async(mame_path: Path, *basenames: str) -> dict['Basename', str]:
	proc = await asyncio.subprocess.create_subprocess_exec(
		mame_path, '-listfull', *basenames, stdout=subprocess.PIPE, stderr=subprocess.PIPE
	)
	stdout, stderr = await proc.communicate()
	if proc.returncode:
		# no check=True for asyncio
		# This probably won't matter, as it just does this if one of the basenames is not recognized
		logger.warning('MAME -listfull returned %d: %s', proc.returncode, stderr.decode('utf-8'))
	return dict(_parse_listfull(stdout.decode('utf-8')))
