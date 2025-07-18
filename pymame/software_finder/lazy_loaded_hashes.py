import hashlib
import zipfile
import zlib
from abc import ABC, abstractmethod
from functools import cached_property
from os import stat_result
from pathlib import Path


class LazyLoadedHashes(ABC):
	@abstractmethod
	def get_size(self) -> int: ...
	@abstractmethod
	def get_crc32(self) -> int: ...
	@abstractmethod
	def get_sha1(self) -> bytes: ...

	def get_suffix(self) -> str | None:
		"""
		Returns:
			A lowercase file suffix, without the dot, or None if this is not relevant (e.g. not matching against a file).
		"""
		return None

	@cached_property
	def size(self) -> int:
		return self.get_size()

	@cached_property
	def crc32(self) -> int:
		return self.get_crc32()

	@cached_property
	def sha1(self) -> bytes:
		return self.get_sha1()

	@cached_property
	def suffix(self) -> str | None:
		return self.get_suffix()


class ContentsHashes(LazyLoadedHashes):
	@abstractmethod
	def get_contents(self) -> bytes: ...

	@cached_property
	def contents(self) -> bytes:
		return self.get_contents()

	def get_size(self) -> int:
		return len(self.contents)

	def get_crc32(self) -> int:
		return zlib.crc32(self.contents)

	def get_sha1(self) -> bytes:
		return hashlib.sha1(self.contents, usedforsecurity=False).digest()


class FileHashes(ContentsHashes):
	def __init__(
		self,
		path: Path,
		stat: stat_result | None = None,
		size: int | None = None,
		crc32: int | None = None,
		sha1: bytes | None = None,
	) -> None:
		self.path = path
		self.stat = stat or path.stat()
		"""Potentially the result of stat(), if we already know it"""
		self._size = size
		"""Potentially the size of the file, if we already know it"""
		self._crc32 = crc32
		"""Potentially the CRC32 of the file's contents, if we already know it"""
		self._sha1 = sha1
		"""Potentially the SHA-1 of the file's contents, if we already know it"""

	def get_size(self) -> int:
		return self._size if self._size is not None else self.stat.st_size

	def get_contents(self) -> bytes:
		return self.path.read_bytes()

	def get_suffix(self) -> str | None:
		return self.path.suffix[1:].lower()

	def get_crc32(self) -> int:
		if self._crc32 is not None:
			return self._crc32
		return super().get_crc32()

	def get_sha1(self) -> bytes:
		if self._sha1:
			return self._sha1
		return super().get_sha1()


class BytesHashes(ContentsHashes):
	def __init__(self, contents: bytes, suffix: str | None = None) -> None:
		self._contents = contents
		self._suffix = suffix

	def get_suffix(self) -> str | None:
		return self._suffix

	def get_contents(self) -> bytes:
		return self._contents


class ZipMemberHashes(ContentsHashes):
	def __init__(self, zip_file: zipfile.ZipFile, zip_info: zipfile.ZipInfo | str) -> None:
		self.zip_file = zip_file
		self.zip_info = zip_file.getinfo(zip_info) if isinstance(zip_info, str) else zip_info

	def get_crc32(self) -> int:
		return self.zip_info.CRC

	def get_size(self) -> int:
		return self.zip_info.file_size

	def get_suffix(self) -> str | None:
		return self.zip_info.filename.rsplit('.', 1)[-1].lower()

	def get_contents(self) -> bytes:
		"""Unfortunately if you end up needing the SHA-1 you'll have to actually read the file

		Returns:
			bytes"""
		return self.zip_file.read(self.zip_info)
