import logging
import re
from collections.abc import Mapping, Sequence
from os.path import expandvars
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def try_get_paths_from_ini(
	ini: Mapping[str, str], key: str, ini_name_for_log: Any = None
) -> Sequence[Path]:
	if key not in ini:
		return ()
	exist_paths: list[Path] = []
	for path in parse_mame_ini_path(ini[key]):
		if not path.is_dir():
			logger.warning(
				'%s had %s in %s, but it does not exist or is not a directory',
				key,
				path,
				ini_name_for_log,
			)
		else:
			exist_paths.append(path)
	return exist_paths


def try_get_path_from_ini(
	ini: Mapping[str, str], key: str, ini_name_for_log: Any = None
) -> Path | None:
	paths = try_get_paths_from_ini(ini, key, ini_name_for_log)
	if not paths:
		return None
	if len(paths) > 1:
		logger.warning(
			'%s in %s should only have one value, but it has: %s', key, ini_name_for_log, paths
		)
	return paths[0]


def parse_mame_ini_path(value: str) -> Sequence[Path]:
	if value[0] == '"' and value[-1] == '"':
		value = value[1:-1]
	return [Path(expandvars(value)) for value in value.split(';')]


# It is possible to have just a key with no value, but that means the config value is not set, so it's not important
ini_line_regex = re.compile(r'^(?P<key>\w+)\s*(?P<value>.+)(?:#.+)?$')


def read_mame_ini(path: Path) -> dict[str, str]:
	d: dict[str, str] = {}
	for line in path.read_text('utf8').splitlines():
		line = line.strip()
		if line.startswith('#') or not line:
			continue
		match = ini_line_regex.match(line)
		if match:
			d[match['key']] = match['value']
	return d


def try_read_ini(name: str, ini_dir: Path, default_ini_dir: Path) -> dict[str, str] | None:
	"""Attempts to read an  .ini file with a specific name (with extension), checking first in ini_dir, and then default_ini_dir if not there."""
	path = ini_dir / name
	try:
		ini = read_mame_ini(path)
	except FileNotFoundError:
		if ini_dir != default_ini_dir:
			logger.warning(
				'inipath was set to %s but %s was not found in there, trying default', ini_dir, name
			)
			return try_read_ini(name, default_ini_dir, default_ini_dir)
		return None
	except UnicodeDecodeError as ex:
		logger.warning('Could not read mame.ini at %s: %s', path, ex)
	else:
		return ini


class MAMEini:
	def __init__(self, ini_file: Path | Mapping[str, str]) -> None:
		if isinstance(ini_file, Path):
			ini_file = read_mame_ini(ini_file)

		self._known_keys = {
			'homepath',
			'rompath',
			'hashpath',
			'artpath',
			'inipath',
			'cfg_directory',
		}
		# others that might end up being worth using: samplepath  (multipath), swpath (multipath, for loose software), nvram_directory, snapshot_directory, diff_directory
		self.data = ini_file

	# Can't help but feel there's a better not-repeating-oneself way to do this, oh well
	@property
	def rom_paths(self):
		"""Includes CHDs as well"""
		return try_get_paths_from_ini(self.data, 'rompath', 'mame.ini')

	@property
	def hash_paths(self):
		return try_get_paths_from_ini(self.data, 'hashpath', 'mame.ini')

	@property
	def artwork_paths(self):
		return try_get_paths_from_ini(self.data, 'artpath', 'mame.ini')

	@property
	def plugin_home(self):
		return try_get_path_from_ini(self.data, 'homepath', 'mame.ini')

	@property
	def ini_path(self):
		"""TODO: This is actually a multipath, but it seems a bit weird to actually have multiple paths here (arguably weird at all to set this to anything except the default)"""
		return try_get_path_from_ini(self.data, 'inipath', 'mame.ini')

	@property
	def config_directory(self):
		return try_get_path_from_ini(self.data, 'cfg_directory', 'mame.ini')

	@property
	def other_settings(self):
		return {k: v for k, v in self.data.items() if k not in self._known_keys}


class UIini:
	def __init__(self, ini_file: Path | Mapping[str, str]) -> None:
		if isinstance(ini_file, Path):
			ini_file = read_mame_ini(ini_file)

		self._known_keys = {'historypath', 'categorypath', 'ui_path'}
		self.data = ini_file

	@property
	def dat_path(self):
		return try_get_path_from_ini(self.data, 'historypath', 'ui.ini')

	@property
	def category_path(self):
		return try_get_path_from_ini(self.data, 'categorypath', 'ui.ini')

	@property
	def ui_folder_path(self):
		return try_get_path_from_ini(self.data, 'ui_path', 'ui.ini')


def try_get_mame_inis(
	mame_ini_path: Path | None, ui_ini_path: Path | None, *, warn_if_default_not_found: bool = True
):
	"""Tries to get mame.ini and ui.ini, or returns None if it cannot."""
	default_mame_ini_dir = ini_dir = Path('~/.mame/').expanduser()
	# TODO: Surely this is different on Windows, but eh, it's just a default so it just means Windows users will need to figure it out
	# inipath is set within mame.ini, but if that's changed, how would you know without the inipath to know where mame.ini is? Hrm there's gotta be something more to it
	default_mame_ini_path = default_mame_ini_dir / 'mame.ini'
	mame_ini_path = mame_ini_path or default_mame_ini_path
	try:
		mame_ini = MAMEini(mame_ini_path)
	except FileNotFoundError:
		if mame_ini_path != default_mame_ini_path:
			logger.warning('mame.ini not found at %s', mame_ini_path)
		elif warn_if_default_not_found:
			logger.warning(
				'mame.ini not found at its default location at %s', default_mame_ini_path
			)
		mame_ini = None
	else:
		if mame_ini.ini_path:
			ini_dir = mame_ini.ini_path
	if ui_ini_path:
		ui_ini = UIini(ui_ini_path)
	else:
		ui_ini_raw = try_read_ini('ui.ini', ini_dir, default_mame_ini_dir)
		ui_ini = UIini(ui_ini_raw) if ui_ini_raw else None
	return mame_ini, ui_ini
