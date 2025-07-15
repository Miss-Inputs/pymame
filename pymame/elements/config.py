"""Coin counters are stored in the config files, so we might as well have a look"""

from collections.abc import Mapping, Sequence
from functools import cached_property

from pymame.xml_wrapper import ElementWrapper


class CoinCounter(ElementWrapper):
	@property
	def index(self) -> int:
		return int(self.xml.attrib['index'])

	@property
	def count(self) -> int:
		return int(self.xml.attrib['number'])


class TicketCounter(ElementWrapper):
	@property
	def count(self) -> int:
		return int(self.xml.attrib['number'])


class Counters(ElementWrapper):
	@cached_property
	def coin_counters(self) -> Sequence[CoinCounter]:
		return tuple(CoinCounter(coins) for coins in self.xml.iter('coins'))

	@cached_property
	def coin_counters_as_dict(self) -> Mapping[int, int]:
		return {counter.index: counter.count for counter in self.coin_counters}

	@property
	def total_coins(self) -> int:
		return sum(counter.count for counter in self.coin_counters)

	@cached_property
	def tickets(self) -> int | None:
		"""Return None if tickets are not relevant to this"""
		ticket_counter = self.xml.find_first('tickets')
		return TicketCounter(ticket_counter).count if ticket_counter else None


class SystemConfig(ElementWrapper):
	@property
	def name(self) -> str:
		return self.xml.attrib['name']

	# bgfx

	@property
	def counters(self) -> Counters | None:
		counters_element = self.xml.find_first('counters')
		return Counters(counters_element) if counters_element else None

	# input, ui_warnings


class MAMEConfigFile(ElementWrapper):
	@property
	def version(self) -> int:
		return int(self.xml.attrib['version'])

	@cached_property
	def systems(self) -> Sequence[SystemConfig]:
		"""Usually only one in each file?"""
		return tuple(SystemConfig(system) for system in self.xml.iter('system'))
