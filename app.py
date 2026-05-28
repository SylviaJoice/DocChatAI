import os
import io
from docx import Document
from PIL import Image
import pandas as pd
import streamlit as st
import fitz
import google.generativeai as genai

genai.configure(
    api_key=st.secrets["GEMINI_API_KEY"]
)
model = genai.GenerativeModel("gemini-2.5-flash-lite")

st.set_page_config(page_title="DocChatAI", layout="wide")
st.markdown("""
<style>
.stApp { background-color: #111111; }
.block-container { max-width: 900px; padding-top: 2rem; }
.main-title {
    text-align: center;
    font-size: 34px;
    font-weight: 700;
    color: #F5F5F5;
    margin-bottom: 6px;
}
.sub-title {
    text-align: center;
    font-size: 15px;
    color: #A3A3A3;
    margin-bottom: 30px;
}
[data-testid="stSidebar"] { background-color: #181818; }
.footer {
    text-align: center;
    color: #777;
    font-size: 12px;
    margin-top: 25px;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="main-title">DocChatAI</div>
<div class="sub-title">Upload a document and ask questions in a conversational format</div>
""", unsafe_allow_html=True)

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "document_text" not in st.session_state:
    st.session_state.document_text = ""

if "dataframe" not in st.session_state:
    st.session_state.dataframe = None
if "uploaded_image" not in st.session_state:
    st.session_state.uploaded_image = None
if "image_bytes" not in st.session_state:
    st.session_state.image_bytes = None

if "image_type" not in st.session_state:
    st.session_state.image_type = None

def find_column_from_question(df, question):
    question = question.lower()

    for col in df.columns:
        if str(col).lower() in question:
            return col

    return None


with st.sidebar:
    st.subheader("Document")

    uploaded_file = st.file_uploader(
        "Upload File",
        type=["pdf", "docx", "xlsx", "csv", "png", "jpg", "jpeg", "webp"]
    )

    if st.button("Clear Conversation"):
        st.session_state.chat_history = []
        st.session_state.document_text = ""
        st.session_state.dataframe = None
        st.rerun()

    st.markdown("---")
    st.caption("Basic Document Q&A System")

if uploaded_file:

    text = ""

    st.session_state.dataframe = None
    st.session_state.uploaded_image = None

    # PDF
    if uploaded_file.name.endswith(".pdf"):

        pdf_document = fitz.open(
            stream=uploaded_file.read(),
            filetype="pdf"
        )

        for page in pdf_document:
            text += page.get_text()

    # WORD
    elif uploaded_file.name.endswith(".docx"):

        doc = Document(uploaded_file)

        for para in doc.paragraphs:
            text += para.text + "\n"

    # EXCEL
    elif uploaded_file.name.endswith(".xlsx"):

        df = pd.read_excel(uploaded_file)

        st.session_state.dataframe = df

        text = df.to_string()

    # CSV
    elif uploaded_file.name.endswith(".csv"):

        df = pd.read_csv(uploaded_file)

        st.session_state.dataframe = df

        text = df.to_string()

    # IMAGE
    elif uploaded_file.name.endswith(("png", "jpg", "jpeg", "webp")):

     image = Image.open(uploaded_file).convert("RGB")

    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format="PNG")

    st.session_state.uploaded_image = image
    st.session_state.image_bytes = img_byte_arr.getvalue()
    st.session_state.image_type = "image/png"

    text = "Image uploaded for visual question answering."
    st.session_state.document_text = text

    st.success("Document uploaded successfully. You can start asking questions.")

    for chat in st.session_state.chat_history:

        with st.chat_message("user"):
            st.write(chat["question"])

        with st.chat_message("assistant"):
            st.write(chat["answer"])

    question = st.chat_input("Ask a question about the document")

    if question:

        lower_question = question.lower()

        math_keywords = [
            "average",
            "mean",
            "sum",
            "total",
            "count",
            "maximum",
            "minimum",
            "highest",
            "lowest"
        ]

        is_math_question = any(
            word in lower_question
            for word in math_keywords
        )

        with st.chat_message("user"):
            st.write(question)

        # PANDAS CALCULATIONS
        if is_math_question and st.session_state.dataframe is not None:

            df = st.session_state.dataframe

            numeric_cols = df.select_dtypes(include="number").columns

            answer = ""

            selected_col = find_column_from_question(df, question)

            if selected_col is None and len(numeric_cols) > 0:
                selected_col = numeric_cols[0]

            if ("average" in lower_question or "mean" in lower_question) and selected_col is not None:

                avg = df[selected_col].mean()

                answer = f"The average of {selected_col} is {avg:.2f}"

            elif ("maximum" in lower_question or "highest" in lower_question) and selected_col is not None:

                maximum = df[selected_col].max()

                answer = f"The highest value in {selected_col} is {maximum}"

            elif ("minimum" in lower_question or "lowest" in lower_question) and selected_col is not None:

                minimum = df[selected_col].min()

                answer = f"The lowest value in {selected_col} is {minimum}"

            elif ("sum" in lower_question or "total" in lower_question) and selected_col is not None:

                total = df[selected_col].sum()

                answer = f"The total of {selected_col} is {total}"

            elif "count" in lower_question:

                answer = f"The dataset contains {len(df)} rows."

            else:

                answer = "I could not identify the calculation request."

            with st.chat_message("assistant"):
                st.write(answer)

        # IMAGE + NORMAL DOCUMENT QA
        else:

            # IMAGE QA
            if st.session_state.uploaded_image is not None:

                image_part = {
                    "mime_type": st.session_state.image_type,
                    "data": st.session_state.image_bytes
                }

                with st.chat_message("assistant"):
                    with st.spinner("Analyzing image..."):
                        response = model.generate_content([
                            question,
                            image_part
                        ])

                        answer = response.text
                        st.write(answer)

            # NORMAL DOCUMENT QA
            else:

                prompt = f"""
                You are a professional document question answering assistant.

                Answer only using the document content given below.
                If the answer is not found in the document, say:
                "I don't know from this document."

                Keep the answer clear and concise.

                DOCUMENT:
                {st.session_state.document_text[:6000]}

                QUESTION:
                {question}
                """

                with st.chat_message("assistant"):
                    with st.spinner("Generating answer..."):
                        response = model.generate_content(prompt)
                        answer = response.text
                        st.write(answer)