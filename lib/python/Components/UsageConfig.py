from Components.Harddisk import harddiskmanager
from config import ConfigSubsection, ConfigYesNo, config, ConfigSelection, ConfigText, ConfigNumber, ConfigSet, ConfigLocations, ConfigSelectionNumber, ConfigClock, ConfigSlider, ConfigEnableDisable, ConfigSubDict, ConfigNothing
from Tools.Directories import resolveFilename, SCOPE_HDD, defaultRecordingLocation
from enigma import setTunerTypePriorityOrder, setPreferredTuner, setSpinnerOnOff, setEnableTtCachingOnOff, eEnv, eDVBDB, Misc_Options, eBackgroundFileEraser, eServiceEvent
from Components.NimManager import nimmanager
from Components.Harddisk import harddiskmanager
from Components.ServiceList import refreshServiceList
from SystemInfo import SystemInfo
import os
import time

def InitUsageConfig():
    config.usage = ConfigSubsection()
    config.usage.showdish = ConfigYesNo(default=True)
    config.misc.showrotorposition = ConfigSelection(default='no', choices=[('no', _('no')),
     ('yes', _('yes')),
     ('withtext', _('with text')),
     ('tunername', _('with tuner name'))])
    config.usage.multibouquet = ConfigYesNo(default=True)
    config.usage.alternative_number_mode = ConfigYesNo(default=False)

    def alternativeNumberModeChange(configElement):
        eDVBDB.getInstance().setNumberingMode(configElement.value)
        refreshServiceList()

    config.usage.alternative_number_mode.addNotifier(alternativeNumberModeChange)
    config.usage.hide_number_markers = ConfigYesNo(default=True)
    config.usage.hide_number_markers.addNotifier(refreshServiceList)
    config.usage.servicetype_icon_mode = ConfigSelection(default='0', choices=[('0', _('None')), ('1', _('Left from servicename')), ('2', _('Right from servicename'))])
    config.usage.servicetype_icon_mode.addNotifier(refreshServiceList)
    config.usage.crypto_icon_mode = ConfigSelection(default='0', choices=[('0', _('None')), ('1', _('Left from servicename')), ('2', _('Right from servicename'))])
    config.usage.crypto_icon_mode.addNotifier(refreshServiceList)
    config.usage.record_indicator_mode = ConfigSelection(default='0', choices=[('0', _('None')),
     ('1', _('Left from servicename')),
     ('2', _('Right from servicename')),
     ('3', _('Red colored'))])
    config.usage.record_indicator_mode.addNotifier(refreshServiceList)
    choicelist = [('-1', _('Disable'))]
    for i in range(0, 1300, 100):
        choicelist.append((str(i), ngettext('%d pixel wide', '%d pixels wide', i) % i))

    config.usage.servicelist_column = ConfigSelection(default='-1', choices=choicelist)
    config.usage.servicelist_column.addNotifier(refreshServiceList)
    config.usage.service_icon_enable = ConfigYesNo(default=False)
    config.usage.service_icon_enable.addNotifier(refreshServiceList)
    config.usage.servicelist_cursor_behavior = ConfigSelection(default='standard', choices=[('standard', _('Standard')),
     ('keep', _('Keep service')),
     ('reverseB', _('Reverse bouquet buttons')),
     ('keep reverseB', _('Keep service') + ' + ' + _('Reverse bouquet buttons'))])
    choicelist = [('by skin', _('As defined by the skin'))]
    for i in range(5, 41):
        choicelist.append(str(i))

    config.usage.servicelist_number_of_services = ConfigSelection(default='by skin', choices=choicelist)
    config.usage.servicelist_number_of_services.addNotifier(refreshServiceList)
    config.usage.multiepg_ask_bouquet = ConfigYesNo(default=False)
    config.usage.quickzap_bouquet_change = ConfigYesNo(default=False)
    config.usage.e1like_radio_mode = ConfigYesNo(default=True)
    choicelist = [('0', _('No timeout'))]
    for i in range(1, 12):
        choicelist.append((str(i), ngettext('%d second', '%d seconds', i) % i))

    config.usage.infobar_timeout = ConfigSelection(default='5', choices=choicelist)
    config.usage.show_infobar_on_zap = ConfigYesNo(default=True)
    config.usage.show_infobar_on_skip = ConfigYesNo(default=True)
    config.usage.show_infobar_on_event_change = ConfigYesNo(default=False)
    config.usage.show_second_infobar = ConfigSelection(default=None, choices=[(None, _('None'))] + choicelist + [('EPG', _('EPG'))])
    config.usage.show_simple_second_infobar = ConfigYesNo(default=True)
    config.usage.infobar_frontend_source = ConfigSelection(default='tuner', choices=[('settings', _('Settings')), ('tuner', _('Tuner'))])
    config.usage.oldstyle_zap_controls = ConfigYesNo(default=False)
    config.usage.oldstyle_channel_select_controls = ConfigYesNo(default=False)
    config.usage.zap_with_ch_buttons = ConfigYesNo(default=False)
    config.usage.ok_is_channelselection = ConfigYesNo(default=False)
    config.usage.volume_instead_of_channelselection = ConfigYesNo(default=False)
    config.usage.channelselection_preview = ConfigYesNo(default=False)
    config.usage.show_spinner = ConfigYesNo(default=True)
    config.usage.enable_tt_caching = ConfigYesNo(default=True)
    choicelist = []
    for i in (10, 30):
        choicelist.append((str(i), ngettext('%d second', '%d seconds', i) % i))

    for i in (60, 120, 300, 600, 1200, 1800):
        m = i / 60
        choicelist.append((str(i), ngettext('%d minute', '%d minutes', m) % m))

    for i in (3600, 7200, 14400):
        h = i / 3600
        choicelist.append((str(i), ngettext('%d hour', '%d hours', h) % h))

    config.usage.hdd_standby = ConfigSelection(default='300', choices=[('0', _('No standby'))] + choicelist)
    config.usage.output_12V = ConfigSelection(default='do not change', choices=[('do not change', _('Do not change')), ('off', _('Off')), ('on', _('On'))])
    config.usage.pip_zero_button = ConfigSelection(default='standard', choices=[('standard', _('Standard')),
     ('swap', _('Swap PiP and main picture')),
     ('swapstop', _('Move PiP to main picture')),
     ('stop', _('Stop PiP'))])
    config.usage.pip_hideOnExit = ConfigSelection(default='without popup', choices=[('no', _('No')), ('popup', _('With popup')), ('without popup', _('Without popup'))])
    choicelist = [('-1', _('Disabled')), ('0', _('No timeout'))]
    for i in [60,
     300,
     600,
     900,
     1800,
     2700,
     3600]:
        m = i / 60
        choicelist.append((str(i), ngettext('%d minute', '%d minutes', m) % m))

    config.usage.pip_last_service_timeout = ConfigSelection(default='0', choices=choicelist)
    config.usage.default_path = ConfigText(default=resolveFilename(SCOPE_HDD))
    config.usage.timer_path = ConfigText(default='<default>')
    config.usage.instantrec_path = ConfigText(default='<default>')
    config.usage.timeshift_path = ConfigText(default='/media/hdd/')
    config.usage.allowed_timeshift_paths = ConfigLocations(default=['/media/hdd/'])
    config.usage.movielist_trashcan = ConfigYesNo(default=True)
    config.usage.movielist_trashcan_days = ConfigNumber(default=8)
    config.usage.movielist_trashcan_reserve = ConfigNumber(default=40)
    config.usage.on_movie_start = ConfigSelection(default='resume', choices=[('ask yes', _('Ask user') + ' ' + _('default') + ' ' + _('yes')),
     ('ask no', _('Ask user') + ' ' + _('default') + ' ' + _('no')),
     ('resume', _('Resume from last position')),
     ('beginning', _('Start from the beginning'))])
    config.usage.on_movie_stop = ConfigSelection(default='movielist', choices=[('ask', _('Ask user')), ('movielist', _('Return to movie list')), ('quit', _('Return to previous service'))])
    config.usage.on_movie_eof = ConfigSelection(default='movielist', choices=[('ask', _('Ask user')),
     ('movielist', _('Return to movie list')),
     ('quit', _('Return to previous service')),
     ('pause', _('Pause movie at end')),
     ('playlist', _('Play next (return to movie list)')),
     ('playlistquit', _('Play next (return to previous service)')),
     ('loop', _('Continues play (loop)')),
     ('repeatcurrent', _('Repeat'))])
    config.usage.next_movie_msg = ConfigYesNo(default=True)
    config.usage.last_movie_played = ConfigText()
    config.usage.leave_movieplayer_onExit = ConfigSelection(default='popup', choices=[('no', _('No')),
     ('popup', _('With popup')),
     ('without popup', _('Without popup')),
     ('movielist', _('Return to movie list'))])
    config.usage.setup_level = ConfigSelection(default='expert', choices=[('simple', _('Simple')), ('intermediate', _('Intermediate')), ('expert', _('Expert'))])
    config.usage.startup_to_standby = ConfigSelection(default='no', choices=[('no', _('No')), ('yes', _('Yes')), ('except', _('No, except Wakeup timer'))])
    config.usage.wakeup_menu = ConfigNothing()
    config.usage.wakeup_enabled = ConfigYesNo(default=False)
    config.usage.wakeup_day = ConfigSubDict()
    config.usage.wakeup_time = ConfigSubDict()
    for i in range(7):
        config.usage.wakeup_day[i] = ConfigEnableDisable(default=False)
        config.usage.wakeup_time[i] = ConfigClock(default=21600)

    choicelist = [('0', _('Do nothing'))]
    for i in range(3600, 21601, 3600):
        h = abs(i / 3600)
        h = ngettext('%d hour', '%d hours', h) % h
        choicelist.append((str(i), _('Standby in ') + h))

    config.usage.inactivity_timer = ConfigSelection(default='0', choices=choicelist)
    config.usage.inactivity_timer_blocktime = ConfigYesNo(default=True)
    config.usage.inactivity_timer_blocktime_begin = ConfigClock(default=time.mktime((0, 0, 0, 18, 0, 0, 0, 0, 0)))
    config.usage.inactivity_timer_blocktime_end = ConfigClock(default=time.mktime((0, 0, 0, 23, 0, 0, 0, 0, 0)))
    config.usage.inactivity_timer_blocktime_extra = ConfigYesNo(default=False)
    config.usage.inactivity_timer_blocktime_extra_begin = ConfigClock(default=time.mktime((0, 0, 0, 6, 0, 0, 0, 0, 0)))
    config.usage.inactivity_timer_blocktime_extra_end = ConfigClock(default=time.mktime((0, 0, 0, 9, 0, 0, 0, 0, 0)))
    choicelist = [('0', _('Disabled')), ('event_standby', _('Standby after current event'))]
    for i in range(900, 7201, 900):
        m = abs(i / 60)
        m = ngettext('%d minute', '%d minutes', m) % m
        choicelist.append((str(i), _('Standby in ') + m))

    config.usage.sleep_timer = ConfigSelection(default='0', choices=choicelist)
    choicelist = [('0', _('Disabled'))]
    for i in [60, 300, 600] + range(900, 7201, 900):
        m = abs(i / 60)
        m = ngettext('%d minute', '%d minutes', m) % m
        choicelist.append((str(i), _('after ') + m))

    config.usage.standby_to_shutdown_timer = ConfigSelection(default='0', choices=choicelist)
    config.usage.standby_to_shutdown_timer_blocktime = ConfigYesNo(default=True)
    config.usage.standby_to_shutdown_timer_blocktime_begin = ConfigClock(default=time.mktime((0, 0, 0, 6, 0, 0, 0, 0, 0)))
    config.usage.standby_to_shutdown_timer_blocktime_end = ConfigClock(default=time.mktime((0, 0, 0, 23, 0, 0, 0, 0, 0)))
    choicelist = [('0', _('Disabled'))]
    for m in (1, 5, 10, 15, 30, 60):
        choicelist.append((str(m * 60), ngettext('%d minute', '%d minutes', m) % m))

    config.usage.screen_saver = ConfigSelection(default='300', choices=choicelist)
    config.usage.check_timeshift = ConfigYesNo(default=True)
    choicelist = [('0', _('Disabled'))]
    for i in (2, 3, 4, 5, 10, 20, 30):
        choicelist.append((str(i), ngettext('%d second', '%d seconds', i) % i))

    for i in (60, 120, 300):
        m = i / 60
        choicelist.append((str(i), ngettext('%d minute', '%d minutes', m) % m))

    config.usage.timeshift_start_delay = ConfigSelection(default='0', choices=choicelist)
    config.usage.alternatives_priority = ConfigSelection(default='0', choices=[('0', 'DVB-S/-C/-T'),
     ('1', 'DVB-S/-T/-C'),
     ('2', 'DVB-C/-S/-T'),
     ('3', 'DVB-C/-T/-S'),
     ('4', 'DVB-T/-C/-S'),
     ('5', 'DVB-T/-S/-C'),
     ('127', _('No priority'))])
    config.usage.remote_fallback_enabled = ConfigYesNo(default=False)
    config.usage.remote_fallback = ConfigText(default='', fixed_size=False)
    config.usage.show_timer_conflict_warning = ConfigYesNo(default=True)
    dvbs_nims = [('-2', _('Disabled'))]
    dvbt_nims = [('-2', _('Disabled'))]
    dvbc_nims = [('-2', _('Disabled'))]
    nims = [('-1', _('auto'))]
    for x in nimmanager.nim_slots:
        if x.isCompatible('DVB-S'):
            dvbs_nims.append((str(x.slot), x.getSlotName()))
        elif x.isCompatible('DVB-T'):
            dvbt_nims.append((str(x.slot), x.getSlotName()))
        elif x.isCompatible('DVB-C'):
            dvbc_nims.append((str(x.slot), x.getSlotName()))
        nims.append((str(x.slot), x.getSlotName()))

    config.usage.frontend_priority = ConfigSelection(default='-1', choices=list(nims))
    nims.insert(0, ('-2', _('Disabled')))
    config.usage.recording_frontend_priority = ConfigSelection(default='-2', choices=nims)
    config.usage.frontend_priority_dvbs = ConfigSelection(default='-2', choices=list(dvbs_nims))
    dvbs_nims.insert(1, ('-1', _('auto')))
    config.usage.recording_frontend_priority_dvbs = ConfigSelection(default='-2', choices=dvbs_nims)
    config.usage.frontend_priority_dvbt = ConfigSelection(default='-2', choices=list(dvbt_nims))
    dvbt_nims.insert(1, ('-1', _('auto')))
    config.usage.recording_frontend_priority_dvbt = ConfigSelection(default='-2', choices=dvbt_nims)
    config.usage.frontend_priority_dvbc = ConfigSelection(default='-2', choices=list(dvbc_nims))
    dvbc_nims.insert(1, ('-1', _('auto')))
    config.usage.recording_frontend_priority_dvbc = ConfigSelection(default='-2', choices=dvbc_nims)
    SystemInfo['DVB-S_priority_tuner_available'] = len(dvbs_nims) > 3 and (len(dvbt_nims) > 2 or len(dvbc_nims) > 2)
    SystemInfo['DVB-T_priority_tuner_available'] = len(dvbt_nims) > 3 and (len(dvbs_nims) > 2 or len(dvbc_nims) > 2)
    SystemInfo['DVB-C_priority_tuner_available'] = len(dvbc_nims) > 3 and (len(dvbs_nims) > 2 or len(dvbt_nims) > 2)
    config.misc.disable_background_scan = ConfigYesNo(default=False)
    config.usage.show_event_progress_in_servicelist = ConfigSelection(default='barright', choices=[('barleft', _('Progress bar left')),
     ('barright', _('Progress bar right')),
     ('percleft', _('Percentage left')),
     ('percright', _('Percentage right')),
     ('no', _('No'))])
    config.usage.show_channel_numbers_in_servicelist = ConfigYesNo(default=True)
    config.usage.show_event_progress_in_servicelist.addNotifier(refreshServiceList)
    config.usage.show_channel_numbers_in_servicelist.addNotifier(refreshServiceList)
    config.usage.blinking_display_clock_during_recording = ConfigYesNo(default=False)
    config.usage.show_message_when_recording_starts = ConfigYesNo(default=True)
    config.usage.load_length_of_movies_in_moviellist = ConfigYesNo(default=True)
    config.usage.show_icons_in_movielist = ConfigSelection(default='i', choices=[('o', _('Off')),
     ('p', _('Progress')),
     ('s', _('Small progress')),
     ('i', _('Icons'))])
    config.usage.movielist_unseen = ConfigYesNo(default=False)
    config.usage.swap_snr_on_osd = ConfigYesNo(default=False)

    def SpinnerOnOffChanged(configElement):
        setSpinnerOnOff(int(configElement.value))

    config.usage.show_spinner.addNotifier(SpinnerOnOffChanged)

    def EnableTtCachingChanged(configElement):
        setEnableTtCachingOnOff(int(configElement.value))

    config.usage.enable_tt_caching.addNotifier(EnableTtCachingChanged)

    def TunerTypePriorityOrderChanged(configElement):
        setTunerTypePriorityOrder(int(configElement.value))

    config.usage.alternatives_priority.addNotifier(TunerTypePriorityOrderChanged, immediate_feedback=False)

    def PreferredTunerChanged(configElement):
        setPreferredTuner(int(configElement.value))

    config.usage.frontend_priority.addNotifier(PreferredTunerChanged)
    config.usage.hide_zap_errors = ConfigYesNo(default=False)
    config.usage.hide_ci_messages = ConfigYesNo(default=True)
    config.usage.show_cryptoinfo = ConfigYesNo(default=True)
    config.usage.show_eit_nownext = ConfigYesNo(default=True)
    config.usage.show_vcr_scart = ConfigYesNo(default=False)
    config.usage.show_update_disclaimer = ConfigYesNo(default=True)
    config.usage.pic_resolution = ConfigSelection(default=None, choices=[(None, _('Same resolution as skin')),
     ('(720, 576)', '720x576'),
     ('(1280, 720)', '1280x720'),
     ('(1920, 1080)', '1920x1080')][:SystemInfo['HasFullHDSkinSupport'] and 4 or 3])
    if SystemInfo['Fan']:
        choicelist = [('off', _('Off')), ('on', _('On')), ('auto', _('Auto'))]
        if os.path.exists('/proc/stb/fp/fan_choices'):
            choicelist = [ x for x in choicelist if x[0] in open('/proc/stb/fp/fan_choices', 'r').read().strip().split(' ') ]
        config.usage.fan = ConfigSelection(choicelist)

        def fanChanged(configElement):
            open(SystemInfo['Fan'], 'w').write(configElement.value)

        config.usage.fan.addNotifier(fanChanged)
    if SystemInfo['FanPWM']:

        def fanSpeedChanged(configElement):
            open(SystemInfo['FanPWM'], 'w').write(hex(configElement.value)[2:])

        config.usage.fanspeed = ConfigSlider(default=127, increment=8, limits=(0, 255))
        config.usage.fanspeed.addNotifier(fanSpeedChanged)
    if SystemInfo['StandbyLED']:

        def standbyLEDChanged(configElement):
            open(SystemInfo['StandbyLED'], 'w').write(configElement.value and 'on' or 'off')

        config.usage.standbyLED = ConfigYesNo(default=True)
        config.usage.standbyLED.addNotifier(standbyLEDChanged)
    if SystemInfo['WakeOnLAN']:

        def wakeOnLANChanged(configElement):
            if 'fp' in SystemInfo['WakeOnLAN']:
                open(SystemInfo['WakeOnLAN'], 'w').write(configElement.value and 'enable' or 'disable')
            else:
                open(SystemInfo['WakeOnLAN'], 'w').write(configElement.value and 'on' or 'off')

        config.usage.wakeOnLAN = ConfigYesNo(default=False)
        config.usage.wakeOnLAN.addNotifier(wakeOnLANChanged)
    config.epg = ConfigSubsection()
    config.epg.eit = ConfigYesNo(default=True)
    config.epg.mhw = ConfigYesNo(default=False)
    config.epg.freesat = ConfigYesNo(default=True)
    config.epg.viasat = ConfigYesNo(default=True)
    config.epg.netmed = ConfigYesNo(default=True)
    config.epg.virgin = ConfigYesNo(default=False)
    config.misc.showradiopic = ConfigYesNo(default=True)

    def EpgSettingsChanged(configElement):
        from enigma import eEPGCache
        mask = 4294967295L
        if not config.epg.eit.value:
            mask &= ~(eEPGCache.NOWNEXT | eEPGCache.SCHEDULE | eEPGCache.SCHEDULE_OTHER)
        if not config.epg.mhw.value:
            mask &= ~eEPGCache.MHW
        if not config.epg.freesat.value:
            mask &= ~(eEPGCache.FREESAT_NOWNEXT | eEPGCache.FREESAT_SCHEDULE | eEPGCache.FREESAT_SCHEDULE_OTHER)
        if not config.epg.viasat.value:
            mask &= ~eEPGCache.VIASAT
        if not config.epg.netmed.value:
            mask &= ~(eEPGCache.NETMED_SCHEDULE | eEPGCache.NETMED_SCHEDULE_OTHER)
        if not config.epg.virgin.value:
            mask &= ~(eEPGCache.VIRGIN_NOWNEXT | eEPGCache.VIRGIN_SCHEDULE)
        eEPGCache.getInstance().setEpgSources(mask)

    config.epg.eit.addNotifier(EpgSettingsChanged)
    config.epg.mhw.addNotifier(EpgSettingsChanged)
    config.epg.freesat.addNotifier(EpgSettingsChanged)
    config.epg.viasat.addNotifier(EpgSettingsChanged)
    config.epg.netmed.addNotifier(EpgSettingsChanged)
    config.epg.virgin.addNotifier(EpgSettingsChanged)
    config.epg.histminutes = ConfigSelectionNumber(min=0, max=120, stepwidth=15, default=0, wraparound=True)

    def EpgHistorySecondsChanged(configElement):
        from enigma import eEPGCache
        eEPGCache.getInstance().setEpgHistorySeconds(config.epg.histminutes.getValue() * 60)

    config.epg.histminutes.addNotifier(EpgHistorySecondsChanged)

    def setHDDStandby(configElement):
        for hdd in harddiskmanager.HDDList():
            hdd[1].setIdleTime(int(configElement.value))

    config.usage.hdd_standby.addNotifier(setHDDStandby, immediate_feedback=False)
    if SystemInfo['12V_Output']:

        def set12VOutput(configElement):
            Misc_Options.getInstance().set_12V_output(configElement.value == 'on' and 1 or 0)

        config.usage.output_12V.addNotifier(set12VOutput, immediate_feedback=False)
    config.usage.keymap = ConfigText(default=eEnv.resolve('${datadir}/enigma2/keymap.xml'))
    config.usage.keytrans = ConfigText(default=eEnv.resolve('${datadir}/enigma2/keytranslation.xml'))
    config.seek = ConfigSubsection()
    config.seek.selfdefined_13 = ConfigNumber(default=15)
    config.seek.selfdefined_46 = ConfigNumber(default=60)
    config.seek.selfdefined_79 = ConfigNumber(default=300)
    config.seek.speeds_forward = ConfigSet(default=[2,
     4,
     8,
     16,
     32,
     64,
     128], choices=[2,
     4,
     6,
     8,
     12,
     16,
     24,
     32,
     48,
     64,
     96,
     128])
    config.seek.speeds_backward = ConfigSet(default=[2,
     4,
     8,
     16,
     32,
     64,
     128], choices=[1,
     2,
     4,
     6,
     8,
     12,
     16,
     24,
     32,
     48,
     64,
     96,
     128])
    config.seek.speeds_slowmotion = ConfigSet(default=[2, 4, 8], choices=[2,
     4,
     6,
     8,
     12,
     16,
     25])
    config.seek.enter_forward = ConfigSelection(default='2', choices=['2',
     '4',
     '6',
     '8',
     '12',
     '16',
     '24',
     '32',
     '48',
     '64',
     '96',
     '128'])
    config.seek.enter_backward = ConfigSelection(default='1', choices=['1',
     '2',
     '4',
     '6',
     '8',
     '12',
     '16',
     '24',
     '32',
     '48',
     '64',
     '96',
     '128'])
    config.seek.on_pause = ConfigSelection(default='play', choices=[('play', _('Play')), ('step', _('Single step (GOP)')), ('last', _('Last speed'))])
    config.usage.timerlist_finished_timer_position = ConfigSelection(default='end', choices=[('beginning', _('At beginning')), ('end', _('At end'))])

    def updateEnterForward(configElement):
        if not configElement.value:
            configElement.value = [2]
        updateChoices(config.seek.enter_forward, configElement.value)

    config.seek.speeds_forward.addNotifier(updateEnterForward, immediate_feedback=False)

    def updateEnterBackward(configElement):
        if not configElement.value:
            configElement.value = [2]
        updateChoices(config.seek.enter_backward, configElement.value)

        config.seek.speeds_backward.addNotifier(updateEnterBackward, immediate_feedback=False)

# VTI Settings start
    config.usage.show_bsod = ConfigYesNo(default = False)
    config.misc.placeholder = NoSave(ConfigSelection(default = "1", choices = [("1", " ")]))
    config.misc.use_ci_assignment = ConfigYesNo(default = True)
    config.misc.disable_auto_channel_list = ConfigYesNo(default = False)
    config.misc.allow_service_delete = ConfigYesNo(default = False)
    config.misc.ecm_info = ConfigYesNo(default = True)
    config.misc.enable_custom_mainmenu = ConfigYesNo(default = False)
    config.usage.ts_min_duration = ConfigSelection(default = "0", choices = [
        ("0", _("off")),
        ("1", _("1 minute")),
        ("2", _("2 minutes")),
        ("5", _("5 minutes")),
        ("10", _("10 minutes")),])
    config.usage.ts_show_old_ts = ConfigYesNo(default = False)
    config.usage.ts_use_history_keys = ConfigYesNo(default = False)
    config.usage.ts_clean_intervall = ConfigSelection(default = "0", choices = ["0", "1", "2", "3", "4", "5", "6", "12", "24"])
    config.usage.ts_clean_ts_older_than = ConfigSelection(default = "1", choices = [("0.25", "1/4"), ("0.5", "1/2"), ("1.0", "1"), ("2.0", "2"), ("3.0", "3"), ("4.0", "4"), ("5.0", "5")])
    config.usage.ts_ask_before_service_changed = ConfigSelection(default = "delete", choices = [
        ("ask", _("Ask user")),
        ("delete", _("delete timeshift file")),
        ("keep_ts", _("keep timeshift file")),])
    config.usage.ts_auto_start = ConfigSelection(default = "0", choices = [
        ("0", _("off")),
        ("1", _("1 second")),
        ("2", _("2 seconds")),
        ("3", _("3 seconds")),
        ("4", _("4 seconds")),
        ("5", _("5 seconds")),
        ("10", _("10 seconds")),
        ("20", _("20 seconds")),
        ("30", _("30 seconds")),
        ("60", _("1 minute")),
        ("120", _("2 minutes")),
        ("300", _("5 minutes")),])
    config.usage.ts_event_change = ConfigSelection(default = "split_and_keep", choices = [
        ("ask", _("Ask user")),
        ("continue", _("continue timeshift")),
        ("split_and_keep", _("split & keep")),
        ("split_and_delete", _("split & delete")),
        ("stop_and_keep", _("stop & keep")),
        ("stop_and_delete", _("stop & delete")),])
    config.usage.infobar_dimm = ConfigSelection(default = "off", choices = [
        ("fade_in", _("fade in")),
        ("fade_in_out", _("fade in/out")),
        ("fade_out", _("fade out")),
        ("off", _("off")),])
    config.usage.infobar_dimm_speed = ConfigSelection(default = "30", choices = [
        ("15", _("fast")),
        ("30", _("default")),
        ("50", _("slow")),])

    config.usage.enable_zaphistory = ConfigYesNo(default = True)
    config.usage.show_epg_progress_percent = ConfigYesNo(default = False)
    config.usage.servicelist_show_picon = ConfigSelection(default = "0", choices = [
        ("0", _("off")),
        ("100", "100x60 px"),
        ("50", "50x30 px"),
        ("1", _("user defined")),])
    config.usage.servicelist_picon_dir = ConfigDirectory(default = "/usr/share/enigma2/picon")
    config.usage.servicelist_two_lines = ConfigYesNo(default = False)
    config.usage.servicelist_show_event_time = ConfigYesNo(default = False)
    config.usage.servicelist_mark_rec_service = ConfigYesNo(default = True)
    config.usage.servicelist_show_rec_service_symbol = ConfigYesNo(default = True)
    config.usage.servicelist_show_servicenumber = ConfigYesNo(default = True)
    config.usage.servicelist_name_width = ConfigInteger(default = 200, limits = (1, 1920))
    config.usage.servicelist_use_matrix = ConfigYesNo(default = False)
    config.usage.servicelist_show_next_event = ConfigYesNo(default = False)
    config.usage.servicelist_show_service_type_icon = ConfigYesNo(default = False)
    config.usage.servicelist_preview_mode = ConfigYesNo(default = False)
    config.usage.servicelist_hide_service_name = ConfigYesNo(default = False)
    
    rec_button_choices = \
        [
            ("record_menu", _("show record menu")),
            ("running_record", _("show running records")),
            ("timer_list", _("show timer list")),
            ("event_record", _("add recording (stop after current event)")),
            ("indefinitely_record", _("add recording (indefinitely)")),
            ("manualduration_record", _("add recording (enter recording duration)")),
            ("manualendtime_record", _("add recording (enter recording endtime)")),
            ("timeshift_to_record", _("Transform Timeshift into recording"))
        ]
    
    config.usage.rec_button = ConfigSelection(default = "record_menu", choices = rec_button_choices)
    config.usage.rec_button_long = ConfigSelection(default = "running_record", choices = rec_button_choices)
    
    
    config.usage.remove_finished_timers = ConfigYesNo(default = True)
    config.usage.enable_eit_epg = ConfigYesNo(default = True)
    def setEITepg(configElement):
            from enigma import eEPGCache
            eEPGCache.getInstance().setEITenabled(int(config.usage.enable_eit_epg.getValue()))
    config.usage.enable_eit_epg.addNotifier(setEITepg)
    config.usage.show_nownext_eit = ConfigYesNo(default = True)
    config.usage.show_old_epg = ConfigSelection(default = "21600", choices = [
        ("0", _("off")),
        ("3600", "1 h"),
        ("21600", "6 h"),
        ("43200", "12 h"),
        ("86400", "24 h"),])
    def setOldEPGBuffer(configElement):
            from enigma import eEPGCache
            eEPGCache.getInstance().setOldEPG(int(config.usage.show_old_epg.getValue()))
    config.usage.show_old_epg.addNotifier(setOldEPGBuffer)

    config.usage.epg_buffer = ConfigInteger(default = 14, limits = (1, 28))
    def setEPGBufferDays(configElement):
            from enigma import eEPGCache
            eEPGCache.getInstance().setEPGBuffer(config.usage.epg_buffer.getValue())
    config.usage.epg_buffer.addNotifier(setEPGBufferDays)
    epg_choices = [
        ("eventview", _("Event Description")),
        ("singleepg", _("Single Service EPG")),
        ("multiepg", _("Multi EPG")),
        ("epgbar", _("Service EPGBar"))]
    if os.path.exists('/usr/lib/enigma2/python/Plugins/Extensions/GraphMultiEPG/plugin.py'):
        epg_choices.append(("graphicalmultiepg", _("Graphical Multi EPG")))
    config.usage.epg_default_view = ConfigSelection(default = "eventview", choices = epg_choices)

    config.usage.enable_tt_caching = ConfigYesNo(default = True)
    def EnableTtCachingChanged(configElement):
        setEnableTtCachingOnOff(int(configElement.value))
    config.usage.enable_tt_caching.addNotifier(EnableTtCachingChanged)

    config.usage.stop_seek_eof = ConfigSelection(default = "20", choices = [
        ("0", _("off")),
        ("10", "10 " + _("seconds")),
        ("20", "20 " + _("seconds")),
        ("30", "30 " + _("seconds")),
        ("60", "60 " + _("seconds"))])

    def updateVideoDirChoice(configElement):
        tmp = configElement.value
        tmp.append(("off", _("off")))
        tmp.append(("last_video", _("last video")))
        tmp.append(("latest_movies", _("latest movies")))
        tmp.append(("all_movies", _("All movies")))
        if (config.movielist.start_videodir.value, config.movielist.start_videodir.value) in tmp:
            default = config.movielist.start_videodir.value
        else:
            default = "last_video"
        config.movielist.start_videodir.setChoices(tmp, default)
    tmp = []
    for x in config.movielist.videodirs.value:
        tmp.append((x,x))
    tmp.append(("off", _("off")))
    tmp.append(("last_video", _("last video")))
    tmp.append(("latest_movies", _("latest movies")))
    tmp.append(("all_movies", _("All movies")))
    config.movielist.start_videodir = ConfigSelection(default = "last_video", choices = tmp)
    config.movielist.videodirs.addNotifier(updateVideoDirChoice)
    config.usage.movielist_folder_based_config = ConfigYesNo(default = True)
    config.usage.movielist_support_pig = ConfigYesNo(default = True)
    config.usage.movielist_last_played_movie = ConfigText(default = "")
    config.usage.movielist_select_last_movie = ConfigYesNo(default = True)
    config.usage.movielist_resume_at_eof = ConfigYesNo(default = True)
    config.usage.movielist_show_cover = ConfigYesNo(default = True)
    config.usage.movielist_show_dir = ConfigYesNo(default = True)
    config.usage.movielist_show_trash_dir = ConfigYesNo(default = False)
    config.usage.movielist_use_trash_dir = ConfigYesNo(default = False)
    config.usage.movielist_show_icon = ConfigYesNo(default = True)
    config.usage.movielist_show_color = ConfigYesNo(default = True)
    config.usage.movielist_show_picon = ConfigYesNo(default = False)
    config.usage.movielist_show_channel_info = ConfigYesNo(default = True)
    config.usage.movielist_show_recording_date = ConfigYesNo(default = True)
    config.usage.movielist_show_file_size = ConfigYesNo(default = True)
    config.usage.movielist_show_folder_info = ConfigYesNo(default = True)
    config.usage.movielist_show_folder_info_new = ConfigYesNo(default = True)
    config.usage.movielist_show_folder_info_only_new = ConfigYesNo(default = True)
    config.usage.movielist_show_folder_info_sort_by_new = ConfigYesNo(default = True)
    config.usage.movielist_show_folder_info_dirs = ConfigYesNo(default = False)
    config.usage.movielist_show_folder_info_left = ConfigYesNo(default = False)
    config.usage.movielist_hide_timeshift_files = ConfigYesNo(default = False)
    config.usage.movielist_only_day = ConfigYesNo(default = True)
    config.usage.movielist_show_last_stop_time = ConfigYesNo(default = False)
    config.usage.movielist_show_duration = ConfigYesNo(default = True)
    config.usage.movielist_duration_in_min = ConfigYesNo(default = True)
    config.usage.movielist_progress_seen = ConfigInteger(default = 80, limits = (40, 99))
    config.usage.movielist_leave_exit = ConfigYesNo(default = True)
    config.usage.movielist_ask_movie_del = ConfigYesNo(default = False)
    config.usage.movielist_show_progress = ConfigSelection(default = "progress_bar", choices = [
        ("progress_bar", _("progress bar")),
        ("progress_percent", _("percent")),
        ("progress_calculate", _("only calculate")),
        ("progress_off", _("off"))])
    config.usage.timerlist_show_icon = ConfigYesNo(default = True)
    config.usage.timerlist_show_epg = ConfigYesNo(default = True)
    config.usage.timerlist_style = ConfigSelection(default = "0", choices = [
        ("0", _("Default")),
        ("1", _("Style") + " 1"),
        ("2", _("Style") + " 2"),
        ("3", _("Style") + " 3"),
        ("4", _("Style") + " 4"),
        ("5", _("Style") + " 5"),])
    config.usage.channelzap_w_bouquet = ConfigYesNo(default = False)
    config.usage.show_favourites_w_bouquet = ConfigSelection(default = "down", choices = [("down", _("Channel -")), ("up", _("Channel +")), ("off", _("off"))])
    config.usage.show_servicelist_at_modeswitch = ConfigYesNo(default = False)
    config.usage.use_pig = ConfigYesNo(default = False)
    config.usage.use_extended_pig = ConfigYesNo(default = False)
    config.usage.use_extended_pig_channelselection = ConfigYesNo(default = False)
    config.usage.show_infobar_on_splitscreen = ConfigYesNo(default = False)
    pip_modes = [("splitscreen", _("Split Screen")), ("audiozap", _("Audio Zap")), ("pip", _("Picture in Picture"))]
    config.usage.default_pip_mode = ConfigSelection(default = "splitscreen", choices = pip_modes)
    config.usage.default_zero_double_click_mode = ConfigSelection(default = "pip", choices = pip_modes)
    default_timeout = SystemInfo["CanPiP"] and 500 or 50
    config.usage.zero_doubleclick_timeout = ConfigInteger(default = default_timeout, limits = (50, 5000))
    config.usage.zap_pip = ConfigYesNo(default = True)
    config.usage.zap_before_record = ConfigYesNo(default = False)
    config.usage.zap_notification_record = ConfigYesNo(default = True)
    if SystemInfo["CanPiP"]:
        config.usage.pip_in_EPGBar = ConfigYesNo(default = True)
    else:
        config.usage.pip_in_EPGBar = ConfigYesNo(default = False)
    config.usage.picon_dir = ConfigDirectory(default = "/usr/share/enigma2/picon")
    config.usage.picon_scale = ConfigYesNo(default = True)
    config.usage.sort_menu_byname = ConfigYesNo(default = False)
    config.usage.sort_plugins_byname = ConfigYesNo(default = True)
    config.usage.plugins_sort_mode = ConfigSelection(default = "user", choices = [
        ("a_z", _("alphabetical")),
        ("default", _("Default")),
        ("user", _("user defined")),])
    config.usage.plugin_sort_weight = ConfigDictionarySet()
    config.usage.menu_sort_mode = ConfigSelection(default = "user", choices = [
        ("a_z", _("alphabetical")),
        ("default", _("Default")),
        ("user", _("user defined")),])
    config.usage.menu_sort_weight = ConfigDictionarySet(default = { "mainmenu" : {"submenu" : {} }})
    config.usage.numberzap_timeout = ConfigInteger(default = 3000, limits = (100, 20000))
    config.usage.numberzap_show_servicename = ConfigYesNo(default = True)
    config.usage.numberzap_show_picon = ConfigYesNo(default = True)
    config.usage.startup_service_leavestandby = ConfigYesNo(default = False)
    config.usage.overzap_notplayable = ConfigYesNo(default = True)
    config.usage.disable_tuner_error_popup = ConfigYesNo(default = False)
    config.usage.disable_infobar_timeout_okbutton = ConfigYesNo(default = False)
    config.usage.ask_timer_file_del = ConfigYesNo(default = True)
    config.usage.record_file_name_date_at_end = ConfigYesNo(default = False)
    config.usage.silent_rec_mode = ConfigYesNo(default = True)
    config.usage.vfd_scroll_delay = ConfigSelection(default = "10000", choices = [
        ("10000", "10 " + _("seconds")),
        ("20000", "20 " + _("seconds")),
        ("30000", "30 " + _("seconds")),
        ("60000", "1 " + _("minute")),
        ("300000", "5 " + _("minutes")),
        ("noscrolling", _("off"))])
    config.usage.vfd_scroll_speed = ConfigSelection(default = "300", choices = [
        ("500", _("slow")),
        ("300", _("normal")),
        ("100", _("fast"))])

    def get_default_RC():
        device = HardwareInfoVu().get_device_name()
        if device =="duo2":
            return "2"
        elif device == "ultimo":
            return "1"
        return "0"

    config.usage.rc_style = ConfigSelection(default = get_default_RC(), choices = [
        ("0", "Vu+ 1 (Duo, Solo, Uno, Solo2)"),
        ("1", "Vu+ 2 (Ultimo)"),
        ("2", "Vu+ 3 (Duo2)")])
    config.usage.use_force_overwrite = ConfigYesNo(default = True)
    config.usage.use_package_conffile = ConfigYesNo(default = True)
    config.usage.use_rm_force_depends = ConfigYesNo(default = False)
    config.usage.use_rm_autoremove = ConfigYesNo(default = True)
    config.usage.check_for_updates = ConfigInteger(default = 0, limits = (0, 24))
    config.usage.show_notification_for_updates = ConfigYesNo(default = True)
    config.usage.update_available = NoSave(ConfigYesNo(default = False))
    config.usage.blinking_rec_symbol_during_recording = ConfigYesNo(default = True)
    config.usage.enable_hbbtv_autostart = ConfigYesNo(default = True)
    config.subtitles = ConfigSubsection()
    config.subtitles.subtitle_fontcolor = ConfigSelection(default = "0", choices = [
        ("0", _("default")),
        ("1", _("white")),
        ("2", _("yellow")),
        ("3", _("green")),
        ("4", _("cyan")),
        ("5", _("blue")),
        ("6", _("magneta")),
        ("7", _("red")),
        ("8", _("black")) ])
    config.subtitles.subtitle_fontsize  = ConfigSelection(choices = ["%d" % x for x in range(16,101) if not x % 2], default = "20")
    config.subtitles.subtitle_padding_y  = ConfigSelection(choices = ["%d" % x for x in range(2,301) if not x % 2], default = "10")
    config.subtitles.subtitle_bgcolor = ConfigSelection(default = "0", choices = [
        ("0", _("black")),
        ("1", _("red")),
        ("2", _("magneta")),
        ("3", _("blue")),
        ("4", _("cyan")),
        ("5", _("green")),
        ("6", _("yellow")),
        ("7", _("white"))])
    config.subtitles.subtitle_bgopacity = ConfigSelection(default = "225", choices = [
        ("0", _("No transparency")),
        ("25", "10%"),
        ("50", "20%"),
        ("75", "30%"),
        ("100", "40%"),
        ("125", "50%"),
        ("150", "60%"),
        ("175", "70%"),
        ("200", "80%"),
        ("225", "90%"),
        ("255", _("Full transparency"))])
    config.subtitles.subtitle_edgestyle = ConfigSelection(default = "2", choices = [
        ("0", _("None")),
        ("1", _("Raised")),
        ("2", _("Depressed")),
        ("3", _("Uniform"))])
    config.subtitles.subtitle_edgestyle_level = ConfigSelection(choices = ["0", "1", "2", "3", "4", "5"], default = "3")
    config.subtitles.subtitle_opacity = ConfigSelection(default = "0", choices = [
        ("0", _("No transparency")),
        ("75", "25%"),
        ("150", "50%")])
    config.subtitles.subtitle_original_position = ConfigYesNo(default = True)
    config.subtitles.subtitle_alignment = ConfigSelection(choices = [("left", _("left")), ("center", _("center")), ("right", _("right"))], default = "center")
    config.subtitles.subtitle_position = ConfigSelection( choices = ["0", "50", "100", "150", "200", "250", "300", "350", "400", "450", "500", "550", "600"], default = "100")

    config.subtitles.dvb_subtitles_centered = ConfigYesNo(default = False)

    subtitle_delay_choicelist = []
    for i in range(-900000, 1845000, 45000):
        if i == 0:
            subtitle_delay_choicelist.append(("0", _("No delay")))
        else:
            subtitle_delay_choicelist.append((str(i), "%2.1f sec" % (i / 90000.)))
    config.subtitles.subtitle_noPTSrecordingdelay = ConfigSelection(default = "315000", choices = subtitle_delay_choicelist)
    config.subtitles.subtitle_bad_timing_delay = ConfigSelection(default = "0", choices = subtitle_delay_choicelist)
    config.subtitles.subtitle_rewrap = ConfigYesNo(default = False)
    config.subtitles.colourise_dialogs = ConfigYesNo(default = False)
    config.subtitles.pango_subtitle_fontswitch = ConfigYesNo(default = True)
    config.subtitles.pango_subtitles_delay = ConfigSelection(default = "0", choices = subtitle_delay_choicelist)
    config.subtitles.pango_subtitles_fps = ConfigSelection(default = "1", choices = [
        ("1", _("Original")),
        ("23976", _("23.976")),
        ("24000", _("24")),
        ("25000", _("25")),
        ("29970", _("29.97")),
        ("30000", _("30"))])
    config.subtitles.pango_autoturnon = ConfigYesNo(default = True)

    debug_choices = [("off", _("off")),
        ("console", _("Console")),
        ("file", _("File")),
        ("fileloop", _("File (loop)")),
        ("console|file", _("Console & File")),
        ("console|fileloop", _("Console & File (loop)")),]
    config.usage.debug_config = ConfigSelection(default = "off_", choices = debug_choices)
    debug_file = "/etc/enigma2/dvbapp2debug.conf"
    val = "off"
    if os.path.exists(debug_file):
        f = open(debug_file, "r")
        lines = f.readlines()
        f.close()
        if lines and len(lines):
            val = lines[0].strip()
            is_valid = False
            for x in debug_choices:
                if x[0] == val:
                    is_valid = True
                    config.usage.debug_config.value = val
                    break
    config.usage.debug_config.value = val
    def e2DebugLogChanged(configElement):
        f = "/etc/enigma2/dvbapp2debug.conf"
        if configElement.value == "off":
            if os.path.exists(f):
                os.remove(f)
            eInitializeDebugOutput()
        else:
            with open(f, "w") as o_f:
                o_f.write(str(configElement.value) + "\n")
            if o_f.closed:
                eInitializeDebugOutput()
    config.usage.debug_config.addNotifier(e2DebugLogChanged, initial_call = False, immediate_feedback = False)
# VTI Settings end

    def updateEraseSpeed(el):
        eBackgroundFileEraser.getInstance().setEraseSpeed(int(el.value))

    def updateEraseFlags(el):
        eBackgroundFileEraser.getInstance().setEraseFlags(int(el.value))

    config.misc.erase_speed = ConfigSelection(default='20', choices=[('10', '10 MB/s'),
     ('20', '20 MB/s'),
     ('50', '50 MB/s'),
     ('100', '100 MB/s')])
    config.misc.erase_speed.addNotifier(updateEraseSpeed, immediate_feedback=False)
    config.misc.erase_flags = ConfigSelection(default='1', choices=[('0', _('Disable')), ('1', _('Internal hdd only')), ('3', _('Everywhere'))])
    config.misc.erase_flags.addNotifier(updateEraseFlags, immediate_feedback=False)
    if SystemInfo['ZapMode']:

        def setZapmode(el):
            open(SystemInfo['ZapMode'], 'w').write(el.value)

        config.misc.zapmode = ConfigSelection(default='mute', choices=[('mute', _('Black screen')),
         ('hold', _('Hold screen')),
         ('mutetilllock', _('Black screen till locked')),
         ('holdtilllock', _('Hold till locked'))])
        config.misc.zapmode.addNotifier(setZapmode, immediate_feedback=False)
    if SystemInfo['VFD_scroll_repeats']:

        def scroll_repeats(el):
            open(SystemInfo['VFD_scroll_repeats'], 'w').write(el.value)

        choicelist = []
        for i in range(1, 11, 1):
            choicelist.append(str(i))

        config.usage.vfd_scroll_repeats = ConfigSelection(default='3', choices=choicelist)
        config.usage.vfd_scroll_repeats.addNotifier(scroll_repeats, immediate_feedback=False)
    if SystemInfo['VFD_scroll_delay']:

        def scroll_delay(el):
            open(SystemInfo['VFD_scroll_delay'], 'w').write(el.value)

        choicelist = []
        for i in range(0, 1001, 50):
            choicelist.append(str(i))

        config.usage.vfd_scroll_delay = ConfigSelection(default='150', choices=choicelist)
        config.usage.vfd_scroll_delay.addNotifier(scroll_delay, immediate_feedback=False)
    if SystemInfo['VFD_initial_scroll_delay']:

        def initial_scroll_delay(el):
            open(SystemInfo['VFD_initial_scroll_delay'], 'w').write(el.value)

        choicelist = []
        for i in range(0, 20001, 500):
            choicelist.append(str(i))

        config.usage.vfd_initial_scroll_delay = ConfigSelection(default='1000', choices=choicelist)
        config.usage.vfd_initial_scroll_delay.addNotifier(initial_scroll_delay, immediate_feedback=False)
    if SystemInfo['VFD_final_scroll_delay']:

        def final_scroll_delay(el):
            open(SystemInfo['VFD_final_scroll_delay'], 'w').write(el.value)

        choicelist = []
        for i in range(0, 20001, 500):
            choicelist.append(str(i))

        config.usage.vfd_final_scroll_delay = ConfigSelection(default='1000', choices=choicelist)
        config.usage.vfd_final_scroll_delay.addNotifier(final_scroll_delay, immediate_feedback=False)
    if SystemInfo['HasForceLNBOn']:

        def forceLNBPowerChanged(configElement):
            open(SystemInfo['HasForceLNBOn'], 'w').write(configElement.value)

        config.misc.forceLnbPower = ConfigSelection(default='off', choices=[('on', _('Yes')), ('off', _('No'))])
        config.misc.forceLnbPower.addNotifier(forceLNBPowerChanged)
    if SystemInfo['HasForceToneburst']:

        def forceToneBurstChanged(configElement):
            open(SystemInfo['HasForceToneburst'], 'w').write(configElement.value)

        config.misc.forceToneBurst = ConfigSelection(default='disable', choices=[('enable', _('Yes')), ('disable', _('No'))])
        config.misc.forceToneBurst.addNotifier(forceToneBurstChanged)
    if SystemInfo['HasBypassEdidChecking']:

        def setHasBypassEdidChecking(configElement):
            open(SystemInfo['HasBypassEdidChecking'], 'w').write(configElement.value)

        config.av.bypassEdidChecking = ConfigSelection(default='00000000', choices=[('00000001', _('Yes')), ('00000000', _('No'))])
        config.av.bypassEdidChecking.addNotifier(setHasBypassEdidChecking)
    config.subtitles = ConfigSubsection()
    config.subtitles.ttx_subtitle_colors = ConfigSelection(default='1', choices=[('0', _('original')), ('1', _('white')), ('2', _('yellow'))])
    config.subtitles.ttx_subtitle_original_position = ConfigYesNo(default=False)
    config.subtitles.subtitle_position = ConfigSelection(choices=['0',
     '10',
     '20',
     '30',
     '40',
     '50',
     '60',
     '70',
     '80',
     '90',
     '100',
     '150',
     '200',
     '250',
     '300',
     '350',
     '400',
     '450'], default='50')
    config.subtitles.subtitle_alignment = ConfigSelection(choices=[('left', _('left')), ('center', _('center')), ('right', _('right'))], default='center')
    config.subtitles.subtitle_rewrap = ConfigYesNo(default=False)
    config.subtitles.colourise_dialogs = ConfigYesNo(default=False)
    config.subtitles.subtitle_borderwidth = ConfigSelection(choices=['1',
     '2',
     '3',
     '4',
     '5'], default='3')
    config.subtitles.subtitle_fontsize = ConfigSelection(choices=[ '%d' % x for x in range(16, 101) if not x % 2 ], default='40')
    config.subtitles.showbackground = ConfigYesNo(default=False)
    subtitle_delay_choicelist = []
    for i in range(-900000, 1845000, 45000):
        if i == 0:
            subtitle_delay_choicelist.append(('0', _('No delay')))
        else:
            subtitle_delay_choicelist.append((str(i), '%2.1f sec' % (i / 90000.0)))

    config.subtitles.subtitle_noPTSrecordingdelay = ConfigSelection(default='315000', choices=subtitle_delay_choicelist)
    config.subtitles.dvb_subtitles_yellow = ConfigYesNo(default=False)
    config.subtitles.dvb_subtitles_original_position = ConfigSelection(default='0', choices=[('0', _('Original')), ('1', _('Fixed')), ('2', _('Relative'))])
    config.subtitles.dvb_subtitles_centered = ConfigYesNo(default=True)
    config.subtitles.subtitle_bad_timing_delay = ConfigSelection(default='0', choices=subtitle_delay_choicelist)
    config.subtitles.dvb_subtitles_backtrans = ConfigSelection(default='0', choices=[('0', _('No transparency')),
     ('25', '10%'),
     ('50', '20%'),
     ('75', '30%'),
     ('100', '40%'),
     ('125', '50%'),
     ('150', '60%'),
     ('175', '70%'),
     ('200', '80%'),
     ('225', '90%'),
     ('255', _('Full transparency'))])
    config.subtitles.pango_subtitle_colors = ConfigSelection(default='1', choices=[('0', _('alternative')), ('1', _('white')), ('2', _('yellow'))])
    config.subtitles.pango_subtitle_fontswitch = ConfigYesNo(default=True)
    config.subtitles.pango_subtitles_delay = ConfigSelection(default='0', choices=subtitle_delay_choicelist)
    config.subtitles.pango_subtitles_fps = ConfigSelection(default='1', choices=[('1', _('Original')),
     ('23976', _('23.976')),
     ('24000', _('24')),
     ('25000', _('25')),
     ('29970', _('29.97')),
     ('30000', _('30'))])
    config.subtitles.pango_autoturnon = ConfigYesNo(default=True)
    config.autolanguage = ConfigSubsection()
    audio_language_choices = [('---', _('None')),
     ('orj dos ory org esl qaa und mis mul ORY ORJ Audio_ORJ', _('Original')),
     ('ara', _('Arabic')),
     ('eus baq', _('Basque')),
     ('bul', _('Bulgarian')),
     ('hrv', _('Croatian')),
     ('ces cze', _('Czech')),
     ('dan', _('Danish')),
     ('dut ndl', _('Dutch')),
     ('eng qaa', _('English')),
     ('est', _('Estonian')),
     ('fin', _('Finnish')),
     ('fra fre', _('French')),
     ('deu ger', _('German')),
     ('ell gre', _('Greek')),
     ('heb', _('Hebrew')),
     ('hun', _('Hungarian')),
     ('ita', _('Italian')),
     ('lav', _('Latvian')),
     ('lit', _('Lithuanian')),
     ('ltz', _('Luxembourgish')),
     ('nor', _('Norwegian')),
     ('pol', _('Polish')),
     ('por dub DUB', _('Portuguese')),
     ('fas per', _('Persian')),
     ('ron rum', _('Romanian')),
     ('rus', _('Russian')),
     ('srp', _('Serbian')),
     ('slk slo', _('Slovak')),
     ('slv', _('Slovenian')),
     ('spa', _('Spanish')),
     ('swe', _('Swedish')),
     ('tha', _('Thai')),
     ('tur Audio_TUR', _('Turkish')),
     ('ukr Ukr', _('Ukrainian'))]

    def setEpgLanguage(configElement):
        eServiceEvent.setEPGLanguage(configElement.value)

    config.autolanguage.audio_epglanguage = ConfigSelection(audio_language_choices[:1] + audio_language_choices[2:], default='---')
    config.autolanguage.audio_epglanguage.addNotifier(setEpgLanguage)

    def setEpgLanguageAlternative(configElement):
        eServiceEvent.setEPGLanguageAlternative(configElement.value)

    config.autolanguage.audio_epglanguage_alternative = ConfigSelection(audio_language_choices[:1] + audio_language_choices[2:], default='---')
    config.autolanguage.audio_epglanguage_alternative.addNotifier(setEpgLanguageAlternative)
    config.autolanguage.audio_autoselect1 = ConfigSelection(choices=audio_language_choices, default='---')
    config.autolanguage.audio_autoselect2 = ConfigSelection(choices=audio_language_choices, default='---')
    config.autolanguage.audio_autoselect3 = ConfigSelection(choices=audio_language_choices, default='---')
    config.autolanguage.audio_autoselect4 = ConfigSelection(choices=audio_language_choices, default='---')
    config.autolanguage.audio_defaultac3 = ConfigYesNo(default=False)
    config.autolanguage.audio_defaultddp = ConfigYesNo(default=False)
    config.autolanguage.audio_usecache = ConfigYesNo(default=True)
    subtitle_language_choices = audio_language_choices[:1] + audio_language_choices[2:]
    config.autolanguage.subtitle_autoselect1 = ConfigSelection(choices=subtitle_language_choices, default='---')
    config.autolanguage.subtitle_autoselect2 = ConfigSelection(choices=subtitle_language_choices, default='---')
    config.autolanguage.subtitle_autoselect3 = ConfigSelection(choices=subtitle_language_choices, default='---')
    config.autolanguage.subtitle_autoselect4 = ConfigSelection(choices=subtitle_language_choices, default='---')
    config.autolanguage.subtitle_hearingimpaired = ConfigYesNo(default=False)
    config.autolanguage.subtitle_defaultimpaired = ConfigYesNo(default=False)
    config.autolanguage.subtitle_defaultdvb = ConfigYesNo(default=False)
    config.autolanguage.subtitle_usecache = ConfigYesNo(default=True)
    config.autolanguage.equal_languages = ConfigSelection(default='15', choices=[('0', _('None')),
     ('1', '1'),
     ('2', '2'),
     ('3', '1,2'),
     ('4', '3'),
     ('5', '1,3'),
     ('6', '2,3'),
     ('7', '1,2,3'),
     ('8', '4'),
     ('9', '1,4'),
     ('10', '2,4'),
     ('11', '1,2,4'),
     ('12', '3,4'),
     ('13', '1,3,4'),
     ('14', '2,3,4'),
     ('15', _('All'))])
    config.streaming = ConfigSubsection()
    config.streaming.stream_ecm = ConfigYesNo(default=False)
    config.streaming.descramble = ConfigYesNo(default=True)
    config.streaming.descramble_client = ConfigYesNo(default=False)
    config.streaming.stream_eit = ConfigYesNo(default=True)
    config.streaming.stream_ait = ConfigYesNo(default=True)
    config.streaming.authentication = ConfigYesNo(default=False)
    config.mediaplayer = ConfigSubsection()
    config.mediaplayer.useAlternateUserAgent = ConfigYesNo(default=False)
    config.mediaplayer.alternateUserAgent = ConfigText(default='')


def updateChoices(sel, choices):
    if choices:
        defval = None
        val = int(sel.value)
        if val not in choices:
            tmp = choices[:]
            tmp.reverse()
            for x in tmp:
                if x < val:
                    defval = str(x)
                    break

        sel.setChoices(map(str, choices), defval)


def preferredPath(path):
    if config.usage.setup_level.index < 2 or path == '<default>':
        return None
    elif path == '<current>':
        return config.movielist.last_videodir.value
    elif path == '<timer>':
        return config.movielist.last_timer_videodir.value
    else:
        return path


def preferredTimerPath():
    return preferredPath(config.usage.timer_path.value)


def preferredInstantRecordPath():
    return preferredPath(config.usage.instantrec_path.value)


def defaultMoviePath():
    return defaultRecordingLocation(config.usage.default_path.value)
