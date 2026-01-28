import os
from datetime import datetime

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="MDExtractor", page_icon="📄", layout="wide")

st.title("MDExtractor")
st.caption("Upload DOCX files and view recent documents.")

col_upload, col_list = st.columns([1, 1.2], gap="large")

with col_upload:
    st.subheader("Upload")
    st.write("Drag and drop a DOCX file below.")
    file = st.file_uploader("Choose a DOCX file", type=["docx"])
    if file is not None:
        if st.button("Upload", type="primary"):
            with st.spinner("Uploading..."):
                response = requests.post(
                    f"{API_URL}/documents",
                    files={"file": (file.name, file.getvalue())},
                    timeout=30,
                )
            if response.ok:
                st.success("Uploaded successfully.")
            else:
                st.error(f"Upload failed: {response.status_code} {response.text}")

with col_list:
    st.subheader("Recent uploads")
    if st.button("Refresh"):
        st.session_state["refresh"] = datetime.utcnow().isoformat()

    try:
        response = requests.get(f"{API_URL}/documents", params={"limit": 25}, timeout=10)
        if response.ok:
            data = response.json()
            items = data.get("items", [])
            if not items:
                st.info("No uploads yet.")
            else:
                for item in items:
                    with st.container(border=True):
                        st.write(item["original_filename"])
                        st.caption(f"{item['status']} · {item['created_at']} · {item['storage_url']}")
        else:
            st.error(f"Failed to load documents: {response.status_code} {response.text}")
    except requests.RequestException as exc:
        st.error(f"API unavailable: {exc}")
