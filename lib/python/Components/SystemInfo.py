from enigma import eDVBResourceManager, Misc_Options
from Tools.Directories import fileExists, fileCheck, pathExists
from Tools.HardwareInfo import HardwareInfo

SystemInfo = { }

#FIXMEE...
def getNumVideoDecoders():
	idx = 0
	while fileExists("/dev/dvb/adapter0/video%d"%(idx), 'f'):
		idx += 1
	return idx

SystemInfo["NumVideoDecoders"] = getNumVideoDecoders()
SystemInfo['PIPAvailable'] = SystemInfo['NumVideoDecoders'] > 1
SystemInfo["CanMeasureFrontendInputPower"] = eDVBResourceManager.getInstance().canMeasureFrontendInputPower()


def countFrontpanelLEDs():
	leds = 0
	if fileExists("/proc/stb/fp/led_set_pattern"):
		leds += 1

	while fileExists("/proc/stb/fp/led%d_pattern" % leds):
		leds += 1

	return leds

SystemInfo["NumFrontpanelLEDs"] = countFrontpanelLEDs()
SystemInfo["FrontpanelDisplay"] = fileExists("/dev/dbox/oled0") or fileExists("/dev/dbox/lcd0")
SystemInfo["FrontpanelDisplayGrayscale"] = fileExists("/dev/dbox/oled0")
SystemInfo["DeepstandbySupport"] = HardwareInfo().get_device_name() != "dm800"
SystemInfo["HasHbbTV"] = fileExists("/usr/lib/enigma2/python/Plugins/Extensions/HbbTV/plugin.py") or fileExists("/usr/lib/enigma2/python/Plugins/Extensions/HbbTV/plugin.pyo")
SystemInfo["HasWebKitHbbTV"] = fileExists("/usr/lib/enigma2/python/Plugins/Extensions/WebkitHbbTV/plugin.py") or fileExists("/usr/lib/enigma2/python/Plugins/Extensions/WebkitHbbTV/plugin.pyo")
SystemInfo["CanPiP"] = getNumVideoDecoders() > 1
SystemInfo["Can3DSurround"] = fileExists("/proc/stb/audio/3d_surround_choices")
SystemInfo["CanSpeakerPosition"] = fileExists("/proc/stb/audio/3d_surround_speaker_position_choices")
SystemInfo["CanAVL"] = fileExists("/proc/stb/audio/avl_choices")
SystemInfo["CanDownmixAC3"] = fileExists("/proc/stb/audio/ac3_choices")
# disable AAC downmix for now, has to be converted to AC3 in passthrough mode
SystemInfo["CanDownmixAAC"] = False #fileExists("/proc/stb/audio/aac_choices")
SystemInfo["CanMultiChannelPCM"] = fileExists("/proc/stb/audio/multichannel_pcm")
SystemInfo['ZapMode'] = fileCheck('/proc/stb/video/zapmode') or fileCheck('/proc/stb/video/zapping_mode')
SystemInfo['Fan'] = fileCheck('/proc/stb/fp/fan')
SystemInfo['FanPWM'] = SystemInfo['Fan'] and fileCheck('/proc/stb/fp/fan_pwm')
SystemInfo['StandbyLED'] = fileCheck('/proc/stb/power/standbyled')
SystemInfo['HasExternalPIP'] = not HardwareInfo().get_device_model().startswith('et9') and fileCheck('/proc/stb/vmpeg/1/external')
SystemInfo['VideoDestinationConfigurable'] = fileExists('/proc/stb/vmpeg/0/dst_left')
SystemInfo['hasPIPVisibleProc'] = fileCheck('/proc/stb/vmpeg/1/visible')
SystemInfo['LcdLiveTV'] = fileCheck('/proc/stb/fb/sd_detach') or fileCheck('/proc/stb/lcd/live_enable')
SystemInfo['3DMode'] = fileCheck('/proc/stb/fb/3dmode') or fileCheck('/proc/stb/fb/primary/3d')
SystemInfo['3DZNorm'] = fileCheck('/proc/stb/fb/znorm') or fileCheck('/proc/stb/fb/primary/zoffset')
SystemInfo['12V_Output'] = Misc_Options.getInstance().detected_12V_output()
SystemInfo['WakeOnLAN'] = not HardwareInfo().get_device_model().startswith('et8000') and fileCheck('/proc/stb/power/wol') or fileCheck('/proc/stb/fp/wol')
SystemInfo['VFD_scroll_repeats'] = not HardwareInfo().get_device_model().startswith('et8500') and fileCheck('/proc/stb/lcd/scroll_repeats')
SystemInfo['VFD_scroll_delay'] = not HardwareInfo().get_device_model().startswith('et8500') and fileCheck('/proc/stb/lcd/scroll_delay')
SystemInfo['VFD_initial_scroll_delay'] = not HardwareInfo().get_device_model().startswith('et8500') and fileCheck('/proc/stb/lcd/initial_scroll_delay')
SystemInfo['VFD_final_scroll_delay'] = not HardwareInfo().get_device_model().startswith('et8500') and fileCheck('/proc/stb/lcd/final_scroll_delay')
SystemInfo['Blindscan_t2_available'] = fileCheck('/proc/stb/info/vumodel')
SystemInfo['RcTypeChangable'] = not (HardwareInfo().get_device_model().startswith('et8500') or HardwareInfo().get_device_model().startswith('et7')) and pathExists('/proc/stb/ir/rc/type')
SystemInfo['HasFullHDSkinSupport'] = HardwareInfo().get_device_model() not in 'et4000 et5000 sh1 hd500c hd1100 xp1000 vusolo'
SystemInfo['HasForceLNBOn'] = fileCheck('/proc/stb/frontend/fbc/force_lnbon')
SystemInfo['HasForceToneburst'] = fileCheck('/proc/stb/frontend/fbc/force_toneburst')
SystemInfo['HasBypassEdidChecking'] = fileCheck('/proc/stb/hdmi/bypass_edid_checking')
