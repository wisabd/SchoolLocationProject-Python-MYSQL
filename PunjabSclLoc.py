import streamlit as st
import folium
from streamlit_folium import st_folium
import json
import pandas as pd
import math
import requests
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

API_KEY = os.getenv('API_KEY')
DATABASE_URL = os.getenv('DATABASE_URL')
SECRET_KEY = os.getenv('SECRET_KEY')

#data_url1 = "https://raw.githubusercontent.com/wisabd/Data_PMIU/blob/main/PunjabLoc.csv"
#data_url2 = "https://raw.githubusercontent.com/wisabd/Data_PMIU/blob/main/file3.csv"

@st.cache_data
def load_data_from_gh(data_url):
    try:
        # Send request with authentication
        headers = {'Authorization': f'token {API_KEY}'}
        response = requests.get(data_url, headers=headers)
        response.raise_for_status()  # Raise an     error for bad status codes

        # Read the CSV data from the response
        df = pd.read_csv(pd.compat.StringIO(response.text))
        return df
    except Exception as e:
        st.error(f"Failed to load data: {e}")
        return None


upgrade_candidates = []
lowenrol = []

# --- HAVERSINE AND PROXIMITY FUNCTIONS ---
def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate the great-circle distance between two points."""
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2)
    c = 2 * math.asin(math.sqrt(a))
    return c * 6371  # Earth radius in km

def is_point_in_box(test_lat, test_lon, min_lat, min_lon, max_lat, max_lon):
    """Checks if a point is inside a bounding box."""
    return (min_lat <= test_lat <= max_lat) and (min_lon <= test_lon <= max_lon)

def has_nearby_high_school(middle_school_lat, middle_school_lon, high_schools_list, radius_km):
    """
    Check if there are any high schools within the given radius of a middle school.
    Returns:
        bool: True if at least one high school is found within the radius, False otherwise
    """
    #Calculate bounding box around the middle school for fast filtering
    delta_lat = radius_km / 111.2
    lat_rad = math.radians(middle_school_lat)
    delta_lon = radius_km / (111.2 * math.cos(lat_rad))

    min_lat = middle_school_lat - delta_lat
    max_lat = middle_school_lat + delta_lat
    min_lon = middle_school_lon - delta_lon
    max_lon = middle_school_lon + delta_lon

    # Check each high school
    for high_school in high_schools_list:
        hs_lat, hs_lon = high_school['lat'], high_school['lng']

        # Fast bounding box check first
        if is_point_in_box(hs_lat, hs_lon, min_lat, min_lon, max_lat, max_lon):
            # Precise distance calculation
            distance = haversine_distance(middle_school_lat, middle_school_lon, hs_lat, hs_lon)
            if distance <= radius_km:
                return True  # Found at least one high school within radius
    return False  #No high schools found within radius


def get_school_color(school, high_schools_list):
    """
    Determines the color for a school, applying the golden rule for isolated middle schools
    with enrollment > 200.
    Args:
        school: Dictionary with school data including 's_level', 'lat', 'lng', 'enrolment'
        high_schools_list: List of all high school dictionaries
    Returns:
        tuple: (fill_color, border_color) for the school
    """
    school_level = school['Level']
    if school_level == "High":
        fill_color = "green"
        border_color = "darkgreen"
    elif school_level == "Middle":
        # Check if this middle school has ANY high schools within 5km radius
        has_nearby_high = has_nearby_high_school(
            school['Lat'],
            school['Lng'],
            high_schools_list,
            5.0  # 5km radius
        )
        # Get enrollment (handle missing values)
        enrollment = school.get('total_enrollment')
        has_high_enrollment = pd.notna(enrollment) and enrollment > 200

        if has_nearby_high:
            # Middle school has high school(s) nearby - use default purple
            fill_color = "yellow"
            border_color = "yellow"
        else:
            # ISOLATED middle school (no high schools within 5km)
            if has_high_enrollment:
                # ISOLATED AND high enrollment (>200) - make it golden!
                fill_color = "red"
                border_color = "red"
            else:
                # ISOLATED but low enrollment - use a different color (e.g., orange)
                fill_color = "blue"
                border_color = "blue"
    else:
        # Default color for other school levels
        fill_color = "black"
        border_color = "black"
    return fill_color, border_color

# Set page configuration for full-width display
st.set_page_config(
    page_title="Population Density Map",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Load data
# Data loaded from the cleaned dataframe of Pujab with no missing Lat, Lon - No UC data in this
dataframe_pop = pd.read_csv('/Users/muhammadwisalabdullah/Downloads/PunjabLoc.csv')

#Data filtered to get High schools and Middle schools for Boys using pandas
# Filter for both High and Middle schools (Male)
filtered_data = dataframe_pop[
    ((dataframe_pop['Level'] == "High") | (dataframe_pop['Level'] == "Middle")) &
    (dataframe_pop['Gender'] == "Male")
    ]

#Population data from WorldPop loaded
records = pd.read_csv('/Users/muhammadwisalabdullah/Downloads/file3.csv')
records['count'] = range(1, len(records) + 1)
# Sample data creation from the population data into a dictionary format
data = {
    'latitude': records['Latitude'],
    'longitude': records['Longitude'],
    'population_density': records['Population Density at 1km'],
}

# Dictionary format loaded into dataframe
df = pd.DataFrame(data)

# Calculate statistics
stats = {
    'max': df['population_density'].max(),
    'min': df['population_density'].min(),
    'mean': df['population_density'].mean(),
    'median': df['population_density'].median(),
    'std': df['population_density'].std(),
    'total_points': len(df),
    'q25': df['population_density'].quantile(0.25),
    'q75': df['population_density'].quantile(0.75),
    'q90': df['population_density'].quantile(0.90)
}

# Create base map with better initial view, using Folium with some starting position
m = folium.Map(
    location=[df['latitude'].mean(), df['longitude'].mean()],
    zoom_start=10,
    tiles='CartoDB positron',
    control_scale=True,
    prefer_canvas=True
)

# Prepare heat data: [lat, lng, weight]
heat_data = [[row['latitude'], row['longitude'], row['population_density']]
             for index, row in df.iterrows()]
# Create colormap
from branca.colormap import LinearColormap

colormap = LinearColormap(
    colors=['blue', 'cyan', 'lime', 'yellow', 'orange', 'red'],
    vmin=stats['min'],
    vmax=stats['max'],
    caption='Population Density (people/km²)'
)

# Create gradient dictionary manually for HeatMap: 6 gradients
gradient = {
    0.0: 'blue',
    0.2: 'cyan',
    0.4: 'lime',
    0.6: 'yellow',
    0.8: 'orange',
    1.0: 'red'
}

# Add heat map layer: HEATmap uses heat_data to be created, then it is added to folium map m
from folium.plugins import HeatMap

HeatMap(heat_data,
        min_opacity=0.3,
        max_zoom=18,
        radius=25,
        blur=15,
        gradient=gradient
        ).add_to(m)

# Add colormap to map
colormap.add_to(m)

# Create comprehensive statistics panel
stats_html = f'''
<div style="
    position: fixed;
    top: 50px;
    right: 50px;
    width: 300px;
    background: white;
    padding: 15px;
    border: 2px solid #0078D7;
    border-radius: 8px;
    z-index: 9999;
    font-family: Arial, sans-serif;
    box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    max-height: 400px;
    overflow-y: auto;
">
    <h3 style="margin: 0 0 15px 0; color: #0078D7; text-align: center;">
        📊 Population Density Statistics
    </h3>

    <div style="margin-bottom: 12px;">
        <span style="font-weight: bold; color: #333;">Total Data Points:</span>
        <span style="float: right; color: #0078D7;">{stats['total_points']:,}</span>
    </div>

    <div style="margin-bottom: 12px;">
        <span style="font-weight: bold; color: #333;">Maximum Density:</span>
        <span style="float: right; color: #D13438;">{stats['max']:,.0f}</span>
    </div>

    <div style="margin-bottom: 12px;">
        <span style="font-weight: bold; color: #333;">Minimum Density:</span>
        <span style="float: right; color: #107C10;">{stats['min']:,.0f}</span>
    </div>

    <div style="margin-bottom: 12px;">
        <span style="font-weight: bold; color: #333;">Average Density:</span>
        <span style="float: right; color: #0078D7;">{stats['mean']:,.0f}</span>
    </div>

    <div style="margin-bottom: 12px;">
        <span style="font-weight: bold; color: #333;">Median Density:</span>
        <span style="float: right; color: #极0078D7;">{stats['median']:,.0f}</span>
    </div>

    <div style="margin-bottom: 12px;">
        <span style="font-weight: bold; color: #333;">Standard Deviation:</span>
        <span style="float: right; color: #0078D7;">{stats['std']:,.0f}</span>
    </div>

    <hr style="margin: 15px 0; border-color: #ccc;">

    <h4 style="margin: 10极 0; color: #505050;">Quantiles:</h4>

    <div style="margin-bottom: 8px;">
        <span style="color: #666;">25th Percentile:</span>
        <span style="float: right; color: #505050;">{stats['q25']:,.0f}</span>
    </div>

    <div style="margin-bottom: 8px;">
        <span style="color: #666;">75th Percentile:</span>
        <span style="float: right; color: #505050;">{stats['q75']:,.0f}</span>
    </div>

    <div style="margin-bottom: 8px;">
        <span style="color: #666;">90th Percentile:</span>
        <span style="float: right; color: #505050;">{stats['q90']:,.0f}</span>
    </div>

    <hr style="margin: 15px 0; border-color: #ccc;">

    <div style="font-size: 12px; color: #666; text-align: center;">
        <i>Density values in people/km²</i>
    </div>
</div>
'''

# Add statistics panel to map
#m.get_root().html.add_child(folium.Element(stats_html))

# Add title
title_html = '''
<div style="
    position: fixed;
    top: 10px;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(255, 255, 255, 0.9);
    padding: 10px 20px;
    border: 2px solid #0078D7;
    border-radius: 20px;
    z-index: 10000;
    font-family: Arial, sans-serif;
    font-weight: bold;
    font-size: 16px;
    color: #0078D7;
    box-shadow: 0 2px 6px rgba(0,0,0,0.3);
">
    🌍 Population Density Map - Lahore Region
</div>
'''
m.get_root().html.add_child(folium.Element(title_html))

# --- PREPARE HIGH SCHOOLS LIST FOR PROXIMITY CHECK ---
high_schools_list = []
isolated_high_enrollment_count = 0
isolated_low_enrollment_count = 0
non_isolated_count = 0

# First pass: collect all high schools
for index, row in filtered_data.iterrows():
    #HIGH Schools added to a list with coordinates, names
    if row['Level'] == "High":
        high_schools_list.append({
            'lat': row['Lat'],
            'lng': row['Lng'],
            'name': row['School_Name']
        })

# Count schools by level for statistics
high_school_count = len(filtered_data[filtered_data['Level'] == "High"])
middle_school_count = len(filtered_data[filtered_data['Level'] == "Middle"])

# Add school circles with different colors based on level
for index, row in filtered_data.iterrows():
    radius = 1000
    school_name = row['School_Name']
    school_level = row['Level']
    enrollment = row.get('total_enrollment')

    # Use the new function to determine colors
    fill_color, border_color = get_school_color(row, high_schools_list)

    # Count different types of middle schools
    if school_level == "Middle":
        # Evaluate 5km within a given middle school for existence of a high school
        has_nearby_high = has_nearby_high_school(row['Lat'], row['Lng'], high_schools_list, 5.0)
        # Check for high enrollment
        has_high_enrollment = pd.notna(enrollment) and enrollment > 200

        if not has_nearby_high:
            if has_high_enrollment:
                upgrade_candidates.append((row['Lat'], row['Lng'], row['School_Name'], row['EMIS_Code'], row['total_enrollment']))
                isolated_high_enrollment_count += 1

            else:
                lowenrol.append((row['Lat'], row['Lng'], row['School_Name'], row['EMIS_Code'], row['total_enrollment']))
                isolated_low_enrollment_count += 1
        else:
            non_isolated_count += 1
        # Get isolated, non isolated counts

    # Create a detailed popup with all requested information including enrollment
    enrollment_text = f"{enrollment if pd.notna(enrollment) else 'N/A'}"
    enrollment_color = "green" if pd.notna(enrollment) and enrollment > 200 else "inherit"

    popup_text = f"""
    <div style="font-family: Arial, sans-serif; max-width: 300px;">
        <h3 style="margin: 0 0 10px 0; color: #0078D7;">
            {school_name}
        </h3>
        <table style="width: 100%; border-collapse: collapse;">
            <tr>
                <td style="padding: 5px; border-bottom: 1px solid #eee; font-weight: bold; width: 30%;">School ID:</td>
                <td style="padding: 5px; border-bottom: 1px solid #eee;">{row['EMIS_Code']}</td>
            </tr>
            <tr>
                <td style="padding: 5px; border-bottom: 1px solid #eee; font-weight: bold;">Level:</td>
                <td style="padding: 5px; border-bottom: 1px solid #eee;">{school_level}</td>
            </tr>
            <tr>
                <td style="padding: 5px; border-bottom: 1px solid #eee; font-weight: bold;">Enrollment:</td>
                <td style="padding: 5px; border-bottom: 1px solid #eee; font-weight: bold; color: {enrollment_color};">
                    {enrollment_text}
                </td>
            </tr>
            <tr>
                <td style="padding: 5px; border-bottom: 1px solid #eee; font-weight: bold;">Type:</td>
                <td style="padding: 5px; border-bottom: 1px solid #eee;">{row['Gender']}</极td>
            </tr>
            <tr>
                <td style="padding: 5px; border-bottom: 1px solid #eee; font-weight: bold;">Latitude:</td>
                <td style="padding: 5px; border-bottom: 1px solid #eee;">{row['Lat']:.6f}</td>
            </tr>
            <tr>
                <td style="padding: 5px; border-bottom: 1px solid #eee; font-weight: bold;">Longitude:</td>
                <td style="padding: 5px; border-bottom: 1px solid #eee;">{row['Lng']:.6f}</td>
            </tr>
            <tr>
                <td style="padding: 5px; border-bottom: 1px solid #eee; font-weight: bold;">Radius:</td>
                <td style="padding: 5px; border-bottom: 1px solid #eee;">{radius} meters</td>
            </tr>
            {"<tr><td style='padding: 5px; border-bottom: 1px solid #eee; font-weight: bold;'>Status:</td><td style='padding: 5px; border-bottom: 1px solid #eee; color: goldenrod; font-weight: bold;'>ISOLATED - High Enrollment (>200)</td></tr>" if school_level == "Middle" and fill_color == "goldenrod" else ""}
            {"<tr><td style='padding: 5px; border-bottom: 1px solid #eee; font-weight: bold;'>Status:</td><td style='padding: 5px; border-bottom: 1px solid #eee; color: orange; font-weight: bold;'>ISOLATED - Low Enrollment (≤200)</td></tr>" if school_level == "Middle" and fill_color == "orange" else ""}
        </table>
    </div>
    """

    # Create tooltip with enrollment information
    tooltip_text = f"{school_level} School: {school_name}"
    if pd.notna(enrollment):
        tooltip_text += f" (Enrollment: {enrollment})"

    # Plot circles of every school
    folium.Circle(
        location=[row['Lat'], row['Lng']],
        radius=100,
        color=border_color,
        weight=2,
        fill_opacity=0.7,
        opacity=1,
        fill_color=fill_color,
        fill=True,
        popup=popup_text,
        tooltip=tooltip_text,
    ).add_to(m)

# Update legend to include all school types
legend_html = f'''
<div style="
    position: fixed;
    bottom: 50px;
    right: 50px;
    width: 280px;
    height: 220px;
    background: white;
    border: 2px solid grey;
    z-index: 9999;
    padding: 15px;
    border-radius: 8px;
    font-family: Arial, sans-serif;
    font-size: 14;
    box-shadow: 0 4px 8px rgba(0,0,0,0.2);
">
    <div style="text-align: center; font-weight: bold; margin-bottom: 12px; color: #0078D7; font-size: 16px;">
        🏫 School Legend
    </div>

    <div style="display: table; width: 100%; margin-bottom: 8px;">
        <div style="display: table-row;">
            <div style="display: table-cell; vertical-align: middle; padding-right: 10px; width: 30px;">
                <div style="width: 20px; height: 20px; border: 2px solid darkgreen; border-radius: 50%; background-color: rgba(0, 128, 0, 0.7);"></div>
            </div>
            <div style="display: table-cell; vertical-align: middle;">
                High School ({high_school_count})
            </div>
        </div>
    </div>

    <div style="display: table; width: 100%; margin-bottom: 8px;">
        <div style="display: table-row;">
            <div style="display: table-cell; vertical-align: middle; padding-right: 10px; width: 30px;">
                <div style="width: 20px; height: 20px; border: 2px solid darkpurple; border-radius: 50%; background-color: rgba(128, 0, 128, 0.7);"></div>
            </div>
            <div style="display: table-cell; vertical-align: middle;">
                Middle School ({non_isolated_count})
            </div>
        </div>
    </div>

    <div style="display: table; width: 100%; margin-bottom: 8px;">
        <极div style="display: table-row;">
            <div style="display: table-cell; vertical-align: middle; padding-right: 10px; width: 30px;">
                <div style="width: 20px; height: 20px; border: 2px solid gold; border-radius: 50%; background-color: rgba(218, 165, 32, 0.7);"></div>
            </div>
            <div style="display: table-cell; vertical-align: middle;">
                Isolated - High Enrollment ({isolated_high_enrollment_count})
            </div>
        </div>
    </div>

    <div style="display: table; width: 100%;">
        <div style="display: table-row;">
            <div style="display: table-cell; vertical-align: middle; padding-right: 10px; width: 30px;">
                <div style="width: 20px; height: 20px; border: 2px solid darkorange; border-radius: 50%; background-color: rgba(255, 165, 0, 0.7);"></div>
            </div>
            <div style="display: table-cell; vertical-align: middle;">
                Isolated - Low Enrollment ({isolated_low_enrollment_count})
            </div>
        </div>
    </div>
</div>
'''

m.get_root().html.add_child(folium.Element(legend_html))

# Create main layout with larger map
st.title("🌍 Punjab Region - Middle to High School Upgrade")

# Display school statistics - added detailed middle school counts
col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
with col_stat1:
    st.metric("🏫 Total Schools", len(filtered_data))
with col_stat2:
    st.metric("🎓 High Schools", high_school_count)
with col_stat3:
    st.metric("📚 Total Middle Schools", middle_school_count)
with col_stat4:
    st.metric("⭐ Isolated High Enrollment", isolated_high_enrollment_count)

# Add another row for the low enrollment count
col_stat5, col_stat6 = st.columns(2)
with col_stat5:
    st.metric("🟠 Isolated Low Enrollment", isolated_low_enrollment_count)

# Display the map with much larger dimensions
col_map, col_info = st.columns([3, 1])

with col_map:
    # Display the map with increased size
    map_data = st_folium(
        m,
        width=1200,
        height=800,
        returned_objects=["last_clicked", "bounds", "zoom"]
    )

with col_info:
    st.header("Quick Info")
    st.info("""
    **Map Controls:**
    - 🖱️ Scroll to zoom
    - 🖱️ Drag to pan
    - 📍 Click to capture coordinates
    - 🎯 Click markers for school info

    **School Colors:**
    -  Green: High Schools
    -  Yellow: Middle Schools with High Schools nearby
    -  Red: Isolated Middle Schools with Enrollment > 200
    -  Blue: Isolated Middle Schools with Enrollment ≤ 200
    """)

    if map_data and map_data.get("last_clicked"):
        lat = map_data["last_clicked"]["lat"]
        lng = map_data["last_clicked"]["lng"]
        st.success(f"**Last Click:** {lat:.6f}, {lng:.6f}")

# Initialize session state for clicked coordinates history
if 'click_history' not in st.session_state:
    st.session_state.click_history = []

# Store last clicked coordinates
if map_data and map_data.get("last_clicked"):
    lat = map_data["last_clicked"]["lat"]
    lng = map_data["last_clicked"]["lng"]
    coord_text = f"{lat:.6f}, {lng:.6f}"

    # Add to history if it's a new click
    if not st.session_state.click_history or st.session_state.click_history[0] != coord_text:
        st.session_state.click_history.insert(0, coord_text)
        # Keep only last 10 clicks
        st.session_state.click_history = st.session_state.click_history[:10]

# Streamlit Menu Below Map
st.markdown("---")
st.header("📍 Map Interaction Tools")

# Create tabs for different functionalities
tab1, tab2, tab3 = st.tabs(["📏 Distance Calculator", "📍 Clicked Coordinates", "📊 Data Statistics"])

with tab1:
    st.subheader("Distance Calculator")

    # Create two columns for the calculator
    col1, col2 = st.columns(2)

    with col1:
        st.write("**Point 1**")
        point1_lat = st.number_input("Latitude", value=31.5204, format="%.6f", key="point1_lat")
        point1_lon = st.number_input("Longitude", value=74.3587, format="%.6f", key="point1_lon")

    with col2:
        st.write("**Point 2**")
        point2_lat = st.number_input("Latitude", value=31.5497, format="%.6f", key="point2_lat")
        point2_lon = st.number_input("Longitude", value=74.3436, format="%.6f", key="point2_lon")


    # Calculate distance function for the clicked coordinates on the map
    def calculate_distance(lat1, lon1, lat2, lon2):
        # Haversine formula
        R = 6371  # Earth radius in kilometers
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) * math.sin(dlat / 2) +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon / 2) * math.sin(dlon / 2))
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = R * c
        return distance


    # Calculate and display results
    if st.button("Calculate Distance", type="primary", key="calc_dist"):
        try:
            distance_km = calculate_distance(point1_lat, point1_lon, point2_lat, point2_lon)
            st.success(f"**Distance between points:** {distance_km:.2f} km")

            # Additional information
            col_info1, col_info2, col_info3 = st.columns(3)
            with col_info1:
                st.metric("Point 1", f"{point1_lat:.6f}, {point1_lon:.6f}")
            with col_info2:
                st.metric("Point 2", f"{point2_lat:.6f}, {point2_lon:.6f}")
            with col_info3:
                st.metric("Straight-line Distance", f"{distance_km:.2f} km")

        except Exception as e:
            st.error(f"Error calculating distance: {e}")

with tab2:
    st.subheader("Clicked Coordinates")

    if st.session_state.click_history:
        # Current clicked coordinates
        current_coords = st.session_state.click_history[0]
        lat, lng = map(float, current_coords.split(', '))
        st.success("✅ Coordinates captured from map click!")

        col_curr1, col_curr2 = st.columns([3, 1])
        with col_curr1:
            st.text_input("Current Coordinates:", value=current_coords, key="current_coords", disabled=True)
        with col_curr2:
            if st.button("📋 Copy", key="copy_coords"):
                st.toast("Coordinates copied to clipboard!", icon="📋")

        # Quick actions with current coordinates
        st.write("**Quick Actions:**")
        action_col1, action_col2 = st.columns(2)
        with action_col1:
            if st.button("Use for Point 1", key="use_point1"):
                st.session_state.point1_lat = lat
                st.session_state.point1_lon = lng
                st.rerun()
        with action_col2:
            if st.button("Use for Point 2", key="use_point2"):
                st.session_state.point2_lat = lat
                st.session_state.point2_lon = lng
                st.rerun()

        # Click history
        st.write("**Recent Clicks:**")
        for i, coords in enumerate(st.session_state.click_history[:5]):
            col_hist1, col_hist2 = st.columns([4, 1])
            with col_hist1:
                st.code(coords, language="text")
            with col_hist2:
                if st.button("Use", key=f"use_{i}"):
                    lat_hist, lng_hist = map(float, coords.split(', '))
                    st.session_state.point1_lat = lat_hist
                    st.session_state.point1_lon = lng_hist
                    st.rerun()
    else:
        st.info("Click anywhere on the map to capture coordinates here")
        st.write("**How to use:**")
        st.write("1. Click on any location on the map above")
        st.write("2. The coordinates will automatically appear here")
        st.write("3. Use the buttons to populate the distance calculator")

with tab3:
    st.subheader("Data Statistics")

    col_stat1, col_stat2, col_stat3 = st.columns(3)
    with col_stat1:
        st.metric("Total Data Points", f"{stats['total_points']:,}")
        st.metric("Maximum Density", f"{stats['max']:,.0f}")
    with col_stat2:
        st.metric("Average Density", f"{stats['mean']:,.0f}")
        st.metric("Minimum Density", f"{stats['min']:,.0f}")
    with col_stat3:
        st.metric("Standard Deviation", f"{stats['std']:,.0f}")
        st.metric("Median Density", f"{stats['median']:,.0f}")

    st.write("**Quantiles:**")
    col_q1, col_q2, col_q3 = st.columns(3)
    with col_q1:
        st.metric("25th Percentile", f"{stats['q25']:,.0f}")
    with col_q2:
        st.metric("75th Percentile", f"{stats['q75']:,.0f}")
    with col_q3:
        st.metric("90th Percentile", f"{stats['q90']:,.0f}")

    st.write("**School Statistics:**")
    col_sch1, col_sch2, col_sch3, col_sch4 = st.columns(4)
    with col_sch1:
        st.metric("High Schools", high_school_count)
    with col_sch2:
        st.metric("Total Middle Schools", middle_school_count)
    with col_sch3:
        st.metric("Isolated High Enrollment", isolated_high_enrollment_count)
    with col_sch4:
        st.metric("Isolated Low Enrollment", isolated_low_enrollment_count)

# Instructions section
with st.expander("ℹ️ How to use this application"):
    st.markdown("""
    ### 🗺️ Map Interaction Guide

    **Clicking on the Map:**
    - Click anywhere on the map to capture coordinates
    - The coordinates will appear in the "Clicked Coordinates" tab

    **Distance Calculator:**
    - Enter coordinates manually or use map clicks
    - Click "Calculate Distance" to get straight-line distance
    - Results show in kilometers using Haversine formula

    **Map Features:**
    - **Heat Map**: Population density visualization
    - ** Green Circles**: High Schools (Male)
    - ** Yellow Circles**: Middle Schools with High Schools nearby
    - ** Red Circles**: Isolated Middle Schools with Enrollment > 200
    - ** Blue Circles**: Isolated Middle Schools with Enrollment ≤ 200
    - **Statistics Panel**: Top-right shows data metrics
    - **Legend**: Bottom-right explains map symbols

    **Data Information:**
    - Population density data from CSV files
    - School data includes both High and Middle Schools (Male)
    - All coordinates in decimal degrees format
    - Enrollment data displayed in school popups
    - Isolated Middle Schools are those with no High Schools within 5km radius
    """)

# Save the map option
st.markdown("---")
if st.button("💾 Save Map as HTML File"):
    m.save('population_heatmap.html')
    st.success("Map saved as 'population_heatmap.html'")
    st.info("You can open this file in any web browser to view the map offline")

# Footer
st.markdown("---")
st.caption("🌍 Built with Streamlit, Folium, and Python | Population Density Analysis Tool")

# Convert directly to DataFrame
dfx = pd.DataFrame(upgrade_candidates, columns=['Latitude', 'Longitude', 'School_Name', 'EMIS_code', 'total_enrollment'])
dflow = pd.DataFrame(lowenrol, columns=['Latitude', 'Longitude', 'School_Name', 'EMIS_code', 'total_enrollment'])
st.dataframe(dfx)
st.dataframe(dflow)
# Save to CSV
#dfx.to_csv('/Users/muhammadwisalabdullah/Downloads/schools_data.csv', index=False)
#print("CSV file saved successfully!")
#print(f"DataFrame shape: {dfx.shape}")

import folium
from datetime import datetime
