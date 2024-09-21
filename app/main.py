import streamlit as st
from my_library import get_assets
st.title("Assets in Cognite Data Fusion")

st.write(get_assets())