import xbmcaddon
import xbmcplugin
import xbmc
import xbmcgui
import os
import threading
import json
import KodiMonitor
import Utils as utils
from DownloadUtils import DownloadUtils
from PlayUtils import PlayUtils
from ClientInformation import ClientInformation
from LibrarySync import LibrarySync
librarySync = LibrarySync()


# service class for playback monitoring
class Player( xbmc.Player ):

    logLevel = 0
    played_information = {}
    downloadUtils = None
    settings = None
    playStats = {}
    
    def __init__( self, *args ):
        
        self.settings = xbmcaddon.Addon(id='plugin.video.mb3sync')
        self.downloadUtils = DownloadUtils()
        try:
            self.logLevel = int(self.settings.getSetting('logLevel'))   
        except:
            pass        
        self.printDebug("mb3sync Service -> starting playback monitor service")
        self.played_information = {}
        pass    
        
    def printDebug(self, msg, level = 1):
        if(self.logLevel >= level):
            if(self.logLevel == 2):
                try:
                    xbmc.log("mb3sync " + str(level) + " -> " + inspect.stack()[1][3] + " : " + str(msg))
                except UnicodeEncodeError:
                    xbmc.log("mb3sync " + str(level) + " -> " + inspect.stack()[1][3] + " : " + str(msg.encode('utf-8')))
            else:
                try:
                    xbmc.log("mb3sync " + str(level) + " -> " + str(msg))
                except UnicodeEncodeError:
                    xbmc.log("mb3sync " + str(level) + " -> " + str(msg.encode('utf-8')))        
    
    def deleteItem (self, url):
        return_value = xbmcgui.Dialog().yesno(__language__(30091),__language__(30092))
        if return_value:
            self.printDebug('Deleting via URL: ' + url)
            progress = xbmcgui.DialogProgress()
            progress.create(__language__(30052), __language__(30053))
            self.downloadUtils.downloadUrl(url, type="DELETE")
            progress.close()
            xbmc.executebuiltin("Container.Refresh")
            return 1
        else:
            return 0
        
    def hasData(self, data):
        if(data == None or len(data) == 0 or data == "None"):
            return False
        else:
            return True 
    
    def stopAll(self):

        if(len(self.played_information) == 0):
            return 
            
        addonSettings = xbmcaddon.Addon(id='plugin.video.mb3sync')
        self.printDebug("mb3sync Service -> played_information : " + str(self.played_information))
        
        for item_url in self.played_information:
            data = self.played_information.get(item_url)
            
            if(data != None):
                self.printDebug("mb3sync Service -> item_url  : " + item_url)
                self.printDebug("mb3sync Service -> item_data : " + str(data))
                
                deleteurl = data.get("deleteurl")
                runtime = data.get("runtime")
                currentPosition = data.get("currentPosition")
                item_id = data.get("item_id")
                refresh_id = data.get("refresh_id")
                currentFile = data.get("currentfile")
                
                if(refresh_id != None):
                    #todo: trigger update of single item from MB3, for now trigger full playcounts update
                    librarySync.updatePlayCounts()
                
                if(currentPosition != None and self.hasData(runtime)):
                    runtimeTicks = int(runtime)
                    self.printDebug("mb3sync Service -> runtimeticks:" + str(runtimeTicks))
                    percentComplete = (currentPosition * 10000000) / runtimeTicks
                    markPlayedAt = float(90) / 100    

                    self.printDebug("mb3sync Service -> Percent Complete:" + str(percentComplete) + " Mark Played At:" + str(markPlayedAt))
                    self.stopPlayback(data)
                    
                    if (percentComplete > markPlayedAt):
                        gotDeleted = 0
                        if(deleteurl != None and deleteurl != ""):
                            self.printDebug("mb3sync Service -> Offering Delete:" + str(deleteurl))
                            gotDeleted = self.deleteItem(deleteurl)

            
        self.played_information.clear()

        # stop transcoding - todo check we are actually transcoding?
        clientInfo = ClientInformation()
        txt_mac = clientInfo.getMachineId()
        url = ("http://%s:%s/mediabrowser/Videos/ActiveEncodings" % (addonSettings.getSetting('ipaddress'), addonSettings.getSetting('port')))  
        url = url + '?DeviceId=' + txt_mac
        self.downloadUtils.downloadUrl(url, type="DELETE")
    
    def stopPlayback(self, data):
        addonSettings = xbmcaddon.Addon(id='plugin.video.mb3sync')
        
        item_id = data.get("item_id")
        audioindex = data.get("AudioStreamIndex")
        subtitleindex = data.get("SubtitleStreamIndex")
        playMethod = data.get("playmethod")
        currentPosition = data.get("currentPosition")
        positionTicks = str(int(currentPosition * 10000000))
                
        url = ("http://%s:%s/mediabrowser/Sessions/Playing/Stopped" % (addonSettings.getSetting('ipaddress'), addonSettings.getSetting('port')))  
            
        url = url + "?itemId=" + item_id

        url = url + "&canSeek=true"
        url = url + "&PlayMethod=" + playMethod
        url = url + "&QueueableMediaTypes=Video"
        url = url + "&MediaSourceId=" + item_id
        url = url + "&PositionTicks=" + positionTicks   
        if(audioindex != None and audioindex!=""):
          url = url + "&AudioStreamIndex=" + audioindex
            
        if(subtitleindex != None and subtitleindex!=""):
          url = url + "&SubtitleStreamIndex=" + subtitleindex
            
        self.downloadUtils.downloadUrl(url, postBody="", type="POST")    
    
    
    def reportPlayback(self):
        self.printDebug("reportPlayback Called")
        
        currentFile = xbmc.Player().getPlayingFile()
        
        #TODO need to change this to use the one in the data map
        playTime = xbmc.Player().getTime()
        
        data = self.played_information.get(currentFile)
        
        # only report playback if mb3sync has initiated the playback (item_id has value)
        if(data != None and data.get("item_id") != None):
            addonSettings = xbmcaddon.Addon(id='plugin.video.mb3sync')
            
            item_id = data.get("item_id")
            audioindex = data.get("AudioStreamIndex")
            subtitleindex = data.get("SubtitleStreamIndex")
            playMethod = data.get("playmethod")
            paused = data.get("paused")
            
            url = ("http://%s:%s/mediabrowser/Sessions/Playing/Progress" % (addonSettings.getSetting('ipaddress'), addonSettings.getSetting('port')))  
                
            url = url + "?itemId=" + item_id

            url = url + "&canSeek=true"
            url = url + "&PlayMethod=" + playMethod
            url = url + "&QueueableMediaTypes=Video"
            url = url + "&MediaSourceId=" + item_id
            
            url = url + "&PositionTicks=" + str(int(playTime * 10000000))   
                
            if(audioindex != None and audioindex!=""):
              url = url + "&AudioStreamIndex=" + audioindex
                
            if(subtitleindex != None and subtitleindex!=""):
              url = url + "&SubtitleStreamIndex=" + subtitleindex
            
            if(paused == None):
                paused = "false"
            url = url + "&IsPaused=" + paused
           
            self.downloadUtils.downloadUrl(url, postBody="", type="POST")
    
    def onPlayBackPaused( self ):
        currentFile = xbmc.Player().getPlayingFile()
        self.printDebug("PLAYBACK_PAUSED : " + currentFile)
        if(self.played_information.get(currentFile) != None):
            self.played_information[currentFile]["paused"] = "true"
        self.reportPlayback()
    
    def onPlayBackResumed( self ):
        currentFile = xbmc.Player().getPlayingFile()
        self.printDebug("PLAYBACK_RESUMED : " + currentFile)
        if(self.played_information.get(currentFile) != None):
            self.played_information[currentFile]["paused"] = "false"
        self.reportPlayback()
    
    def onPlayBackSeek( self, time, seekOffset ):
        self.printDebug("PLAYBACK_SEEK")
        self.reportPlayback()
        
    def onPlayBackStarted( self ):
        # Will be called when xbmc starts playing a file
        WINDOW = xbmcgui.Window( 10000 )
        self.stopAll()
        addonSettings = xbmcaddon.Addon(id='plugin.video.mb3sync')
        
        if xbmc.Player().isPlaying():
            currentFile = xbmc.Player().getPlayingFile()
            self.printDebug("mb3sync Service -> onPlayBackStarted" + currentFile)
            
            # grab all the info about this item from the stored windows props
            # only ever use the win props here, use the data map in all other places
            deleteurl = WINDOW.getProperty(currentFile + "deleteurl")
            runtime = WINDOW.getProperty(currentFile + "runtimeticks")
            item_id = WINDOW.getProperty(currentFile + "item_id")
            refresh_id = WINDOW.getProperty(currentFile + "refresh_id")
            audioindex = WINDOW.getProperty(currentFile + "AudioStreamIndex")
            subtitleindex = WINDOW.getProperty(currentFile + "SubtitleStreamIndex")
            playMethod = WINDOW.getProperty(currentFile + "playmethod")
            itemType = WINDOW.getProperty(currentFile + "type")
            seekTime = WINDOW.getProperty(currentFile + "seektime")
            if seekTime != "":
                self.seekToPosition(int(seekTime))
            
            if(item_id == None or len(item_id) == 0):
                return
        
            url = ("http://%s:%s/mediabrowser/Sessions/Playing" % (addonSettings.getSetting('ipaddress'), addonSettings.getSetting('port')))  
            
            url = url + "?itemId=" + item_id

            url = url + "&canSeek=true"
            url = url + "&PlayMethod=" + playMethod
            url = url + "&QueueableMediaTypes=Video"
            url = url + "&MediaSourceId=" + item_id
            
            if(audioindex != None and audioindex!=""):
              url = url + "&AudioStreamIndex=" + audioindex
            
            if(subtitleindex != None and subtitleindex!=""):
              url = url + "&SubtitleStreamIndex=" + subtitleindex
            
            self.downloadUtils.downloadUrl(url, postBody="", type="POST")
            
            # save data map for updates and position calls
            data = {}
            data["deleteurl"] = deleteurl
            data["runtime"] = runtime
            data["item_id"] = item_id
            data["refresh_id"] = refresh_id
            data["currentfile"] = currentFile
            data["AudioStreamIndex"] = audioindex
            data["SubtitleStreamIndex"] = subtitleindex
            data["playmethod"] = playMethod
            data["Type"] = itemType
            self.played_information[currentFile] = data
            
            self.printDebug("mb3sync Service -> ADDING_FILE : " + currentFile)
            self.printDebug("mb3sync Service -> ADDING_FILE : " + str(self.played_information))

            # log some playback stats
            if(itemType != None):
                if(self.playStats.get(itemType) != None):
                    count = self.playStats.get(itemType) + 1
                    self.playStats[itemType] = count
                else:
                    self.playStats[itemType] = 1
                    
            if(playMethod != None):
                if(self.playStats.get(playMethod) != None):
                    count = self.playStats.get(playMethod) + 1
                    self.playStats[playMethod] = count
                else:
                    self.playStats[playMethod] = 1
            
            # reset in progress position
            self.reportPlayback()
            
    def GetPlayStats(self):
        return self.playStats
        
    def onPlayBackEnded( self ):
        # Will be called when xbmc stops playing a file
        self.printDebug("mb3sync Service -> onPlayBackEnded")
        self.stopAll()

    def onPlayBackStopped( self ):
        # Will be called when user stops xbmc playing a file
        self.printDebug("mb3sync Service -> onPlayBackStopped")
        self.stopAll()

    def seekToPosition(self, seekTo):
           
        #Jump to resume point
        jumpBackSec = 10
        seekToTime = seekTo - jumpBackSec
        count = 0
        while xbmc.Player().getTime() < (seekToTime - 5) and count < 11: # only try 10 times
            count = count + 1
            xbmc.Player().pause
            xbmc.sleep(100)
            xbmc.Player().seekTime(seekToTime)
            xbmc.sleep(100)
            xbmc.Player().play()