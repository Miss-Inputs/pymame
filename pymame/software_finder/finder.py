from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic, TypeVar

if TYPE_CHECKING:
	from pymame import Software, SoftwareList, SoftwarePart


@dataclass
class SoftwareMatchResult:
	software_list: 'SoftwareList'
	software: 'Software'
	part: 'SoftwarePart'

	def __str__(self) -> str:
		return f'{self.software.id} {self.part.element.name}'


_InputType = TypeVar('_InputType')


class SoftwareFinder(ABC, Generic[_InputType]):
	def __init__(self, data: _InputType) -> None:
		self.data = data

	@abstractmethod
	def part_matches(self, part: 'SoftwarePart') -> bool:
		"""Return True if we should consider this part to match whatever the input is."""

	def find(self, software_lists: Iterable['SoftwareList']) -> Iterator[SoftwareMatchResult]:
		for software_list in software_lists:
			for software in software_list.iter_software():
				for part in software.iter_parts():
					if self.part_matches(part):
						yield SoftwareMatchResult(software_list, software, part)

	def find_first(self, software_lists: Iterable['SoftwareList']) -> SoftwareMatchResult | None:
		for result in self.find(software_lists):
			return result
		return None

	def find_all(self, software_lists: Iterable['SoftwareList']) -> Sequence[SoftwareMatchResult]:
		return tuple(self.find(software_lists))

	def narrow_down_results(
		self, results: Iterable[SoftwareMatchResult]
	) -> Sequence[SoftwareMatchResult]:
		"""Returns the results from another `SoftwareFinder` that also match this one.

		Returns:
			A smaller list of SoftwareMatchResult"""
		return tuple(result for result in results if self.part_matches(result.part))


class ShittyNameSoftwareFinder(SoftwareFinder[str]):
	"""This sucks and only matches by name, avoiding all the false positives, and doesn't work very well"""

	@staticmethod
	def normalize_name(name: str):
		return name.replace(': ', ' ').replace(' - ', ' ').casefold()

	def part_matches(self, part: 'SoftwarePart') -> bool:
		software = part.software
		if len(software.element.parts) != 1:
			return False
		return self.normalize_name(software.name) == self.data
