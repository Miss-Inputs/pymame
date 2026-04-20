import logging
import shutil
from collections.abc import Collection
from pathlib import Path

import pydantic
import pydantic_settings

from pymame.mame_ini import MAMEini, UIini, try_get_mame_inis

logger = logging.getLogger(__name__)


def autodetect_mame_path() -> Path | None:
	which = shutil.which('mame')
	return Path(which) if which else None


class MAMESettings(pydantic_settings.BaseSettings):
	mame_executable_path: Path
	"""Path to MAME executable"""

	use_unsafe_listxml: bool = False
	"""Use an unsafe way of parsing output of -listxml which doesn't wait for the process to finish. Might be okay, but might deadlock"""
	# It's probably more okay than this description makes it out to be…
	xml_path: Path | None = None
	"""Read a whole file with the saved output of -listxml (or a datfile for some other MAME version) instead of using -listxml"""
	list_software_from_file: bool = True
	"""Read the .xml file directly instead of using -getsoftlist, to avoid subprocess and because the DTD does not result in the notes field being output"""

	# Search paths from mame.ini
	rom_paths: Collection[Path] = pydantic.Field(default_factory=tuple)
	hash_paths: Collection[Path] = pydantic.Field(default_factory=tuple)
	"""Location of software list .xml files (hashpath in mame.ini), for software list loading."""
	artwork_paths: Collection[Path] = pydantic.Field(default_factory=tuple)
	"""artpath in mame.ini"""
	# Search paths from ui.ini
	cat_path: Path | None = None
	"""categorypath in ui.ini (can this ever be more than one path?)"""
	dats_path: Path | None = None
	"""historypath in ui.ini (can this ever be more than one path?)"""
	ui_path: Path | None = None
	"""Folder for various UI files (ui_path in ui.ini), such as favorites.ini."""
	# Paths in mame.ini where things are saved to (and read from by us)
	plugin_config_home: Path | None = None
	"""homepath in mame.ini"""
	configs_path: Path | None = None
	"""cfg_directory in mame.ini"""

	@property
	def timer_db_path(self) -> Path | None:
		"""Path to the database used by the timer plugin, if our plugin home directory is known."""
		return self.plugin_config_home / 'timer' / 'timer.db' if self.plugin_config_home else None

	def _set_from_mame_ini(self, mame_ini: MAMEini):
		if mame_ini.rom_paths:
			self.rom_paths = mame_ini.rom_paths
		if mame_ini.hash_paths:
			self.hash_paths = mame_ini.hash_paths
		if mame_ini.artwork_paths:
			self.artwork_paths = mame_ini.artwork_paths
		if mame_ini.plugin_home:
			self.plugin_config_home = mame_ini.plugin_home
		if mame_ini.config_directory:
			self.configs_path = mame_ini.config_directory

	def _set_from_ui_ini(self, ui_ini: UIini):
		# historypath = try_get_path_from_ini(ui_ini, 'historypath', 'ui.ini')
		# categorypath = try_get_path_from_ini(ui_ini, 'categorypath', 'ui.ini')
		# ui_path = try_get_path_from_ini(ui_ini, 'ui_path', 'ui.ini')
		if ui_ini.dat_path:
			self.dats_path = ui_ini.dat_path
		if ui_ini.category_path:
			self.cat_path = ui_ini.category_path
		if ui_ini.ui_folder_path:
			self.ui_path = ui_ini.ui_folder_path

	@classmethod
	def autodetect(
		cls,
		mame_path: Path | None,
		mame_ini_path: Path | None = None,
		ui_ini_path: Path | None = None,
	):
		mame_path = mame_path or autodetect_mame_path()
		if not mame_path:
			# TODO: This might theoretically be wrong, maybe it does work with just an .xml file
			raise FileNotFoundError('Could not find MAME, nothing else will work')

		instance = cls(mame_executable_path=mame_path)
		mame_ini, ui_ini = try_get_mame_inis(
			mame_ini_path, ui_ini_path, warn_if_default_not_found=True
		)
		if mame_ini:
			instance._set_from_mame_ini(mame_ini)
		if ui_ini:
			instance._set_from_ui_ini(ui_ini)

		return instance
