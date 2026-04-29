from enum import Enum, auto
from typing import ClassVar


class MachineType(Enum):
	"""Different types of things emulated by MAME, which may be found in an arcade or not, and may be thought of as a normal arcade game or not"""

	Arcade = auto()
	"""Normal arcade game (I suck at wording)"""
	BIOS = auto()
	"""Arcade system BIOS that runs other arcade games"""
	CoinPusher = auto()
	"""Thing found in arcades that pushes coins"""
	ConsoleCartridge = auto()
	"""Cartridge for some game console, where the CPU or other hardware is in each cartridge and not the console, so for MAME it will be individual machines"""
	Device = auto()
	"""Device, not a whole system"""
	Gambling = auto()
	"""Gambling machine usually found in a casino and not an arcade"""
	Handheld = auto()
	"""Handheld game console with inbuilt games"""
	KiddyRide = auto()
	"""Thing found in public places (shopping centres etc) that kids ride on which isn't quite an arcade game but sort of is"""
	LCDHandheld = auto()
	"""Handheld game with ink graphics"""
	Redemption = auto()
	"""Sort of an arcade game that focuses more about winning tickets than gameplay"""
	MedalGame = auto()
	"""Like redemption but with medals"""
	Mechanical = auto()
	"""Game with mechanical elements"""
	Pinball = auto()
	"""Pinball machine (real pinballs, not a video game simulation of pinball)"""
	PlugAndPlay = auto()
	"""Home console that connects to a TV without any separate games"""
	PrintClub = auto()
	"""Booth for taking photos"""
	Other = auto()
	"""Some other thing that is not a game or otherwise something with its own specific machine type"""
	Unknown = auto()
	"""Something specifically listed as unknown in catlist/catver"""


class CatlistCategory:
	def __init__(self, category: str) -> None:
		if category.startswith('Arcade: '):
			self.is_arcade = True
			category = category[8:]
		else:
			self.is_arcade = False

		if category.startswith('TTL * '):
			self.extra, self._has_extra, self.category = category.partition(' * ')
		else:
			self.category, self._has_extra, self.extra = category.partition(' * ')
		self._components = self.category.split(' / ')

	def __str__(self) -> str:
		s = f'Catlist ({"/".join(self._components)}, type: {self.machine_type}, arcade: {self.is_arcade}'
		if self._has_extra:
			s += f', extra: {self.extra}'
		return s + ')'

	@property
	def is_ttl(self) -> bool:
		return self.extra == 'TTL'

	@property
	def is_mature(self) -> bool:
		return self.extra == 'Mature'

	@property
	def _is_plug_and_play(self) -> bool:
		if self.is_arcade:
			return False
		if self._components[0] in {
			# Some games are just stored directly as the genre (with subgenre) in catlist.ini like this, which seems strange, but okay
			'Driving',
			'MultiGame',
			'Music Game',
			'Platform',
			'Quiz',
			'Shooter',
			'TV Bundle',
			'Tabletop',
		}:
			return True
		return self._components[0] == 'Handheld' and "Plug n' Play TV Game" in self._components

	category_combo_types: ClassVar[dict[tuple[str, str], MachineType]] = {
		('Arcade', 'Unknown'): MachineType.Unknown,
		('Driving', 'Kiddie Ride'): MachineType.KiddyRide,
		('Electromechanical', 'Bingo'): MachineType.Gambling,
		('Electromechanical', 'Kids Game Ride'): MachineType.KiddyRide,
		('Electromechanical', 'Pinball'): MachineType.Pinball,
		('Electromechanical', 'Reels'): MachineType.Gambling,
		('Handheld', 'Dedicated Game'): MachineType.Handheld,  # might be LCDHandheld… hrm
		('Handheld', 'Electronic LCD Game'): MachineType.LCDHandheld,
		('Handheld', 'Multi-Games'): MachineType.Handheld,
		('Medal Game', 'Coin Pusher'): MachineType.CoinPusher,
		('Misc.', 'Coin Pusher'): MachineType.CoinPusher,
		('Misc.', 'Print Club'): MachineType.PrintClub,
		('Misc.', 'Unknown Arcade Game'): MachineType.Unknown,
		('Misc.', 'Unknown'): MachineType.Unknown,
		('Non Arcade', 'Unknown'): MachineType.Unknown,
		('System', 'BIOS'): MachineType.BIOS,
		('System', 'Device'): MachineType.Device,
		('Watch', 'LCD Game'): MachineType.LCDHandheld,
		# Electromechanical / Rocking Car might also mean kiddy ride?
		# public-facing non-game machines, I guess, not sure if any of these deserve a more specific MachineType
		('Electromechanical', 'Change Money'): MachineType.Other,
		('Electromechanical', 'Utilities'): MachineType.Other,
		('Misc.', 'Laserdisc Simulator'): MachineType.Other,
	}
	genre_types: ClassVar[dict[str, MachineType]] = {
		'Casino': MachineType.Gambling,
		'Coin Pusher': MachineType.CoinPusher,
		'Electromechanical': MachineType.Mechanical,
		'Gambling': MachineType.Gambling,
		'Medal Game': MachineType.MedalGame,
		'Redemption Game': MachineType.Redemption,
		'Slot Machine': MachineType.Gambling,
	}

	@property
	def machine_type(self) -> MachineType:
		combo = (self._components[0], self._components[1])
		if combo in self.category_combo_types:
			return self.category_combo_types[combo]
		if self._components[0] in self.genre_types:
			return self.genre_types[self._components[0]]
		if self.is_arcade and self._components[0] != 'Utilities':
			return MachineType.Arcade
		if self._is_plug_and_play:
			return MachineType.PlugAndPlay
		return MachineType.Other

	@property
	def genre(self) -> str | None:
		if self.machine_type in {
			MachineType.Mechanical,
			MachineType.Redemption,
			MachineType.MedalGame,
		}:
			return self._components[1]
		if self.is_arcade:
			return self._components[0]
		if self._is_plug_and_play:
			if self._components[1] == "Plug n' Play TV Game" and len(self._components) > 2:
				return self._components[2]
			if self._components[0] != 'Handheld':
				return self._components[0]
		return None

	@property
	def subgenre(self) -> str | None:
		if self.machine_type in {
			MachineType.Mechanical,
			MachineType.Redemption,
			MachineType.MedalGame,
		}:
			return self._components[2] if len(self._components) > 2 else None
		if self.is_arcade and len(self._components) > 1:
			return self._components[1]
		if (
			self._is_plug_and_play
			and self._components[0] != 'Handheld'
			and len(self._components) == 2
		):
			return self._components[1]
		return None
