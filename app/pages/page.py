import streamlit as st
from my_library import get_assets
st.title("This is a page in the app")

st.write(get_assets())