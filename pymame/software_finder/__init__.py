"""Finds software inside software lists."""

from .finder import SoftwareFinder, SoftwareMatchResult
from .hashes_finder import CRC32SoftwareFinder, SHA1SoftwareFinder, find_software_for_hashes
from .lazy_loaded_hashes import BytesHashes, FileHashes, LazyLoadedHashes, ZipMemberHashes

__all__ = [
	'BytesHashes',
	'CRC32SoftwareFinder',
	'FileHashes',
	'LazyLoadedHashes',
	'SHA1SoftwareFinder',
	'SoftwareFinder',
	'SoftwareMatchResult',
	'ZipMemberHashes',
	'find_software_for_hashes',
]
