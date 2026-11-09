"""The offline shop's decoration (NOVA-9; OLD uiMyShopDecoration.py, spec 3.8): the shop's model
and its sign's style, chosen in two steps before the builder opens.

The shop name dialog's decoration button opens it (Interface.OpenMyShopDecoWnd).
Step 1 lists CONFIG's models by their shop_deco.txt names, step 2 the sign
styles CONFIG allows (0, the plain board, then the patterns). The right side
shows the chosen model turning (NOVA-137: OLD's player.SelectShopModel and
MyShopDecoShow on the client's "shop_deco" render target) over its name, or the
style's frame; a client without render targets names the model only.
Clicks only choose; Complete commits the choice into
uiPrivateShopBuilder.SHOP_DECO (the model vnum) and SHOP_STYLE, and only with
CONFIG's decoration item in the inventory (o-cli bug 10: OLD wrote both at
every click, so a cancelled choice still applied). Cancel, X and Escape
keep what was committed."""

import ui
import chat
import player
import localeInfo
import uiScriptLocale

STEP_MODEL = 1
STEP_STYLE = 2

# The model view in the legacy preview board (166 x 120): the model over its name.
MODEL_VIEW_RECT = (3, 3, 160, 96)
MODEL_NAME_BELOW_VIEW = 46


def model_preview_available():
	"""The client draws shop models into "shop_deco" (NOVA-137)."""
	return hasattr(player, "SelectShopModel") and hasattr(player, "MyShopDecoShow")


class MyShopDecorationWindow(ui.ScriptWindow):

	def __init__(self):
		ui.ScriptWindow.__init__(self)
		self.isLoaded = False
		self.interface = None
		self.step = STEP_MODEL
		self.models = []           # [(vnum, name)]
		self.styles = []           # [(style, name, pattern, color)]
		self.selectedModel = 0     # a vnum
		self.selectedStyle = 0
		self.preview = None
		self.modelView = None

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def __LoadWindow(self):
		if self.isLoaded:
			return
		self.isLoaded = True
		try:
			pyScrLoader = ui.PythonScriptLoader()
			pyScrLoader.LoadScriptFile(self, "UIScript/myshopdecorationwindow.py")
		except:
			import exception
			exception.Abort("MyShopDecorationWindow.LoadWindow.LoadObject")

		try:
			GetObject = self.GetChild
			self.titleBar = GetObject("MyShopTitleBar")
			self.titleName = GetObject("TitleName")
			self.descriptionText = GetObject("DescriptionText")
			self.itemList = GetObject("ItemList")
			self.scrollBar = GetObject("ScrollBar")
			self.previewWindow = GetObject("PreviewWindow")
			self.modelName = GetObject("ModelName")
			self.nextButton = GetObject("NextButton")
			self.cancelButton = GetObject("CancelButton")
			self.prevButton = GetObject("PrevButton")
			self.completeButton = GetObject("CompleteButton")
		except:
			import exception
			exception.Abort("MyShopDecorationWindow.LoadWindow.BindObject")

		self.titleBar.SetCloseEvent(ui.__mem_func__(self.Close))
		self.itemList.SetEvent(ui.__mem_func__(self.OnSelectEntry))
		self.scrollBar.SetScrollEvent(ui.__mem_func__(self.OnScroll))
		self.nextButton.SetEvent(ui.__mem_func__(self.UseNextButton))
		self.cancelButton.SetEvent(ui.__mem_func__(self.Close))
		self.prevButton.SetEvent(ui.__mem_func__(self.UsePrevButton))
		self.completeButton.SetEvent(ui.__mem_func__(self.UseCompleteButton))

	def BindInterface(self, interface):
		self.interface = interface

	def Destroy(self):
		self.Close()
		self.preview = None
		self.modelView = None
		self.interface = None
		self.isLoaded = False
		self.ClearDictionary()

	def Open(self):
		"""Step 1, starting from what is committed (SHOP_DECO 0: CONFIG's first model)."""
		import offlineshopconst
		import uiPrivateShopBuilder
		self.__LoadWindow()
		cfg = offlineshopconst.config()
		self.models = offlineshopconst.deco_models(cfg)
		self.styles = offlineshopconst.deco_styles(cfg)
		vnums = [vnum for (vnum, _) in self.models]
		self.selectedModel = uiPrivateShopBuilder.SHOP_DECO if uiPrivateShopBuilder.SHOP_DECO in vnums else (vnums[0] if vnums else 0)
		styles = [style for (style, _, _, _) in self.styles]
		self.selectedStyle = uiPrivateShopBuilder.SHOP_STYLE if uiPrivateShopBuilder.SHOP_STYLE in styles else 0
		self.__ShowStep(STEP_MODEL)
		self.SetCenterPosition()
		self.Show()
		self.SetTop()

	def Close(self):
		self.__ClearPreview()
		self.Hide()

	def OnPressEscapeKey(self):
		self.Close()
		return True

	def GetStep(self):
		return self.step

	def GetSelection(self):
		"""(model vnum, style) chosen, not yet committed."""
		return (self.selectedModel, self.selectedStyle)

	def __Entries(self):
		if self.step == STEP_MODEL:
			return [(vnum, name) for (vnum, name) in self.models]
		return [(style, name) for (style, name, _, _) in self.styles]

	def __ShowStep(self, step):
		self.step = step
		if step == STEP_MODEL:
			self.titleName.SetText(localeInfo.MYSHOP_DECO_STEP_MODEL)
			self.descriptionText.SetText(uiScriptLocale.MYSHOP_DECO_SELECT_MODEL)
			self.nextButton.Show()
			self.cancelButton.Show()
			self.prevButton.Hide()
			self.completeButton.Hide()
			selected = self.selectedModel
		else:
			self.titleName.SetText(localeInfo.MYSHOP_DECO_STEP_TITLE)
			self.descriptionText.SetText(uiScriptLocale.MYSHOP_DECO_SELECT_TITLE)
			self.nextButton.Hide()
			self.cancelButton.Hide()
			self.prevButton.Show()
			self.completeButton.Show()
			selected = self.selectedStyle

		entries = self.__Entries()
		self.itemList.ClearItem()
		for (key, name) in entries:
			self.itemList.InsertItem(key, name)
		viewCount = self.itemList.GetViewItemCount()
		if len(entries) > viewCount:
			self.scrollBar.SetMiddleBarSize(float(viewCount) / float(len(entries)))
			self.scrollBar.SetPos(0.0)
			self.scrollBar.Show()
		else:
			self.scrollBar.Hide()
		keys = [key for (key, _) in entries]
		if selected in keys:
			self.itemList.SelectItem(keys.index(selected))
		self.__RefreshPreview()

	def OnScroll(self):
		entries = self.__Entries()
		hidden = max(0, len(entries) - self.itemList.GetViewItemCount())
		self.itemList.SetBasePos(int(self.scrollBar.GetPos() * hidden))

	def OnSelectEntry(self, key, name):
		"""A click chooses; nothing is committed before Complete (o-cli bug 10)."""
		if self.step == STEP_MODEL:
			self.selectedModel = key
		else:
			self.selectedStyle = key
		self.__RefreshPreview()

	def UseNextButton(self):
		self.__ShowStep(STEP_STYLE)

	def UsePrevButton(self):
		self.__ShowStep(STEP_MODEL)

	def UseCompleteButton(self):
		"""Commits the choice; it needs CONFIG's decoration item (OLD uiMyShopDecoration.py:230-237)."""
		import offlineshopconst
		import uiPrivateShopBuilder
		decoVnum = offlineshopconst.config()["deco_vnum"]
		if player.GetItemCountByVnum(decoVnum) < 1:
			chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.DECORATION_REQUIRES_SCROLL)
			return
		uiPrivateShopBuilder.SHOP_DECO = self.selectedModel
		uiPrivateShopBuilder.SHOP_STYLE = self.selectedStyle
		self.Close()

	def __MakePreview(self, style):
		"""The style's frame, or the plain board for 0 (NovaUI's window makes its own)."""
		if style:
			return ui.ShopDecoTitle(style)
		return ui.ThinBoard2()

	def __MakeModelView(self):
		"""The render target showing "shop_deco" (NovaUI's window makes its own); None
		on a client without render targets."""
		if not model_preview_available() or not ui.RenderTarget.IsAvailable():
			return None
		view = ui.RenderTarget()
		view.SetParent(self.previewWindow)
		view.AddFlag("not_pick")
		(x, y, width, height) = MODEL_VIEW_RECT
		view.SetPosition(x, y)
		view.SetSize(width, height)
		view.SetRenderTarget("shop_deco")
		return view

	def __ShowModel(self):
		"""Step 1: the chosen model, turning (OLD SelectShopModel, MyShopDecoShow). False
		when the client cannot show it."""
		if self.modelView is None:
			self.modelView = self.__MakeModelView()
		if self.modelView is None or not self.selectedModel:
			return False
		player.SelectShopModel(self.selectedModel)
		player.MyShopDecoShow(True)
		self.modelView.Show()
		return True

	def __HideModel(self):
		if self.modelView is not None:
			self.modelView.Hide()
		if model_preview_available():
			player.MyShopDecoShow(False)

	def __ClearPreview(self):
		if self.preview:
			self.preview.Hide()
		self.preview = None
		self.__HideModel()

	def __RefreshPreview(self):
		"""The model's name, or the style's frame with its name."""
		self.__ClearPreview()
		if self.step == STEP_MODEL:
			names = dict(self.models)
			self.modelName.SetText(names.get(self.selectedModel, str(self.selectedModel)))
			self.modelName.SetPosition(0, MODEL_NAME_BELOW_VIEW if self.__ShowModel() else 0)
			return
		self.modelName.SetPosition(0, 0)
		names = dict((style, name) for (style, name, _, _) in self.styles)
		self.modelName.SetText(names.get(self.selectedStyle, ""))
		preview = self.__MakePreview(self.selectedStyle)
		preview.SetParent(self.previewWindow)
		preview.AddFlag("not_pick")
		preview.SetPosition(23, 70)
		preview.SetSize(120, 32)
		preview.Show()
		self.preview = preview
