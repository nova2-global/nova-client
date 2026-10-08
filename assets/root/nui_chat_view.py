"""The closed chat's lines (nui/windows/chat-view/chat-view.rml, P11 spec D4).

With an exe that has the Wave 3a engine (nui_hud.has_engine_3a), the NovaUI
chat (nui_chat.ChatWindow) makes ChatViewBoard below and shows it while the
chat is closed and shown: RmlUi lays a whole document out again when an
element is added or removed, so the closed chat's appended lines lay out
this small document instead of the chat's, whose lines element is off while
it is closed. The facade places the board where it places the chat and
routes its link presses as the chat's."""

import nui
import nui_hud

DOCUMENT = "nui/windows/chat-view/chat-view.rml"


class ChatViewBoard(nui.Window):
	"""The closed chat's lines; its events go to the chat facade."""

	DOCUMENT = DOCUMENT
	MODEL = "chat_view"
	FEEDS = {"view_chat": "system.view_chat"}

	def __init__(self, owner):
		self._owner = nui_hud.keep_weakly(owner)
		nui.Window.__init__(self)

	def initial_model(self):
		return {"view_chat": True}

	@nui.on("link")
	def on_link(self, link):
		self._owner.input.on_link(link)
