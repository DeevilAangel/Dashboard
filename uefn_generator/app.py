import os
import re
import streamlit as st
from dotenv import load_dotenv

from styles import inject_styles
from claude_client import stream_response

# --- CONFIGURAÇÃO ---
load_dotenv()

st.set_page_config(
    page_title="UEFN AI Map Generator",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_styles()

# --- SESSION STATE ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None

# --- PROMPTS DE EXEMPLO ---
EXAMPLE_PROMPTS = [
    "🏟️ Arena circular com 4 portões de entrada e cobertura central",
    "🧱 Labirinto 5x5 com corredores e saídas",
    "🏔️ Plataforma central elevada com rampas nos 4 lados",
    "⚔️ Arena simétrica 1v1 com 3 níveis de altura",
    "🌲 Campo aberto com floresta nas bordas e bunkers centrais",
    "🏰 Castelo medieval com muralhas, torres e pátio interior",
]

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("## 🗺️ UEFN AI Map Generator")
    st.markdown("---")

    st.markdown("### 💡 Exemplos Rápidos")
    st.caption("Clica para usar como prompt")

    for prompt in EXAMPLE_PROMPTS:
        if st.button(prompt, key=f"btn_{prompt[:20]}"):
            st.session_state.pending_prompt = prompt

    st.markdown("---")

    st.markdown("### ⚙️ Configurações")
    st.caption("Modelo: Claude Opus 4.6")
    st.caption("Thinking: Adaptativo")

    if st.button("🗑️ Limpar Histórico", type="secondary"):
        st.session_state.messages = []
        st.rerun()

    st.markdown("---")
    st.markdown("### 📋 Como usar")
    st.markdown("""
1. Descreve o teu mapa
2. Copia o código gerado
3. No UEFN: **Tools → Execute Python Script**
4. Cola e executa!
    """)
    st.markdown("---")
    st.caption("Powered by Claude Opus 4.6")


# --- HEADER ---
st.title("🗺️ UEFN AI Map Generator")
st.caption("Descreve o teu mapa Fortnite → Obtém código Python → Cola no UEFN")


# --- WELCOME BANNER (só quando o histórico está vazio) ---
def render_welcome_banner():
    st.markdown("""
<div class="welcome-banner">
    <h3 style="color: #00d4ff; margin-top: 0;">👋 Bem-vindo ao UEFN AI Map Generator!</h3>
    <p>Descreve o mapa que queres criar em linguagem natural e a IA gera código Python
    pronto a executar no UEFN.</p>
    <div style="margin: 16px 0;">
        <span class="welcome-step">1️⃣ Descreve o mapa</span>
        <span style="color: #4a5a6a; margin: 0 8px;">→</span>
        <span class="welcome-step">2️⃣ Obtém código Python</span>
        <span style="color: #4a5a6a; margin: 0 8px;">→</span>
        <span class="welcome-step">3️⃣ Cola no UEFN</span>
    </div>
    <details>
        <summary style="color: #00d4ff; cursor: pointer;">Ver exemplo de código gerado</summary>
        <pre style="background: #0d1117; border: 1px solid #00d4ff33; border-radius: 8px;
                    padding: 12px; margin-top: 8px; overflow-x: auto; font-size: 0.8rem;">
# Arena Circular com 4 Portões
import math

cube_class = unreal.load_class(None, '/Script/Engine.StaticMeshActor')
WALL_MESH = '/Game/StarterContent/Shapes/Shape_Cube.uasset'

# --- MURALHA CIRCULAR ---
radius = 3000
segments = 32
wall_height = 600

for i in range(segments):
    angle = (2 * math.pi / segments) * i
    x = radius * math.cos(angle)
    y = radius * math.sin(angle)
    yaw = math.degrees(angle) + 90

    actor = actor_sub.spawn_actor_from_class(
        cube_class,
        unreal.Vector(x, y, wall_height / 2),
        unreal.Rotator(0, yaw, 0)
    )
    actor.set_actor_scale3d(unreal.Vector(3.0, 0.5, wall_height / 100))
    actor.set_actor_label(f'Wall_Seg_{i}')
        </pre>
    </details>
</div>
""", unsafe_allow_html=True)


# --- RENDERIZAR MENSAGEM COM CÓDIGO DESTACADO ---
def render_message_content(content: str, container):
    """Renderiza conteúdo com blocos de código em destaque."""
    parts = re.split(r'(```python\n.*?```)', content, flags=re.DOTALL)
    for part in parts:
        if part.startswith('```python'):
            code = re.sub(r'^```python\n|```$', '', part, flags=re.DOTALL)
            container.code(code, language="python")
        elif part.strip():
            container.markdown(part)


# --- HISTÓRICO DO CHAT ---
def render_chat_history():
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            render_message_content(msg["content"], st)


# --- LÓGICA PRINCIPAL ---
if not st.session_state.messages:
    render_welcome_banner()

render_chat_history()

# Obter prompt: do input direto ou do botão da sidebar
prompt = st.chat_input("Descreve o mapa que queres criar no UEFN...")

if st.session_state.pending_prompt:
    prompt = st.session_state.pending_prompt
    st.session_state.pending_prompt = None

if prompt:
    # Adicionar mensagem do utilizador
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Streaming da resposta do assistente
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        full_response = ""
        cursor = "▌"

        try:
            # Construir histórico para a API (max 20 mensagens para não exceder contexto)
            api_messages = st.session_state.messages[-20:]

            for chunk in stream_response(api_messages):
                full_response += chunk
                response_placeholder.markdown(full_response + cursor)

            # Re-renderizar final com blocos de código destacados
            response_placeholder.empty()
            render_message_content(full_response, st)

        except ValueError as e:
            error_msg = f"⚠️ **Erro de configuração**: {e}"
            response_placeholder.error(error_msg)
            full_response = error_msg

        except Exception as e:
            error_msg = f"⚠️ **Erro**: {str(e)}"
            response_placeholder.error(error_msg)
            full_response = error_msg

    # Guardar resposta no histórico
    st.session_state.messages.append({"role": "assistant", "content": full_response})
