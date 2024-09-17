#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jun 13 10:57:18 2024

@author: fmuir
"""

import os
import timeit
import pickle
import time
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from scipy.interpolate import interp1d

from sklearn.decomposition import PCA
from sklearn.cluster import KMeans, SpectralClustering, DBSCAN
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.model_selection import train_test_split
# from sklearn.utils.class_weight import compute_class_weight
# from imblearn.over_sampling import SMOTE

from tensorflow.keras.models import Sequential
from tensorflow.keras import Input
from tensorflow.keras.layers import GRU, Dense, Dropout
from tensorflow.keras.optimizers import Adam
from imblearn.over_sampling import SMOTE
from tensorflow.keras.callbacks import EarlyStopping, TensorBoard

# Only use tensorflow in CPU mode
import tensorflow as tf
tf.config.set_visible_devices([],'GPU')



def LoadIntersections(filepath, sitename):
    """
    Load in transect intersection dataframes stored as pickle files. Generated 
    using Transects.GetIntersections(), Transects.SaveIntersections(), 
    Transects.GetBeachWidth(), Transects.SaveWaterIntersections(),
    Transects.TZIntersect(), Transects.SlopeIntersect(), 
    Transects.WavesIntersect().
    FM Jul 2024

    Parameters
    ----------
    filepath : str
        Path to 'Data' directory for chosen site.
    sitename : str
        Name of site chosen.

    Returns
    -------
    TransectInterGDF : GeoDataFrame
        GeoDataFrame of cross-shore transects, intersected with vegetation edge lines.
    TransectInterGDFWater : GeoDataFrame
        GeoDataFrame of cross-shore transects, intersected with waterlines.
    TransectInterGDFTopo : GeoDataFrame
        GeoDataFrame of cross-shore transects, intersected with slope raster and vegetation transition zones.
    TransectInterGDFWave : GeoDataFrame
        GeoDataFrame of cross-shore transects, intersected with Copernicus hindcast wave data.

    """
    with open(os.path.join
              (filepath , sitename, 'intersections', sitename + '_transect_intersects.pkl'), 'rb') as f:
        TransectInterGDF = pickle.load(f)
        
    with open(os.path.join
              (filepath , sitename, 'intersections', sitename + '_transect_water_intersects.pkl'), 'rb') as f:
        TransectInterGDFWater = pickle.load(f)

    with open(os.path.join
              (filepath , sitename, 'intersections', sitename + '_transect_topo_intersects.pkl'), 'rb') as f:
        TransectInterGDFTopo = pickle.load(f)

    with open(os.path.join
              (filepath , sitename, 'intersections', sitename + '_transect_wave_intersects.pkl'), 'rb') as f:
        TransectInterGDFWave = pickle.load(f)
        
    return TransectInterGDF, TransectInterGDFWater, TransectInterGDFTopo, TransectInterGDFWave
        

def CompileTransectData(TransectInterGDF, TransectInterGDFWater, TransectInterGDFTopo, TransectInterGDFWave):
    """
    Merge together transect geodataframes produced from COASTGUARD.VedgeSat and CoastSat. Each transect holds 
    timeseries of a range of satellite-derived metrics.
    FM Aug 2024

    Parameters
    ----------
    TransectInterGDF : GeoDataFrame
        DataFrame of cross-shore transects intersected with timeseries of veg edges.
    TransectInterGDFWater : GeoDataFrame
        DataFrame of cross-shore transects intersected with timeseries of waterlines.
    TransectInterGDFTopo : GeoDataFrame
        DataFrame of cross-shore transects intersected with timeseries of slopes at the veg edge.
    TransectInterGDFWave : GeoDataFrame
        DataFrame of cross-shore transects intersected with timeseries of wave conditions.

    Returns
    -------
    CoastalDF : DataFrame
        DataFrame process.

    """
    # Merge veg edge intersection data with waterline intersection data
    CoastalDF = pd.merge(TransectInterGDF[['TransectID','dates','distances']], 
                         TransectInterGDFWater[['TransectID','wldates','wlcorrdist', 'waterelev','beachwidth']],
                         how='inner', on='TransectID')
    # Merge combined dataframe with topographic info
    # TransectInterGDFTopo[['TransectID','TZwidth', 'TZwidthMn', 'SlopeMax', 'SlopeMean']]
    CoastalDF = pd.merge(CoastalDF, 
                         TransectInterGDFTopo[['TransectID','TZwidth']],
                         how='inner', on='TransectID')
    # Merge combined dataframe with wave info
    # TransectInterGDFWave[['TransectID','WaveHs', 'WaveDir', 'WaveTp', 'WaveDiffus']]
    CoastalDF = pd.merge(CoastalDF, 
                         TransectInterGDFWave[['TransectID','WaveHs', 'WaveDir', 'WaveTp']],
                         how='inner', on='TransectID')
    
    
    return CoastalDF


def InterpWL(CoastalDF, Tr):
    """
    Interpolate over waterline associated timeseries so that dates match 
    vegetation associated ones.
    FM Aug 2024

    Parameters
    ----------
    CoastalDF : DataFrame
        DataFrame of cross-shore transects (rows) and intersected coastal 
        timeseries/metrics (columns).
    Tr : int
        Transect ID of choice.

    Returns
    -------
    TransectDF : DataFrame
        Subset row matching the requested transect ID (Tr), with interpolated
        values for 'wlcorrdist', 'waterelev' and 'beachwidth'.

    """
    TransectDF = CoastalDF.iloc[[Tr],:] # single-row dataframe
    # TransectDF = TransectDF.transpose()

    # Interpolate over waterline associated variables to match dates with veg edge dates
    wl_numdates = pd.to_datetime(TransectDF['wldates'][Tr]).values.astype(np.int64)
    ve_numdates = pd.to_datetime(TransectDF['dates'][Tr]).values.astype(np.int64)
    wl_interp_f = interp1d(wl_numdates, TransectDF['wlcorrdist'][Tr], kind='linear', fill_value='extrapolate')
    wl_interp = wl_interp_f(ve_numdates).tolist()
    welev_interp_f = interp1d(wl_numdates, TransectDF['waterelev'][Tr], kind='linear', fill_value='extrapolate')
    welev_interp = welev_interp_f(ve_numdates).tolist()
    TransectDF['wlcorrdist'] = [wl_interp]
    TransectDF['waterelev'] = [welev_interp]
    # Recalculate beachwidth
    beachwidth = [abs(wl_interp[i] - TransectDF['distances'][Tr][i]) for i in range(len(wl_interp))]
    TransectDF['beachwidth'] = [beachwidth]
    
    TransectDF.drop(columns=['wldates'], inplace=True)
    
    # Transpose to get columns of variables and rows of timesteps
    TransectDF = pd.DataFrame({col: pd.Series(val.iloc[0]) for col,val in TransectDF.items()})
    
    return TransectDF


def PreprocessTraining(CoastalDF):
    
    X = CoastalDF.drop(columns=['TransectID', 'labels'])
    y = CoastalDF['labels']
    # Normalize the features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    
def Cluster(TransectDF, ValPlots=False):
    """
    

    Parameters
    ----------
    TransectDF : DataFrame
        Dataframe of single cross-shore transect, with timeseries of satellite-derived metrics attached.
    ValPlots : bool, optional
        Plot validation plots of silhouette score and inertia. The default is False.

    Returns
    -------
    VarDF : DataFrame
        Dataframe of just coastal metrics/variables in timeseries, with cluster values attached to each timestep.

    """
    # Define variables dataframe from transect dataframe by removing dates and transposing
    VarDF = TransectDF.drop(columns=['TransectID', 'dates'])
    VarDF.interpolate(method='nearest', axis=0, inplace=True) # fill nans using nearest
    VarDF.interpolate(method='linear', axis=0, inplace=True) # if any nans left over at start or end, fill with linear
    VarDF_scaled = StandardScaler().fit_transform(VarDF)
    
    
    # Fit k-means clustering to data iteratively over different cluster sizes
    k_n = range(2,15)
    # Inertia = compactness of clusters i.e. total variance within a cluster
    # Silhouette score = how similar object is to its own cluster vs other clusters 
    inertia = []
    sil_scores = []
    
    for k in k_n:
        kmeansmod = KMeans(n_clusters=k, random_state=42)
        kmeansmod.fit(VarDF_scaled)
        inertia.append(kmeansmod.inertia_)
        sil_scores.append(silhouette_score(VarDF_scaled, kmeansmod.labels_))
    
    # Apply PCA to reduce the dimensions to 2D for visualization
    pca = PCA(n_components=2)
    pca_VarDF = pca.fit_transform(VarDF_scaled)
    eigenvectors = pca.components_

    # Create a DataFrame for PCA results and add cluster labels
    pca_df = pd.DataFrame(data=pca_VarDF, columns=['PC1', 'PC2'])
    pca_df['Cluster'] = kmeansmod.labels_
    
    
    if ValPlots is True:
        # Optional: Plot an elbow graph to find the optimal number of clusters
        plt.figure(figsize=(10, 5))
        plt.plot(k_n, inertia, marker='o')
        plt.title('Elbow Method For Optimal k')
        plt.xlabel('Number of Clusters (k)')
        plt.ylabel('Inertia')
        plt.show()
        
        # Optional: Plot silhouette scores for further cluster evaluation
        plt.figure(figsize=(10, 5))
        plt.plot(k_n, sil_scores, marker='o')
        plt.title('Silhouette Scores For Optimal k')
        plt.xlabel('Number of Clusters (k)')
        plt.ylabel('Silhouette Score')
        plt.show()
    
    
    # # Fit the KMeans model with the chosen number of clusters
    # # Clusters are informed by 'impact' levels low, medium and high
    # optimal_k = 3
    # tic = timeit.default_timer() # start timer
    # kmeansmod = KMeans(n_clusters=optimal_k, random_state=42)
    # kmeansmod.fit(VarDF_scaled)
    # toc = timeit.default_timer() # stop timer
    
    # # Analyze the clustering results
    # VarDF['Cluster'] = kmeansmod.labels_
    
    ClusterMods = {'kmeans':KMeans(n_clusters=3, random_state=42),
                   'spectral':SpectralClustering(n_clusters=3, eigen_solver='arpack', random_state=42)}
    for Mod in ClusterMods.keys():
        
        ClusterMods[Mod].fit(VarDF_scaled)
        VarDF[Mod+'Cluster'] = ClusterMods[Mod].labels_
        ClusterMeans = VarDF.groupby(Mod+'Cluster').mean()
        
        ClusterCentres = np.array([pca_VarDF[VarDF[Mod+'Cluster'] == i].mean(axis=0) for i in range(3)])

        HighImpact = np.argmax(ClusterCentres[:, 0])
        LowImpact = np.argmax(ClusterCentres[:, 1])
        MediumImpact = (set([0,1,2]) - {HighImpact, LowImpact}).pop()
        
        ClusterToImpact = {HighImpact:'High',
                           MediumImpact:'Medium',
                           LowImpact:'Low'}
        ImpactLabels = [ClusterToImpact[Cluster] for Cluster in VarDF[Mod+'Cluster']]
        VarDF['Impact'] = ImpactLabels
        
        # HighImpact = ClusterMeans[(ClusterMeans['distances'] == ClusterMeans['distances'].min()) & # landward VE
        #                           (ClusterMeans['wlcorrdist'] == ClusterMeans['wlcorrdist'].min()) & # landward WL
        #                           (ClusterMeans['waterelev'] == ClusterMeans['waterelev'].max()) & # high water
        #                           (ClusterMeans['beachwidth'] == ClusterMeans['beachwidth'].min()) & # narrow width
        #                           (ClusterMeans['TZwidth'] == ClusterMeans['TZwidth'].min()) & # narrow TZ
        #                           (ClusterMeans['WaveHs'] == ClusterMeans['WaveHs'].max()) & # high waves
        #                           (ClusterMeans['WaveTp'] == ClusterMeans['WaveTp'].max())].index[0] # long period
        
        # LowImpact = ClusterMeans[(ClusterMeans['distances'] == ClusterMeans['distances'].max()) & # seaward VE
        #                           (ClusterMeans['wlcorrdist'] == ClusterMeans['wlcorrdist'].max()) & # seaward WL
        #                           (ClusterMeans['waterelev'] == ClusterMeans['waterelev'].min()) & # low water
        #                           (ClusterMeans['beachwidth'] == ClusterMeans['beachwidth'].max()) & # wide width
        #                           (ClusterMeans['TZwidth'] == ClusterMeans['TZwidth'].max()) & # wide TZ
        #                           (ClusterMeans['WaveHs'] == ClusterMeans['WaveHs'].min()) & # low waves
        #                           (ClusterMeans['WaveTp'] == ClusterMeans['WaveTp'].min())].index[0] # short period
        # AllClusters = set([0,1,2])
        # MediumImpact = (AllClusters - set([HighImpact, LowImpact])).pop()

        # Cluster to impact
        # ClusterToImpact = {'High': HighImpact,
        #                    'Medium':MediumImpact,
        #                    'Low':LowImpact}
        # VarDF['Impact'] = VarDF[Mod+'Cluster'].map(ClusterToImpact)
        
        # inertia.append(ClusterMods[Mod].inertia_)
        # sil_scores.append(silhouette_score(VarDF_scaled, ClusterMods[Mod].labels_))
    
        # Create a DataFrame for PCA results and add cluster labels
        pca_df = pd.DataFrame(data=pca_VarDF, columns=['PC1', 'PC2'])
        pca_df['Cluster'] = ClusterMods[Mod].labels_
    
        # Optional: Visualization of clusters
        # For high dimensional data, consider using PCA or t-SNE to reduce dimensions for visualization
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.scatter(VarDF.index, 
                   VarDF['WaveHs'], 
                   c=VarDF[Mod+'Cluster'], 
                   cmap='RdYlGn')  # Example visualization using one variable
        # ax2 = ax.twinx()
        # ax2.scatter(VarDF.index, VarDF['WaveHs'], c=VarDF['Cluster'], cmap='viridis', marker='s')  # Example visualization using one variable
        plt.title(f'Clustering Method: {Mod}')
        ax.set_xlabel('Time')
        # ax.set_ylabel('Cross-shore VE position (m)')
        ax.set_ylabel('Significant wave height (m)')
        plt.show()
        
        # Plot the clusters in the PCA space
        fig, ax = plt.subplots(figsize=(5, 5))
        clusterDF = []
        for cluster in pca_df['Cluster'].unique():
            cluster_data = pca_df[pca_df['Cluster'] == cluster]
            plt.scatter(
                cluster_data['PC1'], 
                cluster_data['PC2'], 
                label=f'Cluster {cluster}', 
                s=40,
                alpha=0.7
            )
            clusterDF.append(cluster_data)
        
        coeffs = np.transpose(pca.components_[0:2, :])*2
        n_coeffs = coeffs.shape[0]
        
        # Plot eignevectors of each variable
        for i in range(n_coeffs):
            plt.arrow(0, 0, coeffs[i,0], coeffs[i,1], color='k', alpha=0.5, head_width=0.02, zorder=5)
            plt.annotate(text=VarDF.columns[i], xy=(coeffs[i,0], coeffs[i,1]), 
                         xytext=(coeffs[i,0]*15,5), textcoords='offset points',
                         color='k', ha='center', va='center', zorder=5)
        
        plt.title(f'{Mod} Clusters in PCA Space')
        plt.xlabel('Principal Component 1')
        plt.ylabel('Principal Component 2')
        plt.legend()
        plt.show()
        
        
    return VarDF