import yaml
import numpy as np
import pandas as pd
import pathlib as pl
from myphdlib.interface.session import SessionBase
from myphdlib.general.labjack import loadLabjackData
from myphdlib.general.labjack import extractLabjackEvent
from myphdlib.extensions.deeplabcut import loadBodypartData
import scipy as sp
from matplotlib import pylab as plt
from scipy.signal import savgol_filter
from myphdlib.general.labjack import filterPulsesFromPhotologicDevice


class GonogoSession(SessionBase):
    """
    """

    def __init__(self, sessionFolder):
        """
        """

        super().__init__(sessionFolder)

        return

    @property
    def fps(self):
        """
        """

        result = list(self.sessionFolderPath.joinpath('videos').glob('*_metadata.yaml'))
        if len(result) != 1:
            raise Exception('Could not locate video acquisition metadata file')
        with open(result.pop(), 'r')  as stream:
            metadata = yaml.full_load(stream)

        for key in metadata.keys():
            if key in ('cam1', 'cam2'):
                if metadata[key]['ismaster']:
                    fps = int(metadata[key]['framerate'])

        return fps
    @property
    def probeMetadata(self):
        """
        """

        result = list(self.sessionFolderPath.joinpath('videos').glob('*ProbeMetadata.txt'))
        if len(result) != 1:
            raise Exception('Could not locate the probe metadata')
        else:
            return result.pop()

    @property
    def rightCameraMovie(self):
        """
        """

        result = list(self.sessionFolderPath.joinpath('videos').glob('*_rightCam-0000.mp4'))
        if len(result) != 1:
            raise Exception('Could not locate the right camera movie')
        else:
            return result.pop()

    @property
    def leftEyePose(self):
        """
        """

        result = list(self.sessionFolderPath.joinpath('videos').glob('*shuffle1*'))
        if len(result) != 1:
            raise Exception('Could not locate the left eye pose estimate')
        else:
            return result.pop()
    @property
    def tonguePose(self):
        """
        """

        result = list(self.sessionFolderPath.joinpath('videos').glob('*licksNov3shuffle1*'))
        if len(result) != 1:
            raise Exception('Could not locate the tongue pose estimate')
        else:
            return result.pop()

    @property
    def rightCameraTimestamps(self):
        """
        """

        result = list(self.sessionFolderPath.joinpath('videos').glob('*rightCam_timestamps.txt'))
        if len(result) != 1:
            raise Exception('Could not locate the right camera timestamps')
        else:
            return result.pop()

    @property
    def leftCameraTimestamps(self):
        """
        """

        result = list(self.sessionFolderPath.joinpath('videos').glob('*leftCam_timestamps.txt'))
        if len(result) != 1:
            raise Exception('Could not locate the left camera timestamps')
        else:
            return result.pop()

    @property
    def labjackFolder(self):
        """
        """

        result = list(self.sessionFolderPath.joinpath('labjack').glob('*dreadd*'))
        if len(result) != 1:
            raise Exception('Could not locate the Labjack folder')
        else:
            return result.pop()

    def _loadLabjackMatrix(self):
        """
        Load labjack matrix into memory and store as attribute
        """

        self._labjackMatrix = None
        labjackDirectory = self.labjackFolder
        labjackData = loadLabjackData(labjackDirectory)


        return labjackData

    def extractProbeTimestamps(self, pulseFilter):
        """
        Extract timestamps of probes from Labjack data and return probe timestamps
        """
        labjackDirectory = self.labjackFolder
        labjackData = loadLabjackData(labjackDirectory)
        timestamps = labjackData[:, 0]
        # probeOnset, probeIndices = extractLabjackEvent(labjackData, 6, edge = 'rising')
        filtered = filterPulsesFromPhotologicDevice(labjackData[:, 6],
            minimumPulseWidthInSeconds=pulseFilter
        )
        probeIndices = np.where(np.diff(filtered) > 0.5)[0]
        probeTimestamps = timestamps[probeIndices]
        self.write(probeTimestamps, 'probeTimestamps')
        return

    def loadProbeTimestamps(self):
        """
        """

        if 'probeTimestamps' not in self.keys():
            raise Exception('Probe timestamps not extracted')
        else:
            return self.read('probeTimestamps')

    def extractFrameTimestamps(self):
        """
        Extract timestamps of frames from Labjack data and return frame timestamps
        """
        labjackDirectory = self.labjackFolder
        labjackData = loadLabjackData(labjackDirectory)
        timestamps = labjackData[:, 0]
        frameOnset, frameIndices = extractLabjackEvent(labjackData, 7, edge = 'both')
        frameTimestamps = timestamps[frameIndices]
        self.write(frameTimestamps, 'frameTimestamps')
        return

    def extractPuffTimestamps(self):
        """
        Extract timestamps of frames from Labjack data and return frame timestamps
        """
        labjackDirectory = self.labjackFolder
        labjackData = loadLabjackData(labjackDirectory)
        timestamps = labjackData[:, 0]
        puffOnset, puffIndices = extractLabjackEvent(labjackData, 8, edge = 'rising')
        puffTimestamps = timestamps[puffIndices]
        self.write(puffTimestamps, 'puffTimestamps')
        return

    def loadFrameTimestamps(self):
        """
        """

        if 'frameTimestamps' not in self.keys():
            raise Exception('Frame timestamps not extracted')
        else:
            return self.read('frameTimestamps')
    
    def loadPuffTimestamps(self):
        """
        """

        if 'puffTimestamps' not in self.keys():
            raise Exception('Puff timestamps not extracted')
        else:
            return self.read('puffTimestamps')
          
          

    def extractLickTimestamps(self):
        """
        Extract timestamps of licks recorded by DLC and synchronized with Labjack data and return lick timestamps
        """
        frameTimestamps = self.loadFrameTimestamps()
        csv = self.tonguePose
        spoutLikelihood = loadBodypartData(csv, bodypart='spout', feature='likelihood')
        M = np.diff(spoutLikelihood, n=1)
        M1 = M*-1
        peaks, _ = sp.signal.find_peaks(M1, height=0.9, threshold=None, distance=None, prominence=None, width=None, wlen=None, rel_height=0.5, plateau_size=None)
        frameIndex = np.arange(len(loadBodypartData(csv, bodypart='spout', feature='likelihood')))
        peakFrames = frameIndex[peaks]
        lickTimestamps = frameTimestamps[peakFrames]
        self.lickTimestamps = lickTimestamps
        return lickTimestamps

    def createLickRaster(self, lickTimestamps):
        """
        Find licks within a given range of each probe and plot in a raster, return plot
        """
        probeTimestamps = self.loadProbeTimestamps()
        L = list()
        for probe in probeTimestamps:
            lickRelative = (self.lickTimestamps - probe)
            mask = np.logical_and(
                lickRelative > -1,
                lickRelative < 5,
            )
            lickRelativeFiltered = lickRelative[mask]
            L.append(lickRelativeFiltered)
        L1 = np.array(L)
        fig, ax = plt.subplots() 
        font = {'size' : 20}
        plt.rc('font', **font)
        plt.gca().invert_yaxis()
        for rowIndex, row in enumerate(L1):
            x = row
            y0 = rowIndex - 0.5
            y1 = rowIndex + 0.5
            ax.vlines(x, y0, y1, color='k')
        ax.set_ylabel('Trial', fontsize="20")
        ax.set_xlabel('Time from probe (sec)', fontsize="20")
        fig.set_figheight(4)
        fig.set_figwidth(12)
        return fig
    
    def createLickRasterCorrected(self, lickTimestamps):
        """
        Find licks within a given range of each probe and plot in a raster, return plot
        """
        probeTimestamps = self.loadFilteredProbes()
        L = list()
        for probe in probeTimestamps:
            lickRelative = (self.lickTimestamps - probe)
            mask = np.logical_and(
                lickRelative > -2,
                lickRelative < 5,
            )
            lickRelativeFiltered = lickRelative[mask]
            L.append(lickRelativeFiltered)
        L1 = np.array(L)
        fig, ax = plt.subplots()
        font = {'size' : 15}
        plt.rc('font', **font)
        plt.gca().invert_yaxis()
        for rowIndex, row in enumerate(L1):
            x = row
            y0 = rowIndex - 0.5
            y1 = rowIndex + 0.5
            ax.vlines(x, y0, y1, color='k')
        ax.set_ylabel('Trial')
        ax.set_xlabel('Time from probe (sec)')
        fig.set_figheight(10)
        fig.set_figwidth(6)
        return fig

    def createSaccadeRaster(self, totalSaccades, lickTimestamps):
        probeTimestamps = self.loadProbeTimestamps()
        L = list()
        L2 = list()
        for sac in totalSaccades:
            lickRelative = (lickTimestamps - sac)
            probeRelative = (probeTimestamps - sac)
            mask = np.logical_and(
                lickRelative > -2,
                lickRelative < 5,
            )
            lickRelativeFiltered = lickRelative[mask]
            L.append(lickRelativeFiltered)
            mask = np.logical_and(
                probeRelative > -2,
                probeRelative < 5,
            )
            probeRelativeFiltered = probeRelative[mask]
            L2.append(probeRelativeFiltered)
        L1 = np.array(L)
        L3 = np.array(L2)
        fig, ax = plt.subplots()
        font = {'size' : 15}
        plt.rc('font', **font)
        plt.gca().invert_yaxis()
        for rowIndex, row in enumerate(L1):
            x = row
            y0 = rowIndex - 0.5
            y1 = rowIndex + 0.5
            ax.vlines(x, y0, y1, color='k')
        ax.set_ylabel('Trial')
        ax.set_xlabel('Time from probe (sec)')
        fig.set_figheight(10)
        fig.set_figwidth(6)
        for rowIndex, row in enumerate(L3):
            x = row
            y0 = rowIndex - 0.5
            y1 = rowIndex + 0.5
            ax.vlines(x, y0, y1, color='r')
        ax.set_ylabel('Trial')
        ax.set_xlabel('Time from probe (sec)')
        fig.set_figheight(10)
        fig.set_figwidth(6)
        return fig
    

    def extractContrastValues(self):
        """
        Reads probe metadata file and zips array of contrast values with probe timestamps, returns zipped list of contrast values
        """
        probeTimestamps = self.loadProbeTimestamps()
        metadata = self.probeMetadata
        fn = open(metadata, 'r'); # open the file
        allText = fn.readlines() # read the lines of text
        text = allText[1:] # remove the header
        contrastValues = []; # initialize
        indNum = 0; # initialize
        for lines in text: # loop through each line and extract the lick value
            #indStart = lines.find('0.');
            indStop = lines.find('0,')
            valueRead = lines[:indStop]
            contrastValues.append(valueRead)
        contrastValues = np.array(contrastValues)
        limit = len(probeTimestamps)
        contrastValues = contrastValues[:limit]
        self.contrastValues = contrastValues
        return contrastValues
    
    def sortUniqueContrasts(self, contrastValues):
        """
        Sorts the array of contrast values into a dictionary with 4 keys representing the unique contrast values, returns the dictionary
        """
        probeTimestamps = self.loadProbeTimestamps()
        dictionary = dict() # Initialize an empty dictionary
        uniqueContrastValues = np.unique(self.contrastValues) # Find the unique constrast values
        for uniqueContrastValue in uniqueContrastValues: # Iterterate through the unique contrast values
            mask = self.contrastValues == uniqueContrastValue # Create a mask for each unique contrast value
            dictionary[uniqueContrastValue] = np.array(probeTimestamps)[mask]
        self.dictionary = dictionary
        return dictionary

    def sortUniqueContrastsCorrected(self):
        """
        Sorts the array of contrast values into a dictionary with 4 keys representing the unique contrast values, returns the dictionary
        """
        probeTimestamps = self.loadFilteredProbes()
        filteredContrast = self.loadFilteredContrast()
        dictionary = dict() # Initialize an empty dictionary
        uniqueContrastValues = np.unique(filteredContrast) # Find the unique constrast values
        for uniqueContrastValue in uniqueContrastValues: # Iterterate through the unique contrast values
            mask = filteredContrast == uniqueContrastValue # Create a mask for each unique contrast value
            dictionary[uniqueContrastValue] = np.array(probeTimestamps)[mask]
        self.dictionary = dictionary
        return dictionary

    def createContrastRaster(self, lickTimestamps, dictionary):
        """
        Create a raster sorted by contrast, returns arrays to plot
        """
        probeTimestamps = self.loadProbeTimestamps()
        list1 = list()
        list8 = list()
        list6 = list()
        list5 = list()
        listtemp = list()

        for key in self.dictionary:
            for probeTimestamp in self.dictionary[key]:
                lickRelative = (self.lickTimestamps - probeTimestamp)
                mask = np.logical_and(
                    lickRelative > -2,
                    lickRelative < 5,
                )
                lickRelativeFiltered = lickRelative[mask]
    
                listtemp.append(lickRelativeFiltered)

            if key == '0.80':
                list1 = listtemp
                array1 = np.array(list1)
                listtemp.clear()
            if key == '0.60':
                list8 = listtemp
                array8 = np.array(list8)
                listtemp.clear()
            if key == '0.55':
                list6 = listtemp
                array6 = np.array(list6)
                listtemp.clear()
            if key == '0.50':
                list5 = listtemp
                array5 = np.array(list5)
                listtemp.clear()
        self.array1 = array1
        self.array8 = array8
        self.array6 = array6
        self.array5 = array5
        return array1, array8, array6, array5

    def createContrastRasterCorrected(self, lickTimestamps, dictionary):
        """
        Create a raster sorted by contrast, returns arrays to plot
        """
        probeTimestamps = self.loadFilteredProbes()
        list1 = list()
        list8 = list()
        list6 = list()
        list5 = list()
        listtemp = list()

        for key in self.dictionary:
            for probeTimestamp in self.dictionary[key]:
                lickRelative = (self.lickTimestamps - probeTimestamp)
                mask = np.logical_and(
                    lickRelative > -2,
                    lickRelative < 5,
                )
                lickRelativeFiltered = lickRelative[mask]
    
                listtemp.append(lickRelativeFiltered)

            if key == '0.80':
                list1 = listtemp
                array1 = np.array(list1)
                listtemp.clear()
            if key == '0.60':
                list8 = listtemp
                array8 = np.array(list8)
                listtemp.clear()
            if key == '0.55':
                list6 = listtemp
                array6 = np.array(list6)
                listtemp.clear()
            if key == '0.50':
                list5 = listtemp
                array5 = np.array(list5)
                listtemp.clear()
        self.array1 = array1
        self.array8 = array8
        self.array6 = array6
        self.array5 = array5
        return array1, array8, array6, array5

    def plotContrastRaster(self, array1, array8, array6, array5):
        """
        Actually plots the contrast raster
        """        
        fig, ax = plt.subplots()
        for rowIndex, row in enumerate(self.array1):
            x = row
            y0 = rowIndex - 0.5
            y1 = rowIndex + 0.5
            ax.vlines(x, y0, y1, color='k')
        ax.set_ylabel('Trial')
        ax.set_xlabel('Time (sec)')
        fig.set_figheight(10)
        fig.set_figwidth(6)
        for rowIndex1, row1 in enumerate(self.array8):
            x = row1
            y0 = rowIndex + (rowIndex1 - 0.5)
            y1 = rowIndex + (rowIndex1 + 0.5)
            ax.vlines(x, y0, y1, color='b')
        for rowIndex2, row2 in enumerate(self.array6):
            x = row2
            y0 = rowIndex + rowIndex1 + (rowIndex2 - 0.5)
            y1 = rowIndex + rowIndex1 + (rowIndex2 + 0.5)
            ax.vlines(x, y0, y1, color='g')
        for rowIndex3, row3 in enumerate(self.array5):
            x = row3
            y0 = rowIndex + rowIndex1 + rowIndex2 + (rowIndex3 - 0.5)
            y1 = rowIndex + rowIndex1 + rowIndex2 + (rowIndex3 + 0.5)
            ax.vlines(x, y0, y1, color='r')
        return fig

    def extractSaccadeTimestamps(self):
        """
        Extract indices of saccades and use frame timestamps to extract total saccade timestamps, not nasal vs temporal
        """
        frameTimestamps = self.loadFrameTimestamps()
        res = self.read('saccadeClassificationResults')
        nasalIndices = res['left']['nasal']['indices']
        temporalIndices = res['left']['temporal']['indices']
        nasalSaccades = frameTimestamps[nasalIndices]
        temporalSaccades = frameTimestamps[temporalIndices]
        totalSaccades = np.concatenate((nasalSaccades, temporalSaccades))
        self.totalSaccades = totalSaccades 
        return totalSaccades

    def findFilteredIndices(self, lickTimestamps):
        """
        Eliminate disengaged trials 
        """
        reactionTimes = list()
        probeTimestamps = self.loadProbeTimestamps()
        frameTimestamps = self.loadFrameTimestamps()
        for probe in probeTimestamps:
            reactionTimeList = (self.lickTimestamps - probe)
            reactionList = list()
            for reaction in reactionTimeList:
                if reaction > 0:
                    reactionList.append(reaction)
                else:
                    reactionList.append(15)
            reactionTime = min(reactionList)
            reactionTimes.append(reactionTime)
        reactionTimes = np.array(reactionTimes)
        smoothed = sp.signal.savgol_filter(reactionTimes, 15, 3)
        zipFilter = zip(probeTimestamps, smoothed)
        filterIndices = list()
        for index, (timestamp, threshold) in enumerate(zipFilter):
            if threshold < 13:
                filterIndices.append(index)
        filterIndices = np.array(filterIndices)
        self.filterIndices = filterIndices
        return filterIndices

    def correctProbeTimestamps(self, filterIndices):
        probeTimestamps = self.loadProbeTimestamps()
        probeTimestampsCorrected = probeTimestamps[self.filterIndices]
        self.probeTimestampsCorrected = probeTimestampsCorrected
        return probeTimestampsCorrected
    
    def correctProbeTimestamps2(self, x, y):
        probeTimestamps = self.loadProbeTimestamps()
        filteredProbes = probeTimestamps[x:y]
        self.filteredProbes = filteredProbes
        self.write(filteredProbes, 'filteredProbes')
        return 

    def correctContrastValues2(self, contrastValues, x, y):
        filteredContrast = contrastValues[x:y]
        self.filteredContrast = filteredContrast
        self.write(filteredContrast, 'filteredContrast')
        return 

    def loadFilteredProbes(self):
        if 'filteredProbes' not in self.keys():
            raise Exception('filtered probes not extracted')
        else:
            return self.read('filteredProbes')

    def loadFilteredContrast(self):
        if 'filteredContrast' not in self.keys():
            raise Exception('filtered contrasts not extracted')
        else:
            return self.read('filteredContrast')

    def correctContrastValues(self, filterIndices, contrastValues):
        contrastValuesCorrected = self.contrastValues[self.filterIndices]
        self.contrastValuesCorrected = contrastValuesCorrected
        return contrastValuesCorrected


    def createZippedList(self, totalSaccades):
        """
        Create a boolean variable to determine whether trial is perisaccadic and create zipped list of probetimestamps, contrast values, and boolean variable
        """
        probeTimestamps = self.loadProbeTimestamps()
        perisaccadicProbeBool = list()
        for probe in probeTimestamps:
            saccadesRelative = (self.totalSaccades - probe)
            mask = np.logical_and(
                saccadesRelative > -0.05,
                saccadesRelative < 0.05
            )
            perisaccades = saccadesRelative[mask]
            if any(perisaccades):
                perisaccadicTrial = True
            else:
                perisaccadicTrial = False
            perisaccadicProbeBool.append(perisaccadicTrial)
    
        perisaccadicProbeBool = np.array(perisaccadicProbeBool)
        zipped3 = list(zip(probeTimestamps, self.contrastValues, puffProbeBool))
        self.zipped3 = zipped3
        self.perisaccadicProbeBool = perisaccadicProbeBool
        return zipped3, perisaccadicProbeBool

    def createZippedProbeList(self):
        """
        Create a boolean variable to determine whether trial is perisaccadic and create zipped list of probetimestamps, contrast values, and boolean variable
        """
        probeTimestamps = self.loadProbeTimestamps()
        puffTimestamps = self.loadPuffTimestamps()
        puffProbeBool = list()
        for probe in probeTimestamps:
            puffRelative = (puffTimestamps - probe)
            mask = np.logical_and(
                puffRelative > -1,
                puffRelative < 1
            )
            peripuffsaccades = puffRelative[mask]
            if any(peripuffsaccades):
                puffTrial = True
            else:
                puffTrial = False
            puffProbeBool.append(puffTrial)
    
        puffProbeBool = np.array(puffProbeBool)

        self.puffProbeBool = puffProbeBool
        return puffProbeBool

    def createZippedProbeListCorrected(self):
        """
        Create a boolean variable to determine whether trial is perisaccadic and create zipped list of probetimestamps, contrast values, and boolean variable
        """
        probeTimestamps = self.loadFilteredProbes()
        puffTimestamps = self.loadPuffTimestamps()
        puffProbeBool = list()
        for probe in probeTimestamps:
            puffRelative = (puffTimestamps - probe)
            mask = np.logical_and(
                puffRelative > -1,
                puffRelative < 1
            )
            peripuffsaccades = puffRelative[mask]
            if any(peripuffsaccades):
                puffTrial = True
            else:
                puffTrial = False
            puffProbeBool.append(puffTrial)
    
        puffProbeBool = np.array(puffProbeBool)

        self.puffProbeBool = puffProbeBool
        return puffProbeBool


    def createZippedPuffList(self):
        """
        Create a boolean variable to determine whether trial is perisaccadic and create zipped list of probetimestamps, contrast values, and boolean variable
        """
        probeTimestamps = self.loadProbeTimestamps()
        puffTimestamps = self.loadPuffTimestamps()
        puffProbeBool2 = list()
        for puff in puffTimestamps:
            probeRelative = (probeTimestamps - puff)
            mask = np.logical_and(
                probeRelative > -1,
                probeRelative < 1
            )
            peripuffsaccades2 = probeRelative[mask]
            if any(peripuffsaccades2):
                probeTrial = True
            else:
                probeTrial = False
            puffProbeBool2.append(probeTrial)
    
        puffProbeBool2 = np.array(puffProbeBool2)

        self.puffProbeBool2 = puffProbeBool2
        return puffProbeBool2

    def createZippedPuffListCorrected(self):
        """
        Create a boolean variable to determine whether trial is perisaccadic and create zipped list of probetimestamps, contrast values, and boolean variable
        """
        probeTimestamps = self.loadFilteredProbes()
        puffTimestamps = self.loadPuffTimestamps()
        puffProbeBool2 = list()
        for puff in puffTimestamps:
            probeRelative = (probeTimestamps - puff)
            mask = np.logical_and(
                probeRelative > -1,
                probeRelative < 1
            )
            peripuffsaccades2 = probeRelative[mask]
            if any(peripuffsaccades2):
                probeTrial = True
            else:
                probeTrial = False
            puffProbeBool2.append(probeTrial)
    
        puffProbeBool2 = np.array(puffProbeBool2)

        self.puffProbeBool2 = puffProbeBool2
        return puffProbeBool2


    def createZippedListCorrected(self, totalSaccades):
        """
        Create a boolean variable to determine whether trial is perisaccadic and create zipped list of probetimestamps, contrast values, and boolean variable
        """
        probeTimestamps = self.loadFilteredProbes()
        filteredContrast = self.loadFilteredContrast()
        perisaccadicProbeBool = list()
        for probe in probeTimestamps:
            saccadesRelative = (self.totalSaccades - probe)
            mask = np.logical_and(
                saccadesRelative > -0.05,
                saccadesRelative < 0.05
            )
            perisaccades = saccadesRelative[mask]
            if any(perisaccades):
                perisaccadicTrial = True
            else:
                perisaccadicTrial = False
            perisaccadicProbeBool.append(perisaccadicTrial)
    
        perisaccadicProbeBool = np.array(perisaccadicProbeBool)

        zipped3 = list(zip(probeTimestamps, filteredContrast, perisaccadicProbeBool))
        self.zipped3 = zipped3
        self.perisaccadicProbeBool = perisaccadicProbeBool
        return zipped3, perisaccadicProbeBool

    def createPeriAndExtraSaccadicLists(self, perisaccadicProbeBool, contrastValues):
        """
        Based on boolean variable, separates probetimestamps and contrast values into zipped lists of perisaccadic and extrasaccadic trials
        """
        probeTimestamps = self.loadProbeTimestamps()
        listPT = list()
        listCT = list()
        listPF = list()
        listCF = list()
        probeBoolIndex = 0
        for probeBool in self.perisaccadicProbeBool:
            if probeBool == True:
                listPT.append(probeTimestamps[probeBoolIndex])
                listCT.append(contrastValues[probeBoolIndex])
            else:
                listPF.append(probeTimestamps[probeBoolIndex])
                listCF.append(contrastValues[probeBoolIndex])
            probeBoolIndex = probeBoolIndex + 1

        zipTrue = zip(listCT, listPT)
        zipFalse = zip(listCF, listPF)
        self.listCT = listCT
        self.listPT = listPT
        self.listCF = listCF
        self.listPF = listPF
        self.zipTrue = zipTrue
        self.zipFalse = zipFalse
        return zipTrue, zipFalse, listCT, listPT, listCF, listPF

    def createPeriAndExtraSaccadicListsCorrected(self, perisaccadicProbeBool):
        """
        Based on boolean variable, separates probetimestamps and contrast values into zipped lists of perisaccadic and extrasaccadic trials
        """
        probeTimestamps = self.loadFilteredProbes()
        filteredContrast = self.loadFilteredContrast()
        listPT = list()
        listCT = list()
        listPF = list()
        listCF = list()
        probeBoolIndex = 0
        for probeBool in self.perisaccadicProbeBool:
            if probeBool == True:
                listPT.append(probeTimestamps[probeBoolIndex])
                listCT.append(filteredContrast[probeBoolIndex])
            else:
                listPF.append(probeTimestamps[probeBoolIndex])
                listCF.append(filteredContrast[probeBoolIndex])
            probeBoolIndex = probeBoolIndex + 1

        zipTrue = zip(listCT, listPT)
        zipFalse = zip(listCF, listPF)
        self.listCT = listCT
        self.listPT = listPT
        self.listCF = listCF
        self.listPF = listPF
        self.zipTrue = zipTrue
        self.zipFalse = zipFalse
        return zipTrue, zipFalse, listCT, listPT, listCF, listPF


    def createPerisaccadicDictionary(self, listCT, listPT):
        """
        Compile probetimestamps from zipTrue (listPT) into a dictionary based on contrast values
        """
        dictionaryTrue = dict() # Initialize an empty dictionary
        uniqueContrastValuesTrue = np.unique(self.listCT) # Find the unique constrast values
        for uniqueContrastValueTrue in uniqueContrastValuesTrue: # Iterterate through the unique contrast values
            mask = np.array(self.listCT) == uniqueContrastValueTrue # Create a mask for each unique contrast value
            dictionaryTrue[uniqueContrastValueTrue] = np.array(self.listPT)[mask]
        self.dictionaryTrue = dictionaryTrue
        return dictionaryTrue


    def createExtrasaccadicDictionary(self, listCF, listPF):
        """
        Compile probetimestamps from zipFalse (listPF) into a dictionary based on contrast values
        """
        dictionaryFalse = dict() # Initialize an empty dictionary
        uniqueContrastValuesFalse = np.unique(self.listCF) # Find the unique constrast values
        for uniqueContrastValueFalse in uniqueContrastValuesFalse: # Iterterate through the unique contrast values
            mask = np.array(self.listCF) == uniqueContrastValueFalse # Create a mask for each unique contrast value
            dictionaryFalse[uniqueContrastValueFalse] = np.array(self.listPF)[mask]
        self.dictionaryFalse = dictionaryFalse
        return dictionaryFalse

    def calculateExtrasaccadicResponsePercentages(self, dictionaryFalse, lickTimestamps):
        """
        Calculate the percentage of response trials for each contrast in extrasaccadic trials
        """
        count1 = 0
        count6 = 0
        count5 = 0
        count4 = 0
        tempcount = 0
        percentage1 = 0
        percentage6 = 0
        percentage5 = 0
        percentage4 = 0

        for key in self.dictionaryFalse:
            for probeTimestamp in self.dictionaryFalse[key]:
                for lick in self.lickTimestamps:
                    lickRelative = (lick - probeTimestamp)
                    if lickRelative > 0 and lickRelative < 0.5:
                        tempcount = (tempcount + 1)
                        break
            if key == '0.80':
                count1 = tempcount
                tempcount = 0
                percentage1 = count1/len(self.dictionaryFalse['0.80'])
            if key == '0.60':
                count6 = tempcount
                tempcount = 0
                percentage6 = count6/len(self.dictionaryFalse['0.60'])
            if key == '0.55':
                count5 = tempcount
                tempcount = 0
                percentage5 = count5/len(self.dictionaryFalse['0.55'])
            if key == '0.50':
                count4 = tempcount
                tempcount = 0
                percentage4 = count4/len(self.dictionaryFalse['0.50'])
        percentList = (percentage4, percentage5, percentage6, percentage1)
        percentExtrasaccadic = np.array(percentList)
        self.percentExtrasaccadic = percentExtrasaccadic
        self.percentage1 = percentage1
        return percentExtrasaccadic, percentage1

    def calculateExtrasaccadicResponseNumbers(self, dictionaryFalse, lickTimestamps):
        """
        Calculate and return number of response trials and number of total trials in each contrast for extrasaccadic trials
        """
        count1 = 0
        count6 = 0
        count5 = 0
        count4 = 0
        tempcount = 0
        length1 = 0
        length6 = 0
        length5 = 0
        length4 = 0

        for key in self.dictionaryFalse:
            for probeTimestamp in self.dictionaryFalse[key]:
                for lick in self.lickTimestamps:
                    lickRelative = (lick - probeTimestamp)
                    if lickRelative > 0 and lickRelative < 0.5:
                        tempcount = (tempcount + 1)
                        break
            if key == '0.80':
                count1 = tempcount
                tempcount = 0
                length1 = len(self.dictionaryFalse['0.80'])
            if key == '0.60':
                count6 = tempcount
                tempcount = 0
                length6 = len(self.dictionaryFalse['0.60'])
            if key == '0.55':
                count5 = tempcount
                tempcount = 0
                length5 = len(self.dictionaryFalse['0.55'])
            if key == '0.50':
                count4 = tempcount
                tempcount = 0
                length4 = len(self.dictionaryFalse['0.50'])
        countList = (count4, count5, count6, count1)
        countArrayExtrasaccadic = np.array(countList)
        dictLength = (length4, length5, length6, length1)
        dictArrayExtrasaccadic = np.array(dictLength)
        self.countArrayExtrasaccadic = countArrayExtrasaccadic
        self.dictArrayExtrasaccadic = dictArrayExtrasaccadic
        return countArrayExtrasaccadic, dictArrayExtrasaccadic


    def calculatePerisaccadicResponsePercentages(self, dictionaryTrue, lickTimestamps):
        """
        Calculate the percentage of resposne trials for each contrast in perisaccadic trials
        """
        count1T = 0
        count6T = 0
        count5T = 0
        count4T = 0
        tempcountT = 0
        percentage1T = 0
        percentage6T = 0
        percentage5T = 0
        percentage4T = 0

        for key in self.dictionaryTrue:
            for probeTimestamp in self.dictionaryTrue[key]:
                for lick in self.lickTimestamps:
                    lickRelative = (lick - probeTimestamp)
                    if lickRelative > 0 and lickRelative < 0.5:
                        tempcountT = (tempcountT + 1)
                        break
            if key == '0.80':
                count1T = tempcountT
                tempcountT = 0
                percentage1T = count1T/len(self.dictionaryTrue['0.80'])
            if key == '0.60':
                count6T = tempcountT
                tempcountT = 0
                percentage6T = count6T/len(self.dictionaryTrue['0.60'])
            if key == '0.55':
                count5T = tempcountT
                tempcountT = 0
                percentage5T = count5T/len(self.dictionaryTrue['0.55'])
            if key == '0.50':
                count4T = tempcountT
                tempcountT = 0
                percentage4T = count4T/len(self.dictionaryTrue['0.50'])

        percentListT = (percentage4T, percentage5T, percentage6T, percentage1T)
        percentPerisaccadic = np.array(percentListT)
        self.percentPerisaccadic = percentPerisaccadic
        return percentPerisaccadic

    def calculatePerisaccadicResponseNumbers(self, dictionaryTrue, lickTimestamps):
        """
        Calculate the number of response trials and total trials for each contrast in perisaccadic trials
        """
        count1T = 0
        count6T = 0
        count5T = 0
        count4T = 0
        tempcountT = 0
        length4 = 0
        length5 = 0
        length6 = 0
        length1 = 0

        for key in self.dictionaryTrue:
            for probeTimestamp in self.dictionaryTrue[key]:
                for lick in self.lickTimestamps:
                    lickRelative = (lick - probeTimestamp)
                    if lickRelative > 0 and lickRelative < 0.5:
                        tempcountT = (tempcountT + 1)
                        break
            if key == '0.80':
                count1T = tempcountT
                tempcountT = 0
                length1 = len(self.dictionaryTrue['0.80'])
            if key == '0.60':
                count6T = tempcountT
                tempcountT = 0
                length6 = len(self.dictionaryTrue['0.60'])
            if key == '0.55':
                count5T = tempcountT
                tempcountT = 0
                length5 = len(self.dictionaryTrue['0.55'])
            if key == '0.50':
                count4T = tempcountT
                tempcountT = 0
                length4 = len(self.dictionaryTrue['0.50'])

        countListT = (count4T, count5T, count6T, count1T)
        countArrayPerisaccadic = np.array(countListT)
        dictLengthT = (length4, length5, length6, length1)
        dictArrayPerisaccadic = np.array(dictLengthT)
        self.countArrayPerisaccadic = countArrayPerisaccadic
        self.dictArrayPerisaccadic = dictArrayPerisaccadic
        return countArrayPerisaccadic, dictArrayPerisaccadic


    def calculateNormalizedResponseRateExtrasaccadic(self, percentExtrasaccadic, percentage1):
        """
        Normalizes response rate for extrasaccadic trials by dividing percent response from all contrasts by percent response of the highest contrast
        """
        normalExtrasaccadic = self.percentExtrasaccadic/self.percentage1
        self.normalExtrasaccadic = normalExtrasaccadic
        return normalExtrasaccadic

    def calculateNormalizedResponseRatePerisaccadic(self, percentPerisaccadic, percentage1):
        """
        Normalizes response rate for perisaccadic trials by dividing percent response from all contrasts by percent response of the highest contrast of extrasaccadic trials, since we don't always have perisaccadic trials at highest contrast
        """
        normalPerisaccadic = self.percentPerisaccadic/self.percentage1
        self.normalPerisaccadic = normalPerisaccadic
        return normalPerisaccadic
    
    def createPsychometricSaccadeCurve(self, normalExtrasaccadic, normalPerisaccadic):
        """
        Plot the normalized response rates for extrasaccadic (red) and perisaccadic (blue) trials
        """
        fig, ax = plt.subplots()
        plt.plot(['0%', '5%', '10%', '30%'], self.normalExtrasaccadic, color='r')
        plt.plot(['0%', '5%', '10%', '30%'], self.normalPerisaccadic, color='b')
        plt.ylim([0.0, 1.5])
        ax.set_ylabel('Fraction of Response Trials')
        ax.set_xlabel('Trials by Contrast Change')
        fig.set_figheight(8)
        fig.set_figwidth(6)
        return fig
       
    def createPerisaccadicStimHistogram(self, totalSaccades):
        """
        Create histogram showing how many perisaccadic probes in a session
        """
        probeTimestamps = self.loadProbeTimestamps()
        perisaccadicStimList = list()
        for saccade in self.totalSaccades:
            probeRelative = np.around(probeTimestamps - saccade, 2)
            mask = np.logical_and(
                probeRelative > -1,
                probeRelative < 1,
            )
            if mask.sum() == 1:
                probeRelativeFiltered = probeRelative[mask]
                perisaccadicStimList.append(probeRelativeFiltered)

        perisaccadicStimArray = np.array(perisaccadicStimList)
        fig, ax = plt.subplots()
        ax.hist(perisaccadicStimArray, range=(-0.1, 0.15), bins=10, facecolor='w', edgecolor='k')
        return fig

    def plotSaccadeWaveforms(self):
        """
        Plot nasal and temporal saccade individual and average waveforms
        """
        res = self.read('saccadeClassificationResults')
        nasalWaveforms = res['left']['nasal']['waveforms']
        temporalWaveforms = res['left']['temporal']['waveforms']
        fig = plt.plot()
        plt.plot(nasalWaveforms.mean(0), color='k', alpha=1)
        plt.plot(temporalWaveforms.mean(0), color='k', alpha=1)
        for wave in nasalWaveforms:
            plt.plot(wave, color='b', alpha=0.05)
        for waveT in temporalWaveforms:
            plt.plot(waveT, color='r', alpha=0.05)
        return fig

    def processLickSession(self):
        """
        This takes the unprocessed Labjack and DLC CSV data, analyzes it, and creates a psychometric curve for perisaccadic and extrasaccadic trials
        """
        lickTimestamps = self.extractLickTimestamps()
        contrastValues = self.extractContrastValues()
        totalSaccades = self.extractSaccadeTimestamps()
        zipped3, perisaccadicProbeBool = self.createZippedList(totalSaccades)
        zipTrue, zipFalse, listCT, listPT, listCF, listPF = self.createPeriAndExtraSaccadicLists(perisaccadicProbeBool, contrastValues)
        dictionaryTrue = self.createPerisaccadicDictionary(listCT, listPT)
        dictionaryFalse = self.createExtrasaccadicDictionary(listCF, listPF)
        percentArrayExtrasaccadic, percentage1 = self.calculateExtrasaccadicResponsePercentages(dictionaryFalse, lickTimestamps)
        percentArrayPerisaccadic = self.calculatePerisaccadicResponsePercentages(dictionaryTrue, lickTimestamps)
        normalExtrasaccadic = self.calculateNormalizedResponseRateExtrasaccadic(percentArrayExtrasaccadic, percentage1)
        normalPerisaccadic = self.calculateNormalizedResponseRatePerisaccadic(percentArrayPerisaccadic, percentage1)
        fig = self.createPsychometricSaccadeCurve(normalExtrasaccadic, normalPerisaccadic)
        print(percentArrayExtrasaccadic)
        print(percentage1)
        print(percentArrayPerisaccadic)
        return fig

    def processLickSessionCorrected(self):
        """
        This takes the unprocessed Labjack and DLC CSV data, analyzes it, and creates a psychometric curve for perisaccadic and extrasaccadic trials
        """
        lickTimestamps = self.extractLickTimestamps()
        contrastValues = self.loadFilteredContrast()
        totalSaccades = self.extractSaccadeTimestamps()
        zipped3, perisaccadicProbeBool = self.createZippedListCorrected(totalSaccades)
        zipTrue, zipFalse, listCT, listPT, listCF, listPF = self.createPeriAndExtraSaccadicListsCorrected(perisaccadicProbeBool)
        dictionaryTrue = self.createPerisaccadicDictionary(listCT, listPT)
        dictionaryFalse = self.createExtrasaccadicDictionary(listCF, listPF)
        percentArrayExtrasaccadic, percentage1 = self.calculateExtrasaccadicResponsePercentages(dictionaryFalse, lickTimestamps)
        percentArrayPerisaccadic = self.calculatePerisaccadicResponsePercentages(dictionaryTrue, lickTimestamps)
        normalExtrasaccadic = self.calculateNormalizedResponseRateExtrasaccadic(percentArrayExtrasaccadic, percentage1)
        normalPerisaccadic = self.calculateNormalizedResponseRatePerisaccadic(percentArrayPerisaccadic, percentage1)
        fig = self.createPsychometricSaccadeCurve(normalExtrasaccadic, normalPerisaccadic)
        return fig

    def processMultipleLickSessions(self):
        """
        This takes unprocessed Labjack and DLC CSV data, analyzes it, and returns the number of response trials and total trials for a session for each contrast, so we can combine data across sessions
        """
        lickTimestamps = self.extractLickTimestamps()
        contrastValues = self.extractContrastValues()
        totalSaccades = self.extractSaccadeTimestamps()
        zipped3, perisaccadicProbeBool = self.createZippedList(totalSaccades)
        zipTrue, zipFalse, listCT, listPT, listCF, listPF = self.createPeriAndExtraSaccadicLists(perisaccadicProbeBool, contrastValues)
        dictionaryTrue = self.createPerisaccadicDictionary(listCT, listPT)
        dictionaryFalse = self.createExtrasaccadicDictionary(listCF, listPF)
        countArrayExtrasaccadic, dictArrayExtrasaccadic = self.calculateExtrasaccadicResponseNumbers(dictionaryFalse, lickTimestamps)
        countArrayPerisaccadic, dictArrayPerisaccadic = self.calculatePerisaccadicResponseNumbers(dictionaryTrue, lickTimestamps)
        return countArrayExtrasaccadic, dictArrayExtrasaccadic, countArrayPerisaccadic, dictArrayPerisaccadic
    
    def processMultipleLickSessionsCorrected(self):
        """
        This takes unprocessed Labjack and DLC CSV data, analyzes it, and returns the number of response trials and total trials for a session for each contrast, so we can combine data across sessions
        """
        lickTimestamps = self.extractLickTimestamps()
        contrastValues = self.extractContrastValues()
        filteredProbes = self.loadFilteredProbes()
        filteredContrast = self.loadFilteredContrast()
        totalSaccades = self.extractSaccadeTimestamps()
        zipped3, perisaccadicProbeBool = self.createZippedListCorrected(totalSaccades)
        zipTrue, zipFalse, listCT, listPT, listCF, listPF = self.createPeriAndExtraSaccadicListsCorrected(perisaccadicProbeBool)
        dictionaryTrue = self.createPerisaccadicDictionary(listCT, listPT)
        dictionaryFalse = self.createExtrasaccadicDictionary(listCF, listPF)
        countArrayExtrasaccadic, dictArrayExtrasaccadic = self.calculateExtrasaccadicResponseNumbers(dictionaryFalse, lickTimestamps)
        countArrayPerisaccadic, dictArrayPerisaccadic = self.calculatePerisaccadicResponseNumbers(dictionaryTrue, lickTimestamps)
        return countArrayExtrasaccadic, dictArrayExtrasaccadic, countArrayPerisaccadic, dictArrayPerisaccadic

    def createLickRasterProcess(self):
        """
        This takes unprocessed Labjack and DLC CSV data, analyzes it, and returns two raster plots - one normal lick raster and one lick raster separated out by contrasts
        """
        lickTimestamps = self.extractLickTimestamps()
        contrastValues = self.extractContrastValues()
        dictionary = self.sortUniqueContrasts(contrastValues)
        figRaster = self.createLickRaster(lickTimestamps)
        array1, array8, array6, array5 = self.createContrastRaster(lickTimestamps, dictionary)
        figContrasts = self.plotContrastRaster(array1, array8, array6, array5)
        return figRaster, figContrasts

    def lickAnalysis(self, sessions):
        """
        This takes multiple sessions as input and creates a psychometric curve comparing extrasaccadic and perisaccadic responses - this is the big overarching function
        """
        responseExtrasaccadic = np.array([0, 0, 0, 0])
        totalExtrasaccadic = np.array([0, 0, 0, 0])
        responsePerisaccadic = np.array([0, 0, 0, 0])
        totalPerisaccadic = np.array([0, 0, 0, 0])
        for session in sessions:
            countArrayExtrasaccadic, dictArrayExtrasaccadic, countArrayPerisaccadic, dictArrayPerisaccadic = session.processMultipleLickSessions()
            responseExtrasaccadic = np.add(responseExtrasaccadic, countArrayExtrasaccadic)
            totalExtrasaccadic = np.add(totalExtrasaccadic, dictArrayExtrasaccadic)
            responsePerisaccadic = np.add(responsePerisaccadic, countArrayPerisaccadic)
            totalPerisaccadic = np.add(totalPerisaccadic, dictArrayPerisaccadic)
    
        percentExtrasaccadic = np.divide(responseExtrasaccadic, totalExtrasaccadic)
        percentPerisaccadic = np.divide(responsePerisaccadic, totalPerisaccadic)
        fig, ax = plt.subplots()
        plt.plot(['0%', '5%', '10%', '30%'], percentExtrasaccadic, color='r')
        plt.plot(['0%', '5%', '10%', '30%'], percentPerisaccadic, color='b')
        plt.ylim([0.0, 1.0])
        ax.set_ylabel('Fraction of Response Trials')
        ax.set_xlabel('Trials by Contrast Change')
        print(totalExtrasaccadic)
        print(totalPerisaccadic)
        return fig

    def lickAnalysisCorrected(self, sessions):
        """
        This takes multiple sessions as input and creates a psychometric curve comparing extrasaccadic and perisaccadic responses - this is the big overarching function
        """
        responseExtrasaccadic = np.array([0, 0, 0, 0])
        totalExtrasaccadic = np.array([0, 0, 0, 0])
        responsePerisaccadic = np.array([0, 0, 0, 0])
        totalPerisaccadic = np.array([0, 0, 0, 0])
        fig = plt.plot()
        for session in sessions:
            countArrayExtrasaccadic, dictArrayExtrasaccadic, countArrayPerisaccadic, dictArrayPerisaccadic = session.processMultipleLickSessionsCorrected()
            indvExtrasaccadic = np.divide(countArrayExtrasaccadic, dictArrayExtrasaccadic)
            indvPerisaccadic = np.divide(countArrayPerisaccadic, dictArrayPerisaccadic)
            normExtrasaccadic = 100*(np.divide(indvExtrasaccadic, indvExtrasaccadic[3]))
            normPerisaccadic = 100*(np.divide(indvPerisaccadic, indvExtrasaccadic[3]))

            # Mask NaN values with zeros
            normExtrasaccadic[np.isnan(normExtrasaccadic)] = 0
            normPerisaccadic[np.isnan(normPerisaccadic)] = 0

            #plt.plot(['0%', '5%', '10%', '30%'], normExtrasaccadic, color='r', alpha=0.4)
            #plt.plot(['0%', '5%', '10%', '30%'], normPerisaccadic, color='b', alpha=0.4)
            responseExtrasaccadic = np.add(responseExtrasaccadic, countArrayExtrasaccadic)
            totalExtrasaccadic = np.add(totalExtrasaccadic, dictArrayExtrasaccadic)
            responsePerisaccadic = np.add(responsePerisaccadic, countArrayPerisaccadic)
            totalPerisaccadic = np.add(totalPerisaccadic, dictArrayPerisaccadic)
    
        percentExtrasaccadic = np.divide(responseExtrasaccadic, totalExtrasaccadic)
        percentPerisaccadic = np.divide(responsePerisaccadic, totalPerisaccadic)
        normalExtrasaccadic = 100*(np.divide(percentExtrasaccadic, percentExtrasaccadic[3]))
        normalPerisaccadic = 100*(np.divide(percentPerisaccadic, percentExtrasaccadic[3]))
        #fig, ax = plt.subplots()
        font = {'size' : 25}
        plt.rc('font', **font)
        plt.plot(['0%', '5%', '10%', '30%'], normalExtrasaccadic, color='r')
        plt.plot(['0%', '5%', '10%', '30%'], normalPerisaccadic, color='b')
        plt.ylim([0.0, 250])
        plt.ylabel('% of Response Trials', fontsize="25")
        plt.xlabel('Trials by Contrast Change', fontsize="25")
        plt.xticks(fontsize=25) 
        plt.yticks(fontsize=25) 

        return fig

    def extractPupilRadius(self):
        """
        Loads pupil position data from DLC CSV and extract radius
        """
        csvPupil = self.leftEyePose
        centerX = loadBodypartData(csvPupil, bodypart = 'center', feature = 'x')
        centerY = loadBodypartData(csvPupil, bodypart = 'center', feature = 'y')
        centerXY = np.hstack([
            centerX.reshape(-1, 1),
            centerY.reshape(-1, 1)
        ])
        nasalX = loadBodypartData(csvPupil, bodypart = 'nasal', feature = 'x')
        nasalY = loadBodypartData(csvPupil, bodypart = 'nasal', feature = 'y')
        nasalXY = np.hstack([
            nasalX.reshape(-1, 1),
            nasalY.reshape(-1, 1)
        ])
        pupilRadius = np.linalg.norm(centerXY - nasalXY, axis=1)
        self.pupilRadius = pupilRadius
        return pupilRadius
    
    def findClosestFrame(self, t):
        """
        Finds frame closest to time t 
        """
        frameTimestamps = self.loadFrameTimestamps()
        frameTimestampsRelative = frameTimestamps - t
        closestFrameIndex = np.argmin(np.abs(frameTimestampsRelative))
        self.closestFrameIndex = closestFrameIndex
        return closestFrameIndex

    def findResponseTrials(self, probe, lickTimestamps):
        """
        Define whether a trial is a response or non-response trial
        """
        lickRelative = (self.lickTimestamps - probe)
        mask = np.logical_and(
            lickRelative > 0,
            lickRelative < 0.5
        )
        if any(mask):
            trialResponse = True
        else:
            trialResponse = False
        self.trialResponse = trialResponse
        return trialResponse

    def plotPeristimulusDilation(self, lickTimestamps, pupilRadius):
        """
        Plot response (blue) and non-response (red) trials according to the amount of dilation or constriction in the 50 frames (1/3 of a second) before the probe
        """
        probeTimestamps = self.loadProbeTimestamps()
        frameTimestamps = self.loadFrameTimestamps()
        fig = plt.figure()
        ax = fig.add_subplot(111)
        for probe in probeTimestamps:
            f1 = self.findClosestFrame(probe)
            f5 = f1 - 50
            pupilDiff = self.pupilRadius[f1] - self.pupilRadius[f5]
            trialResponse = self.findResponseTrials(probe, self.lickTimestamps)
            if trialResponse == True:
                ax.plot(probe, pupilDiff, 'o', color = 'b')
            else:
                ax.plot(probe, pupilDiff, 'o', color = 'r')
        x1, x2 = ax.get_xlim()
        ax.hlines(0, x1, x2, color = 'k', linestyle = '-')

        return fig

    def plotPeristimulusPupilTrace(self, lickTimestamps, pupilRadius):
        """ 
        Plot pupil trace for response (blue) and non-response (red) trials
        """
        probeTimestamps = self.loadProbeTimestamps()
        frameTimestamps = self.loadFrameTimestamps()
        waveTrue = list()
        waveFalse = list()
        fig = plt.figure()
        ax = fig.add_subplot(111)
        for probe in probeTimestamps:
            f1 = self.findClosestFrame(probe)
            f0 = f1 - 300
            f2 = f1 + 300
            wave = self.pupilRadius[f0:f2]
            trialResponse = self.findResponseTrials(probe, self.lickTimestamps)
            if trialResponse == True:
                ax.plot(wave, color = 'b', alpha=0.1)
                waveTrue.append(wave)

            else:
                ax.plot(wave, color = 'r', alpha=0.1)
                waveFalse.append(wave)
        waveTrueArray = np.array(waveTrue)
        waveFalseArray = np.array(waveFalse)
        muTrue = waveTrueArray.mean(0)
        muFalse = waveFalseArray.mean(0)
        ax.plot(muTrue, color = 'b', alpha=1)
        ax.plot(muFalse, color = 'r', alpha=1)
        return fig

    def plotPupilData(self):
        """
        Combine multiple functions to make 2 plots to look at pupil radius and dilation in a session
        """
        lickTimestamps = self.extractLickTimestamps()
        pupilRadius = self.extractPupilRadius()
        figDilation = self.plotPeristimulusDilation(lickTimestamps, pupilRadius)
        figTrace = self.plotPeristimulusPupilTrace(lickTimestamps, pupilRadius)
        return figDilation, figTrace

    def plotFilteredLickRasters(self):
        """
        Allows you to enter index range for lick rasters
        """
        filteredContrast = self.loadFilteredContrast()
        lickTimestamps = self.extractLickTimestamps()
        filteredProbes = self.loadFilteredProbes()
        fig1 = self.createLickRasterCorrected(lickTimestamps)
        dictionary = self.sortUniqueContrastsCorrected()
        array1, array8, array6, array5 = self.createContrastRasterCorrected(lickTimestamps, dictionary)
        fig2 = self.plotContrastRaster(array1, array8, array6, array5)
        return fig1, fig2

    def computePeriExtraContrastRaster(self, totalSaccades, dictionary, lickTimestamps):
        """
        do computations to create lick raster in response to probe based on peri vs extra saccadic probes & separated out by contrast
        """
        probeTimestamps = self.loadProbeTimestamps()
        list1 = list()
        list8 = list()
        list6 = list()
        list5 = list()
        list1P = list()
        list8P = list()
        list6P = list()
        list5P = list()
        listtempProbe = list()
        listtempNoProbe = list()

        for key in self.dictionary:
            for probeTimestamp in self.dictionary[key]:
                lickRelative = (self.lickTimestamps - probeTimestamp)
                sacRelative = (self.totalSaccades - probeTimestamp)
                mask = np.logical_and(
                    lickRelative > -2,
                    lickRelative < 5,
                )
                lickRelativeFiltered = lickRelative[mask]
                mask2 = np.logical_and(
                    sacRelative > -0.05,
                    sacRelative < 0.1,
                )
                sacRelativeFiltered = sacRelative[mask2]
                if any(sacRelativeFiltered):
                    listtempProbe.append(lickRelativeFiltered)
                else:
                    listtempNoProbe.append(lickRelativeFiltered)
            if key == '0.80':
                list1P = listtempProbe
                array1P = np.array(list1P)
                listtempProbe.clear()
                list1 = listtempNoProbe
                array1 = np.array(list1)
                listtempNoProbe.clear()
            if key == '0.60':
                list8P = listtempProbe
                array8P = np.array(list8P)
                listtempProbe.clear()
                list8 = listtempNoProbe
                array8 = np.array(list8)
                listtempNoProbe.clear()
            if key == '0.55':
                list6P = listtempProbe
                array6P = np.array(list6P)
                listtempProbe.clear()
                list6 = listtempNoProbe
                array6 = np.array(list6)
                listtempNoProbe.clear()
            if key == '0.50':
                list5P = listtempProbe
                array5P = np.array(list5P)
                listtempProbe.clear()
                list5 = listtempNoProbe
                array5 = np.array(list5)
                listtempNoProbe.clear()
        self.array1P = array1P
        self.array8P = array8P
        self.array6P = array6P
        self.array5P = array5P
        self.array1 = array1
        self.array8 = array8
        self.array6 = array6
        self.array5 = array5
        return array1P, array8P, array6P, array5P, array1, array8, array6, array5

    def plotPeriExtraContrastRaster(self, array1P, array8P, array6P, array5P, array1, array8, array6, array5):
        """
        plots lick raster that was previously computed
        """
        fig, ax = plt.subplots()
        if len(array1) == 0:
            rowIndex = 0
        else:
            for rowIndex, row in enumerate(array1):
                try:
                    x = row
                    y0 = rowIndex - 0.5
                    y1 = rowIndex + 0.5
                    ax.vlines(x, y0, y1, color='k')
                except:
                    import pdb; pdb.set_trace()
            ax.vlines(x, y0, y1, color='k', label="Extrasaccadic 30%")
            ax.set_ylabel('Trial')
            ax.set_xlabel('Time (sec)')
            fig.set_figheight(4)
            fig.set_figwidth(10)
            plt.xlim([-1, 3])
        if len(array8) == 0:
            rowIndex1 = 0
        else:
            for rowIndex1, row1 in enumerate(array8):
                x = row1
                y0 = rowIndex + (rowIndex1 - 0.5)
                y1 = rowIndex + (rowIndex1 + 0.5)
                ax.vlines(x, y0, y1, color='b')
            ax.vlines(x, y0, y1, color='b', label="Extrasaccadic 10%")
        if len(array6) == 0:
            rowIndex2 = 0
        else:
            for rowIndex2, row2 in enumerate(array6):
                x = row2
                y0 = rowIndex + rowIndex1 + (rowIndex2 - 0.5)
                y1 = rowIndex + rowIndex1 + (rowIndex2 + 0.5)
                ax.vlines(x, y0, y1, color='g')
            ax.vlines(x, y0, y1, color='g', label="Extrasaccadic 5%")
        if len(array5) == 0:
            rowIndex3 = 0
        else:
            for rowIndex3, row3 in enumerate(array5):
                x = row3
                y0 = rowIndex + rowIndex1 + rowIndex2 + (rowIndex3 - 0.5)
                y1 = rowIndex + rowIndex1 + rowIndex2 + (rowIndex3 + 0.5)
                ax.vlines(x, y0, y1, color='r')
            ax.vlines(x, y0, y1, color='r', label="Extrasaccadic 0%")
        if len(array1P) == 0:
            rowIndex4 = 0
        else:
            for rowIndex4, row4 in enumerate(array1P):
                x = row4
                y0 = 5 + rowIndex + rowIndex1 + rowIndex2 + rowIndex3 + (rowIndex4 - 0.5)
                y1 = 5 + rowIndex + rowIndex1 + rowIndex2 + rowIndex3 + (rowIndex4 + 0.5)
                ax.vlines(x, y0, y1, color='k')
            ax.vlines(x, y0, y1, color='k', label="Perisaccadic 30%")
        if len(array8P) == 0:
            rowIndex5 = 0
        else:
            for rowIndex5, row5 in enumerate(array8P):
                x = row5
                y0 = 5 + rowIndex + rowIndex1 + rowIndex2 + rowIndex3 + rowIndex4 + (rowIndex5 - 0.5)
                y1 = 5 + rowIndex + rowIndex1 + rowIndex2 + rowIndex3 + rowIndex4 + (rowIndex5 + 0.5)
                ax.vlines(x, y0, y1, color='b')
            ax.vlines(x, y0, y1, color='b', label="Perisaccadic 10%")
        if len(array6P) == 0:
            rowIndex6 = 0
        else:
            for rowIndex6, row6 in enumerate(array6P):
                x = row6
                y0 = 5 + rowIndex + rowIndex1 + rowIndex2 + rowIndex3 + rowIndex4 + rowIndex5 + (rowIndex6 - 0.5)
                y1 = 5 + rowIndex + rowIndex1 + rowIndex2 + rowIndex3 + rowIndex4 + rowIndex5 + (rowIndex6 + 0.5)
                ax.vlines(x, y0, y1, color='g')
            ax.vlines(x, y0, y1, color='g', label="Perisaccadic 5%")
        if len(array5P) == 0:
            rowIndex7 = 0
        else:
            for rowIndex7, row7 in enumerate(array5P):
                x = row7
                y0 = 5 + rowIndex + rowIndex1 + rowIndex2 + rowIndex3 + rowIndex4 + rowIndex5 + rowIndex6 + (rowIndex7 - 0.5)
                y1 = 5 + rowIndex + rowIndex1 + rowIndex2 + rowIndex3 + rowIndex4 + rowIndex5 + rowIndex6 + (rowIndex7 + 0.5)
                ax.vlines(x, y0, y1, color='r')
            ax.vlines(x, y0, y1, color='r', label="Perisaccadic 0%")
        ax.legend(bbox_to_anchor=(1.0, 1.0))
    
        return fig, ax
 
    def saccadeContrastLickAnalysis(self):
        """
        function that compiles multiple functions to analyze lick data and produce lick raster in response to probes, separated by contrast and saccade state
        """
        contrastValues = self.extractContrastValues()
        dictionary = self.sortUniqueContrasts(contrastValues)
        lickTimestamps = self.extractLickTimestamps()
        totalSaccades = self.extractSaccadeTimestamps()
        array1P, array8P, array6P, array5P, array1, array8, array6, array5 = self.computePeriExtraContrastRaster(totalSaccades, dictionary, lickTimestamps)
        print(array1P)
        fig, ax = self.plotPeriExtraContrastRaster(array1P, array8P, array6P, array5P, array1, array8, array6, array5)
        return fig, ax