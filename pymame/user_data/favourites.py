import asyncio
from collections.abc import Collection
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

from async_lru import alru_cache

if TYPE_CHECKING:
	from pymame.typedefs import Basename


@cache
def get_favourites(ui_path: Path) -> Collection['Basename']:
	ini_path = ui_path.joinpath('favorites.ini')
	lines = ini_path.read_text('utf8').splitlines()
	return frozenset(lines[3::16])


@alru_cache
async def get_favourites_async(ui_path: Path) -> Collection['Basename']:
	ini_path = ui_path.joinpath('favorites.ini')
	text = await asyncio.to_thread(ini_path.read_text, encoding='utf-8')
	lines = text.splitlines()
	return frozenset(lines[3::16])
