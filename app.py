import streamlit as st
import gspread
import json
import google.generativeai as genai

# ==========================================
# CONFIGURACIÓN DEL PROFESOR
NOMBRE_DEL_EXCEL = "Base de Datos - Examen Biología DESARROLLAR"
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"] 
# ==========================================

genai.configure(api_key=GEMINI_API_KEY)
modelo = genai.GenerativeModel('gemini-2.5-flash') 

st.set_page_config(page_title="Corrector IA - Biología", layout="wide")
st.title("🔬 Panel de Corrección Asistida por IA")

@st.cache_resource
def conectar_sheets():
    # Lee el archivo JSON desde la memoria segura de Streamlit
    credenciales_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
    gc = gspread.service_account_from_dict(credenciales_dict)
    sh = gc.open(NOMBRE_DEL_EXCEL)
    return sh

try:
    sh = conectar_sheets()
    hoja_preguntas = sh.worksheet("Preguntas")
    hoja_respuestas = sh.worksheet("Respuestas")
except Exception as e:
    st.error(f"Error al conectar con el Excel. Detalle: {e}")
    st.stop()

datos_preguntas = hoja_preguntas.get_all_records()
mapa_preguntas = {}
for fila in datos_preguntas:
    if str(fila.get('Tipo', '')).strip().upper() == 'PREGUNTA':
        mapa_preguntas[str(fila.get('ID', ''))] = fila.get('Contenido', '')

datos_respuestas = hoja_respuestas.get_all_records()
pendientes = [r for r in datos_respuestas if str(r.get('Nota Final', '')).strip() == ""]

st.sidebar.header("Alumnos Pendientes")

if not pendientes:
    st.sidebar.success("¡Todo corregido! 🎉")
    st.info("No hay exámenes pendientes de corrección.")
else:
    opciones_alumnos = {f"{r['Nombre']}": r for r in pendientes}
    seleccionado = st.sidebar.radio("Seleccioná un alumno:", list(opciones_alumnos.keys()))
    
    alumno = opciones_alumnos[seleccionado]
    st.subheader(f"Examen de {alumno['Nombre']}")
    st.caption(f"Registro de Auditoría: {alumno.get('Auditoría', 'Sin datos')}")
    
    respuestas_json = alumno.get('Respuestas del alumno', '{}')
    try:
        respuestas_dict = json.loads(respuestas_json)
    except:
        respuestas_dict = {}
        
    texto_para_ia = f"Alumno: {alumno['Nombre']}\n\n"
    
    for id_preg, preg_texto in mapa_preguntas.items():
        rta_alumno = respuestas_dict.get(id_preg, "(Sin responder)")
        st.markdown(f"**Pregunta:** {preg_texto}")
        st.info(f"**Respuesta:** {rta_alumno}")
        texto_para_ia += f"Pregunta: {preg_texto}\nRespuesta del alumno: {rta_alumno}\n\n"
        
    st.divider()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🤖 Pre-corrección con Gemini")
        if st.button("Generar análisis de la IA"):
            with st.spinner("Analizando respuestas..."):
                prompt = f"""
                Actúa como un profesor de Biología de escuela secundaria en Argentina. 
                Analiza las siguientes respuestas del alumno. 
                Señala sus aciertos, detecta errores conceptuales o cosas que faltaron desarrollar, y sugiere una nota del 1 al 10.
                Sé constructivo, claro y empático. Hablale directamente al alumno.
                
                {texto_para_ia}
                """
                respuesta_ia = modelo.generate_content(prompt)
                st.session_state[f"ia_{alumno['DNI']}"] = respuesta_ia.text
                
        sugerencia_actual = st.session_state.get(f"ia_{alumno['DNI']}", "")
        if sugerencia_actual:
            st.write(sugerencia_actual)
            
    with col2:
        st.markdown("### 📝 Tu Corrección Definitiva")
        st.write("Acá definís qué le llega al alumno (podés copiar y pegar partes del análisis de la IA).")
        
        with st.form("form_correccion"):
            comentario_final = st.text_area("Devolución para el alumno:", height=250)
            nota_final = st.number_input("Nota final (1 a 10):", min_value=1.0, max_value=10.0, step=0.5)
            btn_guardar = st.form_submit_button("💾 Guardar Nota en el Excel")
            
            if btn_guardar:
                if comentario_final.strip() == "":
                    st.warning("Escribí un comentario antes de guardar.")
                else:
                    celda_dni = hoja_respuestas.find(str(alumno['DNI']))
                    if celda_dni:
                        fila = celda_dni.row
                        hoja_respuestas.update(f'G{fila}:I{fila}', [[sugerencia_actual, comentario_final, nota_final]])
                        st.success("¡Nota guardada correctamente! Pasando al siguiente...")
                        st.rerun()
