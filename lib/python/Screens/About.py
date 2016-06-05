from Screen import Screen
from Components.ActionMap import ActionMap
from Components.Sources.StaticText import StaticText
from Components.Harddisk import harddiskmanager
from Components.NimManager import nimmanager
from Components.About import about
from Components.ScrollLabel import ScrollLabel
from Components.Network import iNetwork

from Tools.DreamboxHardware import getFPVersion

def parse_ipv4(ip):
	ret = ""
	idx = 0
	if ip is not None:
		for x in ip:
			if idx == 0:
				ret += str(x)
			else:
				ret += "." + str(x)
			idx += 1
	return ret

def parseFile(filename):
	ret = "N/A"
	try:
		f = open(filename, "rb")
		ret = f.read().strip()
		f.close()
	except IOError:
		print "[ERROR] failed to open file %s" % filename
	return ret

def parseLines(filename):
	ret = ["N/A"]
	try:
		f = open(filename, "rb")
		ret = f.readlines()
		f.close()
	except IOError:
		print "[ERROR] failed to open file %s" % filename
	return ret

class About(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)

		self["EnigmaVersion"] = StaticText(_("Version") + ": " + about.getEnigmaVersionString())
		self["ImageVersion"] = StaticText(_("Image") + ": " + about.getImageVersionString())

		self["TunerHeader"] = StaticText(_("Detected NIMs:"))

		fp_version = getFPVersion()
		if fp_version is None:
			fp_version = ""
		else:
			fp_version = _("Frontprocessor version: %d") % fp_version

		self["FPVersion"] = StaticText(fp_version)

		nims = nimmanager.nimList()
		self.tuner_list = []
		if len(nims) <= 4 :
			for count in (0, 1, 2, 3, 4, 5, 6, 7):
				if count < len(nims):
					self["Tuner" + str(count)] = StaticText(nims[count])
					self.tuner_list.append((nims[count] + "\n"))
				else:
					self["Tuner" + str(count)] = StaticText("")
		else:
			desc_list = []
			count = 0
			cur_idx = -1
			while count < len(nims):
				data = nims[count].split(":")
				idx = data[0].strip('Tuner').strip()
				desc = data[1].strip()
				if desc_list and desc_list[cur_idx]['desc'] == desc:
					desc_list[cur_idx]['end'] = idx
				else:
					desc_list.append({'desc' : desc, 'start' : idx, 'end' : idx})
					cur_idx += 1
				count += 1

			for count in (0, 1, 2, 3, 4, 5, 6, 7):
				if count < len(desc_list):
					if desc_list[count]['start'] == desc_list[count]['end']:
						text = "Tuner %s: %s" % (desc_list[count]['start'], desc_list[count]['desc'])
					else:
						text = "Tuner %s-%s: %s" % (desc_list[count]['start'], desc_list[count]['end'], desc_list[count]['desc'])
				else:
					text = ""

				self["Tuner" + str(count)] = StaticText(text)
				if text != "":
					self.tuner_list.append(text + "\n")

		self["HDDHeader"] = StaticText(_("Detected HDD:"))
		hddlist = harddiskmanager.HDDList()
		hdd = hddlist and hddlist[0][1] or None
		if hdd is not None and hdd.model() != "":
			self["hddA"] = StaticText(_("%s\n(%s, %d MB free)") % (hdd.model(), hdd.capacity(),hdd.free()))
		else:
			self["hddA"] = StaticText(_("none"))


		self.enigma2_version = _("Version") + ": " + about.getEnigmaVersionString()
		self.image_version = _("Image") + ": " + about.getImageVersionString()
		cpu_info = parseLines("/proc/cpuinfo")
		cpu_name = "N/A"
		for line in cpu_info:
			if line.find('model') != -1:
				cpu_name = line.split(':')
				if len(cpu_name) >= 2:
					cpu_name = cpu_name[1].strip()
				break
		
		self.cpu = _("CPU") + ": " + cpu_name
		self.chipset = _("Chipset") + ": " + parseFile("/proc/stb/info/chipset")
		self.tuner_header = _("Detected NIMs:")
		self.hdd_header = _("Detected HDD:")
		self.hdd_list = []
		if len(hddlist):
			for hddX in hddlist:
				hdd = hddX[1]
				if hdd.model() != "":
					self.hdd_list.append((hdd.model() + "\n   %.2f GB - %.2f GB" % (hdd.diskSize()/1000.0, hdd.free()/1000.0) + " " + _("free") + "\n\n"))

		ifaces = iNetwork.getConfiguredAdapters()
		iface_list = []
		for iface in ifaces:
			iface_list.append((_("Interface") + " : " + iNetwork.getAdapterName(iface) + " ("+ iNetwork.getFriendlyAdapterName(iface) + ")\n"))
			iface_list.append((_("IP") + " : " + parse_ipv4(iNetwork.getAdapterAttribute(iface, "ip")) + "\n"))
			iface_list.append((_("Netmask") + " : " + parse_ipv4(iNetwork.getAdapterAttribute(iface, "netmask")) + "\n"))
			iface_list.append((_("Gateway") + " : " + parse_ipv4(iNetwork.getAdapterAttribute(iface, "gateway")) + "\n"))
			if iNetwork.getAdapterAttribute(iface, "dhcp"):
				iface_list.append((_("DHCP") + " : " + _("Yes") + "\n"))
			else:
				iface_list.append((_("DHCP") + " : " + _("No") + "\n"))
			iface_list.append((_("MAC") + " : " + iNetwork.getAdapterAttribute(iface, "mac") + "\n"))
			iface_list.append(("\n"))

		my_txt = self.enigma2_version + "\n"
		my_txt += self.image_version + "\n"
		my_txt += "\n"
		my_txt += self.cpu + "\n"
		my_txt += self.chipset + "\n"
		my_txt += "\n"
		my_txt += self.tuner_header + "\n"
		for x in self.tuner_list:
			my_txt += "   " + x
		my_txt += "\n"
		my_txt += _("Network") + ":\n"
		for x in iface_list:
			my_txt += "   " + x
		my_txt += self.hdd_header + "\n"
		for x in self.hdd_list:
			my_txt += "   " + x
		my_txt += "\n"

		self["FullAbout"] = ScrollLabel(my_txt)

		self["actions"] = ActionMap(["SetupActions", "ColorActions", "EventViewActions"], 
			{
				"cancel": self.close,
				"ok": self.close,
				"pageUp": self.pageUp,
				"pageDown": self.pageDown
			})

	def pageUp(self):
		self["FullAbout"].pageUp()

	def pageDown(self):
		self["FullAbout"].pageDown()
