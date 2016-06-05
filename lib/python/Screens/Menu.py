from Screen import Screen
from Screens.ParentalControlSetup import ProtectedScreen
from Components.Sources.List import List
from Components.ActionMap import NumberActionMap, ActionMap
from Components.Sources.StaticText import StaticText
from Components.config import configfile
from Components.PluginComponent import plugins
from Components.config import config, ConfigDictionarySet, NoSave
from Components.SystemInfo import SystemInfo
from Components.Label import Label
from Plugins.Plugin import PluginDescriptor

from Tools.BoundFunction import boundFunction
from Tools.Directories import resolveFilename, SCOPE_SKIN

import xml.etree.cElementTree

from Screens.Setup import Setup, getSetupTitle


from Screens.Setup import Setup, getSetupTitle
# read the menu
mdom = xml.etree.cElementTree.parse(resolveFilename(SCOPE_SKIN, 'menu.xml'))

class MenuUpdater:
	def __init__(self):
		self.updatedMenuItems = {}

	def addMenuItem(self, id, pos, text, module, screen, weight):
		if not self.updatedMenuAvailable(id):
			self.updatedMenuItems[id] = []
		self.updatedMenuItems[id].append([text, pos, module, screen, weight])

	def delMenuItem(self, id, pos, text, module, screen, weight):
		self.updatedMenuItems[id].remove([text, pos, module, screen, weight])

	def updatedMenuAvailable(self, id):
		return self.updatedMenuItems.has_key(id)

	def getUpdatedMenu(self, id):
		return self.updatedMenuItems[id]

menuupdater = MenuUpdater()

class MenuSummary(Screen):
	pass

class Menu(Screen, ProtectedScreen):
	ALLOW_SUSPEND = True

	def okbuttonClick(self):
		print "okbuttonClick"
		selection = self["menu"].getCurrent()
		if selection is not None:
			selection[1]()

	def execText(self, text):
		exec text

	def runScreen(self, arg):
		# arg[0] is the module (as string)
		# arg[1] is Screen inside this module
		#        plus possible arguments, as
		#        string (as we want to reference
		#        stuff which is just imported)
		# FIXME. somehow
		if arg[0] != "":
			exec "from " + arg[0] + " import *"

		self.openDialog(*eval(arg[1]))

	def nothing(self): #dummy
		pass

	def openDialog(self, *dialog):				# in every layer needed
		self.session.openWithCallback(self.menuClosed, *dialog)

	def openSetup(self, dialog):
		self.session.openWithCallback(self.menuClosed, Setup, dialog)

	def addMenu(self, destList, node):
		requires = node.get("requires")
		if requires:
			if requires[0] == '!':
				if SystemInfo.get(requires[1:], False):
					return
			elif not SystemInfo.get(requires, False):
				return
		MenuTitle = _(node.get("text", "??").encode("UTF-8"))
		entryID = node.get("entryID", "undefined")
		weight = node.get("weight", 50)
		x = node.get("flushConfigOnClose")
		if x:
			a = boundFunction(self.session.openWithCallback, self.menuClosedWithConfigFlush, Menu, node)
		else:
			a = boundFunction(self.session.openWithCallback, self.menuClosed, Menu, node)
		#TODO add check if !empty(node.childNodes)
		destList.append((MenuTitle, a, entryID, weight))

	def menuClosedWithConfigFlush(self, *res):
		configfile.save()
		self.menuClosed(*res)

	def menuClosed(self, *res):
		if res and res[0]:
			self.close(True)

	def addItem(self, destList, node):
		requires = node.get("requires")
		if requires:
			if requires[0] == '!':
				if SystemInfo.get(requires[1:], False):
					return
			elif not SystemInfo.get(requires, False):
				return
		configCondition = node.get("configcondition")
		if configCondition and not eval(configCondition + ".value"):
			return
		item_text = node.get("text", "").encode("UTF-8")
		entryID = node.get("entryID", "undefined")
		weight = node.get("weight", 50)
		for x in node:
			if x.tag == 'screen':
				module = x.get("module")
				screen = x.get("screen")

				if screen is None:
					screen = module

				print module, screen
				if module:
					module = "Screens." + module
				else:
					module = ""

				# check for arguments. they will be appended to the
				# openDialog call
				args = x.text or ""
				screen += ", " + args

				destList.append((_(item_text or "??"), boundFunction(self.runScreen, (module, screen)), entryID, weight))
				return
			elif x.tag == 'code':
				destList.append((_(item_text or "??"), boundFunction(self.execText, x.text), entryID, weight))
				return
			elif x.tag == 'setup':
				id = x.get("id")
				if item_text == "":
					item_text = _(getSetupTitle(id))
				else:
					item_text = _(item_text)
				destList.append((item_text, boundFunction(self.openSetup, id), entryID, weight))
				return
		destList.append((item_text, self.nothing, entryID, weight))


	def __init__(self, session, parent):
		Screen.__init__(self, session)
		list = []

		menuID = None
		for x in parent:						#walk through the actual nodelist
			if not x.tag:
				continue
			if x.tag == 'item':
				item_level = int(x.get("level", 0))
				if item_level <= config.usage.setup_level.index:
					self.addItem(list, x)
					count += 1
			elif x.tag == 'menu':
				self.addMenu(list, x)
				count += 1
			elif x.tag == "id":
				menuID = x.get("val")
				count = 0

			if menuID is not None:
				# menuupdater?
				if menuupdater.updatedMenuAvailable(menuID):
					for x in menuupdater.getUpdatedMenu(menuID):
						if x[1] == count:
							list.append((x[0], boundFunction(self.runScreen, (x[2], x[3] + ", ")), x[4]))
							count += 1

		if menuID is not None:
			# plugins
			for l in plugins.getPluginsForMenu(menuID):
				# check if a plugin overrides an existing menu
				plugin_menuid = l[2]
				for x in list:
					if x[2] == plugin_menuid:
						list.remove(x)
						break
				list.append((l[0], boundFunction(l[1], self.session, close=self.close), l[2], l[3] or 50))

		# for the skin: first try a menu_<menuID>, then Menu
		self.skinName = [ ]
		if menuID is not None:
			if menuID == "vtimain":
				self.skinName.append("menu_system")
			else:
				self.skinName.append("menu_" + menuID)
		self.skinName.append("Menu")

## VTi function moved from VTiPanel to Menu Screen
		if config.usage.menu_sort_mode.value == "user" and menuID == "mainmenu":
			plugin_list = []
			id_list = []
			for l in plugins.getPlugins([PluginDescriptor.WHERE_PLUGINMENU ,PluginDescriptor.WHERE_EXTENSIONSMENU, PluginDescriptor.WHERE_EVENTINFO]):
				l.id = (l.name.lower()).replace(' ','_')
				if l.id not in id_list:
					id_list.append(l.id)
					plugin_list.append((l.name, boundFunction(l.__call__, session), l.id, 200))
			addlist = config.plugins.vtipanel.menushown.value
			addlist = addlist.split(',')
			for entry in plugin_list:
				if entry[2] in addlist:
					m_list.append(entry)

		self.list = m_list

		if menuID is not None and config.usage.menu_sort_mode.value == "user":
			self.sub_menu_sort = NoSave(ConfigDictionarySet())
			self.sub_menu_sort.value = config.usage.menu_sort_weight.getConfigValue(self.menuID, "submenu") or {}
			idx = 0
			for x in self.list:
				entry = list(self.list.pop(idx))
				m_weight = self.sub_menu_sort.getConfigValue(entry[2], "sort") or entry[3]
				entry.append(m_weight)
				self.list.insert(idx, tuple(entry))
				self.sub_menu_sort.changeConfigValue(entry[2], "sort", m_weight)
				idx += 1
			self.full_list = list(m_list)

		if config.usage.menu_sort_mode.value == "a_z":
			# Sort by Name
			m_list.sort(key=self.sortByName)
		elif config.usage.menu_sort_mode.value == "user":
			self["blue"].setText(_("Edit mode on"))
			self.hide_show_entries()
			m_list = self.list
		else:
			# Sort by Weight
			m_list.sort(key=lambda x: int(x[3]))
		self["menu"] = List(m_list)
		self["menu"].enableWrapAround = True
		if config.usage.menu_sort_mode.value == "user":
			self["menu"].onSelectionChanged.append(self.selectionChanged)

		self["actions"] = NumberActionMap(["OkCancelActions", "MenuActions", "NumberActions"],
			{
				"ok": self.keyOk,
				"cancel": self.keyCancel,
				"menu": self.closeRecursive,
				"0": self.resetSortOrder,
				"1": self.keyNumberGlobal,
				"2": self.keyNumberGlobal,
				"3": self.keyNumberGlobal,
				"4": self.keyNumberGlobal,
				"5": self.keyNumberGlobal,
				"6": self.keyNumberGlobal,
				"7": self.keyNumberGlobal,
				"8": self.keyNumberGlobal,
				"9": self.keyNumberGlobal,
			})

		if config.usage.menu_sort_mode.value == "user":
			self["MoveActions"] = ActionMap(["WizardActions"],
				{
					"left": self.keyLeft,
					"right": self.keyRight,
					"up": self.keyUp,
					"down": self.keyDown,
				}, -1
			)

			self["EditActions"] = ActionMap(["ColorActions"],
			{
				"green": self.keyGreen,
				"yellow": self.keyYellow,
				"blue": self.keyBlue,
			})

		a = parent.get("title", "").encode("UTF-8") or None
		a = a and _(a)
		if a is None:
			a = _(parent.get("text", "").encode("UTF-8"))
		#	ikseong - enter Main menu
		else:
			t_history.reset()
			
		self["title"] = StaticText(a)
		self.menu_title = a

		#	ikseong make menu title
		self["thistory"] = StaticText(t_history.thistory)
		history_len = len(t_history.thistory)
		self["title0"] = StaticText('')
		self["title1"] = StaticText('')
		self["title2"] = StaticText('')
		if history_len < 13 :
			self["title0"] = StaticText(a)
		elif history_len < 21 :
			self["title0"] = StaticText('')
			self["title1"] = StaticText(a)
		else:
			self["title0"] = StaticText('')
			self["title1"] = StaticText('')
			self["title2"] = StaticText(a)				

#		english title			
#		if(t_history.thistory ==''):
#			t_history.thistory = str(etitle) + ' > '
#		else:
#			t_history.thistory = t_history.thistory + str(etitle) + ' > '

		if(t_history.thistory ==''):
			t_history.thistory = str(a) + ' > '
		else:
			t_history.thistory = t_history.thistory + str(a) + ' > '
		#
		
	def isProtected(self):
		if config.ParentalControl.setuppinactive.value:
			if config.ParentalControl.config_sections.main_menu.value and self.menuID == "mainmenu":
				return True
			elif config.ParentalControl.config_sections.configuration.value and self.menuID == "setup":
				return True
			elif config.ParentalControl.config_sections.vti_menu.value and self.menuID == "vtimain":
				return True
			elif config.ParentalControl.config_sections.standby_menu.value and self.menuID == "shutdown":
				return True

	def keyNumberGlobal(self, number):
		print "menu keyNumber:", number
		# Calculate index
		number -= 1

		if len(self["menu"].list) > number:
			self["menu"].setIndex(number)
			self.okbuttonClick()

	def closeNonRecursive(self):
		self.close(False)

	def closeRecursive(self):
		self.close(True)

	def createSummary(self):
		return MenuSummary

	def isProtected(self):
		if config.ParentalControl.setuppinactive.value:
			if config.ParentalControl.config_sections.main_menu.value and not(hasattr(self.session, 'infobar') and self.session.infobar is None):
				return self.menuID == "mainmenu"
			elif config.ParentalControl.config_sections.configuration.value and self.menuID == "setup":
				return True
			elif config.ParentalControl.config_sections.standby_menu.value and self.menuID == "shutdown":
				return True
class MainMenu(Menu):
	#add file load functions for the xml-file

	def __init__(self, *x):
		self.skinName = "Menu"
		Menu.__init__(self, *x)

