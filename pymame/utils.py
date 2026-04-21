import asyncio
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from configparser import RawConfigParser
from enum import Enum
from pathlib import Path
from typing import Any


def try_parse_int(s: str | None, base: int = 10, *, allow_different_base: bool = True):
	if not s:
		return None
	if allow_different_base and s.startswith('0x'):
		base = 16
	try:
		return int(s, base)
	except ValueError:
		return None


def try_parse_hexbytes(s: str | None, default: bytes | None = None):
	if not s:
		return default
	try:
		return bytes.fromhex(s)
	except ValueError:
		return default


def try_parse_strenum[EnumType: Enum](s: str | None, enum_type: type[EnumType]):
	if not s:
		return None
	try:
		return enum_type(s)
	except ValueError:
		return None


class NoNonsenseConfigParser(RawConfigParser):
	"""No "interpolation", no using : as a delimiter, no lowercasing every option, that's all silly"""

	def __init__(
		self,
		defaults: Any = None,
		*,
		allow_no_value: bool = False,
		strict: bool = True,
		empty_lines_in_values: bool = True,
		delimiters: tuple[str, ...] = ('=',),
		comment_prefixes: str = '#',
	):
		# Less of these weird options please, just parse the ini
		super().__init__(
			defaults=defaults,
			allow_no_value=allow_no_value,
			delimiters=delimiters,
			comment_prefixes=comment_prefixes,
			strict=strict,
			empty_lines_in_values=empty_lines_in_values,
		)

	def optionxform(self, optionstr: str) -> str:
		return optionstr


def multidict[KT, VT](tuples: Iterable[tuple[KT, VT]]) -> Mapping[KT, Sequence[VT]]:
	d = defaultdict(list)
	for k, v in tuples:
		d[k].append(v)
	return dict(d)


def _listdir_sync(path: Path):
	return list(path.iterdir())


async def listdir_async(path: Path):
	"""Calling to_thread on iterdir and then on several calls to next() to make an async version of iterdir() seems to be slow, so just get all child paths at once with async instead"""
	return await asyncio.to_thread(_listdir_sync, path)
