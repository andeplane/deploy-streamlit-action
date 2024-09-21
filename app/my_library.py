import streamlit as st
from cognite.client import CogniteClient
client = CogniteClient()

# Cache the assets list
@st.cache_data
def get_assets():
    assets = client.assets.list(limit=1000).to_pandas()
    assets = assets.fillna(0)
    return assets