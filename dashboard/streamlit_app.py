#!/usr/bin/env python3
"""
Streamlit Dashboard for Real-Time Person Tracking
Live view with statistics, analytics, and system monitoring
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from utilities.id_manager import RedisIDManager
from utilities.database import DatabaseManager

# Page config
st.set_page_config(
    page_title="Person Tracking Dashboard",
    page_icon="👥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
.big-font {
    font-size:30px !important;
    font-weight: bold;
}
.metric-card {
    background-color: #f0f2f6;
    padding: 20px;
    border-radius: 10px;
    margin: 10px 0;
}
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def init_managers():
    """Initialize ID manager and database"""
    id_mgr = RedisIDManager(use_redis=True, ttl_hours=24)
    db = DatabaseManager(use_postgres=True)
    return id_mgr, db


def main():
    """Main dashboard"""

    st.title("👥 Real-Time Person Tracking Dashboard")
    st.markdown("---")

    # Initialize managers
    id_mgr, db = init_managers()

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Settings")

        camera_id = st.selectbox(
            "Camera",
            ["cam_0", "cam_1", "cam_2", "all"],
            index=0
        )

        refresh_rate = st.slider(
            "Refresh Rate (seconds)",
            min_value=1,
            max_value=30,
            value=5
        )

        st.markdown("---")
        st.header("📊 System Info")

        # ID Manager stats
        stats = id_mgr.get_stats(camera_id if camera_id != "all" else "cam_0")
        st.metric("Backend", stats['backend'])
        st.metric("Cached IDs", stats.get('person_count', 0))
        st.metric("TTL", f"{stats['ttl_hours']}h")

        if st.button("🔄 Clear Cache"):
            id_mgr.clear_expired()
            st.success("Cache cleared!")

    # Main content
    col1, col2, col3, col4 = st.columns(4)

    # Get today's stats
    date = datetime.now().date()
    if camera_id != "all":
        daily_stats = db.get_daily_stats(camera_id, date)
    else:
        daily_stats = {
            'total_unique': 0,
            'max_density': 0,
            'avg_fps': 0,
            'detections_count': 0
        }

    if daily_stats:
        with col1:
            st.metric(
                "Total Unique Today",
                daily_stats.get('total_unique', 0),
                delta="+5 vs yesterday"  # TODO: Calculate from DB
            )

        with col2:
            st.metric(
                "Max Density",
                daily_stats.get('max_density', 0),
                delta="Peak crowd"
            )

        with col3:
            st.metric(
                "Avg FPS",
                f"{daily_stats.get('avg_fps', 0):.1f}",
                delta="System performance"
            )

        with col4:
            st.metric(
                "Detections",
                daily_stats.get('detections_count', 0),
                delta="Total today"
            )

    st.markdown("---")

    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Live Stats",
        "📈 Analytics",
        "🎥 Camera Feed",
        "🔍 Search"
    ])

    with tab1:
        st.header("Live Statistics")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Current Status")

            # Real-time metrics (placeholder)
            st.metric("People in Frame", 3)
            st.metric("Active Tracks", 5)
            st.metric("Tracking Accuracy", "94.5%")

            # Camera motion
            st.subheader("Camera Motion")
            motion_status = st.empty()
            motion_status.success("✅ Camera stable")

        with col2:
            st.subheader("Recent Detections")

            # Create sample recent detections dataframe
            recent_df = pd.DataFrame({
                'Time': [
                    (datetime.now() - timedelta(seconds=i*10)).strftime('%H:%M:%S')
                    for i in range(5)
                ],
                'Person ID': [1, 2, 3, 4, 5],
                'Confidence': [0.95, 0.92, 0.88, 0.91, 0.94],
                'Status': ['Counted', 'Counted', 'Counted', 'Counted', 'Counted']
            })

            st.dataframe(recent_df, use_container_width=True)

    with tab2:
        st.header("Analytics & Trends")

        # Time series plot
        st.subheader("Hourly Traffic")

        # Generate sample data
        hours = list(range(24))
        counts = [5, 3, 2, 1, 1, 3, 8, 15, 25, 30, 28, 32, 35, 33, 30, 28, 25, 30, 35, 28, 20, 15, 10, 7]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=hours,
            y=counts,
            mode='lines+markers',
            name='People Count',
            line=dict(color='#1f77b4', width=3),
            marker=dict(size=8)
        ))

        fig.update_layout(
            title='People Count by Hour',
            xaxis_title='Hour of Day',
            yaxis_title='Unique People',
            hovermode='x unified',
            height=400
        )

        st.plotly_chart(fig, use_container_width=True)

        # Distribution
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Daily Comparison")

            days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            values = [120, 135, 128, 142, 150, 95, 88]

            fig = px.bar(
                x=days,
                y=values,
                labels={'x': 'Day', 'y': 'People Count'},
                title='Weekly Traffic Pattern'
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Peak Hours")

            peak_data = pd.DataFrame({
                'Time': ['9-10 AM', '12-1 PM', '5-6 PM'],
                'Count': [35, 32, 35],
                'Type': ['Morning', 'Lunch', 'Evening']
            })

            fig = px.pie(
                peak_data,
                values='Count',
                names='Time',
                title='Peak Hour Distribution'
            )
            st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.header("Camera Feed")
        st.info("📹 Live camera feed would be displayed here via WebRTC or MJPEG stream")

        # Placeholder for video feed
        video_placeholder = st.empty()
        video_placeholder.image(
            "https://via.placeholder.com/640x480/1f77b4/ffffff?text=Camera+Feed",
            caption=f"Camera: {camera_id}",
            use_column_width=True
        )

        # Controls
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("⏸️ Pause"):
                st.info("Feed paused")
        with col2:
            if st.button("📸 Snapshot"):
                st.success("Snapshot saved!")
        with col3:
            if st.button("🔄 Restart"):
                st.info("Feed restarted")

    with tab4:
        st.header("Search & Filter")

        # Search controls
        col1, col2 = st.columns(2)

        with col1:
            search_date = st.date_input(
                "Date",
                value=datetime.now().date()
            )

        with col2:
            search_time = st.time_input(
                "Time",
                value=datetime.now().time()
            )

        # Person ID search
        person_id = st.number_input(
            "Person ID",
            min_value=1,
            max_value=10000,
            value=1
        )

        if st.button("🔍 Search"):
            # Get person from ID manager
            person_data = id_mgr.get_person(person_id, camera_id)

            if person_data:
                st.success(f"Found Person #{person_id}")

                # Display person info
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric("First Seen", person_data.get('first_seen', 'N/A'))
                with col2:
                    st.metric("Last Seen", person_data.get('last_seen', 'N/A'))
                with col3:
                    st.metric("Seen Count", person_data.get('seen_count', 0))

                # Show image if available
                image_path = person_data.get('image_path')
                if image_path and Path(image_path).exists():
                    st.image(image_path, caption=f"Person #{person_id}", width=300)

            else:
                st.warning(f"Person #{person_id} not found in cache")

    # Auto-refresh
    st.markdown("---")
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    st.caption(f"Auto-refresh every {refresh_rate} seconds")


if __name__ == "__main__":
    main()

