import logging
from collections.abc import Collection, Sequence
from typing import Any

from pymame import DumpStatus, SoftwareList, SoftwarePart
from pymame.elements.software_element import DataAreaElement, DiskAreaElement, LoadFlag, ROMElement

from .finder import SoftwareFinder, SoftwareMatchResult
from .lazy_loaded_hashes import LazyLoadedHashes

logger = logging.getLogger(__name__)

#TODO: Some ROMs should enforce the suffix matches, e.g. .wav


def should_ignore_rom(rom: ROMElement):
	return rom.load_flag in {LoadFlag.Ignore, LoadFlag.Continue}


# TODO: Actually I don't like this, just check ROMs that don't have any funny load flags at all
def rom_matches(rom: ROMElement, hashes: LazyLoadedHashes, *, use_sha1: bool = False):
	if rom.size is None:
		return False

	size = hashes.size
	if rom.size != size:
		return False

	# TODO: Implement LoadFlag.Fill

	if use_sha1:
		if rom.sha1 is None:
			return False
		return rom.sha1 == hashes.sha1
	if rom.crc is None:
		return False
	return rom.crc == hashes.crc32


def should_ignore_data_area(data_area: DataAreaElement) -> bool:
	return data_area.name == 'nvram' or all(should_ignore_rom(rom) for rom in data_area.roms)


def data_area_matches(
	data_area: DataAreaElement, hashes: LazyLoadedHashes, *, use_sha1: bool = False
):
	roms = [rom for rom in data_area.roms if not should_ignore_rom(rom)]
	if len(roms) == 1:
		return rom_matches(roms[0], hashes, use_sha1=use_sha1)
	return False


def disk_area_matches(disk_area: DiskAreaElement, hashes: LazyLoadedHashes):
	dumped_disks = [disk for disk in disk_area.disks if disk.status != DumpStatus.NoDump]
	if len(dumped_disks) == 1:
		return dumped_disks[0].sha1 == hashes.sha1
	return False


class CRC32SoftwareFinder(SoftwareFinder[LazyLoadedHashes]):
	def part_matches(self, part: SoftwarePart) -> bool:
		if part.element.disk_areas:
			# nope! We can't match them against a CRC32, so they can't be it
			return False
		data_areas = [
			data_area
			for data_area in part.element.data_areas
			if not should_ignore_data_area(data_area)
		]
		if len(data_areas) == 1:
			return data_area_matches(data_areas[0], self.data)
		return False


class SHA1SoftwareFinder(SoftwareFinder[LazyLoadedHashes]):
	def part_matches(self, part: SoftwarePart) -> bool:
		data_areas = [
			data_area
			for data_area in part.element.data_areas
			if not should_ignore_data_area(data_area)
		]
		disk_areas = [disk_area for disk_area in part.element.disk_areas if disk_area.disks]
		if len(data_areas) == 1 and not disk_areas:
			return data_area_matches(data_areas[0], self.data, use_sha1=True)
		if self.data.suffix == 'chd' and len(disk_areas) == 1 and not data_areas:
			return disk_area_matches(disk_areas[0], self.data)
		return False


def _combine_matches(matches: Sequence[SoftwareMatchResult]) -> Sequence[SoftwareMatchResult]:
	# Sometimes you can, for example, have a game with multiple floppy disks, and the clone set only changes some other floppy disk, so you'd get multiple results for both the parent and clone set for the same floppy disk
	if len(matches) == 1:
		return matches
	if not all(m.software_list.basename == matches[0].software_list.basename for m in matches[1:]):
		return matches
	if not all(m.part.element.name == matches[0].part.element.name for m in matches[1:]):
		return matches
	family_names = [m.software.parent_basename or m.software.basename for m in matches]
	if all(name == family_names[0] for name in family_names[1:]):
		# Try to return the parent, or just the first one if they are all clones of the same thing
		return [next((m for m in matches if not m.software.parent_basename), matches[0])]
	return matches


def find_software_for_hashes(
	software_lists: Collection[SoftwareList], hashes: LazyLoadedHashes, path_for_log: Any = None
) -> Sequence[SoftwareMatchResult]:
	if not software_lists:
		return ()

	matches = CRC32SoftwareFinder(hashes).find_all(software_lists)
	if not matches:
		return ()
	matches = _combine_matches(matches)
	if len(matches) == 1:
		return matches

	logger.warning(
		'Hash collision for %s! Returned %s, how often does this happen?',
		path_for_log,
		[str(match) for match in matches],
	)

	matches = SHA1SoftwareFinder(hashes).narrow_down_results(matches)
	return _combine_matches(matches)
