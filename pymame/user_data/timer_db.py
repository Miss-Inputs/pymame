import asyncio
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

from async_lru import alru_cache

if TYPE_CHECKING:
	from pymame.typedefs import Basename, SoftwareBasename, SoftwareListBasename


@dataclass
class TimerDBEntry:
	total_time: timedelta
	play_count: int
	emulated_time: timedelta

	@classmethod
	def from_db_row(cls, row: sqlite3.Row):
		return cls(
			timedelta(seconds=row['total_time']),
			row['play_count'],
			timedelta(seconds=row['emu_sec'], microseconds=row['emu_nsec'] / 1000),
		)


@dataclass
class TimerDB:
	systems: Mapping['Basename', TimerDBEntry]
	software: Mapping[tuple['SoftwareListBasename', 'SoftwareBasename'], TimerDBEntry]


def _load_timer_db(db_path: Path) -> TimerDB:
	with sqlite3.connect(db_path) as db:
		db.row_factory = sqlite3.Row
		drivers: dict[Basename, TimerDBEntry] = {}
		software: dict[tuple[SoftwareListBasename, SoftwareBasename], TimerDBEntry] = {}
		for row in db.execute('SELECT * FROM timer'):
			if row['software']:
				softlist = row['softlist']
				software[
					row['driver'], f'{softlist}:{row["software"]}' if softlist else row['software']
				] = TimerDBEntry.from_db_row(row)
			else:
				drivers[row['driver']] = TimerDBEntry.from_db_row(row)
		return TimerDB(drivers, software)


load_timer_db = cache(_load_timer_db)


@alru_cache
async def load_timer_db_async(db_path: Path) -> TimerDB:
	return await asyncio.to_thread(_load_timer_db, db_path)


def try_load_timer_db(db_path: Path) -> TimerDB | None:
	try:
		return load_timer_db(db_path)
	except FileNotFoundError:
		return None


async def try_load_timer_db_async(db_path: Path) -> TimerDB | None:
	try:
		return await load_timer_db_async(db_path)
	except FileNotFoundError:
		return None
