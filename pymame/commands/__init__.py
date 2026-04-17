"""Functions that subprocess MAME to get info, etc; and the MAMEExecutable wrapper for them"""

from .executable import MAMEExecutable
from .listxml import listxml, listxml_all, listxml_all_async, listxml_async
from .misc import listfull, listfull_async
from .software import getsoftlist, getsoftlist_async
from .verifyroms import (
	AuditStatus,
	AuditSubstatus,
	VerifyromsOutput,
	verifyroms_multiple,
	verifyroms_multiple_async,
	verifysamples,
	verifysamples_async,
	verifysoftlist,
)

__all__ = [
	'AuditStatus',
	'AuditSubstatus',
	'MAMEExecutable',
	'VerifyromsOutput',
	'getsoftlist',
	'getsoftlist_async',
	'listfull',
	'listfull_async',
	'listxml',
	'listxml_all',
	'listxml_all_async',
	'listxml_async',
	'verifyroms_multiple',
	'verifyroms_multiple_async',
	'verifysamples',
	'verifysamples_async',
	'verifysoftlist',
]
