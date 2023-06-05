#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Apr 20 16:51:37 2023

@author: fmuir
"""
import os
import numpy as np
import warnings
from datetime import datetime, timedelta
warnings.filterwarnings("ignore")

import matplotlib as mpl
from matplotlib import cm
import matplotlib.colors as pltcls
mpl.use('Qt5Agg')
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.gridspec import GridSpec
import matplotlib.patches as mpatches
from matplotlib.collections import PatchCollection
from matplotlib.patches import Patch
import matplotlib.dates as mdates
plt.ion()

import rasterio
import geopandas as gpd
import pandas as pd
from sklearn.neighbors import KernelDensity
from sklearn.linear_model import LinearRegression

mpl.rcParams.update(mpl.rcParamsDefault)
mpl.rcParams['font.sans-serif'] = 'Arial'

# SCALING:
# Journal 2-column width: 224pt or 3.11in
# Journal 1-column width: 384pt or 5.33in
# Spacing between: 0.33in
# Journal 2-column page: 6.55in


#%%

def movingaverage(interval, windowsize):
    # moving average trendline
    window = np.ones(int(windowsize))/float(windowsize)
    return np.convolve(interval, window, 'same')

#%%

def SatGIF(metadata,settings,output):
    """
    Create animated GIF of sat images and their extracted shorelines.
    
    FM Jul 2022
    
    Parameters
    ----------
    Sat : list
        Image collection metadata


    Returns
    -------
    None.
    """
    

    polygon = settings['inputs']['polygon']
    sitename = settings['inputs']['sitename']
    filepath_data = settings['inputs']['filepath']
    dates = settings['inputs']['dates']

    # create a subfolder to store the .jpg images showing the detection
    filepath_jpg = os.path.join(filepath_data, sitename, 'jpg_files', 'detection')
    if not os.path.exists(filepath_jpg):
            os.makedirs(filepath_jpg)
    # close all open figures
    plt.close('all')
    
    ims_ms = []
    ims_date = []
    
    
    # Loop through satellite list
    for satname in metadata.keys():

        # Get image metadata
        ## need to fix: get this from output not metadata as some images get skipped by user
        filenames = metadata[satname]['filenames']
        filedates = metadata[satname]['dates']
        
        
        # loop through the images
        for i in range(len(filenames)):

            print('\r%s:   %d%%' % (satname,int(((i+1)/len(filenames))*100)), end='')
            
            # TO DO: need to load in images from jpg_files folder
            # Append image array and dates to lists for plotting
            img = rasterio.open(filenames[i])
            im_RGB = img.read()
            
            ims_ms.append(im_RGB)
            ims_date.append(filedates[i])
            
    shorelineArr = output['shorelines']
    sl_date = output['dates']
    
    # shoreline dataframe back to array
    # TO DO: need to load in shorelines from shapefile and match up each date to corresponding image
    #shorelineArr = Toolbox.GStoArr(shoreline)
    # sl_pix=[]
    # for line in shorelineArr:
    #     sl_pix.append(Toolbox.convert_world2pix(shorelineArr, georef))
    
    # Sort image arrays and dates by date
    ims_date_sort, ims_ms_sort = (list(t) for t in zip(*sorted(zip(ims_date, ims_ms), key=lambda x: x[0])))
    
    # Set up figure for plotting
    fig, ax = plt.subplots(figsize=(15, 15))
    ax.grid(False)
    # Set up function to be called repeatedly for FuncAnimation()
    def animate(n):
        ax.imshow(ims_ms_sort[n])
        ax.set_title(ims_date_sort[n])

    # Use FuncAnimation() which sets a figure and calls a function repeatedly for as many frames as you set
    anim = FuncAnimation(fig=fig, func=animate, frames=len(ims_ms), interval=1, repeat=False)
    # Save as GIF; fps controls the speed of refresh
    anim.save(os.path.join(filepath_jpg, sitename + '_AnimatedImages.gif'),fps=3)




def VegTimeseries(sitename, TransectDict, TransectID, daterange):
    """
    

    Parameters
    ----------
    ValidDict : TYPE
        DESCRIPTION.
    TransectID : TYPE
        DESCRIPTION.

    Returns
    -------
    None.

    """
    
    outfilepath = os.path.join(os.getcwd(), 'Data', sitename, 'plots')
    if os.path.isdir(outfilepath) is False:
        os.mkdir(outfilepath)
    
    plotdate = [datetime.strptime(x, '%Y-%m-%d') for x in TransectDict['dates'][TransectID][daterange[0]:daterange[1]]]
    plotsatdist = TransectDict['distances'][TransectID][daterange[0]:daterange[1]]
    plotsatdist = np.array(plotsatdist)[(np.array(plotsatdist) < np.mean(plotsatdist)+40) & (np.array(plotsatdist) > np.mean(plotsatdist)-40)]
    
    plotdate, plotsatdist = [list(d) for d in zip(*sorted(zip(plotdate, plotsatdist), key=lambda x: x[0]))]
    
    # linear regression line
    x = mpl.dates.date2num(plotdate)
    msat, csat = np.polyfit(x,plotsatdist,1)
    polysat = np.poly1d([msat, csat])
    xx = np.linspace(x.min(), x.max(), 100)
    dd = mpl.dates.num2date(xx)
    
    # scaling for single column A4 page
    mpl.rcParams.update({'font.size':8})
    fig, ax = plt.subplots(1,1,figsize=(6.55,3), dpi=300)
    
    ax.plot(plotdate, plotsatdist, linewidth=0, marker='.', c='k', markersize=6, markeredgecolor='k', label='Satellite VegEdge')
    plt.grid(color=[0.7,0.7,0.7], ls=':', lw=0.5)
    
    recjanlist = []
    recmarchlist = []
    for i in range(plotdate[0].year-1, plotdate[-1].year):
        recjan = mdates.date2num(datetime(i, 12, 1, 0, 0))
        recmarch = mdates.date2num(datetime(i+1, 3, 1, 0, 0))
        recwidth = recmarch - recjan
        rec = mpatches.Rectangle((recjan, -500), recwidth, 1000, fc=[0,0.3,1], ec=None, alpha=0.3)
        ax.add_patch(rec)
    
    # recstart= mdates.date2num(plotdate[0])
    # recend= mdates.date2num(plotdate[10])
    # recwidth= recend - recstart
    
    # rec = mpatches.Rectangle((recstart,0), recwidth, 50, color=[0.8,0.8,0.8])
    # ax.add_patch(rec)
    
    # plot trendlines
    yav = movingaverage(plotsatdist, 3)
    ax.plot(plotdate, yav, 'green', lw=1.5, label='3pt Moving Average')
    ax.plot(dd, polysat(xx), '--', color='C7', lw=1.5, label=str(round(msat*365.25,2))+'m/yr')

    plt.legend()
    plt.title('Transect '+str(TransectID))
    plt.xlabel('Date (yyyy-mm)')
    plt.ylabel('Cross-shore distance (m)')
    # plt.xlim(plotdate[0]-10, plotdate[-1]+10)
    plt.ylim(min(plotsatdist)-10, max(plotsatdist)+10)
    plt.tight_layout()
    
    plt.savefig(os.path.join(outfilepath,sitename + '_SatTimeseries_Transect'+str(TransectID)+'.png'))
    print('Plot saved under '+os.path.join(outfilepath,sitename + '_SatTimeseries_Transect'+str(TransectID)+'.png'))
    
    plt.show()
    
    
def VegWaterTimeseries(sitename, TransectDict, TransectIDs):
    """
    

    Parameters
    ----------
    ValidDict : TYPE
        DESCRIPTION.
    TransectID : TYPE
        DESCRIPTION.

    Returns
    -------
    None.

    """
    
    outfilepath = os.path.join(os.getcwd(), 'Data', sitename, 'plots')
    if os.path.isdir(outfilepath) is False:
        os.mkdir(outfilepath)
    figID = ''
        
    if len(TransectIDs) > 1:
        # scaling for single column A4 page
        mpl.rcParams.update({'font.size':7})
        fig, axs = plt.subplots(len(TransectIDs),1,figsize=(6.55,6), dpi=300)
    else:
        # scaling for single column A4 page
        mpl.rcParams.update({'font.size':7})
        fig, axs = plt.subplots(2,1,figsize=(6.55,3), dpi=300, gridspec_kw={'height_ratios':[100,1]})
        
    for TransectID, ax in zip(TransectIDs,axs):
        daterange = [0,len(TransectDict['dates'][TransectID])]
        plotdate = [datetime.strptime(x, '%Y-%m-%d') for x in TransectDict['dates'][TransectID][daterange[0]:daterange[1]]]
        plotsatdist = TransectDict['distances'][TransectID][daterange[0]:daterange[1]]
        plotwldist = TransectDict['wldists'][TransectID][daterange[0]:daterange[1]]
        plotsatdist = np.array(plotsatdist)[(np.array(plotsatdist) < np.mean(plotsatdist)+40) & (np.array(plotsatdist) > np.mean(plotsatdist)-40)]
        
        plotdate, plotsatdist, plotwldist = [list(d) for d in zip(*sorted(zip(plotdate, plotsatdist, plotwldist), key=lambda x: x[0]))]    
                
        ax2 = ax.twinx()
        
        ax.plot(plotdate, plotsatdist, linewidth=0, marker='.', c='#526A24', markersize=6, label='Satellite VegEdge')
        ax2.plot(plotdate, plotwldist, linewidth=0, marker='.', c='#1E6E99', markersize=6, label='Satellite Shoreline')
        ax.grid(color=[0.7,0.7,0.7], ls=':', lw=0.5)
            
        recjanlist = []
        recmarchlist = []
        for i in range(plotdate[0].year-1, plotdate[-1].year):
            recjan = mdates.date2num(datetime(i, 12, 1, 0, 0))
            recmarch = mdates.date2num(datetime(i+1, 3, 1, 0, 0))
            recwidth = recmarch - recjan
            rec = mpatches.Rectangle((recjan, -500), recwidth, 1000, fc=[0.25,0.3,1], ec=None, alpha=0.2)
            ax.add_patch(rec)
          
        # plot trendlines
        vegav = movingaverage(plotsatdist, 3)
        wlav = movingaverage(plotwldist, 3)
        ax.plot(plotdate, vegav, color='#81A739', lw=1.5, label='3pt Moving Average VegEdge')
        ax2.plot(plotdate, wlav, color='#2893CC', lw=1.5, label='3pt Moving Average Shoreline')
    
        # linear regression lines
        x = mpl.dates.date2num(plotdate)
        for y, pltax, clr in zip([plotsatdist, plotwldist], [ax,ax2], ['#81A739','#2893CC']):
            m, c = np.polyfit(x,y,1)
            polysat = np.poly1d([m, c])
            xx = np.linspace(x.min(), x.max(), 100)
            dd = mpl.dates.num2date(xx)
            pltax.plot(dd, polysat(xx), '--', color=clr, lw=1, label=str(round(m*365.25,2))+' m/yr')
    
        if TransectID == 309:
            plt.title('Transect '+str(TransectID)+', Out Head')
        elif TransectID == 1575:
            plt.title('Transect '+str(TransectID)+', Tentsmuir')
        else:
            plt.title('Transect '+str(TransectID))
        ax.set_xlabel('Date (yyyy-mm)')
        ax.set_ylabel('Cross-shore distance (veg) (m)')
        ax2.set_ylabel('Cross-shore distance (water) (m)')
        # plt.xlim(plotdate[0]-10, plotdate[-1]+10)
        ax.set_ylim(min(plotsatdist)-10, max(plotsatdist)+30)
        ax2.set_ylim(min(plotwldist)-10, max(plotwldist)+30)
        
        leg1 = ax.legend(loc=1)
        leg2 = ax2.legend(loc=2)
        # weird zorder with twinned axes; remove first axis legend and plot on top of second
        leg1.remove()
        ax2.add_artist(leg1)
        
        figID += '_'+str(TransectID)
        
    figname = os.path.join(outfilepath,sitename + '_SatVegWaterTimeseries_Transect'+figID+'.png')
    
    if not axs[1].lines:
        fig.delaxes(axs[1])
    plt.tight_layout()
            
    plt.savefig(figname)
    print('Plot saved under '+figname)
    
    plt.show()
    

def ValidTimeseries(sitename, ValidDict, TransectID):
    """
    

    Parameters
    ----------
    ValidDict : TYPE
        DESCRIPTION.
    TransectID : TYPE
        DESCRIPTION.

    Returns
    -------
    None.

    """
    
    outfilepath = os.path.join(os.getcwd(), 'Data', sitename, 'plots')
    if os.path.isdir(outfilepath) is False:
        os.mkdir(outfilepath)
    
    plotdate = [datetime.strptime(x, '%Y-%m-%d') for x in ValidDict['Vdates'][TransectID]]
    plotsatdist = ValidDict['distances'][TransectID]
    plotvaliddist = ValidDict['Vdists'][TransectID]
    
    plotdate, plotvaliddist = [list(d) for d in zip(*sorted(zip(plotdate, plotvaliddist), key=lambda x: x[0]))]
    plotdate, plotsatdist = [list(d) for d in zip(*sorted(zip(plotdate, plotsatdist), key=lambda x: x[0]))]
    
    magma = cm.get_cmap('magma')
    
    x = mpl.dates.date2num(plotdate)
    mvalid, cvalid = np.polyfit(x,plotvaliddist,1)
    msat, csat = np.polyfit(x,plotsatdist,1)
    
    polyvalid = np.poly1d([mvalid, cvalid])
    polysat = np.poly1d([msat, csat])
    
    xx = np.linspace(x.min(), x.max(), 100)
    dd = mpl.dates.num2date(xx)
    
    mpl.rcParams.update({'font.size':8})
    fig, ax = plt.subplots(1,1,figsize=(6.55,3), dpi=300)
    
    validlabels = ['Validation VegEdge','_nolegend_','_nolegend_','_nolegend_']
    satlabels = ['Satellite VegEdge','_nolegend_','_nolegend_','_nolegend_',]
    
    for i,c in enumerate([0.95,0.7,0.6,0.2]):
        ax.plot(plotdate[i], plotvaliddist[i], 'X', color=magma(c), markersize=10,markeredgecolor='k', label=validlabels[i])
        ax.plot(plotdate[i], plotsatdist[i], 'o', color=magma(c),markersize=10,markeredgecolor='k', label=satlabels[i])
    
    
    ax.plot(dd, polyvalid(xx), '--', color=[0.7,0.7,0.7], zorder=0, label=str(round(mvalid*365.25,2))+'m/yr')
    ax.plot(dd, polysat(xx), '-', color=[0.7,0.7,0.7], zorder=0, label=str(round(msat*365.25,2))+'m/yr')
    
    plt.legend()
    plt.xlabel('Date (yyyy-mm)')
    plt.ylabel('Cross-shore distance (m)')
    plt.tight_layout()
    
    plt.savefig(os.path.join(outfilepath,sitename + '_ValidVsSatTimeseries_Transect'+str(TransectID)+'.png'))
    print('Plot saved under '+os.path.join(outfilepath,sitename + '_ValidVsSatTimeseries_Transect'+str(TransectID)+'.png'))
    
    plt.show()


def WidthTimeseries(sitename, TransectDict, TransectID, daterange):
    """
    

    Parameters
    ----------
    ValidDict : TYPE
        DESCRIPTION.
    TransectID : TYPE
        DESCRIPTION.

    Returns
    -------
    None.

    """
    
    outfilepath = os.path.join(os.getcwd(), 'Data', sitename, 'plots')
    if os.path.isdir(outfilepath) is False:
        os.mkdir(outfilepath)
    
    plotdate = [datetime.strptime(x, '%Y-%m-%d') for x in TransectDict['wldates'][TransectID][daterange[0]:daterange[1]]]

    plotwldate = [datetime.strptime(x, '%Y-%m-%d') for x in TransectDict['wldates'][TransectID][daterange[0]:daterange[1]]]
    plotvegdate = [datetime.strptime(x, '%Y-%m-%d') for x in TransectDict['dates'][TransectID][daterange[0]:daterange[1]]]

    plotvegdist = TransectDict['distances'][TransectID][daterange[0]:daterange[1]]
    plotwldist = TransectDict['wlcorrdist'][TransectID][daterange[0]:daterange[1]]
    plotsatdist = TransectDict['beachwidth'][TransectID][daterange[0]:daterange[1]]

    plotvegdate, plotvegdist = [list(d) for d in zip(*sorted(zip(plotvegdate, plotvegdist), key=lambda x: x[0]))]
    plotwldate, plotwldist = [list(d) for d in zip(*sorted(zip(plotwldate, plotwldist), key=lambda x: x[0]))]
    plotdate, plotsatdist = [list(d) for d in zip(*sorted(zip(plotdate, plotsatdist), key=lambda x: x[0]))]

    # linear regression line
    x = mpl.dates.date2num(plotdate)
    msat, csat = np.polyfit(x,plotsatdist,1)
    polysat = np.poly1d([msat, csat])
    xx = np.linspace(x.min(), x.max(), 100)
    dd = mpl.dates.num2date(xx)
    
    # scaling for single column A4 page
    mpl.rcParams.update({'font.size':8})
    fig, ax = plt.subplots(1,1,figsize=(6.55,3), dpi=300)
    
    ax.plot(plotdate, plotsatdist, linewidth=0, marker='.', c='k', markersize=8, markeredgecolor='k', label='Upper Beach Width')
    # plt.plot(plotvegdate, plotvegdist, linewidth=0, marker='.', c='g', markersize=8, label='Upper Beach Width')
    # plt.plot(plotwldate, plotwldist, linewidth=0, marker='.', c='b', markersize=8,  label='Upper Beach Width')

    # plot trendlines
    yav = movingaverage(plotsatdist, 3)
    ax.plot(plotdate, yav, 'r', label='3pt Moving Average')
    ax.plot(dd, polysat(xx), '--', color=[0.7,0.7,0.7], zorder=0, label=str(round(msat*365.25,2))+'m/yr')

    
    plt.legend()
    plt.title('Transect '+str(TransectID))
    plt.xlabel('Date (yyyy-mm)')
    plt.ylabel('Cross-shore distance (m)')
    plt.ylim(-200,1000)
    plt.tight_layout()
    
    plt.savefig(os.path.join(outfilepath,sitename + '_SatTimeseries_Transect'+str(TransectID)+'.png'))
    print('Plot saved under '+os.path.join(outfilepath,sitename + '_SatTimeseries_Transect'+str(TransectID)+'.png'))
    
    plt.show()



def BeachWidthSeries(TransectID):
    
    f = plt.figure(figsize=(8, 3))
    
    
    plt.plot('.-', color='k')
    
    

def ResultsPlot(outfilepath, outfilename, sitename):
    
    
    def formatAxes(fig):
        for i, ax in enumerate(fig.axes):
            ax.tick_params(labelbottom=False, labelleft=False)
    
    fig = plt.figure(layout='constrained', figsize=(6.55,5))
    
    gs = GridSpec(3,3, figure=fig)
    ax1 = fig.add_subplot(gs[0,:])
    ax2 = fig.add_subplot(gs[1,:-1])
    ax3 = fig.add_subplot(gs[1:,-1])
    ax4 = fig.add_subplot(gs[-1,0])
    ax5 = fig.add_subplot(gs[-1,-2])
    
    formatAxes(fig)
    
    # # font size 8 and width of 6.55in fit 2-column journal formatting
    # plt.rcParams['font.size'] = 8
    # fig, ax = plt.subplots(3,2, figsize=(6.55,5), dpi=300, gridspec_kw={'height_ratios':[3,2,2]})
    
    # # outfilepath = os.path.join(os.getcwd(), 'Data', sitename, 'plots')
    # if os.path.isdir(outfilepath) is False:
    #     os.mkdir(outfilepath)
    
    plt.tight_layout()
    #plt.savefig(os.path.join(outfilepath,outfilename), dpi=300)
    print('Plot saved under '+os.path.join(outfilepath,outfilename))
    
    plt.show()
    
    
def ValidPDF(sitename, ValidationShp,DatesCol,ValidDict,TransectIDs,PlotTitle):    
    """
    Generate probability density function of validation vs sat lines
    FM 2023

    Parameters
    ----------
    sitename : TYPE
        DESCRIPTION.
    ValidationShp : TYPE
        DESCRIPTION.
    DatesCol : TYPE
        DESCRIPTION.
    ValidDict : TYPE
        DESCRIPTION.
    TransectIDs : TYPE
        DESCRIPTION.
    PlotTitle : TYPE
        DESCRIPTION.

    Returns
    -------
    None.

    """
    # font size 8 and width of 6.55in fit 2-column journal formatting
    plt.rcParams['font.size'] = 8  
    
    filepath = os.path.join(os.getcwd(), 'Data', sitename, 'plots')
    if os.path.isdir(filepath) is False:
        os.mkdir(filepath)
    
    ValidGDF = gpd.read_file(ValidationShp)
    violin = []
    violindates = []
    Vdates = ValidGDF[DatesCol].unique()
    for Vdate in Vdates:
        valsatdist = []
        for Tr in range(TransectIDs[0],TransectIDs[1]): 
            if Tr > len(ValidDict['Vdates']): # for when transect values extend beyond what transects exist
                print("check your chosen transect values!")
                return
            if Vdate in ValidDict['Vdates'][Tr]:
                DateIndex = (ValidDict['Vdates'][Tr].index(Vdate))
                # rare occasion where transect intersects valid line but NOT sat line (i.e. no distance between them)
                if ValidDict['valsatdist'][Tr] != []:
                    valsatdist.append(ValidDict['valsatdist'][Tr][DateIndex])
                else:
                    continue
            else:
                continue
        # due to way dates are used, some transects might be missing validation dates so violin collection will be empty
        if valsatdist != []: 
            violin.append(valsatdist)
            violindates.append(Vdate)
    # sort both dates and list of values by date
    if len(violindates) > 1:
        violindatesrt, violinsrt = [list(d) for d in zip(*sorted(zip(violindates, violin), key=lambda x: x[0]))]
    else:
        violindatesrt = violindates
        violinsrt = violin
    df = pd.DataFrame(violinsrt)
    df = df.transpose()
    df.columns = violindatesrt
    
    
    # Above is violin stuff, below is KD
    x = np.array()
    x_d = np.linspace(0,1,1000)
    
    kde = KernelDensity(bandwidth=0.03, kernel='gaussian')
    kde.fit(x[:,None])
    logprob = kde.score_samples(x_d[:,None])    
    
    
    fig, ax = plt.subplots(1,1, figsize=(2.48,4.51))
    if len(violindates) > 1:
        ax.plot(x_d, np.exp(logprob), linewidth=1)
    else:
        ax.plot(data = df, linewidth=1)
        
    ax.set(xlabel='Cross-shore distance of satellite-derived line from validation line (m)', ylabel='Validation line date')
    ax.set_title('Accuracy of Transects ' + str(TransectIDs[0]) + ' to ' + str(TransectIDs[1]))
    
    # set axis limits to rounded maximum value of all violins (either +ve or -ve)
    axlim = round(np.max([abs(df.min().min()),abs(df.max().max())]),-1)
    ax.set_xlim(-axlim, axlim)
    ax.set_xticks([-30,-15,-10,10,15,30],minor=True)
    ax.xaxis.grid(b=True, which='minor',linestyle='--', alpha=0.5)
    median = ax.axvline(df.median().mean(), c='r', ls='-.')
    
    handles = [median]
    labels = ['median' + str(round(df.median().mean(),1)) + 'm']
    ax.legend(handles,labels)
    
    ax.set_axisbelow(False)
    plt.tight_layout()
    
    #plt.savefig(os.path.join(outfilepath,outfilename), dpi=300)
    figpath = os.path.join(filepath,sitename+'_Validation_Satellite_Distances_Violin_'+str(TransectIDs[0])+'to'+str(TransectIDs[1])+'.png')
    plt.savefig(figpath)
    print('figure saved under '+figpath)
    
    plt.show()
    
    
def SatRegress(sitename,SatShp,DatesCol,ValidDict,TransectIDs,PlotTitle):
       
    
    filepath = os.path.join(os.getcwd(), 'Data', sitename, 'plots')
    if os.path.isdir(filepath) is False:
        os.mkdir(filepath)
    
    if type(SatShp) == str:
        SatGDF = gpd.read_file(SatShp)
    else:
        SatGDF = SatShp
        
    valdists = []
    satdists = []
    satplotdates = []
    validplotdates = []
    # get unique sat dates
    Sdates = SatGDF[DatesCol].unique()
    # get unique validation dates
    Vdates = []
    for Tr in range(TransectIDs[0], TransectIDs[1]):
        for i in ValidDict['Vdates'][Tr]:
            if i != []:
                try:
                    Vdates.append(ValidDict['Vdates'][Tr][i]) 
                except:
                    Vdates.append(ValidDict['Vdates'][Tr][0])
    Vdates = set(Vdates)
    
    for Sdate in Sdates:
        satdist = []
        valdist = []
        # for each transect in given range
        for Tr in range(TransectIDs[0],TransectIDs[1]): 
            if Tr > len(ValidDict['dates']): # for when transect values extend beyond what transects exist
                print("check your chosen transect values!")
                return
            if Sdate in ValidDict['dates'][Tr]:
                DateIndex = (ValidDict['dates'][Tr].index(Sdate))
                # rare occasion where transect intersects valid line but NOT sat line (i.e. no distance between them)
                if ValidDict['valsatdist'][Tr] != []:
                    satdist.append(ValidDict['distances'][Tr][DateIndex])
                    # extract validation dists by performing difference calc back on sat dists
                    valdist.append(ValidDict['distances'][Tr][DateIndex]-ValidDict['valsatdist'][Tr][DateIndex])
                else:
                    continue
            else:
                continue
        # due to way dates are used, some transects might be missing validation dates so violin collection will be empty
        if satdist != []: 
            satdists.append(satdist)
            satplotdates.append(Sdate)
            valdists.append(valdist)
    # sort both dates and list of values by date
    if len(satplotdates) > 1:
        satplotdatesrt, satsrt, valsrt = [list(d) for d in zip(*sorted(zip(satplotdates, satdists, valdists), key=lambda x: x[0]))]
    else:
        satplotdatesrt = satplotdates
        satsrt = satdists
        valsrt = valdists


    f = plt.figure(figsize=(3.31, 3.31), dpi=300)
    mpl.rcParams.update({'font.size':7})
    ax = f.add_subplot(1,1,1)
    ax.set_facecolor('#ECEAEC')
    
    valsrtclean = []
    satsrtclean = []
    satdateclean = []
    # for each list of transects for a particular date
    for dat, vallist, satlist in zip(range(len(valsrt)), valsrt, satsrt):
        vallistclean = []
        satlistclean = []
        # for each transect obs
        for i in range(len(vallist)):
            if np.isnan(vallist[i]) == False: # if transect obs is not empty
                vallistclean.append(vallist[i])
                satlistclean.append(satlist[i])
        if vallistclean != []: # skip completely empty dates
            satdateclean.append(satplotdatesrt[dat])
            valsrtclean.append(vallistclean)
            satsrtclean.append(satlistclean)

    cmap = cm.get_cmap('magma_r',len(valsrtclean))
    for i in range(len(valsrtclean)): 
        # plot scatter of validation (observed) vs satellite (predicted) distances along each transect
        plt.scatter(valsrtclean[i], satsrtclean[i], color=cmap(i), s=1, alpha=0.2, zorder=0)
        # linear regression
        X = np.array(valsrtclean[i]).reshape((-1,1))
        y = np.array(satsrtclean[i])
        model = LinearRegression(fit_intercept=True).fit(X,y)
        r2 = model.score(X,y)
        
        valfit = np.linspace(0,round(np.max(valsrtclean[i])),len(valsrtclean[i])).reshape((-1,1))
        satfit = model.predict(valfit)

        plt.plot(valfit,satfit, c=cmap(i), alpha=0.6, linewidth=1.2, label=(satdateclean[i]+' R$^2$ = '+str(round(r2,2))))

    plt.legend(ncol=1)
    
    # overall linear regression
    valfull = [item for sublist in valsrtclean for item in sublist]
    satfull =[item for sublist in satsrtclean for item in sublist]
    X = np.array(valfull).reshape((-1,1))
    y = np.array(satfull)
    model = LinearRegression(fit_intercept=True).fit(X,y)
    r2 = model.score(X,y)
    
    valfit = np.linspace(0,round(np.max(valfull)),len(valfull)).reshape((-1,1))
    satfit = model.predict(valfit)

    plt.plot(valfit,satfit, c='#7A7A7A', linestyle='--', linewidth=1.2)
    plt.text(valfit[-1],satfit[-1], 'R$^2$ = '+str(round(r2,2)))


    maxlim = max( max(max(satsrt)), max(max(valsrt)) )
    minlim = min( min(min(satsrt)), min(min(valsrt)) )
    majort = np.arange(-100,maxlim+150,100)
    minort = np.arange(-100,maxlim+150,20)
    ax.set_xticks(majort)
    ax.set_yticks(majort)
    ax.set_xticks(minort, minor=True)
    ax.set_yticks(minort, minor=True)
    ax.grid(which='major', color='#BBB4BB', alpha=0.5)
    ax.grid(which='minor', color='#BBB4BB', alpha=0.2)

    plt.xlim(0,maxlim+150)
    plt.ylim(0,maxlim)
    
    plt.xlabel('Validation Veg Edge cross-shore distance (m)')
    plt.ylabel('Satellite Veg Edge cross-shore distance (m)')
    
    plt.tight_layout()
    
    figpath = os.path.join(filepath,sitename+'_Validation_Satellite_Distances_LinReg_'+str(TransectIDs[0])+'to'+str(TransectIDs[1])+'.png')
    plt.savefig(figpath)
    print('figure saved under '+figpath)
    
    plt.show()
        
    