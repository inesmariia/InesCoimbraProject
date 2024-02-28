#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Feb 27 18:10:41 2024

@author: inesmaria
"""

import streamlit as st
import pandas as pd
import numpy as np
import geopandas as gpd
import folium
from folium.features import GeoJsonTooltip
from streamlit_folium import folium_static, st_folium
from io import BytesIO
from folium.plugins import FloatImage
import openpyxl
import tempfile
import os

# Function to process each sheet in the Excel file
def process_sheet(xls, sheet_name):
    df = pd.read_excel(xls, sheet_name=sheet_name, skiprows=2)

    # Combine headers for each column
    headers = []
    previous_unit = None
    for col_idx, (col, unit) in enumerate(zip(df.columns, df.iloc[0])):
        if pd.notna(unit):
            # If the unit is present in the current column, use it
            current_header = f'{col} ({unit})'
            headers.append(current_header)
            previous_unit = unit
        else:
            # If the unit is missing, use the previous unit
            if previous_unit is not None:
                current_header = f'{col} ({previous_unit})'
                headers.append(current_header)
    
    # Assign combined headers to the DataFrame
    df.columns = headers

    # Drop the row with measurement units
    df = df[1:]

    # Trim empty columns from the right
    df = df.loc[:, :(df.isnull().all().cumsum() == 1).idxmax()]

    # Drop columns with all NaN values
    df.dropna(axis=1, how='all', inplace=True)

    return df

# Function to save dataframe to a CSV and return it as a download link
def to_csv(df):
    output = BytesIO()
    df.to_csv(output, index=False, sep=';', encoding='utf-8')
    output.seek(0)
    return output

# Streamlit app layout
st.sidebar.image("https://i.postimg.cc/hjT72Vcx/logo-black.webp", use_column_width=True)
st.sidebar.title("Coimbra Interactive Map")
page = st.sidebar.radio("Select a Page", ["File Processor", "Interactive Map", "Forecast"])

if page == "File Processor":
    st.title("File Processor")

    uploaded_file = st.file_uploader("Upload your Excel file", type=["xlsx"])

    if uploaded_file is not None:
        xls = pd.ExcelFile(uploaded_file)

        for sheet_name in xls.sheet_names:
            df = process_sheet(xls, sheet_name)
            st.write(f"Preview of {sheet_name}:")
            st.dataframe(df.head())

            # Convert DataFrame to CSV
            csv = to_csv(df)
            st.download_button(
                label=f"Download {sheet_name} as CSV",
                data=csv,
                file_name=f"{sheet_name}.csv",
                mime='text/csv',
            )
##############################################################################################
elif page == "Interactive Map":
    st.title("Interactive Map")

    # Function to calculate quantile bins for automated binning
    def calculate_quantile_bins(data, num_bins=5):
        quantiles = [i / num_bins for i in range(1, num_bins)]
        bin_edges = list(data.quantile(quantiles))
        min_edge, max_edge = data.min(), data.max()
        bin_edges = [min_edge] + bin_edges + [max_edge]
        return bin_edges

    # Load and process the shapefiles/data
    choropleth_gdf = gpd.read_file('./maps/municipal.shp')  # Adjust path as necessary
    choropleth_gdf = choropleth_gdf.to_crs(epsg=4326)

    area_type_gdf = gpd.read_file('./maps/AreasEdificadas2018.shp')
    area_type_gdf = area_type_gdf.set_crs(epsg=3763)
    area_type_gdf = area_type_gdf.to_crs(epsg=4326)

    # Create a mapping from 'TIPO_p' numerical values to human-readable labels
    tipo_p_labels = {
        1: "Residential (>= 10 Buildings)",
        2: "Residential scattered/isolated",
        3: "Non-Residential"
    }

    # Map the 'TIPO_p' values to their labels
    area_type_gdf['TIPO_p_label'] = area_type_gdf['TIPO_p'].map(tipo_p_labels)

    # Define a color for each 'TIPO_p' label
    tipo_p_colors = {
        "Residential (>= 10 Buildings)": "red",
        "Residential scattered/isolated": "orange",
        "Non-Residential": "purple"
    }

    # Sidebar options for Choropleth
    year = st.sidebar.slider("Select Year", 2020, 2021, 2022, 2023)
    df_path = f'tables/{year}.xlsx'
    df = pd.read_excel(df_path)
    column_names = df.columns.tolist()[5:]
    column_name = st.sidebar.selectbox("Select Column", column_names)

    merged = choropleth_gdf.merge(df, left_on='NAME_2_cor', right_on='Region')
    merged[column_name] = pd.to_numeric(merged[column_name], errors='coerce')
    merged[column_name].fillna(0, inplace=True)
    bin_edges = calculate_quantile_bins(merged[column_name])

    m = folium.Map(location=[39.5, -8.0], zoom_start=7)

    folium.Choropleth(
        geo_data=merged,
        data=merged,
        columns=['NAME_2_cor', column_name],
        key_on='feature.properties.NAME_2_cor',
        fill_color='YlGn',
        fill_opacity=0.4,
        line_opacity=0.2,
        legend_name=f'{column_name} in {year}',
        bins=bin_edges,
        reset=True
    ).add_to(m)

    # Sidebar options for Area Type Map with no default selection
    st.sidebar.markdown("## Coimbra Region-only Area Options")
    tipo_p_options = area_type_gdf['TIPO_p_label'].unique()
    selected_tipo_p = st.sidebar.multiselect("Select Residential Density", tipo_p_options, default=[])

    # Filter based on selected TIPO_p labels
    filtered_area_type_gdf = area_type_gdf[area_type_gdf['TIPO_p_label'].isin(selected_tipo_p)]

    # Adding Area Type GeoJSON on top of the Choropleth Map
    if not filtered_area_type_gdf.empty:
        folium.GeoJson(
            filtered_area_type_gdf,
            style_function=lambda feature: {
                'fillColor': tipo_p_colors[feature['properties']['TIPO_p_label']],
                'color': 'black',
                'weight': 0,
                'fillOpacity': 0.6
            },
            tooltip=folium.GeoJsonTooltip(fields=['TIPO_p_label'], aliases=['Area Type:'])
        ).add_to(m)

    # Display the map
    st_folium(m, width=900, height=700)


##############################################################################################
elif page == "Forecast":
    st.title("Forecast")