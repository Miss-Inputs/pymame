"""Parses MAMEInfo into sections"""

from collections.abc import Collection


class MAMEInfoEntry:
	def __init__(self, contents: str):
		#bleh this code still sucks kinda
		self.contents = contents.removeprefix('$mame\n')
		self.sections: dict[str, str] = {}
		self.list_sections: dict[str, Collection[str]] = {}
		self.recommended_games: dict[str, Collection[str]] = {}
		# At the top is generally version number added [author]
		current_section = 'summary'
		current_lines: list[str] = []
		current_is_list = False
		# Hmm how do I even do this

		normal_sections = {
			f'{s}:'
			for s in (
				'WIP',
				'CHANGES',
				'TODO',
				'TEST MODE',
				'Bugs',
				'NOTE',
				'NOTES',
				'SETUP',
				'SETUP and TEST MODE',
				'SERVICE MODE',
				'SETUP/SERVICE MODE',
				'STORY',  # what's this doing in mameinfo and not history? Oh well
				'HOW TO PLAY',  # what's this doing in mameinfo and not history? Oh well
			)
		}
		list_sections = {f'{s}:' for s in ('BIOS', 'DEVICE', 'ROMS', 'Other Emulators')}

		def finish():
			lines = [liney for liney in current_lines if liney]
			current_lines.clear()
			if current_section.startswith('Recommended Games'):
				key = (
					current_section.removeprefix('Recommended Games (')[:-1]
					if '(' in current_section
					else 'Games'
				)
				self.recommended_games[key] = lines
			elif current_is_list:
				# whoops, if current_section starts with "Recommended Games" it should go here, so luckily that works
				self.list_sections[current_section] = lines
			else:
				self.sections[current_section] = '\n'.join(lines)

		for line in contents.splitlines():
			if line in normal_sections or line in list_sections:
				finish()
				current_section = line[:-1]
				current_is_list = line in list_sections
			elif line.startswith('Recommended Games'):
				# Sometimes you get Recommended Games (blah) and no : and there's just nothing to recommend apparently
				finish()
				current_section = line[:-1]
			elif line.startswith('LEVELS:'):
				# Not always just an int, for example 3in1semi: "50-30-45 (Cookie & Bibi - Hyper Man - New Hyper Man)"
				finish()
				current_section = 'Levels'  # in case there's something in between
				current_is_list = False
				self.sections['Levels'] = line.removeprefix('LEVELS:').strip()
			elif line.startswith('ARCADE RELEASE:'):
				# Could parse a date here maybehaps (weird format, e.g. 2000/Oct/18)
				finish()
				current_section = 'Release date'  # in case there's something in between
				current_is_list = False
				self.sections['Release date'] = line.removeprefix('ARCADE RELEASE:').strip()
			elif line.startswith(('Romset:', 'CHD:')):
				# nah
				continue
			else:
				current_lines.append(line.removeprefix('- ').removeprefix('* ').strip())

