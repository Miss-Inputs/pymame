import copy
from collections.abc import Iterator, Mapping
from io import BytesIO
from typing import IO, TYPE_CHECKING

from lxml import etree

from pymame.xml_wrapper import XMLElement, XMLReader

if TYPE_CHECKING:
	from lxml.etree import _Element as Element


class LXMLElement(XMLElement):
	"""Implementation of XML element methods for lxml"""

	def __init__(self, element: 'Element') -> None:
		self.element = element

	@property
	def tag(self) -> str:
		return str(self.element.tag)

	@property
	def attrib(self) -> Mapping[str, str]:
		return dict(self.element.attrib.items())

	def find_first(self, tag: str) -> 'LXMLElement | None':
		element = self.element.find(tag)
		return LXMLElement(element) if element is not None else None

	def iter(self, tag: str) -> Iterator['LXMLElement']:
		for element in self.element.iter(tag):
			yield LXMLElement(element)

	def iter_starts_with(self, prefix: str) -> Iterator['LXMLElement']:
		for element in self.element.iterchildren():
			tag = element.tag
			if isinstance(tag, etree.QName):
				tag = tag.localname
			elif isinstance(tag, memoryview):
				# when the hell would this happen, type checker?
				tag = tag.tobytes().decode('utf-8')
			elif isinstance(tag, (bytes, bytearray)):
				tag = tag.decode('utf-8')

			if tag.startswith(prefix):
				yield LXMLElement(element)

	def find_text(self, tag: str) -> str | None:
		return self.element.findtext(tag)

	@property
	def text(self) -> str | None:
		return self.element.text

	def to_xml_string(self, *, pretty: bool = True) -> str:
		return etree.tostring(self.element, encoding='unicode', pretty_print=pretty)


class LXMLReader(XMLReader[LXMLElement]):  # type: ignore[override] #lxml-stubs is annoying, and types .attrib as _Attrib which is slightly different from Mapping[str, str]
	def read(self, xml: str | bytes) -> LXMLElement:
		return LXMLElement(etree.fromstring(xml, etree.XMLParser(recover=True)))

	def read_from_file(self, xml: IO[bytes]) -> LXMLElement:
		return LXMLElement(etree.parse(xml).getroot())

	def iterparse(self, xml: bytes | IO[bytes], tag: str | None = None) -> Iterator[LXMLElement]:
		if isinstance(xml, bytes):
			xml = BytesIO(xml)
		for _, element in etree.iterparse(xml):
			if element.tag == tag or not tag:
				c = copy.copy(element)
				yield LXMLElement(c)
				element.clear()
