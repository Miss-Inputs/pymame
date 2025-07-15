from enum import Enum, auto


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
	Gambling = auto()
	"""Gambling machine usually found in a casino and not an arcade"""
	Handheld = auto()
	"""Handheld game console with inbuilt games"""
	LCDHandheld = auto()
	"""Handheld game with ink graphics"""
	Redemption = auto()
	"""Sort of an arcade game that focuses more about winning tickets than gameplay"""
	MedalGame = auto()
	"""Like redemption but with medals"""
	Mechanical = auto()
	"""Game with mechanical elements"""
	Pinball = auto()
	"""Pinball machine"""
	PlugAndPlay = auto()
	"""Home console that connects to a TV without any separate games"""
	PrintClub = auto()
	"""Booth for taking photos"""
	Other = auto()
	"""Some other thing"""


class CatlistCategory:
	def __init__(self, category: str) -> None:
		self.category, self._has_extra, self.extra = category.partition(' * ')
		self._components = self.category.removeprefix('Arcade: ').split(' / ')

	def __str__(self) -> str:
		s = f'Catlist ({"/".join(self._components)}, type: {self.machine_type}, arcade: {self.is_arcade}'
		if self._has_extra:
			s += f', extra: {self.extra}'
		return s + ')'

	@property
	def is_arcade(self) -> bool:
		return self.category.startswith('Arcade: ')

	@property
	def is_ttl(self) -> bool:
		return self.extra == 'TTL'

	@property
	def is_mature(self) -> bool:
		return self.extra == 'Mature'

	@property
	def _is_plug_and_play(self) -> bool:
		return self._components[0] == 'Handheld' and "Plug n' Play TV Game" in self._components

	@property
	def machine_type(self) -> MachineType:
		if self.category == 'Arcade: System / BIOS':
			return MachineType.BIOS
		genre_types = {
			'Slot Machine': MachineType.Gambling,
			'Casino': MachineType.Gambling,
			'Redemption Game': MachineType.Redemption,
			'Medal Game': MachineType.MedalGame,
			'Coin Pusher': MachineType.CoinPusher,
			'Print Club': MachineType.PrintClub,
		}
		if self._components[0] in genre_types:
			return genre_types[self._components[0]]
		if self._components[0] == 'Electromechanical':
			if self._components[1] == 'Pinball':
				return MachineType.Pinball
			return MachineType.Mechanical
		if self.is_arcade:
			return MachineType.Arcade
		if self._is_plug_and_play:
			return MachineType.PlugAndPlay
		if self.category == 'Handheld / Electronic Game':
			return MachineType.LCDHandheld
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
		if self._is_plug_and_play and len(self._components) > 2:
			return self._components[2]
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
		return None
