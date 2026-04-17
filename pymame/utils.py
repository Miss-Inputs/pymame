from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from configparser import RawConfigParser
from enum import Enum
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
		comment_prefixes: str = '#',
	):
		# Less of these weird options please, just parse the ini
		super().__init__(
			defaults=defaults,
			allow_no_value=allow_no_value,
			delimiters='=',
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
