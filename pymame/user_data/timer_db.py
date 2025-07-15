import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from pymame.typedefs import Basename, SoftwareBasename, SoftwareListBasename


@dataclass
class TimerDBRow:
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
	systems: Mapping['Basename', TimerDBRow]
	software: Mapping[tuple['SoftwareListBasename', 'SoftwareBasename'], TimerDBRow]


@cache
def load_timer_db(db_path: Path) -> TimerDB:
	with sqlite3.connect(db_path) as db:
		db.row_factory = sqlite3.Row
		drivers: dict[Basename, TimerDBRow] = {}
		software: dict[tuple[SoftwareListBasename, SoftwareBasename], TimerDBRow] = {}
		for row in db.execute('SELECT * FROM timer'):
			if row['software']:
				softlist = row['softlist']
				software[
					row['driver'], f'{softlist}:{row["software"]}' if softlist else row['software']
				] = TimerDBRow.from_db_row(row)
			else:
				drivers[row['driver']] = TimerDBRow.from_db_row(row)
		return TimerDB(drivers, software)


def try_load_timer_db(db_path: Path) -> TimerDB | None:
	try:
		return load_timer_db(db_path)
	except FileNotFoundError:
		return None
