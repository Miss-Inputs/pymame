# pymame

pymame is a Python wrapper around MAME, including frontend commands from the executable, reading "support files" such as categories and history, parsing software lists to help identify files, provide a nicer/type-hintier wrapper around XML elements, and other related things. At the present time of writing, it is written primarily for my own mysterious personal use, and should not be relied on for anything important.

The intended use case is making it easier to develop Python tools that do MAME-related things.

## Requirements
python >=3.13 (sorry if you are on an older OS where this is unavailable, as I haven't had enough of a reason to check that it works with older Python yet), only been tested on Linux so far but probably works on Windows and macOS and whatever else.

In theory, everything should be optional (e.g. you can get away with not having MAME actually installed, if you have the output of -listxml saved to a file), in the likely event that this doesn't work, this is a bug. 

If lxml is installed, it will be used to parse XML files faster. Everything involving I/O should have an async version so you can more effectively use it from async code (some things are going to be missing right now, but this is the goal).

## Example usage
```python
import pymame
settings = pymame.MAMESettings.autodetect('/usr/bin/mame')
mame = pymame.MAME(settings)
for machine in mame.iter_runnable_machines():
	if mame.machine.verifyroms(machine.basename):
		print(machine.name, machine.platform)
```
