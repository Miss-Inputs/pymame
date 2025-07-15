"""An abstraction layer for XML parsers, and a default implementation using xml.etree.ElementTree"""

import copy
from abc import ABC, abstractmethod
from collections.abc import Iterator, Mapping
from functools import lru_cache
from io import BytesIO
from typing import IO, Self, TypeVar
from xml.etree.ElementTree import Element, fromstring, iterparse, parse, tostring

XMLElementType_co = TypeVar('XMLElementType_co', bound='XMLElement', covariant=True)


class XMLElement(ABC):
	@property
	@abstractmethod
	def tag(self) -> str: ...

	@property
	@abstractmethod
	# Just to be annoying, lxml.etree._Element.attrib is a different type not exactly compatible with Mapping[str, str]
	def attrib(self) -> 'Mapping[str, str]':
		"""Mapping of all attribute names to values"""

	@abstractmethod
	def find_first(self, tag: str) -> Self | None:
		"""Find the first element inside this one with a certain tag, or None if not found"""

	@abstractmethod
	def iter(self, tag: str) -> Iterator[Self]:
		"""Iterate through child elements matching the specified tag, as efficiently as possible"""

	@abstractmethod
	def iter_starts_with(self, prefix: str) -> Iterator[Self]:
		"""Iterate through child elements that have a tag starting with some string"""

	@abstractmethod
	def find_text(self, tag: str) -> str | None:
		"""Get text from first element with the specified tag, or None if not found"""

	@property
	@abstractmethod
	def text(self) -> str | None:
		"""Get text from inside the element, or None if not found"""

	@abstractmethod
	def to_xml_string(self, *, pretty: bool = True) -> str:
		"""Convert the element back to string.

		Arguments:
			pretty: Try and get a "pretty" representation, but this might be ignored with some implementations.
		"""


class XMLReader[XMLElementType_co: 'XMLElement'](ABC):
	def __hash__(self) -> int:
		return hash(type(self))

	@abstractmethod
	def read(self, xml: str | bytes) -> XMLElementType_co: ...

	@abstractmethod
	def read_from_file(self, xml: IO[bytes]) -> XMLElementType_co: ...

	@abstractmethod
	def iterparse(
		self, xml: bytes | IO[bytes], tag: str | None = None
	) -> Iterator[XMLElementType_co]: ...


class ElementWrapper:
	"""Wrapper for an element that simply holds the XMLElement, and provides a nicer __str__ and __repr__"""

	def __init__(self, xml: XMLElement):
		self.xml = xml

	def __str__(self) -> str:
		fields = ', '.join(f'{k}: ({v!s})' for k, v in vars(self).items())
		props = (
			(name, prop) for name, prop in vars(type(self)).items() if isinstance(prop, property)
		)
		prop_values = ', '.join(
			f'{name}: ({prop.fget(self)!s})' for name, prop in props if prop.fget
		)
		return f'({type(self)}): ({fields}, {prop_values})'

	def __repr__(self) -> str:
		to_string = self.xml.to_xml_string(pretty=False)
		return f'{type(self)}({to_string})'


class DefaultXMLElement(XMLElement):
	def __init__(self, element: Element) -> None:
		self.element = element

	@property
	def tag(self) -> str:
		return self.element.tag

	@property
	def attrib(self) -> Mapping[str, str]:
		return self.element.attrib

	def find_first(self, tag: str) -> 'DefaultXMLElement | None':
		element = self.element.find(tag)
		return DefaultXMLElement(element) if element is not None else None

	def iter(self, tag: str) -> Iterator['DefaultXMLElement']:
		for element in self.element.iter(tag):
			yield DefaultXMLElement(element)

	def iter_starts_with(self, prefix: str) -> Iterator['DefaultXMLElement']:
		for element in self.element.iter():
			if element.tag.startswith(prefix):
				yield DefaultXMLElement(element)

	def find_text(self, tag: str) -> str | None:
		return self.element.findtext(tag)

	@property
	def text(self) -> str | None:
		return self.element.text

	def to_xml_string(self, *, pretty: bool = True) -> str:
		return tostring(self.element, encoding='unicode')


class DefaultXMLReader(XMLReader[DefaultXMLElement]):
	def read(self, xml: str | bytes) -> DefaultXMLElement:
		return DefaultXMLElement(fromstring(xml))

	def read_from_file(self, xml: IO[bytes]) -> DefaultXMLElement:
		return DefaultXMLElement(parse(xml).getroot())

	def iterparse(
		self, xml: bytes | IO[bytes], tag: str | None = None
	) -> Iterator[DefaultXMLElement]:
		if isinstance(xml, bytes):
			xml = BytesIO(xml)
		for _, element in iterparse(xml):
			if element.tag == tag or tag is None:
				c = copy.copy(element)
				yield DefaultXMLElement(c)
				element.clear()


@lru_cache(maxsize=1)
def get_xml_reader() -> XMLReader[XMLElement]:
	try:
		from lxml_wrapper import LXMLReader  # noqa: PLC0415
	except ImportError:
		return DefaultXMLReader()
	else:
		return LXMLReader()
