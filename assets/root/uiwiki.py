"""NOVA-42: the wiki browser exists only on NovaUI; this class stands in for
it where NovaUI cannot run (the window flag off, or a locale without
NovaUI), so the Interface can make one window either way. Nothing shows."""


class UnavailableWindow(object):
	# NOVA-192: no wiki, so the tooltips name no Shift + right-click.
	AVAILABLE = False

	def Hide(self):
		pass

	def IsShow(self):
		return False

	def Destroy(self):
		pass

	def Toggle(self):
		pass

	def OpenItem(self, vnum):
		return False

	def OpenMob(self, vnum):
		return False

	def WikiAnswer(self, *rows):
		pass

	def SetItemToolTip(self, tooltip):
		pass

	def SetPasteLinkEvent(self, event):
		pass
