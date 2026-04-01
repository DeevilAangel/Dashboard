def inject_styles():
    import streamlit as st
    st.markdown("""
<style>
/* === Tema Dark Gaming UEFN === */

/* Fundo principal */
.stApp {
    background-color: #0a0a0f;
    color: #e0e0e0;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: #0d0d1a;
    border-right: 1px solid #1a1a2e;
}

/* Header / Título */
h1 {
    background: linear-gradient(90deg, #00d4ff, #7b2ff7);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-weight: 800;
    font-size: 2rem !important;
}

h2, h3 {
    color: #00d4ff;
}

/* Input de chat */
[data-testid="stChatInput"] textarea {
    background-color: #12121f !important;
    border: 1px solid #2a2a4a !important;
    color: #e0e0e0 !important;
    border-radius: 12px !important;
}

[data-testid="stChatInput"] textarea:focus {
    border-color: #00d4ff !important;
    box-shadow: 0 0 8px rgba(0, 212, 255, 0.3) !important;
}

/* Mensagens do chat - utilizador */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    background-color: #0f1a2a !important;
    border-left: 3px solid #00d4ff;
    border-radius: 8px;
    padding: 8px;
}

/* Mensagens do chat - assistente */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
    background-color: #0d0d1a !important;
    border-left: 3px solid #7b2ff7;
    border-radius: 8px;
    padding: 8px;
}

/* Blocos de código */
.stCode, [data-testid="stCode"] {
    background-color: #0d1117 !important;
    border: 1px solid #00d4ff33 !important;
    border-radius: 8px !important;
}

/* Botões */
.stButton > button {
    background: linear-gradient(135deg, #12121f, #1a1a35);
    color: #00d4ff;
    border: 1px solid #00d4ff44;
    border-radius: 8px;
    font-weight: 600;
    transition: all 0.2s ease;
    width: 100%;
    text-align: left;
}

.stButton > button:hover {
    background: linear-gradient(135deg, #1a1a35, #0f2040);
    border-color: #00d4ff;
    box-shadow: 0 0 12px rgba(0, 212, 255, 0.3);
    color: #ffffff;
}

/* Botão de limpar histórico */
.stButton > button[kind="secondary"] {
    color: #ff6b35;
    border-color: #ff6b3544;
}

.stButton > button[kind="secondary"]:hover {
    border-color: #ff6b35;
    box-shadow: 0 0 12px rgba(255, 107, 53, 0.3);
}

/* Banner de boas-vindas */
.welcome-banner {
    background: linear-gradient(135deg, #0d0d2b, #0a1a2e);
    border: 1px solid #00d4ff22;
    border-radius: 12px;
    padding: 24px;
    margin: 16px 0;
}

.welcome-step {
    display: inline-block;
    background: #00d4ff22;
    border: 1px solid #00d4ff44;
    border-radius: 20px;
    padding: 4px 12px;
    margin: 4px;
    font-size: 0.85rem;
    color: #00d4ff;
}

/* Caption / texto secundário */
.stCaption {
    color: #6a7a9a !important;
}

/* Scrollbar personalizada */
::-webkit-scrollbar {
    width: 6px;
}
::-webkit-scrollbar-track {
    background: #0a0a0f;
}
::-webkit-scrollbar-thumb {
    background: #2a2a4a;
    border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
    background: #00d4ff44;
}

/* Divider */
hr {
    border-color: #1a1a2e !important;
}

/* Expander */
.streamlit-expanderHeader {
    background-color: #0d0d1a !important;
    color: #00d4ff !important;
}

/* Info / warning boxes */
.stAlert {
    background-color: #0d1117 !important;
    border: 1px solid #2a2a4a !important;
}
</style>
""", unsafe_allow_html=True)
