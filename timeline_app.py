import streamlit as st
import PyPDF2
import os
from datetime import datetime

# Import the local NLP summarization tools
import nltk
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lex_rank import LexRankSummarizer

# Ensure the local language tokenizer is downloaded
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

st.set_page_config(page_title="Local NLP Ofgem Timeline", layout="wide")

# 1. PDF Text Extraction Engine
def extract_text_from_pdf(pdf_path):
    try:
        text = ""
        with open(pdf_path, "rb") as file:
            reader = PyPDF2.PdfReader(file)
            # Read just the first 5 pages where the Executive Summary lives
            num_pages = min(5, len(reader.pages))
            for i in range(num_pages):
                page_text = reader.pages[i].extract_text()
                if page_text:
                    text += page_text + "\n"
        return text
    except Exception as e:
        return ""

# 2. Local Mathematical Summarization Engine
@st.cache_data(show_spinner=False)
def generate_local_summary(pdf_path):
    """Uses a local LexRank algorithm to find the 4 most important sentences."""
    if not os.path.exists(pdf_path):
        return ["⚠️ PDF file not found in the local repository."]
        
    raw_text = extract_text_from_pdf(pdf_path)
    if not raw_text.strip():
        return ["⚠️ Could not extract readable text from this PDF."]
    
    try:
        # Feed the text to the NLP parser
        parser = PlaintextParser.from_string(raw_text, Tokenizer("english"))
        summarizer = LexRankSummarizer()
        
        # Ask the algorithm for the top 4 sentences
        summary_sentences = summarizer(parser.document, 4)
        
        # Clean up the output into a list of strings
        return [str(sentence).strip() for sentence in summary_sentences]
    
    except Exception as e:
        return [f"⚠️ Local summarization failed: {e}"]

# 3. The Repository Ledger
REGULATORY_DOCS = [
    {
        "Cap_Period": "Oct 2026 - Dec 2026",
        "Publication_Date": datetime(2026, 8, 25),
        "File_Path": "pdfs/ofgem_cap_oct2026.pdf",
        "PDF_Link": "https://www.ofgem.gov.uk/"
    },
    {
        "Cap_Period": "Jul 2026 - Sept 2026",
        "Publication_Date": datetime(2026, 5, 22),
        "File_Path": "pdfs/ofgem_cap_jul2026.pdf",
        "PDF_Link": "https://www.ofgem.gov.uk/"
    }
]

# Sort newest to top
REGULATORY_DOCS.sort(key=lambda x: x["Publication_Date"], reverse=True)

# 4. Build the UI
st.title("📑 NLP Regulatory Timeline")
st.write("Upload official Ofgem PDFs, and local algorithms will extract the core methodology changes automatically.")
st.markdown("---")

current_time = datetime.now()

# 5. Render the Timeline
for doc in REGULATORY_DOCS:
    pub_date = doc["Publication_Date"]
    
    if pub_date.year == current_time.year and pub_date.month == current_time.month:
        badge = '<span style="background-color:#2ecc71; color:white; padding:4px 8px; border-radius:4px; font-weight:bold; font-size:12px;">🟢 CURRENT CAP</span>'
    elif pub_date > current_time:
        badge = '<span style="background-color:#f1c40f; color:black; padding:4px 8px; border-radius:4px; font-weight:bold; font-size:12px;">🟡 UPCOMING</span>'
    else:
        badge = '<span style="background-color:#95a5a6; color:white; padding:4px 8px; border-radius:4px; font-weight:bold; font-size:12px;">⚫ HISTORICAL</span>'

    col_date, col_line, col_content = st.columns([2, 0.5, 7])
    
    with col_date:
        st.write(f"### {pub_date.strftime('%d %b %Y')}")
        st.markdown(badge, unsafe_allow_html=True)
        
    with col_line:
        st.markdown('<div style="border-left: 3px solid #34495e; height: 100%; min-height: 200px; margin-left: 20px; opacity: 0.6;"></div>', unsafe_allow_html=True)
        
    with col_content:
        st.markdown(f"## {doc['Cap_Period']}")
        
        with st.spinner("NLP scanning document..."):
            extracted_points = generate_local_summary(doc["File_Path"])
            
        st.markdown("**Core Extraction:**")
        # Format the top 4 sentences as bullet points
        for point in extracted_points:
            st.write(f"- {point}")
            
        st.markdown(f"<br>[🔗 View Original Ofgem Document]({doc['PDF_Link']})", unsafe_allow_html=True)
        
    st.markdown("<br>", unsafe_allow_html=True)
