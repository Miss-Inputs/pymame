from enum import StrEnum

from pymame.xml_wrapper import ElementWrapper


class NamedElement(ElementWrapper):
	"""Some element that only has a required "name" attribute, which happens fairly often"""
	@property
	def name(self) -> str:
		return self.xml.attrib['name']

class DipswitchValueElement(ElementWrapper):
	@property
	def name(self) -> str:
		return self.xml.attrib['name']
	
	@property
	def value(self) -> str:
		# always numeric?
		return self.xml.attrib['value']

	@property
	def is_default(self) -> bool:
		return self.xml.attrib.get('default', 'no') == 'yes'

		

class DumpStatus(StrEnum):
	Good = 'good'
	Bad = 'baddump'
	NoDump = 'nodump'
