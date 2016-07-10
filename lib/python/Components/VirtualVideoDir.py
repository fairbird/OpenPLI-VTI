# -*- coding: utf-8 -*-

import os
import time
import struct
from Components.config import config
from enigma import eServiceReference, eServiceCenter, iServiceInformation

VDIR_INFO_FILE = ".vdirinfo"
LOCAL_LIST_FILE = "/tmp/.video_list"

def readFile(filename):
	content = []
	if os.path.exists(filename):
		f = open(filename, "r")
		content = f.readlines()
		f.close()
	return content

def writeFile(filename, content):
	f_access = False
	try:
		f = open(filename, "wb+")
		f_access = True
	except IOError:
		pass
	if f_access:
		f.write(content)
		f.close()
	return f_access

def getInfoFile():
	if config.usage.vdir_info_path.value == "<default>":
		ret = config.usage.default_path.value
	else:
		ret = config.usage.vdir_info_path.value
	if ret.endswith("/"):
		ret += VDIR_INFO_FILE
	else:
		ret += "/" + VDIR_INFO_FILE
	return ret

class VirtualVideoDir:

	NEWEST_VIDEOS = 1
	VIDEO_HOME = 2
	LOCAL_LIST = 3

	def __init__(self):
		self.infofile = getInfoFile()
		self.f_locked = 0
		self.updateTime()

	def setInfoFile(self, info_file = LOCAL_LIST_FILE):
		self.infofile = info_file

	def deleteInfoFile(self, info_file = LOCAL_LIST_FILE):
		try:
			os.remove(info_file)
		except OSError, IOError:
			pass

	def updateTime(self):
		self.max_time = int(time.time()) - config.usage.days_mark_as_new.value * 86400

	def getMovieTimeDiff(self, ref):
		serviceHandler = eServiceCenter.getInstance()
		info = serviceHandler.info(ref)
		if info is None:
			time = 0
		else:
			time = info.getInfo(ref, iServiceInformation.sTimeCreate)
		time = time - self.max_time
		return time

	def isUnseen(self, moviename):
		ret = True
		moviename = moviename +  ".cuts"
		if os.path.exists(moviename):
			f = open(moviename, "rb")
			packed = f.read()
			f.close()
			while len(packed) > 0:
				packedCue = packed[:12]
				packed = packed[12:]
				cue = struct.unpack('>QI', packedCue)
				if cue[1] == 3:
					ret = False
					break
		return ret

	def getServiceRef(self, movie):
		if movie.endswith("ts"):
			return eServiceReference("1:0:0:0:0:0:0:0:0:0:" + movie)
		else:
			return eServiceReference("4097:0:0:0:0:0:0:0:0:0:" + movie)

	def getServiceRefDir(self, folder):
		return eServiceReference(eServiceReference.idFile, eServiceReference.flagDirectory, folder)

	def getVList(self, list_type = VIDEO_HOME): #NEWEST_VIDEOS):
		vlist = []
		
		if list_type in (self.NEWEST_VIDEOS, self.LOCAL_LIST):
			self.updateTime()
			if not os.path.exists(self.infofile):
				return vlist
			tmp_list = readFile(self.infofile)
			for line in tmp_list:
				movie = line.rstrip('\n')
				if os.path.exists(movie):
					ref = self.getServiceRef(movie)
					if list_type == self.LOCAL_LIST:
						vlist.append(ref)
					elif self.getMovieTimeDiff(ref) >= 0:
						if not config.usage.only_unseen_mark_as_new.value:
							vlist.append(ref)
						elif config.usage.only_unseen_mark_as_new.value and self.isUnseen(movie):
							vlist.append(ref)
		elif list_type == self.VIDEO_HOME:
			for video_dir in config.movielist.videodirs.value:
				if os.path.exists(video_dir):
					if not video_dir.endswith('/'):
						video_dir = video_dir + '/'
					ref = self.getServiceRefDir(video_dir)
					vlist.append(ref)
		return vlist

	def writeVList(self, append = "", overwrite = False):
		self.updateTime()
		txt = ""
		if not overwrite:
			tmp_list = readFile(self.infofile)
			for x in tmp_list:
				movie = x.rstrip("\n")
				if os.path.exists(movie):
					ref = self.getServiceRef(movie)
					if self.getMovieTimeDiff(ref) >= 0:
						if not config.usage.only_unseen_mark_as_new.value:
							txt += x
						elif config.usage.only_unseen_mark_as_new.value and self.isUnseen(movie):
							txt += x
		if isinstance(append, list):
			for t in append:
				txt += t + "\n"
		elif append != "":
			txt += append + "\n"
		if not writeFile(self.infofile, txt):
			if self.f_locked < 11:
				time.sleep(.300)
				self.f_locked += 1
				self.writeVList(append = append)
			else:
				self.f_locked = 0
