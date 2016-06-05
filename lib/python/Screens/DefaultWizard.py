from Wizard import wizardManager
from Screens.Ipkg import Ipkg, PackageSelection
from Screens.WizardLanguage import WizardLanguage
from Tools.Directories import pathExists, resolveFilename, SCOPE_DEFAULTDIR, SCOPE_DEFAULTPARTITIONMOUNTDIR, SCOPE_DEFAULTPARTITION

from Components.Pixmap import Pixmap, MovingPixmap
from Components.config import config, ConfigBoolean, configfile, ConfigYesNo, getConfigListEntry
from Components.DreamInfoHandler import DreamInfoHandler
from Components.Ipkg import IpkgComponent
from Components.PluginComponent import plugins
from Plugins.Plugin import PluginDescriptor
from os import system as os_system, path as os_path, mkdir

config.misc.defaultchosen = ConfigBoolean(default = True)

class DefaultWizard(WizardLanguage, DreamInfoHandler):
	def __init__(self, session, silent = True, showSteps = False, neededTag = None):
		DreamInfoHandler.__init__(self, self.statusCallback, neededTag = neededTag)
		self.silent = silent
		self.setDirectory()
        
		WizardLanguage.__init__(self, session, showSteps = False)
		self["wizard"] = Pixmap()
		self["rc"] = MovingPixmap()
		self["arrowdown"] = MovingPixmap()
		self["arrowup"] = MovingPixmap()
		self["arrowup2"] = MovingPixmap()
	
	def setDirectory(self):
		self.directory = resolveFilename(SCOPE_DEFAULTPARTITIONMOUNTDIR)
		self.xmlfile = "defaultwizard.xml"
		if self.directory:
			os_system("mount %s %s" % (resolveFilename(SCOPE_DEFAULTPARTITION), self.directory))
        
	def markDone(self):
		config.misc.defaultchosen.value = 0
		config.misc.defaultchosen.save()
		configfile.save()
		
	def statusCallback(self, status, progress):
		print "statusCallback:", status, progress
		if status == DreamInfoHandler.STATUS_DONE:
			self["text"].setText(_("The installation of the default settings is finished. You can now continue configuring your STB by pressing the OK button on the remote control."))
			self.markDone()
			self.disableKeys = False

	def getConfigList(self):
		self.packageslist = []
		configList = []
		self.fillPackagesList()
		self.packagesConfig = []
		for x in range(len(self.packageslist)):
			entry = ConfigYesNo()
			self.packagesConfig.append(entry)
			configList.append(getConfigListEntry(self.packageslist[x][0]["attributes"]["name"], entry))
		return configList

	def selectionMade(self):
		print "selection made"
		#self.installPackage(int(index))
		self.indexList = []
		for x in range(len(self.packagesConfig)):
			if self.packagesConfig[x].value:
				self.indexList.append(x)

class DreamPackageWizard(DefaultWizard):
	def __init__(self, session, packagefile, silent = False):
		if not pathExists("/tmp/package"):
			mkdir("/tmp/package")
		os_system("tar xpzf %s -C /tmp/package" % packagefile)
		self.packagefile = packagefile
		DefaultWizard.__init__(self, session, silent)
		
	def setDirectory(self):
		self.directory = "/tmp/package"
		self.xmlfile = "dreampackagewizard.xml"
		
class ImageDefaultInstaller(DreamInfoHandler):
	def __init__(self):
		DreamInfoHandler.__init__(self, self.statusCallback, blocking = True)
		self.directory = resolveFilename(SCOPE_DEFAULTDIR)
		self.fillPackagesList()
		self.installPackage(0)
		
	def statusCallback(self, status, progress):
		pass

def install(choice):
	if choice is not None:
		#os_system("mkdir /tmp/package && tar xpzf %s ")
		choice[2].open(DreamPackageWizard, choice[1])

def installSTBpackages(args):
	cmdList = []
	packages = args[0]
	session = args[1]
	if packages and session:
		cmdList.append((IpkgComponent.CMD_UPDATE, { }))
		for pkg in packages:
			cmdList.append((IpkgComponent.CMD_INSTALL, {"package": pkg}))
		session.open(Ipkg, cmdList = cmdList)

def filescan_open(list, session, **kwargs):
	showDirectories = False
	base_path = os_path.split(list[0].path)[0]
	i = 0
	for x in list:
		if os_path.split(x.path)[0] != base_path:
			showDirectories = True
			break
	session.openWithCallback(installSTBpackages, PackageSelection, path = base_path, showDirectories = showDirectories)

def filescan(**kwargs):
	from Components.Scanner import Scanner, ScanPath
	return \
		Scanner(mimetypes = ["application/x-stb-package"], 
			paths_to_scan = 
				[
					ScanPath(path = "ipk", with_subdirs = True),
					ScanPath(path = "plugins", with_subdirs = True),
					ScanPath(path = "skins", with_subdirs = True),
					ScanPath(path = "software", with_subdirs = True),
					ScanPath(path = "", with_subdirs = False), 
				], 
			name = "STB-Package", 
			description = _("Install settings, skins, software..."), 
			openfnc = filescan_open, )

plugins.addPlugin(PluginDescriptor(name="STB-Package", where = PluginDescriptor.WHERE_FILESCAN, fnc = filescan, internal = True))

wizardManager.registerWizard(DefaultWizard, config.misc.defaultchosen.value, priority = 6)

if config.misc.defaultchosen.value:
	print "Installing image defaults"
	installer = ImageDefaultInstaller()
	print "installing done!"
