import os
from PIL import Image
import streamlit as st

from core.remover import (
    composite_background,
    export_image_bytes,
    get_session,
    load_and_normalize_image,
    remove_background,
)

# Page configuration
st.set_page_config(
    page_title="Background Remover Pro",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for polished interface
st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #888888;
        margin-bottom: 1.5rem;
    }
    .stDownloadButton button {
        background-color: #28a745 !important;
        color: white !important;
        font-weight: 600 !important;
        border: none !important;
    }
    .stDownloadButton button:hover {
        background-color: #218838 !important;
        color: white !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)

st.markdown('<div class="main-title">✨ Background Remover Pro</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">AI-powered image background removal and replacement. Fast, secure, and running locally.</div>',
    unsafe_allow_html=True,
)

# Initialize Session State
if "processed_image" not in st.session_state:
    st.session_state.processed_image = None
if "current_file_id" not in st.session_state:
    st.session_state.current_file_id = None
if "final_display_image" not in st.session_state:
    st.session_state.final_display_image = None

# Sidebar Controls
with st.sidebar:
    st.header("⚙️ Settings & Options")

    bg_mode = st.radio(
        "Background Fill:",
        options=["Transparent", "Solid White", "Solid Black", "Custom Color"],
        index=0,
        help="Select background type for the processed image.",
    )

    custom_color = "#FFFFFF"
    if bg_mode == "Custom Color":
        custom_color = st.color_picker("Pick Background Color", "#3498DB")

    export_format = st.selectbox(
        "Export Format:",
        options=["PNG", "JPEG", "WEBP"],
        index=0,
        help="PNG and WEBP preserve transparency. JPEG uses the selected solid fill or white.",
    )

    with st.expander("🛠️ Advanced Settings", expanded=False):
        use_alpha_matting = st.checkbox(
            "Enable Alpha Matting",
            value=False,
            help="Refines boundaries for tricky subjects like hair, fur, or semi-transparent fabrics.",
        )
        fg_threshold = st.slider("Foreground Threshold", 100, 255, 240, disabled=not use_alpha_matting)
        bg_threshold = st.slider("Background Threshold", 0, 100, 10, disabled=not use_alpha_matting)
        erode_size = st.slider("Erode Size", 1, 30, 10, disabled=not use_alpha_matting)

    st.markdown("---")
    st.markdown("💡 **Tip**: Process once, and you can switch background colors instantly without re-processing!")

# File Uploader
uploaded_file = st.file_uploader(
    "📂 Choose an image to process...",
    type=["jpg", "jpeg", "png", "webp", "bmp"],
    help="Supported formats: JPG, PNG, WEBP, BMP",
)

# Reset state if a new file is uploaded
if uploaded_file is not None:
    file_identifier = f"{uploaded_file.name}_{uploaded_file.size}"
    if st.session_state.current_file_id != file_identifier:
        st.session_state.current_file_id = file_identifier
        st.session_state.processed_image = None
        st.session_state.final_display_image = None

if uploaded_file is not None:
    original_image = load_and_normalize_image(uploaded_file)
    base_name = os.path.splitext(uploaded_file.name)[0]

    col1, col2 = st.columns(2, gap="medium")

    with col1:
        st.subheader("Original Image")
        st.image(original_image, use_container_width=True)
        st.caption(f"Dimensions: {original_image.width} × {original_image.height} px | Format: {uploaded_file.type}")

    with col2:
        st.subheader("Processed Result")
        result_container = st.container()

        # Check if already processed
        if st.session_state.processed_image is None:
            result_container.info("Click **⚡ Remove Background** below to start processing.")
        else:
            # Apply selected background fill instantly without re-running AI
            raw_cutout = st.session_state.processed_image
            if bg_mode == "Solid White":
                display_img = composite_background(raw_cutout, "#FFFFFF")
            elif bg_mode == "Solid Black":
                display_img = composite_background(raw_cutout, "#000000")
            elif bg_mode == "Custom Color":
                display_img = composite_background(raw_cutout, custom_color)
            else:
                display_img = raw_cutout

            st.session_state.final_display_image = display_img
            result_container.image(display_img, use_container_width=True)

    st.markdown("---")

    # Action Buttons Row
    b_col1, b_col2, b_col3 = st.columns([2, 2, 1])

    with b_col1:
        process_clicked = st.button("⚡ Remove Background", type="primary", use_container_width=True)

    with b_col2:
        # Download button remains active across reruns because of session_state
        if st.session_state.final_display_image is not None:
            fill_color = custom_color if bg_mode == "Custom Color" else (
                "#FFFFFF" if bg_mode == "Solid White" else ("#000000" if bg_mode == "Solid Black" else "#FFFFFF")
            )
            export_bytes, mime_type, file_ext = export_image_bytes(
                st.session_state.final_display_image,
                format=export_format,
                bg_fill=fill_color,
            )
            download_filename = f"{base_name}_no_bg{file_ext}"

            st.download_button(
                label=f"💾 Download ({export_format})",
                data=export_bytes,
                file_name=download_filename,
                mime=mime_type,
                use_container_width=True,
            )
        else:
            st.button("💾 Download Result", disabled=True, use_container_width=True)

    with b_col3:
        if st.session_state.processed_image is not None:
            if st.button("🔄 Reset", use_container_width=True):
                st.session_state.processed_image = None
                st.session_state.final_display_image = None
                st.rerun()

    if process_clicked:
        with st.spinner("⏳ Removing background, please wait..."):
            try:
                session = get_session(force_cpu=True)
                raw_result = remove_background(
                    original_image,
                    session=session,
                    alpha_matting=use_alpha_matting,
                    alpha_matting_foreground_threshold=fg_threshold,
                    alpha_matting_background_threshold=bg_threshold,
                    alpha_matting_erode_size=erode_size,
                )
                st.session_state.processed_image = raw_result
                st.success("✔ Background removed successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"✖ Error occurred during processing: {e}")
else:
    # Empty placeholder guide
    st.info("👆 Please upload an image file (JPG, PNG, WEBP, or BMP) to get started.")