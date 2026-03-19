import streamlit as st
import pandas as pd
from bot import fill_form_from_excel
import io

# --- Template columns for assessment data ---
TEMPLATE_COLUMNS = [
    "GR NO",
    "English",
    "Mathematics",
    "Science",
    "Sindhi / Urdu",
    "Islamiat",
    "Social Studies",
    "Presence Status",
    "B Form Number",
    "Result Entered By",
]

st.set_page_config(page_title="SAF Assessment Bot", page_icon="🤖", layout="centered")
st.title("SAF Assessment Bot")
st.caption("Automate assessment result entry on au.sefedu.com")

# --- Template Download ---
template = pd.DataFrame(columns=TEMPLATE_COLUMNS)
# Add a sample row for reference
sample_row = {
    "GR NO": 820,
    "English": 75, "Mathematics": 80, "Science": 65,
    "Sindhi / Urdu": 30, "Islamiat": 25, "Social Studies": 20,
    "Presence Status": "present",
    "B Form Number": "000000",
    "Result Entered By": "",
}
template = pd.concat([template, pd.DataFrame([sample_row])], ignore_index=True)

output = io.BytesIO()
with pd.ExcelWriter(output, engine='openpyxl') as writer:
    template.to_excel(writer, index=False)
excel_data = output.getvalue()

st.download_button(
    label="Download Template",
    data=excel_data,
    file_name="template.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

st.divider()

# --- File Upload ---
uploaded_file = st.file_uploader("Upload your assessment Excel file", type="xlsx")

if uploaded_file is not None:
    data = pd.read_excel(uploaded_file)
    data.columns = data.columns.str.strip()

    # Validate required column
    if "GR NO" not in data.columns:
        st.error("Missing required column: **GR NO**. Please use the template.", icon="🚨")
    else:
        # Check which subject columns are present
        subject_cols = ["English", "Mathematics", "Science", "Sindhi / Urdu", "Islamiat", "Social Studies"]
        present_subjects = [col for col in subject_cols if col in data.columns]
        missing_subjects = [col for col in subject_cols if col not in data.columns]

        if missing_subjects:
            st.warning(f"Missing subject columns (will be skipped): {', '.join(missing_subjects)}")

        st.success(f"Loaded **{len(data)}** student records with marks for: {', '.join(present_subjects)}")
        st.dataframe(data, use_container_width=True)

        st.divider()

        # --- Login Credentials ---
        st.subheader("Portal Credentials")
        col1, col2 = st.columns(2)
        with col1:
            username = st.text_input("Username (Email)")
        with col2:
            password = st.text_input("Password", type="password")

        result_entered_by = st.text_input(
            "Result Entered By (optional, applies to all)",
            help="If set, this name will be filled in the 'Result Entered By' field for every student. "
                 "Individual values in the Excel column will override this."
        )

        st.divider()

        # --- Run Bot ---
        if st.button("Start Filling Assessment Results", type="primary", use_container_width=True):
            if not username or not password:
                st.error("Please enter both username and password.", icon="🚨")
            else:
                with st.spinner("Bot is running... Check the browser window and `process_log.txt` for progress."):
                    fill_form_from_excel(
                        data, username, password,
                        result_entered_by=result_entered_by if result_entered_by else None
                    )
                st.success("Bot has finished processing! Check `process_log.txt` for details.", icon="✅")