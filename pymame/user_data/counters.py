import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from pymame.elements import Counters, MAMEConfigFile
from pymame.xml_wrapper import get_xml_reader

if TYPE_CHECKING:
	from pymame.settings import MAMESettings
	from pymame.typedefs import Basename


def _parse_system_config(path: Path) -> MAMEConfigFile:
	reader = get_xml_reader()
	with path.open('rb') as f:
		xml = reader.read_from_file(f)
		return MAMEConfigFile(xml)


def get_counters(settings: 'MAMESettings', basename: 'Basename') -> Counters | None:
	if not settings.configs_path:
		return None
	cfg_path = settings.configs_path / f'{basename}.cfg'
	try:
		cfg = _parse_system_config(cfg_path)
	except FileNotFoundError:
		return None
	else:
		if not cfg.systems:
			return None
		return cfg.systems[0].counters


async def get_counters_async(settings: 'MAMESettings', basename: 'Basename') -> Counters | None:
	if not settings.configs_path:
		return None
	cfg_path = settings.configs_path / f'{basename}.cfg'
	try:
		cfg = await asyncio.to_thread(_parse_system_config, cfg_path)
	except FileNotFoundError:
		return None
	else:
		if not cfg.systems:
			return None
		return cfg.systems[0].counters
