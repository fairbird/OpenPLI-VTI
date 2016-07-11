from ChannelSelection import ChannelSelection, BouquetSelector, SilentBouquetSelector

from Components.ActionMap import ActionMap, HelpableActionMap
from Components.ActionMap import NumberActionMap
from Components.Harddisk import harddiskmanager
from Components.Input import Input
from Components.Label import Label
from Components.PluginComponent import plugins
from Components.ServiceEventTracker import ServiceEventTracker
from Components.Sources.Boolean import Boolean
from Components.Sources.ServiceEvent import ServiceEvent
from Components.config import config, ConfigBoolean, ConfigClock
from Components.SystemInfo import SystemInfo
from Components.UsageConfig import preferredInstantRecordPath, defaultMoviePath
from EpgSelection import EPGSelection
from Plugins.Plugin import PluginDescriptor

from Screen import Screen
from Screens.ChoiceBox import ChoiceBox
from Screens.Dish import Dish
from Screens.EventView import EventViewEPGSelect, EventViewSimple, EventViewMovieEvent
from Screens.InputBox import InputBox
from Screens.MessageBox import MessageBox
from Screens.MinuteInput import MinuteInput
from Screens.TimerSelection import TimerSelection
from Screens.PictureInPicture import PictureInPicture
from Screens.PiGDummy import PiGDummy
from Screens.SplitScreen import SplitScreen
from Screens.SubtitleDisplay import SubtitleDisplay
from Screens.RdsDisplay import RdsInfoDisplay, RassInteractive
from Screens.TimeDateInput import TimeDateInput
from Screens.UnhandledKey import UnhandledKey
from ServiceReference import ServiceReference

from Tools import Notifications
from Tools.Directories import fileExists
from Tools.MovieInfoParser import getExtendedMovieDescription
from Tools.Bytes2Human import bytes2human

from enigma import eTimer, eServiceCenter, eDVBServicePMTHandler, iServiceInformation, \
	iPlayableService, eServiceReference, eEPGCache, eActionMap

from time import time, localtime, strftime
from os import stat as os_stat, path as os_path, listdir as os_listdir, rename as os_rename
from bisect import insort

from RecordTimer import RecordTimerEntry, RecordTimer

# hack alert!
from Menu import MainMenu, mdom

import Screens.Standby

class InfoBarDish:
	def __init__(self):
		self.dishDialog = self.session.instantiateDialog(Dish)
		self.dishDialog.setAnimationMode(0)

class InfoBarUnhandledKey:
	def __init__(self):
		self.unhandledKeyDialog = self.session.instantiateDialog(UnhandledKey)
		self.unhandledKeyDialog.setAnimationMode(0)
		self.hideUnhandledKeySymbolTimer = eTimer()
		self.hideUnhandledKeySymbolTimer.callback.append(self.unhandledKeyDialog.hide)
		self.checkUnusedTimer = eTimer()
		self.checkUnusedTimer.callback.append(self.checkUnused)
		self.onLayoutFinish.append(self.unhandledKeyDialog.hide)
		eActionMap.getInstance().bindAction('', -0x7FFFFFFF, self.actionA) #highest prio
		eActionMap.getInstance().bindAction('', 0x7FFFFFFF, self.actionB) #lowest prio
		self.flags = (1<<1);
		self.uflags = 0;

	#this function is called on every keypress!
	def actionA(self, key, flag):
		if flag != 4:
			if self.flags & (1<<1):
				self.flags = self.uflags = 0
			self.flags |= (1<<flag)
			if flag == 1: # break
				self.checkUnusedTimer.start(0, True)
		return 0

	#this function is only called when no other action has handled this key
	def actionB(self, key, flag):
		if flag != 4:
			self.uflags |= (1<<flag)

	def checkUnused(self):
		if self.flags == self.uflags:
			self.unhandledKeyDialog.show()
			self.hideUnhandledKeySymbolTimer.start(2000, True)

class InfoBarShowHide:
	""" InfoBar show/hide control, accepts toggleShow and hide actions, might start
	fancy animations. """
	STATE_HIDDEN = 0
	STATE_HIDING = 1
	STATE_SHOWING = 2
	STATE_SHOWN = 3

	def __init__(self):
		self["ShowHideActions"] = ActionMap( ["InfobarShowHideActions"] ,
			{
				"toggleShow": self.toggleShow,
				"hide": self.infobar_hide,
			}, 1) # lower prio to make it possible to override ok and cancel..

		self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
			{
				iPlayableService.evStart: self.serviceStarted,
			})

		self.__state = self.STATE_SHOWN
		self.__locked = 0

		self.hideTimer = eTimer()
		self.hideTimer.callback.append(self.doTimerHide)
		self.hideTimer.start(5000, True)

		self.onShow.append(self.__onShow)
		self.onHide.append(self.__onHide)
		self.unlockTimer = eTimer()
		self.unlockTimer.callback.append(self.unlockEXIT)

		self.DimmingTimer = eTimer()
		self.DimmingTimer.callback.append(self.doDimming)

		self.AnimationInTimer = eTimer()
		self.AnimationInTimer.callback.append(self.doAnimationIn)

		self.unDimmingTimer = eTimer()
		self.unDimmingTimer.callback.append(self.unDimming)


	def unlockEXIT(self):
		self.exit_locked = False
		self.unlockTimer.stop()

	def serviceStarted(self):
		if self.execing:
			if config.usage.show_infobar_on_zap.value:
				if self.session.pipshown:
					if config.usage.show_infobar_on_splitscreen.value:
						self.doShow()
				else:
					self.doShow()

	def __onShow(self):
		self.__state = self.STATE_SHOWN
		if config.usage.infobar_dimm.value == "off" or config.usage.infobar_dimm.value == "fade_out":
			self.startHideTimer()

	def startHideTimer(self):
		if self.__state == self.STATE_SHOWN and not self.__locked:
			idx = config.usage.infobar_timeout.index
			if idx:
				self.hideTimer.start(idx*1000, True)

	def __onHide(self):
		self.__state = self.STATE_HIDDEN
		self.exit_locked = True
		if config.usage.infobar_dimm.value == "fade_out" or config.usage.infobar_dimm.value == "fade_in_out":
			self.unDimmingTimer.start(100, True)
		self.unlockTimer.start(500, True)

	def getDimmSpeed(self):
		return int(config.usage.infobar_dimm_speed.value)

	def doDimming(self):
		self.dimmed = self.dimmed - 1
		self.DimmingTimer.stop()
                if self.__state != self.STATE_HIDDEN:
			f = open("/proc/stb/video/alpha","r")
			osd_alpha = int(f.read().strip())
			f.close()
			f = open("/proc/stb/video/alpha","w")
			f.write("%i" % (osd_alpha*self.dimmed / self.getDimmSpeed()))
			f.close()
			if self.dimmed > 0 and osd_alpha > 0:
				self.animation_active = True
				self.DimmingTimer.start(70, True)
			else:
				if self.__state == self.STATE_SHOWN:
					self.hide()
					self.hideTimer.stop()

	def doAnimationIn(self):
		self.dimmed = self.dimmed + 1
		self.AnimationInTimer.stop()
                if self.__state != self.STATE_HIDDEN:
			osd_alpha = int(config.av.osd_alpha.value*self.dimmed / self.getDimmSpeed())
			if osd_alpha >= 255:
				osd_alpha = 255
				self.dimmed = self.getDimmSpeed()
			else:
				f = open("/proc/stb/video/alpha","w")
				f.write(str(osd_alpha))
				f.close()
			if self.dimmed < self.getDimmSpeed():
				self.AnimationInTimer.start(70, True)
			else:
				self.AnimationInTimer.stop()
				self.startHideTimer()


	def unDimming(self):
		self.unDimmingTimer.stop()
		f=open("/proc/stb/video/alpha","w")
		f.write("%i" % (config.av.osd_alpha.value))
		f.close()

	def doShow(self):
		self.show()
		self.startHideTimer()

	def doTimerHide(self):
		self.hideTimer.stop()
		if config.usage.infobar_dimm.value == "fade_out" or config.usage.infobar_dimm.value == "fade_in_out":
			self.DimmingTimer.start(70, True)
			self.dimmed = self.getDimmSpeed()
		else:
			if self.__state == self.STATE_SHOWN:
				self.hide()

	def toggleShow(self):
		if self.__state == self.STATE_SHOWN:
			if config.usage.infobar_dimm.value == "fade_out" or config.usage.infobar_dimm.value == "fade_in_out":
				self.doTimerHide()
			else:
				self.hide()
				self.hideTimer.stop()
		elif self.__state == self.STATE_HIDDEN:
			if config.usage.infobar_dimm.value == "fade_in" or config.usage.infobar_dimm.value == "fade_in_out":
				self.show()
				self.dimmed = 0
				self.doAnimationIn()
			else:
				self.show()
				if config.usage.disable_infobar_timeout_okbutton.value:
					self.hideTimer.stop()

	def lockShow(self):
		self.__locked = self.__locked + 1
		if self.execing:
			self.show()
			self.hideTimer.stop()

	def unlockShow(self):
		self.__locked = self.__locked - 1
		if self.execing:
			self.startHideTimer()

	def infobar_hide(self):
		if (config.usage.infobar_dimm.value == "fade_out" or config.usage.infobar_dimm.value == "fade_in_out") and self.__state == self.STATE_SHOWN:
			self.DimmingTimer.start(70, True)
			self.dimmed = self.getDimmSpeed()
		else:
			self.hide()

#	def startShow(self):
#		self.instance.m_animation.startMoveAnimation(ePoint(0, 600), ePoint(0, 380), 100)
#		self.__state = self.STATE_SHOWN
#
#	def startHide(self):
#		self.instance.m_animation.startMoveAnimation(ePoint(0, 380), ePoint(0, 600), 100)
#		self.__state = self.STATE_HIDDEN

class NumberZapWithName(Screen):
	skin = """
		<screen name="NumberZapWithName" position="center,center" size="425,130" title="%s">
			<widget alphatest="blend" position="300,35" render="Picon" size="100,60" source="Service" transparent="1" zPosition="1">
				<convert type="ServiceName">Reference</convert>
			</widget>
			<widget name="servicenumber" position="10,14" size="290,30" font="Regular;24" halign="center" />
			<widget name="servicename" position="10,50" size="290,30" font="Regular;24" halign="center" />
			<widget name="servicebouquet" position="10,86" size="290,30" font="Regular;24" halign="center" />
		</screen>
		""" % (_("Channel"))

	def quit(self):
		self.Timer.stop()
		self.close(0)

	def keyOK(self):
		self.Timer.stop()
		self.close(int(self.my_number))

	def keyNumberGlobal(self, number):
		bouquet = self.bouquet
		self.my_number = int(str(self.my_number) + str(number))
		if len(str(self.my_number)) >= 4:
			self.keyOK()
		service_name, bouquet_name = self.getServiceName(self.my_number, bouquet)
		if service_name == None:
			service_name = _("not available")
		if bouquet_name == None:
			bouquet_name = _("not available")
		self.Timer.start(self.timer_duration, True)
		if config.usage.numberzap_show_picon.value:
			self["Service"].newService(self.myservice)
		self["servicenumber"].setText(str(self.my_number))
		self["servicename"].setText(str(service_name))
		self["servicebouquet"].setText(str(bouquet_name))

	def searchNumberHelper(self, serviceHandler, num, bouquet):
		servicelist = serviceHandler.list(bouquet)
		if not servicelist is None:
			while num:
				serviceIterator = servicelist.getNext()
				if not serviceIterator.valid(): #check end of list
					break
				playable = not (serviceIterator.flags & (eServiceReference.isMarker|eServiceReference.isDirectory))
				if playable:
					num -= 1;
			if not num: #found service with searched number ?
				return serviceIterator, 0
		return None, num

	def getServiceName(self, number, bouquet):
		myservice = None
		serviceHandler = eServiceCenter.getInstance()
		
		if not config.usage.multibouquet.value:
			myservice, number = self.searchNumberHelper(serviceHandler, number, bouquet)
		else:
			bouquetlist = serviceHandler.list(bouquet)
			if not bouquetlist is None:
				while number:
					bouquet = bouquetlist.getNext()
					if not bouquet.valid(): #check end of list
						break
					if bouquet.flags & eServiceReference.isDirectory:
						myservice, number = self.searchNumberHelper(serviceHandler, number, bouquet)
		if myservice:
			self.myservice = myservice
			bouquetinfo = serviceHandler.info(bouquet)
			bouquet_name = bouquetinfo.getName(bouquet)
			info = serviceHandler.info(myservice)
			service_name = info.getName(myservice)
			return service_name, bouquet_name
		else:
			self.myservice = None
			return None, None

	def initPicons(self):
		self["Service"].newService(self.myservice)

	def __init__(self, session, number, bouquet):
		Screen.__init__(self, session)
		self["Service"] = ServiceEvent()
		self.my_number = number
		self.bouquet = bouquet
		self.field = ""
		myservice_name, bouquet_name = self.getServiceName(number, bouquet)

		self["servicenumber"] = Label(str(number))
		self["servicename"] = Label(myservice_name)
		self["servicebouquet"] = Label(bouquet_name)

		self["actions"] = NumberActionMap( [ "SetupActions" ],
			{
				"cancel": self.quit,
				"ok": self.keyOK,
				"1": self.keyNumberGlobal,
				"2": self.keyNumberGlobal,
				"3": self.keyNumberGlobal,
				"4": self.keyNumberGlobal,
				"5": self.keyNumberGlobal,
				"6": self.keyNumberGlobal,
				"7": self.keyNumberGlobal,
				"8": self.keyNumberGlobal,
				"9": self.keyNumberGlobal,
				"0": self.keyNumberGlobal
			})

		self.timer_duration = config.usage.numberzap_timeout.value
		self.Timer = eTimer()
		self.Timer.callback.append(self.keyOK)
		self.Timer.start(self.timer_duration, True)
		if config.usage.numberzap_show_picon.value:
			self.onLayoutFinish.append(self.initPicons)

class NumberZap(Screen):
	def quit(self):
		self.Timer.stop()
		self.close(0)

	def keyOK(self):
		self.Timer.stop()
		self.close(int(self["number"].getText()))

	def keyNumberGlobal(self, number):
		self.Timer.start(self.timer_duration, True)		#reset timer
		self.field = self.field + str(number)
		self["number"].setText(self.field)
		if len(self.field) >= 4:
			self.keyOK()

	def __init__(self, session, number):
		Screen.__init__(self, session)
		self.field = str(number)

		self["channel"] = Label(_("Channel:"))

		self["number"] = Label(self.field)

		self["actions"] = NumberActionMap( [ "SetupActions" ],
			{
				"cancel": self.quit,
				"ok": self.keyOK,
				"1": self.keyNumberGlobal,
				"2": self.keyNumberGlobal,
				"3": self.keyNumberGlobal,
				"4": self.keyNumberGlobal,
				"5": self.keyNumberGlobal,
				"6": self.keyNumberGlobal,
				"7": self.keyNumberGlobal,
				"8": self.keyNumberGlobal,
				"9": self.keyNumberGlobal,
				"0": self.keyNumberGlobal
			})

		self.timer_duration = config.usage.numberzap_timeout.value
		self.Timer = eTimer()
		self.Timer.callback.append(self.keyOK)
		self.Timer.start(self.timer_duration, True)

class InfoBarNumberZap:
	""" Handles an initial number for NumberZapping """
	def __init__(self):
		self.pressed_key = -1
		self.init_zero_key_timer()
		self["NumberActions"] = NumberActionMap( [ "NumberActions"],
			{
				"1": self.keyNumberGlobal,
				"2": self.keyNumberGlobal,
				"3": self.keyNumberGlobal,
				"4": self.keyNumberGlobal,
				"5": self.keyNumberGlobal,
				"6": self.keyNumberGlobal,
				"7": self.keyNumberGlobal,
				"8": self.keyNumberGlobal,
				"9": self.keyNumberGlobal,
				"0": self.keyNumberGlobal,
			})

	def init_zero_key_timer(self):
		self.zero_pressed = False
		self.zero_key_timer = eTimer()
		self.zero_key_timer.callback.append(self.end_zero_key_timer)

	def start_zero_key_timer(self):
		if self.zero_pressed:
			self.zero_pressed = False
			self.zero_key_timer.stop()
			self.execute_zero_action(is_double = True)
		else:
			self.zero_pressed = True
			self.zero_key_timer.start(config.usage.zero_doubleclick_timeout.value)

	def end_zero_key_timer(self):
		if self.zero_pressed:
			self.zero_pressed = False
			self.execute_zero_action(is_double = False)

	def execute_zero_action(self, is_double = False):
		if isinstance(self, InfoBarPiP) and self.pipHandles0Action():
			self.pipDoHandle0Action(is_double)
		elif is_double:
			self.execute_zero_doubleclick_action()
		else:
			if self.has_key("TimeshiftActions"):
				if self.timeshift_enabled and config.usage.ts_use_history_keys.value:
					self.chooseTimeshiftFile()
					return
				elif self.timeshift_enabled:
					if config.usage.ts_ask_before_service_changed.value == "ask":
						ts = self.getTimeshift()
						if ts and ts.isTimeshiftActive():
							self.stopTimeshift_wrapper(self.callPreviousService)
							return
						else:
							ts = None
							self.stopTimeshiftConfirmed((True, "keep_ts"))
					else:
						self.stopTimeshiftConfirmed((True, config.usage.ts_ask_before_service_changed.value))
			self.servicelist.recallPrevService()

	def callPreviousService(self, ret):
		if ret and ret[1] != "continue_ts":
			self.stopTimeshiftConfirmed(ret)
			self.servicelist.recallPrevService()


	def keyNumberGlobal(self, number):
		if number == 0:
			self.start_zero_key_timer()
		else:
			if self.has_key("TimeshiftActions") and (not self.timeshift_enabled or self.ts_auto):
				if self.timeshift_enabled:
					if config.usage.ts_ask_before_service_changed.value == "ask":
						ts = self.getTimeshift()
						if ts and ts.isTimeshiftActive():
							self.pressed_key = number
							self.stopTimeshift_wrapper(self.continueNumberZap)
							return
						else:
							ts = None
							self.stopTimeshiftConfirmed((True, "keep_ts"))
					else:
						self.stopTimeshiftConfirmed((True, config.usage.ts_ask_before_service_changed.value))
				if config.usage.numberzap_show_servicename.value:
					bouquet = self.servicelist.bouquet_root
					self.session.openWithCallback(self.numberEntered, NumberZapWithName, number, bouquet)
				else:
					self.session.openWithCallback(self.numberEntered, NumberZap, number)

	def continueNumberZap(self, ret):
		if ret and ret[1] != "continue_ts":
			self.stopTimeshiftConfirmed(ret)
			self.keyNumberGlobal(self.pressed_key)

	def numberEntered(self, retval):
		if retval > 0:
			self.zapToNumber(retval)

	def searchNumberHelper(self, serviceHandler, num, bouquet):
		servicelist = serviceHandler.list(bouquet)
		if not servicelist is None:
			while num:
				serviceIterator = servicelist.getNext()
				if not serviceIterator.valid(): #check end of list
					break
				playable = not (serviceIterator.flags & (eServiceReference.isMarker|eServiceReference.isDirectory))
				if playable:
					num -= 1;
			if not num: #found service with searched number ?
				return serviceIterator, 0
		return None, num

	def zapToNumber(self, number):
		bouquet = self.servicelist.bouquet_root
		service = None
		serviceHandler = eServiceCenter.getInstance()
		# get actual playing service
		servicebeforezap = self.servicelist.getCurrentSelection()
		if not config.usage.multibouquet.value:
			service, number = self.searchNumberHelper(serviceHandler, number, bouquet)
		else:
			bouquetlist = serviceHandler.list(bouquet)
			if not bouquetlist is None:
				while number:
					bouquet = bouquetlist.getNext()
					if not bouquet.valid(): #check end of list
						break
					if bouquet.flags & eServiceReference.isDirectory:
						service, number = self.searchNumberHelper(serviceHandler, number, bouquet)
		if not service is None:
			if self.servicelist.getRoot() != bouquet: #already in correct bouquet?
				self.servicelist.clearPath()
				if self.servicelist.bouquet_root != bouquet:
					self.servicelist.enterPath(self.servicelist.bouquet_root)
				self.servicelist.enterPath(bouquet)
			if config.usage.overzap_notplayable.value:
				# from ServiceInfo.py get service info
				serviceinfo = serviceHandler.info(service)
				# check if playing is possible => if so, break and zap
				if serviceinfo.isPlayable(service, servicebeforezap):
					self.servicelist.setCurrentSelection(service) #select the service in servicelist
					self.servicelist.zap()
			else:
				self.servicelist.setCurrentSelection(service) #select the service in servicelist
				self.servicelist.zap()

config.misc.initialchannelselection = ConfigBoolean(default = True)

from Components.MenuList import MenuList

class InfoBarZapHistory(Screen):
	ALLOW_SUSPEND = True
	
	def __init__(self, session, service_list):
		self.servicelist = service_list
		self.session = session
		Screen.__init__(self, session)
		self.title = _("Zap History")
		self["ServiceEvent"] = ServiceEvent()
		self["ZapHistoryList"] = MenuList([])
		self["ZapHistoryList"].onSelectionChanged.append(self.selectionChanged)
		self["ZapHistoryList"].enableWrapAround = True
		self["ZAPHistoryActions"] = ActionMap(["OkCancelActions"],
			{
				"cancel": self.keyCancel,
				"ok": self.zapTo,
			})
		self["EPGActions"] = ActionMap(["InfobarEPGActions"],
			{
				"showEventInfo": self.openEPG,
			})
		self.onLayoutFinish.append(self.createList)

	def createList(self):
		cur_ref = self.session.nav.getCurrentlyPlayingServiceReference()
		i = 0
		selection_idx = None
		zap_list = []
		for x in reversed(self.servicelist):
			path = x[:]
			ref = path.pop()
			new_service = (ServiceReference(ref).getServiceName(), ref)
			if new_service not in zap_list:
				zap_list.append(new_service)
			if cur_ref is not None and cur_ref == ref and selection_idx is None:
				selection_idx = i
			i += 1
		self["ZapHistoryList"].setList(zap_list)
		if selection_idx is not None:
			self["ZapHistoryList"].moveToIndex(selection_idx)

	def selectionChanged(self):
		cur = self["ZapHistoryList"].getCurrent()
		if cur is not None:
			cur = cur[1]
			self["ServiceEvent"].newService(cur)

	def keyCancel(self):
		self.close(None)

	def zapTo(self):
		i = 0
		cur = self["ZapHistoryList"].getCurrent()
		if cur is not None:
			cur = cur[1]
			for x in self.servicelist:
				ref = x[:].pop()
				if ref == cur:
					break
				else:
					i += 1
				if i == (len(self.servicelist) -1):
					break
		self.close(i)

	def openEPG(self):
		ref = cur = self["ZapHistoryList"].getCurrent()[1]
		self.session.open(EPGSelection, ref)

class InfoBarChannelSelection:
	""" ChannelSelection - handles the channelSelection dialog and the initial
	channelChange actions which open the channelSelection dialog """
	def __init__(self):
		#instantiate forever
		self.servicelist = self.session.instantiateDialog(ChannelSelection)

		self.exit_locked = False

		if config.misc.initialchannelselection.value:
			self.onShown.append(self.firstRun)

		if config.usage.show_favourites_w_bouquet.value == "down":
			bouquet_up_help_str = _("open servicelist")
			bouquet_down_help_str = _("show Favourites")
		elif config.usage.show_favourites_w_bouquet.value == "up":
			bouquet_up_help_str = _("show Favourites")
			bouquet_down_help_str = _("open servicelist")
		else:
			bouquet_up_help_str = _("open servicelist")
			bouquet_down_help_str = _("open servicelist")

		channel_selection_actions = {
				"zapUp": (self.zapUp, _("previous channel")),
				"zapDown": (self.zapDown, _("next channel")),
				"historyBack": (self.historyBack, _("previous channel in history")),
				"historyNext": (self.historyNext, _("next channel in history")),
                                "zapHistory": (self.showZapHistory, _("Zap History")),
			}

		if config.usage.channelzap_w_bouquet.value:
			zap_actions = {
				"openServiceList": (self.zapUp, _("previous channel")),
                                "showFavourites": (self.zapDown, _("next channel")),
				"switchChannelUp": (self.bouquetUp, bouquet_up_help_str),
				"switchChannelDown": (self.bouquetDown, bouquet_down_help_str),
			}
		else:
			zap_actions = {
				"openServiceList": (self.bouquetDown, bouquet_down_help_str),
                                "showFavourites": (self.bouquetUp, bouquet_up_help_str),
				"switchChannelUp": (self.switchChannelUp, _("open servicelist(up)")),
				"switchChannelDown": (self.switchChannelDown, _("open servicelist(down)")),
			}

		channel_selection_actions.update(zap_actions)

		self["ChannelSelectActions"] = HelpableActionMap(self, "InfobarChannelSelection",channel_selection_actions)
		self.zap_up = 1
		self.zap_down = -1

	def showZapHistory(self):
		if config.usage.enable_zaphistory.value and not self.shown and not self.session.pipshown and not self.exit_locked:
			self.session.openWithCallback(self.zapToHistoryEntry, InfoBarZapHistory, self.servicelist.history)

	def zapToHistoryEntry(self, idx = None):
		if idx is not None:
			if self.has_key("TimeshiftActions") and self.timeshift_enabled:
				if config.usage.ts_ask_before_service_changed.value == "ask":
					ts = self.getTimeshift()
					if ts and ts.isTimeshiftActive():
						self.zap_idx = idx
						self.stopTimeshift_wrapper(self.continueZapToHistoryEntry)
						return
					else:
						ts = None
						self.stopTimeshiftConfirmed((True, "keep_ts"))
				else:
					self.stopTimeshiftConfirmed((True, config.usage.ts_ask_before_service_changed.value))
			self.servicelist.historyIndex(idx)

	def continueZapToHistoryEntry(self, ret):
		if ret and ret[1] != "continue_ts":
			self.stopTimeshiftConfirmed(ret)
			self.servicelist.historyIndex(self.zap_idx)

	def bouquetUp(self):
		if config.usage.show_favourites_w_bouquet.value == "up":
			self.servicelist.showFavourites()
		self.openServiceList()

	def bouquetDown(self):
		if config.usage.show_favourites_w_bouquet.value == "down":
			self.servicelist.showFavourites()
		self.openServiceList()

	def showFavourites(self):
		if config.usage.show_favourites_bouquetup.value:
			self.servicelist.showFavourites()
		self.openServiceList()

	def showTvChannelList(self, zap=False):
		self.servicelist.setModeTv()
		if zap:
			self.servicelist.zap()
		if config.usage.show_servicelist_at_modeswitch.value:
			self.session.execDialog(self.servicelist)

	def showRadioChannelList(self, zap=False):
		self.servicelist.setModeRadio()
		if zap:
			self.servicelist.zap()
		if config.usage.show_servicelist_at_modeswitch.value:
			self.session.execDialog(self.servicelist)

	def firstRun(self):
		self.onShown.remove(self.firstRun)
		config.misc.initialchannelselection.value = False
		config.misc.initialchannelselection.save()
		self.switchChannelDown()

	def timeshiftHistoryBack(self):
		if self.has_key("TimeshiftActions"):
			self.newTSFile(-1)

	def timeshiftHistoryNext(self):
		if self.has_key("TimeshiftActions"):
			self.newTSFile(1)

	def historyBack(self):
		if config.usage.ts_use_history_keys.value and self.has_key("TimeshiftActions") and self.timeshift_enabled:
			self.timeshiftHistoryBack()
			return
		hlen = len(self.servicelist.history)
		if hlen < 1 or self.servicelist.history_pos < 1:
			return
		if self.has_key("TimeshiftActions") and self.timeshift_enabled:
			if config.usage.ts_ask_before_service_changed.value == "ask":
				ts = self.getTimeshift()
				if ts and ts.isTimeshiftActive():
					self.stopTimeshift_wrapper(self.continueHistoryBack)
					return
				else:
					ts = None
					self.stopTimeshiftConfirmed((True, "keep_ts"))
			else:
				self.stopTimeshiftConfirmed((True, config.usage.ts_ask_before_service_changed.value))
		self.servicelist.historyBack()

	def historyNext(self):
		if config.usage.ts_use_history_keys.value and self.has_key("TimeshiftActions") and self.timeshift_enabled:
			self.timeshiftHistoryNext()
			return
		hlen = len(self.servicelist.history)
		if hlen < 1 or self.servicelist.history_pos >= (hlen - 1):
			return
		if self.has_key("TimeshiftActions") and self.timeshift_enabled:
			if config.usage.ts_ask_before_service_changed.value == "ask":
				ts = self.getTimeshift()
				if ts and ts.isTimeshiftActive():
					self.stopTimeshift_wrapper(self.continueHistoryNext)
					return
				else:
					ts = None
					self.stopTimeshiftConfirmed((True, "keep_ts"))
			else:
				self.stopTimeshiftConfirmed((True, config.usage.ts_ask_before_service_changed.value))
		self.servicelist.historyNext()

	def continueHistoryBack(self, ret):
		if ret and ret[1] != "continue_ts":
			self.stopTimeshiftConfirmed(ret)
			self.historyBack()

	def continueHistoryNext(self, ret):
		if ret and ret[1] != "continue_ts":
			self.stopTimeshiftConfirmed(ret)
			self.historyNext()

	def newTSFile(self, direction):
		if self.getTimeshift():
			cur_ref = self.session.nav.getCurrentlyPlayingServiceReference().toString()
			if cur_ref in self.ts_files and len(self.ts_files[cur_ref]):
				self.change_ts_file(direction, cur_ref)

	def switchChannelUp(self):
		self.servicelist.moveUp()
		self.session.execDialog(self.servicelist)

	def switchChannelDown(self):
		self.servicelist.moveDown()
		self.session.execDialog(self.servicelist)

	def openServiceList(self):
		self.session.execDialog(self.servicelist)

	def zapUp(self):
		if self.has_key("TimeshiftActions") and self.timeshift_enabled:
			if config.usage.ts_ask_before_service_changed.value == "ask":
				ts = self.getTimeshift()
				if ts and ts.isTimeshiftActive():
					self.zap_direction = self.zap_up
					self.stopTimeshift_wrapper(self.continueZap)
					return
				else:
					ts = None
					self.stopTimeshiftConfirmed((True, "keep_ts"))
			else:
				self.stopTimeshiftConfirmed((True, config.usage.ts_ask_before_service_changed.value))
		if self.servicelist.inBouquet():
			if not self.session.pip_zap_main and isinstance(self, InfoBarPiP) and self.session.pipshown:
				prev = self.session.pip.getCurrentService()
			else:
				prev = self.servicelist.getCurrentSelection()
			# get playing service (not string version)
			prevclean = prev
			if prev:
				prev = prev.toString()
				while True:
					if config.usage.quickzap_bouquet_change.value:
						if self.servicelist.atBegin():
							self.servicelist.prevBouquet()
					self.servicelist.moveUp()
					cur = self.servicelist.getCurrentSelection()
					if cur.toString().startswith("-1"):
						self.servicelist.prevBouquet()
						self.servicelist.moveUp()
						cur = self.servicelist.getCurrentSelection()
					if not cur or (not (cur.flags & 64)) or cur.toString() == prev:
						if config.usage.overzap_notplayable.value:
							# from ServiceInfo.py get service info
							serviceinfo = eServiceCenter.getInstance().info(cur)
							if serviceinfo is not None:
								# check if playing is possible => if so, break and zap
								if serviceinfo.isPlayable(cur, prevclean):
									break
						else:
							break
		else:
			self.servicelist.moveUp()
		self.servicelist.zap()

	def zapDown(self):
		if self.has_key("TimeshiftActions") and self.timeshift_enabled:
			if config.usage.ts_ask_before_service_changed.value == "ask":
				ts = self.getTimeshift()
				if ts and ts.isTimeshiftActive():
					self.zap_direction = self.zap_down
					self.stopTimeshift_wrapper(self.continueZap)
					return
				else:
					ts = None
					self.stopTimeshiftConfirmed((True, "keep_ts"))
			else:
				self.stopTimeshiftConfirmed((True, config.usage.ts_ask_before_service_changed.value))
		if self.servicelist.inBouquet():
			if not self.session.pip_zap_main and isinstance(self, InfoBarPiP) and self.session.pipshown:
				prev = self.session.pip.getCurrentService()
			else:
				prev = self.servicelist.getCurrentSelection()
			# get playing service (not string version)
			prevclean = prev
			if prev:
				prev = prev.toString()
				while True:
					if config.usage.quickzap_bouquet_change.value and self.servicelist.atEnd():
						self.servicelist.nextBouquet()
					else:
						self.servicelist.moveDown()
					cur = self.servicelist.getCurrentSelection()
					if cur.toString().startswith("-1"):
						self.servicelist.nextBouquet()
						cur = self.servicelist.getCurrentSelection()
					if not cur or (not (cur.flags & 64)) or cur.toString() == prev:
						if config.usage.overzap_notplayable.value:
							# from ServiceInfo.py get service info
							serviceinfo = eServiceCenter.getInstance().info(cur)
							if serviceinfo is not None:
								# check if playing is possible => if so, break and zap
								if serviceinfo.isPlayable(cur, prevclean):
									break
						else:
							break
		else:
			self.servicelist.moveDown()
		self.servicelist.zap()

	def continueZap(self, ret):
		if ret and ret[1] != "continue_ts":
			self.stopTimeshiftConfirmed(ret)
			if self.zap_direction == self.zap_up:
				self.zapUp()
			elif self.zap_direction == self.zap_down:
				self.zapDown()

class InfoBarMenu:
	""" Handles a menu action, to open the (main) menu """
	def __init__(self):
		self["MenuActions"] = HelpableActionMap(self, "InfobarMenuActions",
			{
				"mainMenu": (self.mainMenu, _("Enter main menu...")),
			})
		self.session.infobar = None

	def mainMenu(self):
		print "loading mainmenu XML..."
		menu = mdom.getroot()
		assert menu.tag == "menu", "root element in menu must be 'menu'!"

		self.session.infobar = self
		# so we can access the currently active infobar from screens opened from within the mainmenu
		# at the moment used from the SubserviceSelection

		self.session.openWithCallback(self.mainMenuClosed, MainMenu, menu)

	def mainMenuClosed(self, *val):
		self.session.infobar = None

class InfoBarSimpleEventView:
	""" Opens the Eventview for now/next """
	def __init__(self):
		self["EPGActions"] = HelpableActionMap(self, "InfobarEPGActions",
			{
				"showEventInfo": (self.openEventView, _("show event details")),
				"showInfobarOrEpgWhenInfobarAlreadyVisible": self.showEventInfoWhenNotVisible,
			})

	def showEventInfoWhenNotVisible(self):
		if self.shown:
			self.openEventView()
		else:
			self.toggleShow()
			return 1

	def openEventView(self):
		epglist = [ ]
		self.epglist = epglist
		service = self.session.nav.getCurrentService()
		ref = self.session.nav.getCurrentlyPlayingServiceReference()
		info = service.info()
		ptr=info.getEvent(0)
		if ptr:
			epglist.append(ptr)
		ptr=info.getEvent(1)
		if ptr:
			epglist.append(ptr)
		if epglist:
			self.session.open(EventViewSimple, epglist[0], ServiceReference(ref), self.eventViewCallback)
		elif ref.toString().startswith("4097"):
			path = ref.getPath()
			if path.startswith(("rtsp", "rtmp", "http", "mms")):
				name = ref.getName()
				ext_desc = ""
				length = ""
			else:
				seek = self.getSeek()
				length = ""
				if seek:
					length = seek.getLength()
					if not length[0] and length[1] > 1:
						length = length[1] / 90000
						if config.usage.movielist_duration_in_min.value:
							length = "%d min" % (int(length)/60)
						else:
							length = "%02d:%02d:%02d" % (length/3600, length%3600/60, length%60)
				name, ext_desc = getExtendedMovieDescription(ref)
			self.session.open(EventViewMovieEvent, name, ext_desc, length)

	def eventViewCallback(self, setEvent, setService, val): #used for now/next displaying
		epglist = self.epglist
		if len(epglist) > 1:
			tmp = epglist[0]
			epglist[0] = epglist[1]
			epglist[1] = tmp
			setEvent(epglist[0])

class SimpleServicelist:
	def __init__(self, services):
		self.services = services
		self.length = len(services)
		self.current = 0

	def selectService(self, service):
		if not self.length:
			self.current = -1
			return False
		else:
			self.current = 0
			while self.services[self.current].ref != service:
				self.current += 1
				if self.current >= self.length:
					return False
		return True

	def nextService(self):
		if not self.length:
			return
		if self.current+1 < self.length:
			self.current += 1
		else:
			self.current = 0

	def prevService(self):
		if not self.length:
			return
		if self.current-1 > -1:
			self.current -= 1
		else:
			self.current = self.length - 1

	def currentService(self):
		if not self.length or self.current >= self.length:
			return None
		return self.services[self.current]

	def currentServiceidx(self):
		if not self.length or self.current >= self.length:
			return None
		return self.current

	def selectServiceidx(self, idx):
		if idx >= self.length:
			return False
		else:
			self.current = idx
		return True

class InfoBarEPG:
	""" EPG - Opens an EPG list when the showEPGList action fires """
	def __init__(self):
		self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
			{
				iPlayableService.evUpdatedEventInfo: self.__evEventInfoChanged,
			})

		self.has_gmepg = False
		self.isEPGBar = None
		self.EPGBar_PiP_on = False
		self.is_now_next = False
		self.dlg_stack = [ ]
		self.bouquetSel = None
		self.eventView = None
		self["EPGActions"] = HelpableActionMap(self, "InfobarEPGActions",
			{
				"showEPGBar": (self.openEPGBar, _("show service EPGBar...")),
				"showEventInfo": (self.open_selected_EPG_view, _("show EPG...")),
				"showEventInfoPlugin": (self.showEventInfoPlugins, _("list of EPG views...")),
				"showInfobarOrEpgWhenInfobarAlreadyVisible": self.showEventInfoWhenNotVisible,
			})

	def showEventInfoWhenNotVisible(self):
		if self.shown:
			self.openEventView()
		else:
			self.toggleShow()
			return 1

	def zapToService(self, service, check_correct_bouquet = False):
		if not service is None:
			if self.isEPGBar and (config.usage.pip_in_EPGBar.value or self.EPGBar_PiP_on):
				self.showPiP()
			if check_correct_bouquet: # be sure to be in correct bouquet if zapping in SINGLEEPG or EPGBAR (we do not call the bouquetchangeCB !!!)
				self.epg_bouquet = self.bouquetSearchHelper(service)[1]
			if self.servicelist.getRoot() != self.epg_bouquet: #already in correct bouquet?
				self.servicelist.clearPath()
				if self.servicelist.bouquet_root != self.epg_bouquet:
					self.servicelist.enterPath(self.servicelist.bouquet_root)
				self.servicelist.enterPath(self.epg_bouquet)
			self.servicelist.setCurrentSelection(service) #select the service in servicelist
			self.servicelist.zap()

	def getBouquetServices(self, bouquet):
		services = [ ]
		servicelist = eServiceCenter.getInstance().list(bouquet)
		if not servicelist is None:
			while True:
				service = servicelist.getNext()
				if not service.valid(): #check if end of list
					break
				if service.flags & (eServiceReference.isDirectory | eServiceReference.isMarker): #ignore non playable services
					continue
				services.append(ServiceReference(service))
		return services

	def openBouquetEPG(self, bouquet, withCallback=True):
		services = self.getBouquetServices(bouquet)
		if services:
			self.epg_bouquet = bouquet
			if withCallback:
				self.dlg_stack.append(self.session.openWithCallback(self.closed, EPGSelection, services, self.zapToService, None, self.changeBouquetCB))
			else:
				self.session.open(EPGSelection, services, self.zapToService, None, self.changeBouquetCB)

	def changeBouquetCB(self, direction, epg):
		if self.bouquetSel:
			if direction > 0:
				self.bouquetSel.down()
			else:
				self.bouquetSel.up()
			bouquet = self.bouquetSel.getCurrent()
			services = self.getBouquetServices(bouquet)
			if services:
				self.epg_bouquet = bouquet
				epg.setServices(services)

	def closed(self, ret=False):
		closedScreen = self.dlg_stack.pop()
		if self.bouquetSel and closedScreen == self.bouquetSel:
			self.bouquetSel = None
		elif self.eventView and closedScreen == self.eventView:
			self.eventView = None
		if ret:
			dlgs=len(self.dlg_stack)
			if dlgs > 0:
				self.dlg_stack[dlgs-1].close(dlgs > 1)

	def openMultiServiceEPG(self, withCallback=True):
		bouquets = self.servicelist.getBouquetList()
		if bouquets is None:
			cnt = 0
		else:
			cnt = len(bouquets)
		if config.usage.multiepg_ask_bouquet.value:
			self.openMultiServiceEPGAskBouquet(bouquets, cnt, withCallback)
		else:
			self.openMultiServiceEPGSilent(bouquets, cnt, withCallback)

	def openMultiServiceEPGAskBouquet(self, bouquets, cnt, withCallback):
		if cnt > 1: # show bouquet list
			if withCallback:
				self.bouquetSel = self.session.openWithCallback(self.closed, BouquetSelector, bouquets, self.openBouquetEPG, enableWrapAround=True)
				self.dlg_stack.append(self.bouquetSel)
			else:
				self.bouquetSel = self.session.open(BouquetSelector, bouquets, self.openBouquetEPG, enableWrapAround=True)
		elif cnt == 1:
			self.openBouquetEPG(bouquets[0][1], withCallback)

	def openMultiServiceEPGSilent(self, bouquets, cnt, withCallback):
		root = self.servicelist.getRoot()
		rootstr = root.toCompareString()
		current = 0
		for bouquet in bouquets:
			if bouquet[1].toCompareString() == rootstr:
				break
			current += 1
		if current >= cnt:
			current = 0
		if cnt > 1: # create bouquet list for bouq+/-
			self.bouquetSel = SilentBouquetSelector(bouquets, True, self.servicelist.getBouquetNumOffset(root))
		if cnt >= 1:
			self.openBouquetEPG(root, withCallback)

	def changeServiceCB(self, direction, epg):
		if self.serviceSel:
			if direction > 0:
				self.serviceSel.nextService()
			else:
				self.serviceSel.prevService()
			epg.setService(self.serviceSel.currentService())
			if (config.usage.pip_in_EPGBar.value or self.EPGBar_PiP_on) and self.isEPGBar:
				new_ref = self.serviceSel.currentService().ref
				self.handleEPGPiP(new_ref)

	def SingleServiceEPGClosed(self, ret=False):
		if self.session.pipshown:
			self.showPiP()
		self.EPGBar_PiP_on = False
		self.isEPGBar = None
		self.serviceSel = None

	def EPGBarNumberZap(self, number, epg):
		if config.usage.quickzap_bouquet_change.value:
			self.myepg = epg
			if config.usage.numberzap_show_servicename.value:
				bouquet = self.servicelist.bouquet_root
				self.session.openWithCallback(self.EPGBarnumberEntered, NumberZapWithName, number, bouquet)
			else:
				self.session.openWithCallback(self.EPGBarnumberEntered, NumberZap, number)
	
	def EPGBarnumberEntered(self, number):
		if int(number):
			self.serviceSel.selectServiceidx(number - 1)
			new_service = self.serviceSel.currentService()
			self.myepg.setService(new_service)
			if (config.usage.pip_in_EPGBar.value or self.EPGBar_PiP_on) and self.isEPGBar:
				self.handleEPGPiP(new_service.ref)
		self.myepg = None

	def bouquetSearchHelper(self, ref, withBouquets = None):
		bouquets = self.servicelist.getBouquetList()
		service_idx = self.serviceSel.currentServiceidx()
		list_len = 0
		for bouquet in bouquets:
			list_len += len(self.getBouquetServices(bouquet[1]))
			if list_len >= service_idx + 1:
				self.epg_bouquet = bouquet[1]
				break
		if withBouquets:
			return bouquet, bouquets
		else:
			return bouquet

	def bouquetSwitcher(self, service, direction, epg):
		if service and config.usage.quickzap_bouquet_change.value:
			(cur_bouquet, bouquets) = self.bouquetSearchHelper(service, withBouquets=True)
			if len(bouquets) > 1 and (cur_bouquet in bouquets):
				cur_idx = bouquets.index(cur_bouquet)
				if direction < 0:
					next_idx = cur_idx - 1
					if next_idx < 0:
						next_idx = len(bouquets) - 1
				else:
					next_idx = cur_idx + 1
					if next_idx == len(bouquets):
						next_idx = 0
				new_bouquet = bouquets[next_idx]
				list_leng = 0
				for bouquet in bouquets:
					bouquet_len = len(self.getBouquetServices(bouquet[1]))
					list_leng += bouquet_len
					if bouquet == new_bouquet:
						new_service_idx = list_leng - bouquet_len
						break
				self.serviceSel.selectServiceidx(new_service_idx)
				new_service = self.serviceSel.currentService()
				epg.setService(new_service)
				if (config.usage.pip_in_EPGBar.value or self.EPGBar_PiP_on) and self.isEPGBar:
					self.handleEPGPiP(new_service.ref)

	def handleEPGPiP(self, new_ref):
		ref=self.session.nav.getCurrentlyPlayingServiceReference()
		if ref == new_ref:
			if self.session.pipshown:
				self.showPiP()
		else:
			if not self.session.pipshown:
				self.showPiP()
			if self.session.pipshown and new_ref:
				self.session.pip.playService(new_ref)

	def togglePiP(self, ref):
		if self.session.pipshown:
			self.EPGBar_PiP_on = False
		else:
			self.EPGBar_PiP_on = True
		self.showPiP()
		if self.session.pipshown and ref:
			self.session.pip.playService(ref)

	def openEPGBar(self):
		if self.shown:
			self.toggleShow()
		self.isEPGBar = True
		self.openSingleServiceEPG(self.isEPGBar)

	def openSingleServiceEPG(self, isEPGBar = None):
		ref=self.session.nav.getCurrentlyPlayingServiceReference()
		if ref:
			if self.servicelist.getMutableList() is not None: # bouquet in channellist
				current_path = self.servicelist.getRoot()
				self.epg_bouquet = current_path
				if config.usage.quickzap_bouquet_change.value:
					bouquets = self.servicelist.getBouquetList()
					services = []
					for bouquet in bouquets:
						tmp_services = self.getBouquetServices(bouquet[1])
						services.extend(tmp_services)
				else:
					services = self.getBouquetServices(current_path)
				self.serviceSel = SimpleServicelist(services)
				if self.serviceSel.selectService(ref):
					self.session.openWithCallback(self.SingleServiceEPGClosed, EPGSelection, ref, zapFunc = self.zapToService, serviceChangeCB = self.changeServiceCB, isEPGBar = self.isEPGBar, switchBouquet = self.bouquetSwitcher, EPGNumberZap = self.EPGBarNumberZap, togglePiP = self.togglePiP)
				else:
					self.session.openWithCallback(self.SingleServiceEPGClosed, EPGSelection, ref, zapFunc = self.zapToService, isEPGBar = isEPGBar, togglePiP = self.togglePiP)
			else:
				self.session.open(EPGSelection, ref)

	def showEventInfoPlugins(self):
		list = [(p.name, boundFunction(self.runPlugin, p)) for p in plugins.getPlugins(where = PluginDescriptor.WHERE_EVENTINFO)]

		if list:
			list.append((_("show service EPGBar..."), self.openEPGBar))
			list.append((_("show single service EPG..."), self.openSingleServiceEPG))
			list.append((_("Multi EPG"), self.openMultiServiceEPG))
			self.session.openWithCallback(self.EventInfoPluginChosen, ChoiceBox, title=_("Please choose an extension..."), list = list, skin_name = "EPGExtensionsList")
		else:
			self.openSingleServiceEPG()

	def runPlugin(self, plugin):
		plugin(session = self.session, servicelist = self.servicelist)
		
	def EventInfoPluginChosen(self, answer):
		if answer is not None:
			answer[1]()

	def openSimilarList(self, eventid, refstr):
		self.session.open(EPGSelection, refstr, None, eventid)

	def getNowNext(self):
		epglist = [ ]
		service = self.session.nav.getCurrentService()
		info = service and service.info()
		ptr = info and info.getEvent(0)
		if ptr:
			epglist.append(ptr)
		ptr = info and info.getEvent(1)
		if ptr:
			epglist.append(ptr)
		self.epglist = epglist

	def __evEventInfoChanged(self):
		if self.is_now_next and len(self.dlg_stack) == 1:
			self.getNowNext()
			assert self.eventView
			if self.epglist:
				self.eventView.setEvent(self.epglist[0])

	def openEventView(self):
		ref = self.session.nav.getCurrentlyPlayingServiceReference()
		self.getNowNext()
		epglist = self.epglist
		if not epglist:
			self.is_now_next = False
			epg = eEPGCache.getInstance()
			ptr = ref and ref.valid() and epg.lookupEventTime(ref, -1)
			if ptr:
				epglist.append(ptr)
				ptr = epg.lookupEventTime(ref, ptr.getBeginTime(), +1)
				if ptr:
					epglist.append(ptr)
		else:
			self.is_now_next = True
		if epglist:
			self.eventView = self.session.openWithCallback(self.closed, EventViewEPGSelect, self.epglist[0], ServiceReference(ref), self.eventViewCallback, self.openSingleServiceEPG, self.openMultiServiceEPG, self.openSimilarList)
			self.dlg_stack.append(self.eventView)
		else:
			print "no epg for the service avail.. so we show multiepg instead of eventinfo"
			self.openMultiServiceEPG(False)

	def eventViewCallback(self, setEvent, setService, val): #used for now/next displaying
		epglist = self.epglist
		if len(epglist) > 1:
			tmp = epglist[0]
			epglist[0]=epglist[1]
			epglist[1]=tmp
			setEvent(epglist[0])

	def open_selected_EPG_view(self):
		if self.has_gmepg is False:
			list = [(p.name, boundFunction(self.runPlugin, p)) for p in plugins.getPlugins(where = PluginDescriptor.WHERE_EVENTINFO)]
			for x in list:
				if x[0] == _("Graphical Multi EPG"):
					self.has_gmepg = x[1]
		if config.usage.epg_default_view.value == "multiepg":
			self.openMultiServiceEPG()
		elif config.usage.epg_default_view.value == "singleepg":
			self.openSingleServiceEPG()
		elif config.usage.epg_default_view.value == "epgbar":
			self.openEPGBar()
		elif self.has_gmepg and config.usage.epg_default_view.value == "graphicalmultiepg":
			self.has_gmepg()
		else:
			self.openEventView()

class InfoBarRdsDecoder:
	"""provides RDS and Rass support/display"""
	def __init__(self):
		self.rds_display = self.session.instantiateDialog(RdsInfoDisplay)
		self.rds_display.setAnimationMode(0)
		self.rass_interactive = None

		self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
			{
				iPlayableService.evEnd: self.__serviceStopped,
				iPlayableService.evUpdatedRassSlidePic: self.RassSlidePicChanged
			})

		self["RdsActions"] = ActionMap(["InfobarRdsActions"],
		{
			"startRassInteractive": self.startRassInteractive
		},-1)

		self["RdsActions"].setEnabled(False)

		self.onLayoutFinish.append(self.rds_display.show)
		self.rds_display.onRassInteractivePossibilityChanged.append(self.RassInteractivePossibilityChanged)

	def RassInteractivePossibilityChanged(self, state):
		self["RdsActions"].setEnabled(state)

	def RassSlidePicChanged(self):
		if not self.rass_interactive:
			service = self.session.nav.getCurrentService()
			decoder = service and service.rdsDecoder()
			if decoder:
				decoder.showRassSlidePicture()

	def __serviceStopped(self):
		if self.rass_interactive is not None:
			rass_interactive = self.rass_interactive
			self.rass_interactive = None
			rass_interactive.close()

	def startRassInteractive(self):
		self.rds_display.hide()
		self.rass_interactive = self.session.openWithCallback(self.RassInteractiveClosed, RassInteractive)

	def RassInteractiveClosed(self, *val):
		if self.rass_interactive is not None:
			self.rass_interactive = None
			self.RassSlidePicChanged()
		self.rds_display.show()

class InfoBarSeek:
	"""handles actions like seeking, pause"""

	SEEK_STATE_PLAY = (0, 0, 0, ">")
	SEEK_STATE_PAUSE = (1, 0, 0, "||")
	SEEK_STATE_EOF = (1, 0, 0, "END")

	def __init__(self, actionmap = "InfobarSeekActions"):
		self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
			{
				iPlayableService.evSeekableStatusChanged: self.__seekableStatusChanged,
				iPlayableService.evStart: self.__serviceStarted,

				iPlayableService.evEOF: self.__evEOF,
				iPlayableService.evSOF: self.__evSOF,
			})
		self.fast_winding_hint_message_showed = False
		self.is_smartseek = False
		self.smartSeekTimer = eTimer()
		self.smartSeekTimer.callback.append(self.initSmartSeek)
		self.smartSeekTimer_timeout = config.seek.smartseek_timeout.value * 1000
		self.SeekStateTimer = eTimer()
		self.SeekStateTimer.callback.append(self.clearSeekStateText)

		class InfoBarSeekActionMap(HelpableActionMap):
			def __init__(self, screen, *args, **kwargs):
				HelpableActionMap.__init__(self, screen, *args, **kwargs)
				self.screen = screen

			def action(self, contexts, action):
				print "action:", action
				
				if action[:5] == "seek:":
					time = int(action[5:])
					self.screen.doSeekRelative(time * 90000)
					return 1
				elif action[:8] == "seekdef:" and not self.screen.is_smartseek:
					key = int(action[8:])
					time = (-config.seek.selfdefined_13.value, False, config.seek.selfdefined_13.value,
						-config.seek.selfdefined_46.value, False, config.seek.selfdefined_46.value,
						-config.seek.selfdefined_79.value, False, config.seek.selfdefined_79.value)[key-1]
					self.screen.setSeekStateText(time)
					self.screen.doSeekRelative(time * 90000)
					return 1
				elif action[:8] == "seekdef:" and self.screen.is_smartseek:
					key = int(action[8:])
					if key == 7:
						direction = -1
						time = self.screen.getSmartSeekTime(direction)
					elif key == 9:
						direction = 1
						time = self.screen.getSmartSeekTime(direction)
					else:
						time = (-config.seek.selfdefined_13.value, False, config.seek.selfdefined_13.value,
							-config.seek.selfdefined_46.value, False, config.seek.selfdefined_46.value)[key-1]
					self.screen.setSeekStateText(time)
					self.screen.doSeekRelative(time * 90000)
					return 1
				elif action[:10] == "smartseek:":
					key = int(action[10:])
					if key == 8:
						if self.screen.is_smartseek:
							self.screen.initSmartSeek(False, True)
						else:
							self.screen.initSmartSeek(True, True)
						return 1
					return 1
				else:
					return HelpableActionMap.action(self, contexts, action)

		self["SeekActions"] = InfoBarSeekActionMap(self, actionmap,
			{
				"playpauseService": (self.playpauseService, _("continue/pause")),
				"pauseService": (self.pauseService, _("pause")),
				"unPauseService": self.unPauseService,

				"seekFwd": (self.seekFwd, _("skip forward")),
				"seekFwdManual": (self.seekFwdManual, _("skip forward (enter time)")),
				"seekBack": (self.seekBack, _("skip backward")),
				"seekBackManual": (self.seekBackManual, _("skip backward (enter time)"))
			}, prio=-1)
			# give them a little more priority to win over color buttons

		self["SeekActions"].setEnabled(False)

		self.seekstate = self.SEEK_STATE_PLAY
		self.lastseekstate = self.SEEK_STATE_PLAY

		self.onPlayStateChanged = [ ]

		self.lockedBecauseOfSkipping = False

		self.__seekableStatusChanged()

		self.seek_to_eof = int(config.usage.stop_seek_eof.value)

	def initSmartSeek(self, init = False, manual = False):
		self.smartSeekTimer.stop()
		self.smartseek_prev_key = 0
		self.smartseek_time = config.seek.smartseek_time.value
		self.init_direction_change = False
		if init:
			self.is_smartseek = True
			self.smartSeekTimer.start(self.smartSeekTimer_timeout, False)
			if manual:
				time = self.getSmartSeekTime(1)
				self.setSeekStateText(time)
				self.doSeekRelative(time * 90000)
		else:
			self.is_smartseek = False
			if config.seek.smartseek_marker.value:
				if manual:
					diff_time = 0
				else:
					diff_time = self.smartSeekTimer_timeout * 90
				self.smartseek_position = self.cueGetCurrentPosition() - diff_time
				self.setSmartSeekMarker()

	def getSmartSeekTime(self, direction, undo = False):
		if self.init_direction_change == False and ( self.smartseek_prev_key == 0 or self.smartseek_prev_key == direction):
			self.smartseek_time = abs(self.smartseek_time) * direction
		else:
			self.init_direction_change = True
			self.smartseek_time = int(abs(self.smartseek_time) * 100.0 / 200.0) * direction
			if abs(self.smartseek_time) < config.seek.smartseek_min_time.value:
				self.smartseek_time = config.seek.smartseek_min_time.value * direction
		if self.smartseek_prev_key == 0 and config.seek.smartseek_marker.value:
			self.smartseek_position = self.cueGetCurrentPosition()
			self.setSmartSeekMarker()
		self.smartseek_prev_key = direction
		self.smartSeekTimer.stop()
		self.smartSeekTimer.start(self.smartSeekTimer_timeout, False)
		self.is_smartseek_undo = False
		return self.smartseek_time

	def setSmartSeekMarker(self):
		if self.smartseek_position is not None:
			nearest_cutpoint = self.getNearestCutPoint(self.smartseek_position, start = True)
			if nearest_cutpoint is not None:
				self.addMarkSilent((self.smartseek_position, self.CUT_TYPE_MARK))

	def smartSeek_Key_Up_Down(self, direction):
		if not self.is_smartseek:
			self.initSmartSeek(True)
		time = self.getSmartSeekTime(direction)
		self.setSeekStateText(time)
		self.doSeekRelative(time * 90000)

	def undoLastSmartSeek(self):
		if not self.is_smartseek_undo:
			self.is_smartseek_undo = True
			time = - self.smartseek_time
			self.setSeekStateText(time)
			self.doSeekRelative(time * 90000)

	def smartSeek_Key_Down(self):
		self.smartSeek_Key_Up_Down(-1)
		return 1

	def smartSeek_Key_Up(self):
		self.smartSeek_Key_Up_Down(1)
		return 1

	def smartSeekConstant(self, direction):
		if self.is_smartseek:
			self.smartSeekTimer.stop()
			self.smartSeekTimer.start(self.smartSeekTimer_timeout, False)
			self.is_smartseek_undo = False
		time = direction * config.seek.smartseek_constant_time.value
		self.setSeekStateText(time)
		self.doSeekRelative(time * 90000)

	def smartSeek_Key_Left(self):
		self.smartSeekConstant(-1)

	def smartSeek_Key_Right(self):
		self.smartSeekConstant(1)

	def setSeekStateText(self, time):
		if hasattr(self, "pvrStateDialog_is_shown"):
			if not self.pvrStateDialog_is_shown:
				self.pvrStateDialog_is_shown = True
				self.pvrStateDialog.show()
				if not config.usage.show_infobar_on_skip.value:
					self.SeekStateTimer.start(3000, False)
			sign = time < 0 and "-" or "+"
			text = "%s %d s "% (sign ,abs(time))
			self.pvrStateDialog["state"].setText(text)

	def clearSeekStateText(self):
		if hasattr(self, "pvrStateDialog_is_shown"):
			self.SeekStateTimer.stop()
			self.pvrStateDialog_is_shown = False
			self.pvrStateDialog.hide()

	def makeStateForward(self, n):
		return (0, n, 0, ">> %dx" % n)

	def makeStateBackward(self, n):
		return (0, -n, 0, "<< %dx" % n)

	def makeStateSlowMotion(self, n):
		return (0, 0, n, "/%d" % n)

	def isStateForward(self, state):
		return state[1] > 1

	def isStateBackward(self, state):
		return state[1] < 0

	def isStateSlowMotion(self, state):
		return state[1] == 0 and state[2] > 1

	def getHigher(self, n, lst):
		for x in lst:
			if x > n:
				return x
		return False

	def getLower(self, n, lst):
		lst = lst[:]
		lst.reverse()
		for x in lst:
			if x < n:
				return x
		return False

	def showAfterSeek(self):
		if isinstance(self, InfoBarShowHide):
			self.doShow()

	def up(self):
		pass

	def down(self):
		pass

	def getSeek(self):
		service = self.session.nav.getCurrentService()
		if service is None:
			return None

		seek = service.seek()

		if seek is None or not seek.isCurrentlySeekable():
			return None

		return seek

	def isSeekable(self):
		if self.getSeek() is None:
			return False

		if self.__class__.__name__ == "InfoBar": # if we have livestreams in bouquets --> the streams are not seekable and we want to zap the "normal" way
			if not self.timeshift_enabled:   # but timeshift is seekable ! 
				return False
		
		return True

	def __seekableStatusChanged(self):
#		print "seekable status changed!"
		if not self.isSeekable():
			self["SeekActions"].setEnabled(False)
#			print "not seekable, return to play"
			self.setSeekState(self.SEEK_STATE_PLAY)
		else:
			self["SeekActions"].setEnabled(True)
#			print "seekable"

	def __serviceStarted(self):
		self.fast_winding_hint_message_showed = False
		self.seekstate = self.SEEK_STATE_PLAY
		self.__seekableStatusChanged()

	def setSeekState(self, state):
		service = self.session.nav.getCurrentService()

		if service is None:
			return False

		if not self.isSeekable():
			if state not in (self.SEEK_STATE_PLAY, self.SEEK_STATE_PAUSE):
				state = self.SEEK_STATE_PLAY

		pauseable = service.pause()

		if pauseable is None:
			print "not pauseable."
			state = self.SEEK_STATE_PLAY

		self.seekstate = state

		if pauseable is not None:
			if self.seekstate[0]:
				print "resolved to PAUSE"
				pauseable.pause()
			elif self.seekstate[1]:
				print "resolved to FAST FORWARD"
				pauseable.setFastForward(self.seekstate[1])
			elif self.seekstate[2]:
				print "resolved to SLOW MOTION"
				pauseable.setSlowMotion(self.seekstate[2])
			else:
				print "resolved to PLAY"
				pauseable.unpause()

		for c in self.onPlayStateChanged:
			c(self.seekstate)

		self.checkSkipShowHideLock()

		return True

	def playpauseService(self):
		if self.seekstate != self.SEEK_STATE_PLAY:
			self.unPauseService()
		else:
			self.pauseService()

	def pauseService(self):
		if self.seekstate == self.SEEK_STATE_PAUSE:
			if config.seek.on_pause.value == "play":
				self.unPauseService()
			elif config.seek.on_pause.value == "step":
				self.doSeekRelative(1)
			elif config.seek.on_pause.value == "last":
				self.setSeekState(self.lastseekstate)
				self.lastseekstate = self.SEEK_STATE_PLAY
		else:
			if self.seekstate != self.SEEK_STATE_EOF:
				self.lastseekstate = self.seekstate
			self.setSeekState(self.SEEK_STATE_PAUSE);

	def unPauseService(self):
		print "unpause"
		if self.seekstate == self.SEEK_STATE_PLAY:
			return 0
		self.setSeekState(self.SEEK_STATE_PLAY)

	def doSeek(self, pts):
		seekable = self.getSeek()
		if seekable is None:
			return
		seekable.seekTo(pts)

	def doSeekRelative(self, pts):
		seekable = self.getSeek()
		if seekable is None:
			return
		prevstate = self.seekstate

		if self.seekstate == self.SEEK_STATE_EOF:
			if prevstate == self.SEEK_STATE_PAUSE:
				self.setSeekState(self.SEEK_STATE_PAUSE)
			else:
				self.setSeekState(self.SEEK_STATE_PLAY)
				
		if self.seek_to_eof and self.__class__.__name__  != "CutListEditor":
			remaining = self.calcRemainingTime()
			seek_interval = pts / 90
			if remaining < seek_interval:
				len = seekable.getLength()
				play_pos = len[1] - (self.seek_to_eof*1000 * 90)
				self.setSeekState(self.SEEK_STATE_PLAY)
				seekable.seekTo(play_pos)
				self.showAfterSeek()
				return
		
		seekable.seekRelative(pts<0 and -1 or 1, abs(pts))
		if abs(pts) > 100 and config.usage.show_infobar_on_skip.value:
			self.showAfterSeek()

	def seekFwd(self):
		if self.is_smartseek or config.seek.smartseek_remap_skip_fw_rw.value:
			self.smartSeek_Key_Right()
			return

		seek = self.getSeek()
		if seek and not (seek.isCurrentlySeekable() & 2):
			media = 1
		else:
			media = 0
#			if not self.fast_winding_hint_message_showed and (seek.isCurrentlySeekable() & 1):
#				self.session.open(MessageBox, _("No fast winding possible yet.. but you can use the number buttons to skip forward/backward!"), MessageBox.TYPE_INFO, timeout=10)
#				self.fast_winding_hint_message_showed = True
#				return
#			return 0 # trade as unhandled action
		if self.seekstate == self.SEEK_STATE_PLAY:
			self.setSeekState(self.makeStateForward(int(config.seek.enter_forward.value)))
		elif self.seekstate == self.SEEK_STATE_PAUSE and media==0:
			if len(config.seek.speeds_slowmotion.value):
				self.setSeekState(self.makeStateSlowMotion(config.seek.speeds_slowmotion.value[-1]))
			else:
				self.setSeekState(self.makeStateForward(int(config.seek.enter_forward.value)))
		elif self.seekstate == self.SEEK_STATE_EOF:
			pass
		elif self.isStateForward(self.seekstate):
			speed = self.seekstate[1]
			if self.seekstate[2]:
				speed /= self.seekstate[2]
			if media==1 and speed == 8:
				speed = 8
				return 0 # trade as unhandled action
			else:
				speed = self.getHigher(speed, config.seek.speeds_forward.value) or config.seek.speeds_forward.value[-1]
			self.setSeekState(self.makeStateForward(speed))
		elif self.isStateBackward(self.seekstate):
			speed = -self.seekstate[1]
			if self.seekstate[2]:
				speed /= self.seekstate[2]
			speed = self.getLower(speed, config.seek.speeds_backward.value)
			if speed:
				self.setSeekState(self.makeStateBackward(speed))
			else:
				self.setSeekState(self.SEEK_STATE_PLAY)
		elif self.isStateSlowMotion(self.seekstate):
			speed = self.getLower(self.seekstate[2], config.seek.speeds_slowmotion.value) or config.seek.speeds_slowmotion.value[0]
			self.setSeekState(self.makeStateSlowMotion(speed))

	def seekBack(self):
		if self.is_smartseek or config.seek.smartseek_remap_skip_fw_rw.value:
			self.smartSeek_Key_Left()
			return

		seek = self.getSeek()
		if seek and not (seek.isCurrentlySeekable() & 2):
			media = 1
		else:
			media = 0
#			if not self.fast_winding_hint_message_showed and (seek.isCurrentlySeekable() & 1):
#				self.session.open(MessageBox, _("No fast winding possible yet.. but you can use the number buttons to skip forward/backward!"), MessageBox.TYPE_INFO, timeout=10)
#				self.fast_winding_hint_message_showed = True
#				return
#			return 0 # trade as unhandled action
		seekstate = self.seekstate
		if seekstate == self.SEEK_STATE_PLAY and media==0:
			self.setSeekState(self.makeStateBackward(int(config.seek.enter_backward.value)))
		elif seekstate == self.SEEK_STATE_PLAY and media ==1:
			if not self.fast_winding_hint_message_showed:
				self.session.open(MessageBox, _("No rewinding possible yet.. but you can use the number buttons to skip forward/backward!"), MessageBox.TYPE_INFO, timeout=10)
				self.fast_winding_hint_message_showed = True
				return
			return 0 # trade as unhandled action
		elif seekstate == self.SEEK_STATE_EOF:
			self.setSeekState(self.makeStateBackward(int(config.seek.enter_backward.value)))
			self.doSeekRelative(-6)
		elif seekstate == self.SEEK_STATE_PAUSE and media==0:
			self.doSeekRelative(-1)
		elif self.isStateForward(seekstate):
			speed = seekstate[1]
			if seekstate[2]:
				speed /= seekstate[2]
			speed = self.getLower(speed, config.seek.speeds_forward.value)
			if speed:
				self.setSeekState(self.makeStateForward(speed))
			else:
				self.setSeekState(self.SEEK_STATE_PLAY)
		elif self.isStateBackward(seekstate):
			speed = -seekstate[1]
			if seekstate[2]:
				speed /= seekstate[2]
			speed = self.getHigher(speed, config.seek.speeds_backward.value) or config.seek.speeds_backward.value[-1]
			self.setSeekState(self.makeStateBackward(speed))
		elif self.isStateSlowMotion(seekstate):
			speed = self.getHigher(seekstate[2], config.seek.speeds_slowmotion.value)
			if speed:
				self.setSeekState(self.makeStateSlowMotion(speed))
			else:
				self.setSeekState(self.SEEK_STATE_PAUSE)

	def seekFwdManual(self):
		self.session.openWithCallback(self.fwdSeekTo, MinuteInput)

	def fwdSeekTo(self, minutes):
		print "Seek", minutes, "minutes forward"
		self.doSeekRelative(minutes * 60 * 90000)

	def seekBackManual(self):
		self.session.openWithCallback(self.rwdSeekTo, MinuteInput)

	def rwdSeekTo(self, minutes):
		print "rwdSeekTo"
		self.doSeekRelative(-minutes * 60 * 90000)

	def checkSkipShowHideLock(self):
		wantlock = self.seekstate != self.SEEK_STATE_PLAY

		if config.usage.show_infobar_on_skip.value:
			if self.lockedBecauseOfSkipping and not wantlock:
				self.unlockShow()
				self.lockedBecauseOfSkipping = False

			if wantlock and not self.lockedBecauseOfSkipping:
				self.lockShow()
				self.lockedBecauseOfSkipping = True

	def calcRemainingTime(self):
		seekable = self.getSeek()
		if seekable is not None:
			len = seekable.getLength()
			try:
				tmp = self.cueGetEndCutPosition()
				if tmp:
					len = [False, tmp]
			except:
				pass
			pos = seekable.getPlayPosition()
			speednom = self.seekstate[1] or 1
			speedden = self.seekstate[2] or 1
			if not len[0] and not pos[0]:
				if len[1] <= pos[1]:
					return 0
				time = (len[1] - pos[1])*speedden/(90*speednom)
				return time
		return False
		
	def __evEOF(self):
		if self.seekstate == self.SEEK_STATE_EOF:
			return

		# if we are seeking forward, we try to end up ~1s before the end, and pause there or seek_to_eof is set we skip back and switch to play mode.
		seekstate = self.seekstate
		if self.seekstate != self.SEEK_STATE_PAUSE:
			if self.seek_to_eof and self.seekstate != self.SEEK_STATE_PLAY:
				seekable = self.getSeek()
				if seekable:
					len = seekable.getLength()
					play_pos = len[1] - (self.seek_to_eof*1000 * 90)
					self.setSeekState(self.SEEK_STATE_PLAY)
					seekable.seekTo(play_pos)
					return
			else:
				self.setSeekState(self.SEEK_STATE_EOF)

		if seekstate not in (self.SEEK_STATE_PLAY, self.SEEK_STATE_PAUSE): # if we are seeking
			seekable = self.getSeek()
			if seekable is not None:
				seekable.seekTo(-1)
		if seekstate == self.SEEK_STATE_PLAY: # regular EOF
			self.doEofInternal(True)
		else:
			self.doEofInternal(False)

	def doEofInternal(self, playing):
		pass		# Defined in subclasses

	def __evSOF(self):
		self.setSeekState(self.SEEK_STATE_PLAY)
		self.doSeek(0)

from Screens.PVRState import PVRState, TimeshiftState

class InfoBarPVRState:
	def __init__(self, screen=PVRState, force_show = False):
		self.onPlayStateChanged.append(self.__playStateChanged)
		self.pvrStateDialog = self.session.instantiateDialog(screen)
		self.pvrStateDialog.setAnimationMode(0)
		self.onShow.append(self._mayShow)
		self.onHide.append(self.hide_pvrStateDialog)
		self.force_show = force_show
		self.pvrStateDialog_is_shown = False

	def _mayShow(self):
		if self.execing and self.seekstate != self.SEEK_STATE_PLAY:
			self.pvrStateDialog_is_shown = True
			self.pvrStateDialog.show()

	def __playStateChanged(self, state):
		playstateString = state[3]
		self.pvrStateDialog["state"].setText(playstateString)
		
		# if we return into "PLAY" state, ensure that the dialog gets hidden if there will be no infobar displayed
		if not config.usage.show_infobar_on_skip.value and self.seekstate == self.SEEK_STATE_PLAY and not self.force_show:
			self.pvrStateDialog_is_shown = False
			self.pvrStateDialog.hide()
		else:
			self._mayShow()

	def hide_pvrStateDialog(self):
		self.pvrStateDialog_is_shown = False
		self.pvrStateDialog.hide()

class InfoBarTimeshiftState(InfoBarPVRState):
	def __init__(self):
		InfoBarPVRState.__init__(self, screen=TimeshiftState, force_show = True)
		self.__hideTimer = eTimer()
		self.__hideTimer.callback.append(self.__hideTimeshiftState)

	def _mayShow(self):
		if self.execing and self.timeshift_enabled:
			if self.ts_auto:
				ts = self.getTimeshift()
				if ts and ts.isTimeshiftActive():
					self.pvrStateDialog.show()
				ts = None
			else:
				self.pvrStateDialog.show()
			if self.seekstate == self.SEEK_STATE_PLAY and not self.shown:
				self.__hideTimer.start(5*1000, True)

	def __hideTimeshiftState(self):
		self.pvrStateDialog.hide()

class InfoBarShowMovies:

	# i don't really like this class.
	# it calls a not further specified "movie list" on up/down/movieList,
	# so this is not more than an action map
	def __init__(self):
		if config.seek.smartseek_enable.value:
			self["MovieListActions"] = HelpableActionMap(self, "InfobarMovieListActions",
				{
					"movieList": (self.showMovies, _("view recordings...")),
					"up": (self.smartSeek_Key_Up, _("SmartSeek: skip forward...")),
					"down": (self.smartSeek_Key_Down, _("SmartSeek: skip backward..."))
				})
		else:
			self["MovieListActions"] = HelpableActionMap(self, "InfobarMovieListActions",
				{
					"movieList": (self.showMovies, _("view recordings...")),
					"up": (self.showMovies, _("view recordings...")),
					"down": (self.showMovies, _("view recordings..."))
				})

# InfoBarTimeshift requires InfoBarSeek, instantiated BEFORE!

# Hrmf.
#
# Timeshift works the following way:
#                                         demux0   demux1                    "TimeshiftActions" "TimeshiftActivateActions" "SeekActions"
# - normal playback                       TUNER    unused      PLAY               enable                disable              disable
# - user presses "yellow" button.         FILE     record      PAUSE              enable                disable              enable
# - user presess pause again              FILE     record      PLAY               enable                disable              enable
# - user fast forwards                    FILE     record      FF                 enable                disable              enable
# - end of timeshift buffer reached       TUNER    record      PLAY               enable                enable               disable
# - user backwards                        FILE     record      BACK  # !!         enable                disable              enable
#

# in other words:
# - when a service is playing, pressing the "timeshiftStart" button ("yellow") enables recording ("enables timeshift"),
# freezes the picture (to indicate timeshift), sets timeshiftMode ("activates timeshift")
# now, the service becomes seekable, so "SeekActions" are enabled, "TimeshiftEnableActions" are disabled.
# - the user can now PVR around
# - if it hits the end, the service goes into live mode ("deactivates timeshift", it's of course still "enabled")
# the service looses it's "seekable" state. It can still be paused, but just to activate timeshift right
# after!
# the seek actions will be disabled, but the timeshiftActivateActions will be enabled
# - if the user rewinds, or press pause, timeshift will be activated again

# note that a timeshift can be enabled ("recording") and
# activated (currently time-shifting).


class InfoBarTimeshift:
	def __init__(self):
		self["TimeshiftActions"] = HelpableActionMap(self, "InfobarTimeshiftActions",
			{
				"timeshiftStart": (self.startTimeshift, _("start timeshift")),  # the "yellow key"
				"timeshiftSeekToBufferEnd": (self.stopAutoTimeShift, _("seek to timeshift end (Live TV)")),
				"timeshiftStop": (self.stopTimeshift, _("stop timeshift"))      # currently undefined :), probably 'TV'
			}, prio=1)
		self["TimeshiftActivateActions"] = ActionMap(["InfobarTimeshiftActivateActions"],
			{
				"timeshiftActivateEnd": self.activateTimeshiftEnd, # something like "rewind key"
				"timeshiftActivateEndAndPause": self.activateTimeshiftEndAndPause  # something like "pause key"
			}, prio=-1) # priority over record

		self.timeshift_enabled = 0
		self.timeshift_state = 0
		self.ts_rewind_timer = eTimer()
		self.ts_rewind_timer.callback.append(self.rewindService)
		self.callback_fnc = None
		self.current_ts_ev_begin_time = 0
		self.ts_auto = False
		self.ts_auto_timer = eTimer()
		self.ts_auto_timer.callback.append(self.startAutoTimeshift)
		self.ts_auto_clean_timer = eTimer()
		self.ts_auto_clean_timer.callback.append(self.cleanUpTSFiles)
		self.ts_clean_intervall = int(config.usage.ts_clean_intervall.value)*3600
		self.switch_to_live = True
		self.fallback_event = None
		self.ts_begin_time = 0
		self.ts_files = {}
		self.cur_ts_playback_idx = -1
		self.old_ts_files_loaded = False
		if self.ts_clean_intervall:
			self.ts_auto_clean_timer.startLongTimer(180)
		self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
			{
				iPlayableService.evStart: self.__serviceStarted,
				iPlayableService.evSeekableStatusChanged: self.__seekableStatusChanged,
				iPlayableService.evUpdatedEventInfo: self.__eventInfoChangedforTS,
				iPlayableService.evUser + 1: self.applyNewPlaybackFile,
				iPlayableService.evUser + 40: self.verify_playback_idx,
				iPlayableService.evUser + 41: self.setNextFile,
			})

	def getTimeshift(self):
		service = self.session.nav.getCurrentService()
		return service and service.timeshift()

	def startTimeshift(self):
		print "enable timeshift"
		ts = self.getTimeshift()
		if ts is None:
			self.session.open(MessageBox, _("Timeshift not possible!"), MessageBox.TYPE_ERROR)
			print "no ts interface"
			return 0

		if self.timeshift_enabled:
			print "hu, timeshift already enabled?"
		else:
			if not ts.startTimeshift():
				self.timeshift_enabled = 1

				# we remove the "relative time" for now.
				#self.pvrStateDialog["timeshift"].setRelative(time.time())

				# PAUSE.
				#self.setSeekState(self.SEEK_STATE_PAUSE)
				self.activateTimeshiftEnd(False)

				# enable the "TimeshiftEnableActions", which will override
				# the startTimeshift actions
				self.__seekableStatusChanged()
				self.ts_begin_time = int(time())
				if not self.old_ts_files_loaded:
					self.load_old_ts_files()
			else:
				print "timeshift failed"

	def startAutoTimeshift(self):
		if Screens.Standby.inStandby or Screens.Standby.inTryQuitMainloop:
			print "[AutoTimeShift] do not start --> we are in standby or in TryQuitMainLoop"
			return 0
		self.ts_auto = False
		print "[AutoTimeShift] start timeshift"
		ts = self.getTimeshift()
		if ts is None:
			print "[AutoTimeShift] no ts interface"
			return 0
		else:
			if not ts.startTimeshift():
				self.timeshift_enabled = 1
				self.__seekableStatusChanged()
				self.ts_auto = True
				self.ts_begin_time = int(time())
				self.setFallBackEvent()
				if not self.old_ts_files_loaded:
					self.load_old_ts_files()
			else:
				print "[AutoTimeShift] starting timeshift failed"

	def stopAutoTimeShift(self):
		if self.timeshift_enabled:
			ts = self.getTimeshift()
			if ts is not None:
				ts.seektoTimehshiftBufferEnd()
				self.pvrStateDialog.hide()
				self.cur_ts_playback_idx = -1

	def stopTimeshift_wrapper(self, callback_fnc = None):
		self.callback_fnc = callback_fnc
		self.stopTimeshift()

	def stopTimeshift(self):
		if self.callback_fnc is None:
			callback_fnc = self.stopTimeshiftConfirmed
		else:
			callback_fnc = self.callback_fnc
		self.callback_fnc = None
		if not self.timeshift_enabled:
			return 0
		ts = self.getTimeshift()
		if ts is None:
			return 0
		choicebox_list = [(_("Stop Timeshift (deleting TS file)"), "stop_ts"), \
				(_("Stop Timeshift (keeping TS file)"), "keep_ts"), \
				(_("Continue Timeshift"), "continue_ts"), \
				(_("Transform Timeshift into recording"), "transform_to_rec")]
		
		self.session.openWithCallback(callback_fnc, ChoiceBox, \
				title=_("Stop Timeshift ?"), \
				list = choicebox_list,  timeout = 30, timeout_selection = 0)

	def switchTimeshiftToRecording(self):
		ts = self.getTimeshift()
		if ts is None:
			return
		serviceref = self.session.nav.getCurrentlyPlayingServiceReference()
		service = self.session.nav.getCurrentService()
		
		event = None
		epg = eEPGCache.getInstance()
		event = epg.lookupEventTime(serviceref, -1, 0)
		if event is None:
			info = service.info()
			event = info.getEvent(0)
	
		if self.ts_begin_time:
			begin = self.ts_begin_time
		else:
			begin = int(time())
		if event is not None:
			curEvent = parseEvent(event)
			name = curEvent[2]
			description = curEvent[3]
			eventid = curEvent[4]
			end = curEvent[1]
		else:
			end = begin + 3600	# dummy
			name = "instant record from timeshift"
			description = "Transformed timeshift recording"
			eventid = None
			self.session.open(MessageBox, _("No event info found, recording indefinitely."), MessageBox.TYPE_INFO)

		if isinstance(serviceref, eServiceReference):
			serviceref = ServiceReference(serviceref)
		recording = RecordTimerEntry(serviceref, begin, end, name, description, eventid, dirname = config.usage.timeshift_path.value, is_transformed_timeshift = True)
		recording.dontSave = True
		if event is None:
			recording.autoincrease = True
			recording.setAutoincreaseEnd()
		recording.calculateFilename()
		if not hasattr(recording, "Filename"):
			return
		filename = recording.Filename + ".ts"
		ts.setTimeshiftFiletoSave(filename)
		ts.stopTimeshift(True, False)
		self.timeshift_enabled = 0
		self.ts_auto = False
		self.__seekableStatusChanged()

		simulTimerList = self.session.nav.RecordTimer.record(recording)
		if simulTimerList is None:
			if not hasattr(InfoBarInstantRecord, "recording"):
				InfoBarInstantRecord.recording = []
			InfoBarInstantRecord.recording.append(recording)
		else:
			if len(simulTimerList) > 1: # with other recording
				name = simulTimerList[1].name
				name_date = ' '.join((name, strftime('%c', localtime(simulTimerList[1].begin))))
				print "[TIMER] conflicts with", name_date
				recording.autoincrease = True	# start with max available length, then increment
				if recording.setAutoincreaseEnd():
					self.session.nav.RecordTimer.record(recording)
					InfoBarInstantRecord.recording.append(recording)
					self.session.open(MessageBox, _("Record time limited due to conflicting timer %s") % name_date, MessageBox.TYPE_INFO)
				else:
					self.session.open(MessageBox, _("Couldn't record due to conflicting timer %s") % name, MessageBox.TYPE_INFO)
			else:
				self.session.open(MessageBox, _("Couldn't record due to invalid service %s") % serviceref, MessageBox.TYPE_INFO)
			recording.autoincrease = False

	def getPossibleTSFiles(self):
		choice_list = []
		cur_ref = self.session.nav.getCurrentlyPlayingServiceReference().toString()
		if cur_ref in self.ts_files and len(self.ts_files[cur_ref]):
			i = 0
			serviceHandler = eServiceCenter.getInstance()
			for x in self.ts_files[cur_ref]:
				if x.endswith(".ts"):
					info_ref = eServiceReference("1:0:0:0:0:0:0:0:0:0:" + x)
					service = ServiceReference(info_ref)
					info = service and service.info()
					ptr = info and info.getEvent(info_ref)
					time_str = ""
					if ptr:
						begin_t = ptr.getBeginTime()
						duration = ptr.getDuration()
						end_t = localtime(begin_t + duration)
						begin_t = localtime(begin_t)
						day_today = localtime()
						day_str = ""
						if day_today.tm_mday != begin_t.tm_mday:
							day_str = "%02d.%02d " % (begin_t.tm_mday, begin_t.tm_mon)
						begin = "%02d:%02d" % (begin_t.tm_hour, begin_t.tm_min)
						end = "%02d:%02d" % (end_t.tm_hour, end_t.tm_min)
						time_str = day_str + begin + "-" + end + " "
					dur_str = ""
					static_info = serviceHandler.info(info_ref)
					dur = static_info.getLength(info_ref)
					if dur > 0:
						if dur < 60:
							dur_str = "(" + str(dur) + " sec) "
						else:
							dur_str = "(" + str(dur / 60) + " min) "
					title = time_str + dur_str + service.getServiceName()
					base_file = x[:-2]
					choice_list.append((title, (base_file,i)))
				i += 1
			if len(choice_list):
				choice_list.reverse()
		return choice_list

	def chooseTimeshiftFile(self):
		tmp_list = self.getPossibleTSFiles()
		if not len(tmp_list):
			return
		choice_list = []
		ts = self.getTimeshift()
		if ts:
			if ts.isTimeshiftActive():
				choice_list.append((_("Live TV"), ("live_tv",-2)))
			if self.timeshift_enabled:
				ts_file = ts.getCurrentTSFile()
				serviceHandler = eServiceCenter.getInstance()
				info_ref = eServiceReference("1:0:0:0:0:0:0:0:0:0:" + ts_file)
				dur_str = ""
				static_info = serviceHandler.info(info_ref)
				dur = static_info.getLength(info_ref)
				if dur > 0:
					if dur < 60:
						dur_str = "(" + str(dur) + " sec) "
					else:
						dur_str = "(" + str(dur / 60) + " min) "
				begin_str = ""
				if self.ts_begin_time:
					begin_t = localtime(self.ts_begin_time)
					end = "??:??"
					if dur > 0:
						end_t = localtime(self.ts_begin_time + dur)
						end = "%02d:%02d" % (end_t.tm_hour, end_t.tm_min)
					begin_str = "%02d:%02d-%s " % (begin_t.tm_hour, begin_t.tm_min, end)
				choice_list.append((begin_str + dur_str + _("Current timeshift"), (ts_file,-1)))
		choice_list.extend(tmp_list)
		sel_idx = 0
		if ts.isTimeshiftActive() and self.cur_ts_playback_idx == -1:
			sel_idx = 1
		elif ts.isTimeshiftActive() and self.cur_ts_playback_idx > -1:
			sel_idx = len(choice_list) - 1 - self.cur_ts_playback_idx
		if not (sel_idx >= 0 and sel_idx < len(choice_list)):
			sel_idx = 0
		self.session.openWithCallback(self.got_ts_file_for_playing, ChoiceBox, title = _("Please select timeshift file"), list= choice_list, selection = sel_idx)

	def got_ts_file_for_playing(self, ret):
		if ret:
			ts = self.getTimeshift()
			if ts is None:
				return
			ts_idx = int(ret[1][1])
			if ts_idx == -1:
				ts_file = ret[1][0]
			elif ts_idx == -2:
				self.stopAutoTimeShift()
				return
			else:
				ts_file = ret[1][0] + "ts"
			if not os_path.exists(ts_file):
				return
			self.cur_ts_playback_idx = ts_idx
			ts.setNextPlaybackFile(ts_file)
			self.updateTSServiceEvent(ts_file)
			ts.playNextTimeshiftFile()

	def transform_old_ts_to_record(self):
		choice_list = self.getPossibleTSFiles()
		if len(choice_list):
			self.session.openWithCallback(self.got_ts_file_for_transforming, ChoiceBox, title = _("Please select timeshift file"), list= choice_list)

	def got_ts_file_for_transforming(self, ret):
		if ret:
			exts = ("ts", "ts.sc", "eit", "ts.meta")
			old_file = ret[1][0]
			if old_file.find("/timeshift_") > -1:
				new_file = old_file.replace("/timeshift_", "/")
			else:
				new_file = old_file.replace("/TIMESHIFT_", "/")
			for ext in exts:
				try:
					os_rename(old_file + ext, new_file + ext)
				except OSError:
					pass
			cur_ref = self.session.nav.getCurrentlyPlayingServiceReference().toString()
			if cur_ref in self.ts_files and len(self.ts_files[cur_ref]):
				f = old_file + "ts"
				if f in self.ts_files[cur_ref]:
					self.ts_files[cur_ref].remove(f)

	def calculateTSFilename(self):
		serviceref = self.session.nav.getCurrentlyPlayingServiceReference()
		service = self.session.nav.getCurrentService()

		if isinstance(serviceref, eServiceReference):
			service_ref = ServiceReference(serviceref)
		service_name = service_ref.getServiceName()
		
		if self.ts_begin_time:
			begin_date = strftime("%Y%m%d%H%M%S", localtime(self.ts_begin_time))
		else:
			begin_date = strftime("%Y%m%d%H%M%S", localtime())
		str_prefix = "timeshift_"
		if config.recording.ascii_filenames.value:
			str_prefix = "TIMESHIFT_"
		filename = config.usage.timeshift_path.value + str_prefix + begin_date + "_" + service_name + ".ts"

		event = None
		epg = eEPGCache.getInstance()
		if self.ts_begin_time:
			ev_time = (self.ts_begin_time + int(time())) / 2
		else:
			ev_time = int(time()) - 30
		event = epg.lookupEventTime(serviceref, ev_time, 0)

		if event is None:
			if self.fallback_event:
				event = self.fallback_event
			if not event:
				info = service.info()
				event = info.getEvent(0)

		if event is not None:
			curEvent = parseEvent(event)
			if self.ts_begin_time:
				begin = self.ts_begin_time
			else:
				begin = curEvent[0]
			name = curEvent[2]
			description = curEvent[3]
			eventid = curEvent[4]
			end = curEvent[1]
			recording = RecordTimerEntry(service_ref, begin, end, name, description, eventid, checkOldTimers = False, dirname = config.usage.timeshift_path.value, is_transformed_timeshift = False, is_timeshift = True)
			recording.dontSave = True
			recording.calculateFilename()
			if hasattr(recording, "Filename"):
				filename = recording.Filename + ".ts"
			del recording
		
		return filename

	def stopTimeshiftConfirmed(self, confirmed):
		if not confirmed:
			return

		ts = self.getTimeshift()
		if ts is None:
			return
		if confirmed[1] == "keep_ts":
			cancel_save = False
			min_dur = int(config.usage.ts_min_duration.value) * 60
			if min_dur and self.ts_begin_time:
				cur_dur = int(time()) - self.ts_begin_time
				if min_dur and cur_dur < min_dur:
					cancel_save = True
			if cancel_save == False:
				filename = self.calculateTSFilename()
				ts.setTimeshiftFiletoSave(filename)
				cur_ref = self.session.nav.getCurrentlyPlayingServiceReference().toString()
				n_list = []
				if cur_ref in self.ts_files:
					n_list = self.ts_files[cur_ref]
				n_list.append(filename)
				self.ts_files[cur_ref] = n_list
				if self.cur_ts_playback_idx == -1 and ts.isTimeshiftActive():
					self.cur_ts_playback_idx = len(n_list) - 1
			ts.stopTimeshift(self.switch_to_live, cancel_save)
			self.ts_begin_time = 0
			self.switch_to_live = True
		elif confirmed[1] == "continue_ts":
			return
		elif confirmed[1] == "transform_to_rec":
			self.switchTimeshiftToRecording()
			return
		else:
			ts.stopTimeshift(True, True)
			self.ts_begin_time = 0
		self.timeshift_enabled = 0
		self.ts_auto = False

		# disable actions
		self.__seekableStatusChanged()

	# activates timeshift, and seeks to (almost) the end
	def activateTimeshiftEnd(self, back = True):
		ts = self.getTimeshift()
		print "activateTimeshiftEnd"

		if ts is None:
			return

		if ts.isTimeshiftActive():
			print "!! activate timeshift called - but shouldn't this be a normal pause?"
			self.pauseService()
		else:
			print "play, ..."
			ts.activateTimeshift() # activate timeshift will automatically pause
			self.setSeekState(self.SEEK_STATE_PAUSE)

		if back:
			self.ts_rewind_timer.start(200, 1)

	def rewindService(self):
		self.setSeekState(self.makeStateBackward(int(config.seek.enter_backward.value)))

	# same as activateTimeshiftEnd, but pauses afterwards.
	def activateTimeshiftEndAndPause(self):
		print "activateTimeshiftEndAndPause"
		#state = self.seekstate
		self.activateTimeshiftEnd(False)

	def __seekableStatusChanged(self):
		enabled = False

#		print "self.isSeekable", self.isSeekable()
#		print "self.timeshift_enabled", self.timeshift_enabled

		# when this service is not seekable, but timeshift
		# is enabled, this means we can activate
		# the timeshift
		if not self.isSeekable() and self.timeshift_enabled:
			enabled = True

#		print "timeshift activate:", enabled
		self["TimeshiftActivateActions"].setEnabled(enabled)

	def __serviceStarted(self):
		self.current_ts_ev_begin_time = 0
		self.timeshift_enabled = False
		self.__seekableStatusChanged()
		auto_ts_time = int(config.usage.ts_auto_start.value)
		self.ts_auto_timer.stop()
		self.cur_ts_playback_idx = -1
		if auto_ts_time:
			self.updateTSServiceEvent()
			self.ts_auto_timer.start(auto_ts_time * 1000, True)

	def force_serviceStarted(self):
		self.__serviceStarted()

	def eventInfoChangedforTS(self):
		if self.timeshift_enabled:
			if self.cur_ts_playback_idx == -1:
				self.updateTSServiceEvent()
			ts = self.getTimeshift()
			if ts is not None:
				service = self.session.nav.getCurrentService()
				old_begin_time = self.current_ts_ev_begin_time
				info = service and service.info()
				ptr = info and info.getEvent(0)
				self.current_ts_ev_begin_time = ptr and ptr.getBeginTime() or 0
				if old_begin_time:
						if config.usage.ts_event_change.value == "ask":
							self.session.openWithCallback(self.actionAfterventChanged, ChoiceBox, \
								title=_("Live TV event changed"), \
								list=((_("Continue Timeshift"), "continue"), \
								(_("Save old event and continue timeshift"), "split_and_keep"), \
								(_("Delete old event and continue timeshift"), "split_and_delete"), \
								(_("Save old event and stop timeshift"), "stop_and_keep"), \
								(_("Delete old event and stop timeshift"), "stop_and_delete"),), timeout = 30, timeout_selection = 2)
						elif config.usage.ts_event_change.value != "continue":
							self.actionAfterventChanged((True, config.usage.ts_event_change.value))

	def __eventInfoChangedforTS(self):
		if self.timeshift_enabled:
			if self.cur_ts_playback_idx == -1:
				self.updateTSServiceEvent()
			ts = self.getTimeshift()
			if ts is not None:
				service = self.session.nav.getCurrentService()
				old_begin_time = self.current_ts_ev_begin_time
				info = service and service.info()
				ptr = info and info.getEvent(0)
				self.current_ts_ev_begin_time = ptr and ptr.getBeginTime() or 0
				if old_begin_time:
					time_delta = abs(old_begin_time - self.current_ts_ev_begin_time)
					if time_delta > 110:
						if config.usage.ts_event_change.value == "ask":
							self.session.openWithCallback(self.actionAfterventChanged, ChoiceBox, \
								title=_("Live TV event changed"), \
								list=((_("Continue Timeshift"), "continue"), \
								(_("Save old event and continue timeshift"), "split_and_keep"), \
								(_("Delete old event and continue timeshift"), "split_and_delete"), \
								(_("Save old event and stop timeshift"), "stop_and_keep"), \
								(_("Delete old event and stop timeshift"), "stop_and_delete"),), timeout = 30, timeout_selection = 2)
						elif config.usage.ts_event_change.value != "continue":
							self.actionAfterventChanged((True, config.usage.ts_event_change.value))

	def updateTSServiceEvent(self, ts_file = None):
		if ts_file and ts_file.lower().endswith(".ts"):
			ref = eServiceReference("1:0:0:0:0:0:0:0:0:0:" + ts_file)
		else:
			ref = self.session.nav.getCurrentlyPlayingServiceReference()
		self.pvrStateDialog["TimeShiftService"].newService(ref)

	def applyNewPlaybackFile(self):
		self.pvrStateDialog.show()
		self.doShow()
		next_ts_file = ""
		ts = self.getTimeshift()
		if ts is None:
			return
		info_ref = self.session.nav.getCurrentlyPlayingServiceReference()
		if self.cur_ts_playback_idx >= 0:
			cur_ref = info_ref.toString()
			if cur_ref in self.ts_files:
				max_idx = len(self.ts_files[cur_ref]) - 1
				if self.cur_ts_playback_idx < max_idx:
					idx = self.cur_ts_playback_idx + 1
					next_ts_file = self.ts_files[cur_ref][idx]
				else:
					idx = -1
					next_ts_file = ts.getCurrentTSFile()
				if self.cur_ts_playback_idx <= max_idx:
					cur_ts_file = self.ts_files[cur_ref][self.cur_ts_playback_idx]
				self.cur_ts_playback_idx = idx
		ts.setNextPlaybackFile(next_ts_file)
		self.updateTSServiceEvent(next_ts_file)

	def change_ts_file(self, direction, cur_ref):
		next_ts_file = ""
		l_len = len(self.ts_files[cur_ref])
		ts = self.getTimeshift()
		if ts is None:
			return
		if direction > 0 and self.cur_ts_playback_idx >= 0:
			idx = self.cur_ts_playback_idx + 1
			if idx >= l_len:
				idx = -1
		if direction > 0 and self.cur_ts_playback_idx < 0:
			ts.seektoTimehshiftBufferEnd()
			self.pvrStateDialog.hide()
			self.cur_ts_playback_idx = -1
			return
		elif direction < 0:
			if self.cur_ts_playback_idx == -1:
				idx = l_len - 1
			elif self.cur_ts_playback_idx == 0:
				return
			else:
				idx = self.cur_ts_playback_idx - 1
				if idx < 0:
					idx = -1
		if idx >= 0:
			next_ts_file = self.ts_files[cur_ref][idx]
		elif idx < 0:
			next_ts_file = ts.getCurrentTSFile()
		if not os_path.exists(next_ts_file):
			return
		self.cur_ts_playback_idx = idx
		ts.setNextPlaybackFile(next_ts_file)
		self.updateTSServiceEvent(next_ts_file)
		ts.playNextTimeshiftFile()

	def verify_playback_idx(self):
		self.cur_ts_playback_idx = -1

	def setNextFile(self):
		ts = self.getTimeshift()
		if ts is not None:
			cur_ref = self.session.nav.getCurrentlyPlayingServiceReference().toString()
			if cur_ref in self.ts_files and len(self.ts_files[cur_ref]):
				self.change_ts_file(+1, cur_ref)
			else:
				ts.seektoTimehshiftBufferEnd()
				self.pvrStateDialog.hide()
				self.cur_ts_playback_idx = -1

	def resetTimeshiftState(self, leaveStandby = False):
		self.cur_ts_playback_idx = -1
		self.ts_files = {}
		self.old_ts_files_loaded = False
		if leaveStandby and not self.timeshift_enabled:
			self.force_serviceStarted()

	def stop_ts_for_shutdown(self):
		self.stopTimeshiftConfirmed((True, "keep_ts"))

	def setFallBackEvent(self):
		serviceref = self.session.nav.getCurrentlyPlayingServiceReference()
		service = self.session.nav.getCurrentService()
		event = None
		epg = eEPGCache.getInstance()
		ev_time = int(time()) + 60
		event = epg.lookupEventTime(serviceref, ev_time, 0)
		if event is None:
			info = service.info()
			event = info.getEvent(0)
		self.fallback_event = event

	def actionAfterventChanged(self, ret):
		if not ret:
			return
		if self.timeshift_enabled:
			if ret[1] == "split_and_keep":
				self.switch_to_live = False
				self.stopTimeshiftConfirmed((True, "keep_ts"))
				self.fallback_event = None
				self. startAutoTimeshift()
			elif ret[1] == "split_and_delete":
				self.stopTimeshiftConfirmed((True, "stop_ts"))
				self.fallback_event = None
				self. startAutoTimeshift()
			elif ret[1] == "stop_and_keep":
				self.switch_to_live = False
				self.stopTimeshiftConfirmed((True, "keep_ts"))
			elif ret[1] == "stop_and_delete":
				self.stopTimeshiftConfirmed((True, "stop_ts"))

	def load_old_ts_files(self):
		if not config.usage.ts_show_old_ts.value:
			return
		files_to_delete = []
		tmp_dic = {}
		if os_path.exists(config.usage.timeshift_path.value):
			folder_slash = "" if config.usage.timeshift_path.value[-1:] == "/" else "/"
			tmp_file_list = os_listdir(config.usage.timeshift_path.value)
			sorted_list = []
			for x in tmp_file_list:
				if x.lower().startswith("timeshift_") and x.endswith(".ts"):
					f = config.usage.timeshift_path.value + folder_slash + x
					t = os_stat(f).st_mtime
					sorted_list.append((t, f))
			sorted_list = sorted(sorted_list, key=lambda var: var[0])
			for ts_file in sorted_list:
				ts_file = ts_file[1]
				meta_f = ts_file + ".meta"
				if os_path.exists(meta_f):
					with open(meta_f, 'r') as f:
						ref = f.readline().rstrip('\n')
					if ref in tmp_dic:
						t = tmp_dic[ref]
						t.append(ts_file) 
						tmp_dic[ref] = t
					else:
						tmp_dic[ref] = [ts_file]
		self.old_ts_files_loaded = True
		self.ts_files.update(tmp_dic)


	def cleanUpTSFiles(self):
		older_than = int(float(config.usage.ts_clean_ts_older_than.value)*24*60*60)
		cur_ts_file = ""
		if self.timeshift_enabled:
			ts = self.getTimeshift()
			if not ts is None:
				cur_ts_file = ts.getCurrentTSFile()
		self.ts_auto_clean_timer.stop()
		files_to_delete = []
		tmp_dic = {}
		if os_path.exists(config.usage.timeshift_path.value):
			folder_slash = "" if config.usage.timeshift_path.value[-1:] == "/" else "/"
			for ts_file in os_listdir(config.usage.timeshift_path.value):
				if ts_file.lower().startswith("timeshift_") and ts_file.endswith(".ts"):
					full_path = config.usage.timeshift_path.value + folder_slash + ts_file
					meta_f = config.usage.timeshift_path.value + folder_slash + ts_file + ".meta"
					if time() - os_stat(full_path).st_mtime > older_than:
						files_to_delete.append(full_path)
						if os_path.exists(meta_f):
							with open(meta_f, 'r') as f:
								ref = f.readline().rstrip('\n')
							if ref in tmp_dic:
								t = tmp_dic[ref]
								t.append(full_path) 
								tmp_dic[ref] = t
							else:
								tmp_dic[ref] = [full_path]
				elif ts_file.startswith("timeshift.") and not ts_file.endswith(".sc"):
					full_path = config.usage.timeshift_path.value + folder_slash + ts_file
					if full_path != cur_ts_file:
						files_to_delete.append(full_path)
		for service in tmp_dic:
			f_per_service = tmp_dic[service]
			if service in self.ts_files:
				l = self.ts_files[service]
				for x in f_per_service:
					if x in l:
						l.remove(x)
				self.ts_files[service] = l
		if len(files_to_delete):
			serviceHandler = eServiceCenter.getInstance()
			for f in files_to_delete:
				service = eServiceReference("1:0:0:0:0:0:0:0:0:0:" + f)
				serviceHandler.offlineOperations(service).deleteFromDisk(0)
		self.ts_auto_clean_timer.startLongTimer(self.ts_clean_intervall)

from Screens.PiPSetup import PiPSetup

class InfoBarExtensions:
	EXTENSION_SINGLE = 0
	EXTENSION_LIST = 1

	def __init__(self):
		self.list = []

		self["InstantExtensionsActions"] = HelpableActionMap(self, "InfobarExtensions",
			{
				"extensions": (self.showExtensionSelection, _("view extensions...")),
				"vtipanel": (self.openVTIPanel, _("open VTi Panel")),
				"vtiinfopanel": (self.openVTiInfoPanel, _("show VTi system informations")),
			}, 1) # lower priority
		for p in plugins.getPlugins(PluginDescriptor.WHERE_EXTENSIONSINGLE):
			p(self)

	def openVTIPanel(self):
		if fileExists("/usr/lib/enigma2/python/Plugins/SystemPlugins/VTIPanel/plugin.pyo"):
			try:
				from Plugins.SystemPlugins.VTIPanel.plugin import VTIMainMenu
				self.session.open(VTIMainMenu)
			except ImportError:
				self.session.open(MessageBox, _("The VTi Panel is not installed!\nPlease install it."), type = MessageBox.TYPE_INFO,timeout = 10 )
		else:
			self.session.open(MessageBox, _("The VTi Panel is not installed!\nPlease install it."), type = MessageBox.TYPE_INFO,timeout = 10 )

	def openVTiInfoPanel(self):
		if fileExists("/usr/lib/enigma2/python/Plugins/SystemPlugins/VTIPanel/InfoPanel.pyo"):
			try:
				from Plugins.SystemPlugins.VTIPanel.InfoPanel import InfoPanel
				self.session.open(InfoPanel, self)
			except ImportError:
				self.session.open(MessageBox, _("The VTi InfoPanel is not installed!\nPlease install it."), type = MessageBox.TYPE_INFO,timeout = 10 )
		else:
			self.session.open(MessageBox, _("The VTI Info Panel is not installed!\nPlease install it."), type = MessageBox.TYPE_INFO,timeout = 10 )
		
	def addExtension(self, extension, key = None, type = EXTENSION_SINGLE):
		self.list.append((type, extension, key))

	def updateExtension(self, extension, key = None):
		self.extensionsList.append(extension)
		if key is not None:
			if self.extensionKeys.has_key(key):
				key = None

		if key is None:
			for x in self.availableKeys:
				if not self.extensionKeys.has_key(x):
					key = x
					break

		if key is not None:
			self.extensionKeys[key] = len(self.extensionsList) - 1

	def updateExtensions(self):
		self.extensionsList = []
		self.availableKeys = [ "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "red", "green", "yellow", "blue" ]
		self.extensionKeys = {}
		for x in self.list:
			if x[0] == self.EXTENSION_SINGLE:
				self.updateExtension(x[1], x[2])
			else:
				for y in x[1]():
					self.updateExtension(y[0], y[1])


	def showExtensionSelection(self):
		self.updateExtensions()
		extensionsList = self.extensionsList[:]
		keys = []
		list = []
		for x in self.availableKeys:
			if self.extensionKeys.has_key(x):
				entry = self.extensionKeys[x]
				extension = self.extensionsList[entry]
				if extension[2]():
					name = str(extension[0]())
					list.append((extension[0](), extension))
					keys.append(x)
					extensionsList.remove(extension)
				else:
					extensionsList.remove(extension)
		list.extend([(x[0](), x) for x in extensionsList])

		keys += [""] * len(extensionsList)
		if config.usage.plugins_sort_mode.value != "default":
			list.sort(key=self.sortByName)
		self.session.openWithCallback(self.extensionCallback, ChoiceBox, title=_("Please choose an extension..."), list = list, keys = keys, skin_name = "ExtensionsList")

	def extensionCallback(self, answer):
		if answer is not None:
			answer[1][1]()

	def sortByName(self, listentry):
		return listentry[0].lower()

from Tools.BoundFunction import boundFunction
import inspect

# depends on InfoBarExtensions

class InfoBarPlugins:
	def __init__(self):
		self.addExtension(extension = self.getPluginList, type = InfoBarExtensions.EXTENSION_LIST)

	def getPluginName(self, name):
		return name

	def getPluginList(self):
		l = []
		for p in plugins.getPlugins(where = PluginDescriptor.WHERE_EXTENSIONSMENU):
		  args = inspect.getargspec(p.__call__)[0]
		  if len(args) == 1 or len(args) == 2 and isinstance(self, InfoBarChannelSelection):
			  l.append(((boundFunction(self.getPluginName, p.name), boundFunction(self.runPlugin, p), lambda: True), None, p.name))
		l.sort(key = lambda e: e[2]) # sort by name
		return l

	def runPlugin(self, plugin):
		if isinstance(self, InfoBarChannelSelection):
			plugin(session = self.session, servicelist = self.servicelist)
		else:
			plugin(session = self.session)

from Components.Task import job_manager
class InfoBarJobman:
	def __init__(self):
		self.addExtension(extension = self.getJobList, type = InfoBarExtensions.EXTENSION_LIST)

	def getJobList(self):
		return [((boundFunction(self.getJobName, job), boundFunction(self.showJobView, job), lambda: True), None) for job in job_manager.getPendingJobs()]

	def getJobName(self, job):
		return "%s: %s (%d%%)" % (job.getStatustext(), job.name, int(100*job.progress/float(job.end)))

	def showJobView(self, job):
		from Screens.TaskView import JobView
		job_manager.in_background = False
		self.session.openWithCallback(self.JobViewCB, JobView, job)
	
	def JobViewCB(self, in_background):
		job_manager.in_background = in_background

# depends on InfoBarExtensions
class InfoBarPiP:
	
	SERVICELIST_MAIN = 0
	SERVICELIST_PIP = 1
	
	def __init__(self):
		try:
			self.session.pipshown
		except:
			self.session.pipshown = False
		self.setPiP_globals()
		if SystemInfo.get("NumVideoDecoders", 1) > 1:
			if (self.allowPiP):
				self.addExtension((self.getShowHideName, self.showPiPScreen, self.addPiPExt), "blue")
				self.addExtension((self.getMoveName, self.movePiP, self.canMove), "green")
				self.addExtension((self.getShowHideNameSplitScreen, self.showSplitScreen, self.splitScreenshown))
				self.addExtension((self.getShowHideNameAudioZap, self.showAudioZap, self.audioZapshown))
				self.addExtension((self.getNameTogglePiPZap, self.toggle_pip_zap, self.togglePiPZapshown))
				if (self.allowPiPSwap):
					self.addExtension((self.getSwapName, self.swapPiP, self.pipShown), "yellow")
				if config.usage.default_pip_mode.value == "splitscreen":
					hlp_txt = _("(de)activate Split Screen...")
					pip_fnc = self.showSplitScreen
				elif config.usage.default_pip_mode.value == "audiozap":
					hlp_txt = _("(de)activate Audio Zap...")
					pip_fnc = self.showAudioZap
				else:
					hlp_txt = _("(de)activate Picture in Picture...")
					pip_fnc = self.showPiP
				self["PiPActions"] = HelpableActionMap(self, "InfobarPiPActions",
				{
					"show_hide_pip": (pip_fnc, hlp_txt),
				})
			else:
				self.addExtension((self.getShowHideName, self.showPiP, self.pipShown), "blue")
				self.addExtension((self.getMoveName, self.movePiP, self.pipShown), "green")

	def setToggleHelpText(self):
		idx = 0
		actions = []
		if self.session.pipshown:
			hlp_txt = self.getNameTogglePiPZap()
		else:
			hlp_txt = _("Play recorded movies...")
		for x in self.helpList:
			if x[1] == "InfobarActions":
				for y in x[2]:
					if y[0] == "showMovies":
						actions.append(("showMovies", hlp_txt))
					else:
						actions.append(y)
				if len(actions):
					break
			idx += 1
		if len(actions) and idx < len(self.helpList):
			self.helpList[idx] = (x[0], x[1], actions)

	def togglePiPZapshown(self):
		if self.session.pipshown:
			return True
		return False

	def audioZapshown(self):
		if self.session.pipshown and not self.session.is_audiozap:
			return False
		return True

	def splitScreenshown(self):
		if self.session.pipshown:
			if  not self.session.is_splitscreen:
				return False
			if self.session.is_audiozap:
				return False
		return True
	
	def addPiPExt(self):
		if self.session.pipshown and self.session.is_splitscreen:
			return False
		return True

	def canMove(self):
		if self.session.is_splitscreen:
			return False
		return self.session.pipshown

	def pipShown(self):
		return self.session.pipshown

	def pipHandles0Action(self):
		return self.pipShown() and config.usage.pip_zero_button.value != "standard"

	def getNameTogglePiPZap(self):
		return _("Toggle zap focus (PiP, Split Screen, Audio Zap)")

	def getShowHideNameAudioZap(self):
		if self.session.is_splitscreen and self.session.is_audiozap:
			return _("Deactivate Audio Zap")
		return _("Activate Audio Zap")

	def getShowHideNameSplitScreen(self):
		if self.session.is_splitscreen:
			return _("Deactivate Split Screen")
		return _("Activate Split Screen")

	def getShowHideName(self):
		if self.session.pipshown:
			return _("Disable Picture in Picture")
		else:
			return _("Activate Picture in Picture")

	def getSwapName(self):
		return _("Swap Services")

	def getMoveName(self):
		return _("Move Picture in Picture")

	def showAudioZap(self):
		self.session.is_audiozap = True
		self.showSplitScreen()

	def showPiPScreen(self):
		self.showPiP()

	def showSplitScreen(self):
		self.session.is_splitscreen = True
		self.showPiP()
		if not self.session.pipshown:
			self.session.is_splitscreen = False

	def toggle_service_list(self):
		if self.slist_type == self.SERVICELIST_MAIN:
			self.slist_type = self.SERVICELIST_PIP
			if self.session.pip.servicePath:
				servicepath = self.session.pip.servicePath
			else:
				servicepath = self.servicelist.getCurrentServicePath()
			self.session.pip.main_servicePath = self.servicelist.getCurrentServicePath()
		else:
			self.slist_type = self.SERVICELIST_MAIN
			if self.session.pip.main_servicePath:
				servicepath = self.session.pip.main_servicePath
			else:
				servicepath = self.servicelist.getCurrentServicePath()
			self.session.pip.servicePath = self.servicelist.getCurrentServicePath()
		zap = False
		self.servicelist.setCurrentServicePath(servicepath, zap)

	def toggle_pip_zap(self):
		if self.session.pipshown:
			if self.session.pip_zap_main:
				self.session.pip_zap_main = False
			else:
				self.session.pip_zap_main = True
			self.show_zap_focus_text()
			self.toggle_service_list()

	def del_hide_timer(self):
		del self.__pip_hide_timer

	def pip_hide_timer_start(self):
		self.__pip_hide_timer = eTimer()
		self.__pip_hide_timer.callback.append(self.session.pip.hideInfo)
		self.__pip_hide_timer.start(3000, True)

	def show_zap_focus_text(self):
		text = _("Zap focus: ")
		if self.session.pip_in_movieplayer:
			text += _("Live TV")
		elif self.session.is_audiozap:
			if self.session.pip_zap_main:
				text += _("Audio")
			else:
				text += _("Video")
		elif self.session.is_splitscreen:
			if self.session.pip_zap_main:
				text += _("Main window")
			else:
				text += _("Second window")
		else:
			if self.session.pip_zap_main:
				text += _("Main window")
			else:
				text += _("Mini TV")
		self.session.zap_focus_text = text
		self.session.pip.set_zap_focus_text()
		self.pip_hide_timer_start()

	def setPiP_globals(self):
		self.session.pipshown = False
		self.session.is_audiozap = False
		self.session.is_splitscreen = False
		self.session.is_pig = False
		self.session.pip_zap_main = True
		self.session.pip_in_movieplayer = False
		self.slist_type = self.SERVICELIST_MAIN

	def showPiG(self):
		self.session.is_pig = True
		self.showPiP()

	def showPiP(self):
		if self.session.pipshown:
			if self.slist_type == self.SERVICELIST_PIP:
				self.toggle_service_list()
			pip_path = self.session.pip.servicePath
			if pip_path:
				pip_ref = pip_path[len(pip_path) - 1]
			else:
				pip_ref = None
			cur_ref = self.session.nav.getCurrentlyPlayingServiceReference()
			servicepath = self.servicelist.getCurrentServicePath()
			if not cur_ref and pip_ref:
				cur_ref = pip_ref
				self.session.nav.playService(cur_ref)
			if cur_ref and pip_ref and cur_ref == pip_ref:
				servicepath = pip_path
			self.del_hide_timer()
			del self.session.pip
			self.setPiP_globals()
			self.setToggleHelpText()
			if servicepath:
				zap = False
				self.servicelist.setCurrentServicePath(servicepath, zap)
			self.exit_locked = True
			self.unlockTimer.start(500, True)
		else:
			if self.session.is_splitscreen:
				self.session.pip = self.session.instantiateDialog(SplitScreen)
			elif self.session.is_pig:
				self.session.pip = self.session.instantiateDialog(PiGDummy)
			else:
				self.session.pip = self.session.instantiateDialog(PictureInPicture)
			self.session.pip.setAnimationMode(0)
			self.session.pip.show()
			newservice = self.session.nav.getCurrentlyPlayingServiceReference()
			if self.session.pip.playService(newservice):
				self.session.pipshown = True
				self.session.pip.servicePath = self.servicelist.getCurrentServicePath()
				if config.usage.zap_pip.value and not self.session.is_splitscreen and not self.session.is_audiozap:
					self.toggle_pip_zap()
				self.setToggleHelpText()
				self.show_zap_focus_text()
			else:
				self.setPiP_globals()
				del self.session.pip
			self.session.nav.playService(newservice)

	def swapPiP(self):
		swapservice = self.session.nav.getCurrentlyPlayingServiceReference()
		if self.session.pip.servicePath:
			pipref=self.session.pip.getCurrentService()
			self.session.pip.playService(swapservice)
			self.session.nav.playService(pipref)
			self.toggle_service_list()

	def movePiP(self):
		if self.session.pipshown and not self.session.is_splitscreen:
			self.session.open(PiPSetup, pip = self.session.pip)

	def execute_zero_doubleclick_action(self):
		use = 	config.usage.default_zero_double_click_mode.value
		if use == "pip":
			self.showPiP()
		elif use == "splitscreen":
			self.showSplitScreen()
		elif use == "audiozap":
			self.showAudioZap()

	def execute_0_pip_action(self, is_double = False):
		if is_double:
			use = config.usage.pip_zero_button_doubleclick.value
		else:
			use = config.usage.pip_zero_button.value
		if "swap" == use:
			self.swapPiP()
		elif "swapstop" == use:
			self.swapPiP()
			self.showPiP()
		elif "stop" == use:
			self.showPiP()
		elif "zap_focus" == use:
			self.toggle_pip_zap()

	def pipDoHandle0Action(self, is_double = False):
		self.execute_0_pip_action(is_double)

from RecordTimer import parseEvent, RecordTimerEntry
from Screens.TimerEntry import TimerEntry
from Screens.TimerEdit import TimerEditList

class InfoBarInstantRecord:
	"""Instant Record - handles the instantRecord action in order to
	start/stop instant records"""
	def __init__(self):
		rec_button_help_string = {
				"record_menu": _("show record menu"),
				"running_record": _("show running records"),
				"timer_list": _("show timer list"),
				"event_record": _("add recording (stop after current event)"),
				"indefinitely_record": _("add recording (indefinitely)"),
				"manualduration_record": _("add recording (enter recording duration)"),
				"manualendtime_record": _("add recording (enter recording endtime)"),
				"timeshift_to_record": _("Transform Timeshift into recording")
			}
		self["InstantRecordActions"] = HelpableActionMap(self, "InfobarInstantRecord",
			{
				"instantRecord": (self.recButton, rec_button_help_string[config.usage.rec_button.value]),
				"showRunningRecords": (self.recButtonLong, rec_button_help_string[config.usage.rec_button_long.value]),
				"stopRunningRecords": (self.stopRunningRecords, _("Stop current records...")),
			})
		self.recording = []
		self.filename = None
	
	def recButton(self, long_press = False):
		rec_button = config.usage.rec_button.value
		if long_press:
			rec_button = config.usage.rec_button_long.value
		if rec_button == "record_menu":
			self.instantRecord()
		elif rec_button == "running_record":
			self.showRunningRecords()
		elif rec_button == "timer_list":
			self.session.open(TimerEditList)
		if self.__class__.__name__ == "InfoBar":
			if rec_button == "indefinitely_record":
				self.startInstantRecording(limitEvent = False)
			elif rec_button == "event_record":
				self.startInstantRecording(limitEvent = True)
			elif rec_button == "manualduration_record":
				self.startInstantRecording(limitEvent = False)
				self.changeDuration(len(self.recording)-1)
			elif rec_button == "manualendtime_record":
				self.startInstantRecording(limitEvent = True)
				self.setEndtime(len(self.recording)-1)
			elif rec_button == "timeshift_to_record":
				ts = self.getTimeshift()
				if self.timeshift_enabled and ts is not None:
					self.switchTimeshiftToRecording()
				else:
					self.startInstantRecording(limitEvent = True)

	def recButtonLong(self):
		self.recButton(True)

	def stopRunningRecords(self):
		# PTS hack !
		try:
			is_PTS_active = config.plugins.pts.enabled.value
		except KeyError:
			is_PTS_active = False
		
		if self.timeshift_enabled:
			ts = self.getTimeshift()
			if is_PTS_active and not self.isSeekable():
				pass
			elif ts and ts.isTimeshiftActive() and self.isSeekable():
				return 0
		if self.isInstantRecordRunning() and len(self.recording) > 0:
			list = self.getRecordList()
			self.session.openWithCallback(self.stopCurrentRecording, TimerSelection, list)

	def showRunningRecords(self):
		show_only_running = True
		self.session.open(TimerEditList, show_only_running)
	
	def modifyTimer(self, entry = -1):
		if entry is not None and entry != -1:
			timer = self.recording[entry]
			self.session.open(TimerEntry, timer)

	def stopCurrentRecording(self, entry = -1):
		if entry is not None and entry != -1:
			timer = self.recording[entry]
			file_ext = timer.record_service.getFilenameExtension()
			if timer.repeated:
				timer.enable()
				timer.processRepeated(findRunningEvent = False)
				self.session.nav.RecordTimer.doActivate(timer)
			else:
				self.session.nav.RecordTimer.removeEntry(self.recording[entry])
			self.recording.remove(self.recording[entry])
			if config.usage.ask_timer_file_del.value and timer:
				self.filename = os_path.realpath(timer.Filename) + file_ext
				if self.filename:
					self.session.openWithCallback(self.delTimerFiles, MessageBox, _("Do you want to delete recording files of stopped timer ?"), MessageBox.TYPE_YESNO, default = False)

	def delTimerFiles(self, result):
		if result:
			service_to_delete = eServiceReference(1, 0, self.filename)
			self.filename = None
			serviceHandler = eServiceCenter.getInstance()
			offline = serviceHandler.offlineOperations(service_to_delete)
			if offline is not None:
				offline.deleteFromDisk(0)

	def startInstantRecording(self, limitEvent = False):
		serviceref = self.session.nav.getCurrentlyPlayingServiceReference()

		# try to get event info
		event = None
		try:
			service = self.session.nav.getCurrentService()
			epg = eEPGCache.getInstance()
			event = epg.lookupEventTime(serviceref, -1, 0)
			if event is None:
				info = service.info()
				ev = info.getEvent(0)
				event = ev
		except:
			pass

		begin = int(time())
		end = begin + 3600	# dummy
		name = "instant record"
		description = ""
		eventid = None

		if event is not None:
			curEvent = parseEvent(event)
			name = curEvent[2]
			description = curEvent[3]
			eventid = curEvent[4]
			if limitEvent:
				end = curEvent[1]
		else:
			if limitEvent:
				self.session.open(MessageBox, _("No event info found, recording indefinitely."), MessageBox.TYPE_INFO)

		if isinstance(serviceref, eServiceReference):
			serviceref = ServiceReference(serviceref)

		recording = RecordTimerEntry(serviceref, begin, end, name, description, eventid, dirname = preferredInstantRecordPath())
		recording.dontSave = True

		if event is None or limitEvent == False:
			recording.autoincrease = True
			recording.setAutoincreaseEnd()

		simulTimerList = self.session.nav.RecordTimer.record(recording)

		if simulTimerList is None:	# no conflict
			self.recording.append(recording)
		else:
			if len(simulTimerList) > 1: # with other recording
				name = simulTimerList[1].name
				name_date = ' '.join((name, strftime('%c', localtime(simulTimerList[1].begin))))
				print "[TIMER] conflicts with", name_date
				recording.autoincrease = True	# start with max available length, then increment
				if recording.setAutoincreaseEnd():
					self.session.nav.RecordTimer.record(recording)
					self.recording.append(recording)
					self.session.open(MessageBox, _("Record time limited due to conflicting timer %s") % name_date, MessageBox.TYPE_INFO)
				else:
					self.session.open(MessageBox, _("Couldn't record due to conflicting timer %s") % name, MessageBox.TYPE_INFO)
			else:
				self.session.open(MessageBox, _("Couldn't record due to invalid service %s") % serviceref, MessageBox.TYPE_INFO)
			recording.autoincrease = False

	def isInstantRecordRunning(self):
		recordings = self.session.nav.getRecordings()
		if recordings:
			for timer in self.session.nav.RecordTimer.timer_list:
				if timer.state == 2:
					if not timer.justplay:
						if not timer in self.recording:
							self.recording.append(timer)
		print "self.recording:", self.recording
		if self.recording:
			for x in self.recording:
				if x.isRunning():
					return True
		return False

	def getRecordList(self):
		list = []
		recording = self.recording[:]
		for x in recording:
			if not x in self.session.nav.RecordTimer.timer_list:
				self.recording.remove(x)
			elif x.isRunning():
				list.append((x, False))
		return list

	def recordQuestionCallback(self, answer):

		if answer is None or answer[1] == "no":
			return
		list = self.getRecordList()
		
		if answer[1] == "changeduration":
			if len(self.recording) == 1:
				self.changeDuration(0)
			else:
				self.session.openWithCallback(self.changeDuration, TimerSelection, list)
		elif answer[1] == "changeendtime":
			if len(self.recording) == 1:
				self.setEndtime(0)
			else:
				self.session.openWithCallback(self.setEndtime, TimerSelection, list)
		elif answer[1] == "stop":
			if len(self.recording) == 1:
				self.stopCurrentRecording(0)
			else:
				self.session.openWithCallback(self.stopCurrentRecording, TimerSelection, list)
		elif answer[1] in ( "indefinitely" , "manualduration", "manualendtime", "event"):
			self.startInstantRecording(limitEvent = answer[1] in ("event", "manualendtime") or False)
			if answer[1] == "manualduration":
				self.changeDuration(len(self.recording)-1)
			elif answer[1] == "manualendtime":
				self.setEndtime(len(self.recording)-1)
		elif answer[1] == "modify_timer":
			if len(self.recording) == 1:
				self.modifyTimer(0)
			else:
				self.session.openWithCallback(self.modifyTimer, TimerSelection, list)
		elif answer[1] == "show_timer_list":
			self.session.open(TimerEditList)
		elif answer[1] == "timeshift_to_record":
			ts = self.getTimeshift()
			if self.timeshift_enabled and ts is not None:
				self.switchTimeshiftToRecording()
			else:
				self.startInstantRecording(limitEvent = True)
		elif answer[1] == "old_timeshift_to_record":
			self.transform_old_ts_to_record()

	def setEndtime(self, entry):
		if entry is not None and entry >= 0:
			self.selectedEntry = entry
			self.endtime=ConfigClock(default = self.recording[self.selectedEntry].end)
			dlg = self.session.openWithCallback(self.TimeDateInputClosed, TimeDateInput, self.endtime)
			dlg.setTitle(_("Please change recording endtime"))

	def TimeDateInputClosed(self, ret):
		if len(ret) > 1:
			if ret[0]:
				localendtime = localtime(ret[1])
				print "stopping recording at", strftime("%c", localendtime)
				if self.recording[self.selectedEntry].end != ret[1]:
					self.recording[self.selectedEntry].autoincrease = False
				self.recording[self.selectedEntry].end = ret[1]
				self.session.nav.RecordTimer.timeChanged(self.recording[self.selectedEntry])

	def changeDuration(self, entry):
		if entry is not None and entry >= 0:
			self.selectedEntry = entry
			self.session.openWithCallback(self.inputCallback, InputBox, title=_("How many minutes do you want to record?"), text="5", maxSize=False, type=Input.NUMBER)

	def inputCallback(self, value):
		if value is not None:
			print "stopping recording after", int(value), "minutes."
			entry = self.recording[self.selectedEntry]
			if int(value) != 0:
				entry.autoincrease = False
			entry.end = int(time()) + 60 * int(value)
			self.session.nav.RecordTimer.timeChanged(entry)

	def instantRecord(self):
		dir = preferredInstantRecordPath()
		if not dir or not fileExists(dir, 'w'):
			dir = defaultMoviePath()

		if not fileExists("/hdd", 0):
			from os import system
			print "not found /hdd"
			system("ln -s /media/hdd /hdd")
#
		try:
			stat = os_stat(dir)
		except:
			# XXX: this message is a little odd as we might be recording to a remote device
			self.session.open(MessageBox, _("No HDD found or HDD not initialized!"), MessageBox.TYPE_ERROR)
			return

		choice_list = []
		if self.__class__.__name__ == "InfoBar":
			ts = self.getTimeshift()
			if self.timeshift_enabled and ts is not None:
				choice_list = [(_("Transform Timeshift into recording"), "timeshift_to_record")]
			if int(config.usage.ts_auto_start.value) and self.getTimeshift():
				cur_ref = self.session.nav.getCurrentlyPlayingServiceReference().toString()
				if cur_ref in self.ts_files and len(self.ts_files[cur_ref]):
					choice_list.append((_("Transform old timeshift event into recording"), "old_timeshift_to_record"))
			if self.isInstantRecordRunning():
				static_list = [ \
					(_("show timer list"), "show_timer_list"), \
					(_("add recording (stop after current event)"), "event"), \
					(_("add recording (indefinitely)"), "indefinitely"), \
					(_("add recording (enter recording duration)"), "manualduration"), \
					(_("add recording (enter recording endtime)"), "manualendtime"), \
					(_("stop recording"), "stop"), \
					(_("change recording (timer editor)"), "modify_timer"), \
					(_("change recording (duration)"), "changeduration"), \
					(_("change recording (endtime)"), "changeendtime"), \
					(_("back"), "no")]
			else:
				static_list = [ \
					(_("show timer list"), "show_timer_list"), \
					(_("add recording (stop after current event)"), "event"), \
					(_("add recording (indefinitely)"), "indefinitely"), \
					(_("add recording (enter recording duration)"), "manualduration"), \
					(_("add recording (enter recording endtime)"), "manualendtime"), \
					(_("back"), "no")]
		else:
			if self.isInstantRecordRunning():
				static_list = [ \
					(_("show timer list"), "show_timer_list"), \
					(_("stop recording"), "stop"), \
					(_("change recording (timer editor)"), "modify_timer"), \
					(_("change recording (duration)"), "changeduration"), \
					(_("change recording (endtime)"), "changeendtime"), \
					(_("back"), "no")]
			else:
				static_list = [ \
					(_("show timer list"), "show_timer_list"), \
					(_("back"), "no")]
		
		choice_list.extend(static_list)
		self.session.openWithCallback(self.recordQuestionCallback, ChoiceBox, title = _("Recording Menu"), list= choice_list)

from Tools.ISO639 import LanguageCodes

class InfoBarAudioSelection:
	def __init__(self):
		self["AudioSelectionAction"] = HelpableActionMap(self, "InfobarAudioSelectionActions",
			{
				"audioSelection": (self.audioSelection, _("Audio Options...")),
			})

	def audioSelection(self):
		from Screens.AudioSelection import AudioSelection
		self.session.openWithCallback(self.audioSelected, AudioSelection, infobar=self)
		
	def audioSelected(self, ret=None):
		print "[infobar::audioSelected]", ret

class InfoBarSubserviceSelection:
	def __init__(self):
		self["SubserviceSelectionAction"] = HelpableActionMap(self, "InfobarSubserviceSelectionActions",
			{
				"subserviceSelection": (self.subserviceSelection, _("Subservice list...")),
			})

		self["SubserviceQuickzapAction"] = HelpableActionMap(self, "InfobarSubserviceQuickzapActions",
			{
				"nextSubservice": (self.nextSubservice, _("Switch to next subservice")),
				"prevSubservice": (self.prevSubservice, _("Switch to previous subservice"))
			}, -1)
		self["SubserviceQuickzapAction"].setEnabled(False)

		self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
			{
				iPlayableService.evUpdatedEventInfo: self.checkSubservicesAvail
			})

		self.bsel = None

	def checkSubservicesAvail(self):
		service = self.session.nav.getCurrentService()
		subservices = service and service.subServices()
		if not subservices or subservices.getNumberOfSubservices() == 0:
			self["SubserviceQuickzapAction"].setEnabled(False)

	def nextSubservice(self):
		self.changeSubservice(+1)

	def prevSubservice(self):
		self.changeSubservice(-1)

	def changeSubservice(self, direction):
		service = self.session.nav.getCurrentService()
		subservices = service and service.subServices()
		n = subservices and subservices.getNumberOfSubservices()
		if n and n > 0:
			selection = -1
			ref = self.session.nav.getCurrentlyPlayingServiceReference()
			idx = 0
			while idx < n:
				if subservices.getSubservice(idx).toString() == ref.toString():
					selection = idx
					break
				idx += 1
			if selection != -1:
				selection += direction
				if selection >= n:
					selection=0
				elif selection < 0:
					selection=n-1
				newservice = subservices.getSubservice(selection)
				if newservice.valid():
					del subservices
					del service
					self.session.nav.playService(newservice, False)

	def subserviceSelection(self):
		service = self.session.nav.getCurrentService()
		subservices = service and service.subServices()
		self.bouquets = self.servicelist.getBouquetList()
		n = subservices and subservices.getNumberOfSubservices()
		selection = 0
		if n and n > 0:
			ref = self.session.nav.getCurrentlyPlayingServiceReference()
			tlist = []
			idx = 0
			while idx < n:
				i = subservices.getSubservice(idx)
				if i.toString() == ref.toString():
					selection = idx
				tlist.append((i.getName(), i))
				idx += 1

			if self.bouquets and len(self.bouquets):
				keys = ["red", "blue", "",  "0", "1", "2", "3", "4", "5", "6", "7", "8", "9" ] + [""] * n
				if config.usage.multibouquet.value:
					tlist = [(_("Quickzap"), "quickzap", service.subServices()), (_("Add to bouquet"), "CALLFUNC", self.addSubserviceToBouquetCallback), ("--", "")] + tlist
				else:
					tlist = [(_("Quickzap"), "quickzap", service.subServices()), (_("Add to favourites"), "CALLFUNC", self.addSubserviceToBouquetCallback), ("--", "")] + tlist
				selection += 3
			else:
				tlist = [(_("Quickzap"), "quickzap", service.subServices()), ("--", "")] + tlist
				keys = ["red", "",  "0", "1", "2", "3", "4", "5", "6", "7", "8", "9" ] + [""] * n
				selection += 2

			self.session.openWithCallback(self.subserviceSelected, ChoiceBox, title=_("Please select a subservice..."), list = tlist, selection = selection, keys = keys, skin_name = "SubserviceSelection")

	def subserviceSelected(self, service):
		del self.bouquets
		if not service is None:
			if isinstance(service[1], str):
				if service[1] == "quickzap":
					from Screens.SubservicesQuickzap import SubservicesQuickzap
					self.session.open(SubservicesQuickzap, service[2])
			else:
				self["SubserviceQuickzapAction"].setEnabled(True)
				self.session.nav.playService(service[1], False)

	def addSubserviceToBouquetCallback(self, service):
		if len(service) > 1 and isinstance(service[1], eServiceReference):
			self.selectedSubservice = service
			if self.bouquets is None:
				cnt = 0
			else:
				cnt = len(self.bouquets)
			if cnt > 1: # show bouquet list
				self.bsel = self.session.openWithCallback(self.bouquetSelClosed, BouquetSelector, self.bouquets, self.addSubserviceToBouquet)
			elif cnt == 1: # add to only one existing bouquet
				self.addSubserviceToBouquet(self.bouquets[0][1])
				self.session.open(MessageBox, _("Service has been added to the favourites."), MessageBox.TYPE_INFO)

	def bouquetSelClosed(self, confirmed):
		self.bsel = None
		del self.selectedSubservice
		if confirmed:
			self.session.open(MessageBox, _("Service has been added to the selected bouquet."), MessageBox.TYPE_INFO)

	def addSubserviceToBouquet(self, dest):
		self.servicelist.addServiceToBouquet(dest, self.selectedSubservice[1])
		if self.bsel:
			self.bsel.close(True)
		else:
			del self.selectedSubservice

from Components.Sources.HbbtvApplication import HbbtvApplication
gHbbtvApplication = HbbtvApplication()
class InfoBarRedButton:
	def __init__(self):
		if SystemInfo["HasHbbTV"] or SystemInfo["HasWebKitHbbTV"]:
			self["RedButtonActions"] = HelpableActionMap(self, "InfobarRedButtonActions",
				{
					"activateRedButton": (self.activateRedButton, _("Red button...")),
				})
			self["HbbtvApplication"] = gHbbtvApplication
		else:
			self["HbbtvApplication"] = Boolean(fixed=0)
			self["HbbtvApplication"].name = "" #is this a hack?
			
		self.onHBBTVActivation = [ ]
		self.onRedButtonActivation = [ ]
		self.onReadyForAIT = [ ]
		self.__et = ServiceEventTracker(screen=self, eventmap=
			{
				iPlayableService.evHBBTVInfo: self.detectedHbbtvApplication,
				iPlayableService.evUpdatedInfo: self.updateInfomation
			})

	def updateAIT(self, orgId=0):
		for x in self.onReadyForAIT:
			try:
				x(orgId)
			except Exception, ErrMsg: 
				print ErrMsg
				#self.onReadyForAIT.remove(x)

	def updateInfomation(self):
		try:
			self["HbbtvApplication"].setApplicationName("")
			self.updateAIT()
		except Exception, ErrMsg:
			pass
		
	def detectedHbbtvApplication(self):
		service = self.session.nav.getCurrentService()
		info = service and service.info()
		try:
			for x in info.getInfoObject(iServiceInformation.sHBBTVUrl):
				print x
				if x[0] in (-1, 1):
					self.updateAIT(x[3])
					self["HbbtvApplication"].setApplicationName(x[1])
					break
		except Exception, ErrMsg:
			pass

	def activateRedButton(self):
		service = self.session.nav.getCurrentService()
		info = service and service.info()
		if info and info.getInfoString(iServiceInformation.sHBBTVUrl) != "":
			for x in self.onHBBTVActivation:
				x()
		elif False: # TODO: other red button services
			for x in self.onRedButtonActivation:
				x()

class InfoBarAdditionalInfo:
	def __init__(self):

		self["RecordingPossible"] = Boolean(fixed=harddiskmanager.HDDCount() > 0)
		self["TimeshiftPossible"] = self["RecordingPossible"]
		self["ShowTimeshiftOnYellow"] = Boolean(fixed=0)
		self["ShowAudioOnYellow"] = Boolean(fixed=1)
		self["ShowRecordOnRed"] = Boolean(fixed=0)
		self["ExtensionsAvailable"] = Boolean(fixed=1)

class InfoBarNotifications:
	def __init__(self):
		self.onExecBegin.append(self.checkNotifications)
		Notifications.notificationAdded.append(self.checkNotificationsIfExecing)
		self.onClose.append(self.__removeNotification)

	def __removeNotification(self):
		Notifications.notificationAdded.remove(self.checkNotificationsIfExecing)

	def checkNotificationsIfExecing(self):
		if self.execing:
			self.checkNotifications()

	def checkNotifications(self):
		notifications = Notifications.notifications
		if notifications:
			n = notifications[0]

			del notifications[0]
			cb = n[0]

			if n[3].has_key("onSessionOpenCallback"):
				n[3]["onSessionOpenCallback"]()
				del n[3]["onSessionOpenCallback"]

			if cb is not None:
				dlg = self.session.openWithCallback(cb, n[1], *n[2], **n[3])
			else:
				dlg = self.session.open(n[1], *n[2], **n[3])

			# remember that this notification is currently active
			d = (n[4], dlg)
			Notifications.current_notifications.append(d)
			dlg.onClose.append(boundFunction(self.__notificationClosed, d))

	def __notificationClosed(self, d):
		Notifications.current_notifications.remove(d)

class InfoBarServiceNotifications:
	def __init__(self):
		self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
			{
				iPlayableService.evEnd: self.serviceHasEnded
			})

	def serviceHasEnded(self):
		print "service end!"

		try:
			self.setSeekState(self.SEEK_STATE_PLAY)
		except:
			pass

class InfoBarCueSheetSupport:
	CUT_TYPE_IN = 0
	CUT_TYPE_OUT = 1
	CUT_TYPE_MARK = 2
	CUT_TYPE_LAST = 3
	CUT_TYPE_LENGTH = 5

	ENABLE_RESUME_SUPPORT = False

	def __init__(self, actionmap = "InfobarCueSheetActions"):
		self["CueSheetActions"] = HelpableActionMap(self, actionmap,
			{
				"jumpPreviousMark": (self.jumpPreviousMark, _("jump to previous marked position")),
				"jumpNextMark": (self.jumpNextMark, _("jump to next marked position")),
				"toggleMark": (self.toggleMark, _("toggle a cut mark at the current position"))
			}, prio=1)

		self.cut_list = [ ]
		self.show_resume_info = True
		self.is_closing = False
		self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
			{
				iPlayableService.evStart: self.__serviceStarted,
			})

	def __serviceStarted(self):
		if self.is_closing:
			return
		print "new service started! trying to download cuts!"
		self.downloadCuesheet()

		if self.ENABLE_RESUME_SUPPORT:
			last = None
			cue_length = None
			resume = True
			length = None

			for (pts, what) in self.cut_list:
				if what == self.CUT_TYPE_LAST:
					last = pts
				elif what == self.CUT_TYPE_LENGTH:
					cue_length = pts

			if last is not None:
				self.resume_point = last
				
				l = last / 90000
				
				if not config.usage.movielist_resume_at_eof.value:
					if cue_length:
						length = cue_length / 90000
					seek = self.getSeek()
					if seek:
						length_list = seek.getLength()
						if not length_list[0] and length_list[1] > 1:
							length = length_list[1] / 90000
					if length and length > 0:
						seen = (l * 100) / length
						if config.usage.movielist_progress_seen.value <= seen:
							resume = False
				if resume and config.usage.on_movie_start.value == "ask":
					Notifications.AddNotificationWithCallback(self.playLastCB, MessageBox, _("Do you want to resume this playback?") + "\n" + (_("Resume position at %s") % ("%d:%02d:%02d" % (l/3600, l%3600/60, l%60))), timeout=10)
				elif resume and config.usage.on_movie_start.value == "resume":
# TRANSLATORS: The string "Resuming playback" flashes for a moment
# TRANSLATORS: at the start of a movie, when the user has selected
# TRANSLATORS: "Resume from last position" as start behavior.
# TRANSLATORS: The purpose is to notify the user that the movie starts
# TRANSLATORS: in the middle somewhere and not from the beginning.
# TRANSLATORS: (Some translators seem to have interpreted it as a
# TRANSLATORS: question or a choice, but it is a statement.)
					if self.show_resume_info:
						Notifications.AddNotificationWithCallback(self.playLastCB, MessageBox, _("Resuming playback"), timeout=2, type=MessageBox.TYPE_INFO)
					else:
						self.doSeek(self.resume_point)

	def playLastCB(self, answer):
		if answer == True:
			self.doSeek(self.resume_point)
		self.hideAfterResume()

	def hideAfterResume(self):
		if isinstance(self, InfoBarShowHide):
			self.hide()

	def __getSeekable(self):
		service = self.session.nav.getCurrentService()
		if service is None:
			return None
		return service.seek()

	def cueGetCurrentPosition(self):
		seek = self.__getSeekable()
		if seek is None:
			return None
		r = seek.getPlayPosition()
		if r[0]:
			return None
		return long(r[1])

	def cueGetEndCutPosition(self):
		ret = False
		isin = True
		for cp in self.cut_list:
			if cp[1] == self.CUT_TYPE_OUT:
				if isin:
					isin = False
					ret = cp[0]
			elif cp[1] == self.CUT_TYPE_IN:
				isin = True
		return ret
		
	def jumpPreviousNextMark(self, cmp, start=False):
		current_pos = self.cueGetCurrentPosition()
		if current_pos is None:
 			return False
		mark = self.getNearestCutPoint(current_pos, cmp=cmp, start=start)
		if mark is not None:
			pts = mark[0]
		else:
			return False

		self.doSeek(pts)
		return True

	def jumpPreviousMark(self):
		# we add 5 seconds, so if the play position is <5s after
		# the mark, the mark before will be used
		self.jumpPreviousNextMark(lambda x: -x-5*90000, start=True)

	def jumpNextMark(self):
		if not self.jumpPreviousNextMark(lambda x: x-90000):
			self.doSeek(-1)

	def getNearestCutPoint(self, pts, cmp=abs, start=False):
		# can be optimized
		beforecut = True
		nearest = None
		bestdiff = -1
		instate = True
		if start:
			bestdiff = cmp(0 - pts)
			if bestdiff >= 0:
				nearest = [0, False]
		for cp in self.cut_list:
			if beforecut and cp[1] in (self.CUT_TYPE_IN, self.CUT_TYPE_OUT):
				beforecut = False
				if cp[1] == self.CUT_TYPE_IN:  # Start is here, disregard previous marks
					diff = cmp(cp[0] - pts)
					if start and diff >= 0:
						nearest = cp
						bestdiff = diff
					else:
						nearest = None
						bestdiff = -1
			if cp[1] == self.CUT_TYPE_IN:
				instate = True
			elif cp[1] == self.CUT_TYPE_OUT:
				instate = False
			elif cp[1] in (self.CUT_TYPE_MARK, self.CUT_TYPE_LAST):
				diff = cmp(cp[0] - pts)
				if instate and diff >= 0 and (nearest is None or bestdiff > diff):
					nearest = cp
					bestdiff = diff
		return nearest

	def toggleMark(self, onlyremove=False, onlyadd=False, tolerance=5*90000, onlyreturn=False):
		current_pos = self.cueGetCurrentPosition()
		if current_pos is None:
			print "not seekable"
			return

		nearest_cutpoint = self.getNearestCutPoint(current_pos)

		if nearest_cutpoint is not None and abs(nearest_cutpoint[0] - current_pos) < tolerance:
			if onlyreturn:
				return nearest_cutpoint
			if not onlyadd:
				self.removeMark(nearest_cutpoint)
		elif not onlyremove and not onlyreturn:
			self.addMark((current_pos, self.CUT_TYPE_MARK))

		if onlyreturn:
			return None

	def addMarkSilent(self, point):
		insort(self.cut_list, point)
		self.uploadCuesheet()

	def addMark(self, point):
		insort(self.cut_list, point)
		self.uploadCuesheet()
		self.showAfterCuesheetOperation()

	def removeMark(self, point):
		self.cut_list.remove(point)
		self.uploadCuesheet()
		self.showAfterCuesheetOperation()

	def showAfterCuesheetOperation(self):
		if isinstance(self, InfoBarShowHide):
			self.doShow()

	def __getCuesheet(self):
		service = self.session.nav.getCurrentService()
		if service is None:
			return None
		return service.cueSheet()

	def uploadCuesheet(self):
		cue = self.__getCuesheet()

		if cue is None:
			print "upload failed, no cuesheet interface"
			return
		cue.setCutList(self.cut_list)

	def downloadCuesheet(self):
		cue = self.__getCuesheet()

		if cue is None:
			print "download failed, no cuesheet interface"
			self.cut_list = [ ]
		else:
			self.cut_list = cue.getCutList()

class InfoBarSummary(Screen):
	skin = """
	<screen position="0,0" size="132,64">
		<widget source="global.CurrentTime" render="Label" position="62,46" size="82,18" font="Regular;16" >
			<convert type="ClockToText">WithSeconds</convert>
		</widget>
		<widget source="session.RecordState" render="FixedLabel" text=" " position="62,46" size="82,18" zPosition="1" >
			<convert type="ConfigEntryTest">config.usage.blinking_display_clock_during_recording,True,CheckSourceBoolean</convert>
			<convert type="ConditionalShowHide">Blink</convert>
		</widget>
		<widget source="session.CurrentService" render="Label" position="6,4" size="120,42" font="Regular;18" >
			<convert type="ServiceName">Name</convert>
		</widget>
		<widget source="session.Event_Now" render="Progress" position="6,46" size="46,18" borderWidth="1" >
			<convert type="EventTime">Progress</convert>
		</widget>
	</screen>"""

# for picon:  (path="piconlcd" will use LCD picons)
#		<widget source="session.CurrentService" render="Picon" position="6,0" size="120,64" path="piconlcd" >
#			<convert type="ServiceName">Reference</convert>
#		</widget>

class InfoBarSummarySupport:
	def __init__(self):
		pass

	def createSummary(self):
		return InfoBarSummary

class InfoBarMoviePlayerSummary(Screen):
	skin = """
	<screen position="0,0" size="132,64">
		<widget source="global.CurrentTime" render="Label" position="62,46" size="64,18" font="Regular;16" halign="right" >
			<convert type="ClockToText">WithSeconds</convert>
		</widget>
		<widget source="session.RecordState" render="FixedLabel" text=" " position="62,46" size="64,18" zPosition="1" >
			<convert type="ConfigEntryTest">config.usage.blinking_display_clock_during_recording,True,CheckSourceBoolean</convert>
			<convert type="ConditionalShowHide">Blink</convert>
		</widget>
		<widget source="session.CurrentService" render="Label" position="6,4" size="120,42" font="Regular;18" >
			<convert type="ServiceName">Name</convert>
		</widget>
		<widget source="session.CurrentService" render="Progress" position="6,46" size="56,18" borderWidth="1" >
			<convert type="ServicePosition">Position</convert>
		</widget>
	</screen>"""

class InfoBarMoviePlayerSummarySupport:
	def __init__(self):
		pass

	def createSummary(self):
		return InfoBarMoviePlayerSummary

class InfoBarTeletextPlugin:
	def __init__(self):
		self.teletext_plugin = None

		for p in plugins.getPlugins(PluginDescriptor.WHERE_TELETEXT):
			self.teletext_plugin = p

		if self.teletext_plugin is not None:
			self["TeletextActions"] = HelpableActionMap(self, "InfobarTeletextActions",
				{
					"startTeletext": (self.startTeletext, _("View teletext..."))
				})
		else:
			print "no teletext plugin found!"

	def startTeletext(self):
		self.teletext_plugin(session=self.session, service=self.session.nav.getCurrentService())

class InfoBarSubtitleSupport(object):
	def __init__(self):
		object.__init__(self)
		self.subtitle_window = self.session.instantiateDialog(SubtitleDisplay)
		self.subtitle_window.setAnimationMode(0)
		self.__subtitles_enabled = False

		self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
			{
				iPlayableService.evEnd: self.__serviceStopped,
				iPlayableService.evUpdatedInfo: self.__updatedInfo
			})
		self.cached_subtitle_checked = False
		self.__selected_subtitle = None

	def __serviceStopped(self):
		self.cached_subtitle_checked = False
		if self.__subtitles_enabled:
			self.subtitle_window.hide()
			self.__subtitles_enabled = False
			self.__selected_subtitle = None

	def __updatedInfo(self):
		if not self.__selected_subtitle:
			subtitle = self.getCurrentServiceSubtitle()
			self.setSelectedSubtitle(subtitle and subtitle.getCachedSubtitle())
			if self.__selected_subtitle:
				self.setSubtitlesEnable(True)

	def getCurrentServiceSubtitle(self):
		service = self.session.nav.getCurrentService()
		return service and service.subtitle()

	def setSubtitlesEnable(self, enable=True):
		subtitle = self.getCurrentServiceSubtitle()
		if enable:
			if self.__selected_subtitle:
				if subtitle and not self.__subtitles_enabled:
					subtitle.enableSubtitles(self.subtitle_window.instance, self.selected_subtitle)
					self.subtitle_window.show()
					self.__subtitles_enabled = True
		else:
			if subtitle:
				subtitle.disableSubtitles(self.subtitle_window.instance)
			self.__selected_subtitle = None
			self.__subtitles_enabled = False
			self.subtitle_window.hide()

	def setSelectedSubtitle(self, subtitle):
		self.__selected_subtitle = subtitle

	subtitles_enabled = property(lambda self: self.__subtitles_enabled, setSubtitlesEnable)
	selected_subtitle = property(lambda self: self.__selected_subtitle, setSelectedSubtitle)

class InfoBarServiceErrorPopupSupport:
	def __init__(self):
		self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
			{
				iPlayableService.evTuneFailed: self.__tuneFailed,
				iPlayableService.evStart: self.__serviceStarted
			})
		self.__serviceStarted()

	def __serviceStarted(self):
		self.last_error = None
		Notifications.RemovePopup(id = "ZapError")

	def __tuneFailed(self):
		service = self.session.nav.getCurrentService()
		info = service and service.info()
		error = info and info.getInfo(iServiceInformation.sDVBState)

		if error == self.last_error:
			error = None
		else:
			self.last_error = error

		error = {
			eDVBServicePMTHandler.eventNoResources: _("No free tuner!"),
			eDVBServicePMTHandler.eventTuneFailed: _("Tune failed!"),
			eDVBServicePMTHandler.eventNoPAT: _("No data on transponder!\n(Timeout reading PAT)"),
			eDVBServicePMTHandler.eventNoPATEntry: _("Service not found!\n(SID not found in PAT)"),
			eDVBServicePMTHandler.eventNoPMT: _("Service invalid!\n(Timeout reading PMT)"),
			eDVBServicePMTHandler.eventNewProgramInfo: None,
			eDVBServicePMTHandler.eventTuned: None,
			eDVBServicePMTHandler.eventSOF: None,
			eDVBServicePMTHandler.eventEOF: None,
			eDVBServicePMTHandler.eventMisconfiguration: _("Service unavailable!\nCheck tuner configuration!"),
		}.get(error) #this returns None when the key not exist in the dict

		if error is not None:
			if not config.usage.disable_tuner_error_popup.value:
				Notifications.AddPopup(text = error, type = MessageBox.TYPE_ERROR, timeout = 5, id = "ZapError")
		else:
			Notifications.RemovePopup(id = "ZapError")
