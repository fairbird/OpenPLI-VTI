from Screens.Screen import Screen
from enigma import eServiceCenter, getBestPlayableServiceReference, eServiceReference, iPlayableService, getDesktop
from Components.VideoWindow import VideoWindow
from Components.Sources.ServiceEvent import ServiceEvent
from Components.Label import Label
from Components.config import config

class SplitScreen(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		sz_w = getDesktop(0).size().width()
		if sz_w == 1280:
			sz_h = 720
			if self.session.is_audiozap:
				self.skinName = ["AudioZap", "SplitScreen"]
		elif sz_w == 1920:
			sz_h = 1080
			if self.session.is_audiozap:
				self.skinName = ["AudioZap", "SplitScreen"]
		else:
			self.skinName = ["SplitScreenSD"]
			if self.session.is_audiozap:
				self.skinName = ["AudioZapSD", "SplitScreenSD"]
			sz_w = 720
			sz_h = 576
		self.fb_w = sz_w
		self.fb_h = sz_h
		self.fb_w_2 = sz_w
		self.fb_h_2 = sz_h
		self.need_fb_workaround = False
		if config.av.videomode[config.av.videoport.value].value == "2160p":
			self.need_fb_workaround = True
			self.init_done = False
			self.fb_w_2 = 360
			self.fb_h_2 = 288
		self["video1"] = VideoWindow(decoder = 0, fb_width = sz_w, fb_height = sz_h)
		self["video2"] = VideoWindow(decoder = 1, fb_width = self.fb_w_2, fb_height = self.fb_h_2)
		self["MasterService"] = ServiceEvent()
		self["SlaveService"] = ServiceEvent()
		self["zap_focus"] = Label()
		self.session = session
		self.currentService = None
		self.onLayoutFinish.append(self.LayoutFinished)
		self.pipservice = False

	def get_FB_Size(self, video):
		for attr_tuple in self[video].skinAttributes:
			if attr_tuple[0] == "position":
				x = attr_tuple[1].split(',')[0]
				y = attr_tuple[1].split(',')[1]
			elif attr_tuple[0] == "size":
				w = attr_tuple[1].split(',')[0]
				h = attr_tuple[1].split(',')[1]
		x = format(int(float(x) / self.fb_w * 720.0), 'x').zfill(8)
		y = format(int(float(y) / self.fb_h * 576.0), 'x').zfill(8)
		w = format(int(float(w) / self.fb_w * 720.0), 'x').zfill(8)
		h = format(int(float(h) / self.fb_h * 576.0), 'x').zfill(8)
		return [w, h, x, y]
		

	def LayoutFinished(self):
		self.prev_fb_info = self.get_FB_Size(video = "video1") 
		self.prev_fb_info_second_dec = self.get_FB_Size(video = "video2")
		self.onLayoutFinish.remove(self.LayoutFinished)
		self["video1"].instance.setOverscan(False)
		self["video2"].instance.setOverscan(False)
		self.updateServiceInfo()

	def updateServiceInfo(self):
		master_service = self.session.nav.getCurrentlyPlayingServiceReference()
		self["MasterService"].newService(master_service)

	def playService(self, service):
		if service and (service.flags & eServiceReference.isGroup):
			ref = getBestPlayableServiceReference(service, eServiceReference())
		else:
			ref = service
		if ref:
			self.pipservice = eServiceCenter.getInstance().play(ref)
			if self.pipservice and not self.pipservice.setTarget(1):
				self.pipservice.start()
				self.currentService = service
				self["SlaveService"].newService(service)
				self.fb_size_video = []
				if self.need_fb_workaround:
					self.resetFBsize()
				return True
			else:
				self.pipservice = None
		return False

	def initFBresizing(self):
		from Tools.FBHelperTool import FBHelperTool
		self.fbtool = FBHelperTool()
		w, h, x, y = ["00000000", "00000000", "00000000", "00000000"]
		cor_factor = 1.0
		if self.fb_w == 1920:
			cor_factor = 1.5
		for attr_tuple in self["video2"].skinAttributes:
			if attr_tuple[0] == "position":
				x = format(int(float(attr_tuple[1].split(',')[0]) * 1.125 / cor_factor), 'x').zfill(8)
				y = format(int(float(attr_tuple[1].split(',')[1]) * 1.6 / cor_factor), 'x').zfill(8)
			elif attr_tuple[0] == "size":
				w = format(int(float(attr_tuple[1].split(',')[0]) * 1.125 / cor_factor), 'x').zfill(8)
				h = format(int(float(attr_tuple[1].split(',')[1]) * 1.6 / cor_factor), 'x').zfill(8)
		self.fb_size_video = [w, h, x, y]
		self.init_done = True

	def resetFBsize(self):
		if not self.init_done:
			self.initFBresizing()
		self.fbtool.setFBSize(fb_size_pos = self.fb_size_video, decoder = 1, force = True)
		self.prev_fb_info_second_dec = self.fb_size_video

	def stopService(self):
		if self.pipservice and self.pipservice is not None:
			self.pipservice.stop()

	def getCurrentService(self):
		return self.currentService

	def hideInfo(self):
		self["zap_focus"].hide()

	def showInfo(self):
		self["zap_focus"].show()

	def set_zap_focus_text(self):
		self["zap_focus"].setText(self.session.zap_focus_text)
		self.showInfo()
