import logging
import re
import shutil
from collections.abc import Collection, Mapping, Sequence
from os.path import expandvars
from pathlib import Path
from typing import Any

import pydantic
import pydantic_settings

logger = logging.getLogger(__name__)


def autodetect_mame_path() -> Path | None:
	which = shutil.which('mame')
	return Path(which) if which else None


# It is possible to have just a key with no value, but that means the config value is not set, so it's not important
ini_line_regex = re.compile(r'^(?P<key>\w+)\s*(?P<value>.+)(?:#.+)?$')


def parse_mame_ini_path(value: str) -> Sequence[Path]:
	if value[0] == '"' and value[-1] == '"':
		value = value[1:-1]
	return [Path(expandvars(value)) for value in value.split(';')]


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


def try_get_path_from_ini(ini: Mapping[str, str], key: str, ini_name_for_log: Any = None):
	paths = try_get_paths_from_ini(ini, key, ini_name_for_log)
	if not paths:
		return None
	if len(paths) > 1:
		logger.warning(
			'%s in %s should only have one value, but it has: %s', key, ini_name_for_log, paths
		)
	return paths[0]


def read_mame_ini(path: Path) -> Mapping[str, str]:
	d: dict[str, str] = {}
	for line in path.read_text().splitlines():
		line = line.strip()
		if line.startswith('#') or not line:
			continue
		match = ini_line_regex.match(line)
		if match:
			d[match['key']] = match['value']
	return d


def _try_read_ini(name: str, ini_dir: Path, default_ini_dir: Path) -> Mapping[str, str] | None:
	path = ini_dir / name
	try:
		ini = read_mame_ini(path)
	except FileNotFoundError:
		if ini_dir != default_ini_dir:
			logger.warning(
				'inipath was set to %s but %s was not found in there, trying default', ini_dir, name
			)
			return _try_read_ini(name, default_ini_dir, default_ini_dir)
		return None
	else:
		return ini


class MAMESettings(pydantic_settings.BaseSettings):
	mame_executable_path: Path
	"""Path to MAME executable"""
	cat_path: Path | None = None
	"""categorypath in ui.ini (can this ever be more than one path?)"""
	dats_path: Path | None = None
	"""historypath in ui.ini (can this ever be more than one path?)"""
	artwork_paths: Collection[Path] = pydantic.Field(default_factory=tuple)
	"""artpath in mame.ini"""
	plugin_config_home: Path | None = None
	"""homepath in mame.ini"""
	configs_path: Path | None = None
	"""cfg_directory in mame.ini"""
	ui_path: Path | None = None
	"""Folder for various UI files (ui_path in ui.ini)"""
	hash_paths: Collection[Path] = pydantic.Field(default_factory=tuple)
	"""Location of software list .xml files (hashpath in mame.ini)"""

	use_unsafe_listxml: bool = False
	"""Use an unsafe way of parsing output of -listxml which doesn't wait for the process to finish. Might be okay, but might deadlock"""
	xml_path: Path | None = None
	"""Read a whole file with the saved output of -listxml (or a datfile for some other MAME version) instead of using -listxml"""
	list_software_from_file: bool = True
	"""Read the .xml file directly instead of using -getsoftlist, to avoid subprocess and because the DTD does not result in the notes field being output"""

	@property
	def timer_db_path(self) -> Path | None:
		"""Path to the database used by the timer plugin, if our plugin home directory is known."""
		return self.plugin_config_home / 'timer' / 'timer.db' if self.plugin_config_home else None

	@classmethod
	def autodetect(cls, mame_path: Path | None):
		mame_path = mame_path or autodetect_mame_path()
		if not mame_path:
			raise FileNotFoundError('Could not find MAME, nothing else will work')

		homepath = None
		hashpath = ()
		artpath = ()
		cfg_directory = None

		historypath = None
		categorypath = None
		ui_path = None

		default_mame_ini_dir = ini_dir = Path('~/.mame/').expanduser()
		# TODO: Surely this is different on Windows, but eh, it's a default and Windows users would need to figure it out on their own
		# inipath is set within mame.ini, but if that's changed, how would you know without the inipath to know where mame.ini is? Hrm there's gotta be something more to it
		default_mame_ini = default_mame_ini_dir / 'mame.ini'
		if default_mame_ini.is_file():
			ini = read_mame_ini(default_mame_ini)
			homepath = try_get_path_from_ini(ini, 'homepath', 'mame.ini')
			# rompath
			hashpath = try_get_paths_from_ini(ini, 'hashpath', 'mame.ini')
			# samplepath
			artpath = try_get_paths_from_ini(ini, 'artpath', 'mame.ini')
			# ctrlrpath
			inipath = try_get_path_from_ini(ini, 'inipath', 'mame.ini')
			if inipath:
				ini_dir = inipath
			# fontpath
			# cheatpath
			# crosshairpath
			# pluginspath
			# languagepath
			# swpath: Not actually software related
			# output directories:
			cfg_directory = try_get_path_from_ini(ini, 'cfg_directory', 'mame.ini')
			# nvram_directory: Saved data (NVRAM)
			# input_directory
			# state_directory: Savestates
			# snapshot_directory: Screenshots
			# diff_directory: Where diffs to disk images get saved I think
			# comment_directory
			# share_directory
		else:
			logger.warning(
				'MAME is found, but the config file is not in its default location at %s',
				default_mame_ini,
			)

		ui_ini = _try_read_ini('ui.ini', ini_dir, default_mame_ini_dir)
		if ui_ini:
			historypath = try_get_path_from_ini(ui_ini, 'historypath', 'ui.ini')
			categorypath = try_get_path_from_ini(ui_ini, 'categorypath', 'ui.ini')
			ui_path = try_get_path_from_ini(ui_ini, 'ui_path', 'ui.ini')
		else:
			logger.warning('MAME is found, but ui.ini was not found')
		# images:
		# cabinets_directory
		# cpanels_directory
		# pcbs_directory
		# flyers_directory
		# marquees_directory
		# artwork_preview_directory
		# icons_directory
		# covers_directory
		# screenshots:
		# titles_directory: Title screen
		# ends_directory: Ending screen
		# bosses_directory: Boss fight
		# logos_directory: Screen showing the logo
		# scores_directory: High score screen
		# versus_directory: VS mode
		# gameover_directory: Game over
		# howto_directory: Instructions
		# select_directory: Character select screen

		return cls(
			mame_executable_path=mame_path,
			plugin_config_home=homepath,
			hash_paths=hashpath,
			artwork_paths=artpath,
			configs_path=cfg_directory,
			dats_path=historypath,
			cat_path=categorypath,
			ui_path=ui_path,
		)
