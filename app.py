import streamlit as st
from fpdf import FPDF
import datetime
import math
import os
from PIL import Image

# --- RUTAS ABSOLUTAS (Soluciona el problema de la imagen) ---
# Esto obliga a Python a buscar en la misma carpeta exacta donde está este archivo app.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PNG = os.path.join(BASE_DIR, "Jab3d.png")
LOGO_JPG = os.path.join(BASE_DIR, "Jab3d.jpg")

def obtener_ruta_logo():
    if os.path.exists(LOGO_PNG):
        return LOGO_PNG
    elif os.path.exists(LOGO_JPG):
        return LOGO_JPG
    return None

ruta_logo = obtener_ruta_logo()

# --- CONFIGURACIÓN DE LA PÁGINA Y FAVICON ---
# Cambiamos el ícono de la impresora por TU LOGO
try:
    icono_tab = Image.open(ruta_logo) if ruta_logo else "⚙️"
except Exception:
    icono_tab = "⚙️"

st.set_page_config(page_title="JAB 3D - Cotizador", page_icon=icono_tab, layout="centered")

# --- INYECCIÓN DE CSS (ESTILO OLED FORZADO) ---
st.markdown("""
    <style>
    /* Fondo negro puro OLED */
    .stApp {
        background-color: #000000;
    }
    /* Color blanco para textos base */
    p, span, label {
        color: #FFFFFF !important;
    }
    /* Estilo de las cajas de texto (Gris carbón) */
    .stTextInput input, .stNumberInput input {
        background-color: #151515 !important;
        color: #FDF23A !important;
        border: 1px solid #333333 !important;
        border-radius: 5px !important;
    }
    /* Estilo de la caja de selección (Dropdown) */
    div[data-baseweb="select"] > div {
        background-color: #151515 !important;
        color: #FDF23A !important;
        border: 1px solid #333333 !important;
    }
    /* Forzar color Amarillo JAB 3D al Botón Primario (Quitando el rojo por defecto) */
    button[kind="primary"] {
        background-color: #FDF23A !important;
        color: #000000 !important;
        font-weight: bold !important;
        font-size: 18px !important;
        border: 2px solid #FDF23A !important;
        border-radius: 8px !important;
        padding: 15px !important;
    }
    button[kind="primary"]:hover {
        background-color: #D9CF32 !important;
        border-color: #D9CF32 !important;
        color: #000000 !important;
    }
    /* Color para los números del tablero financiero */
    [data-testid="stMetricValue"] {
        color: #FDF23A !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- FUNCIONES DE CÁLCULO ---
def parsear_tiempo(texto_tiempo):
    texto = str(texto_tiempo).strip().lower()
    try:
        if 'h' in texto or 'm' in texto:
            horas = 0.0
            minutos = 0.0
            if 'h' in texto:
                partes = texto.split('h')
                horas = float(partes[0].strip() or 0)
                texto = partes[1].strip()
            if 'm' in texto:
                partes = texto.split('m')
                minutos = float(partes[0].strip() or 0)
            return horas + (minutos / 60.0)
        else:
            return float(texto)
    except Exception:
        return 0.0

def calcular_totales(tiempo_str, gramos, piezas, material, costo_manual, aplicar_iva):
    horas = parsear_tiempo(tiempo_str)
    if horas == 0 or gramos == 0 or piezas == 0:
        return None
        
    if material == "Costo Variable (Manual)":
        precio_kilo = float(costo_manual)
    else:
        materiales = {
            "PLA / PETG Estándar ($300/kg)": 300.0,
            "PLA PRO / Seda ($350/kg)": 350.0,
            "ABS / ASA (Alta Temp) ($350/kg)": 350.0,
            "PLA-CF Fibra Carbono ($400/kg)": 400.0,
            "TPU Flexible ($450/kg)": 450.0,
            "Polímero Alta Gama ($600/kg)": 600.0
        }
        precio_kilo = materiales.get(material, 300.0)

    precio_g = precio_kilo / 1000
    costo_kwh = 1.30
    consumo_w = 110
    desgaste_horas = 4320
    precio_repuestos = 3000
    margen_error = 0.40  
    
    if gramos < 50:
        margen_ganancia = 3.5
    elif gramos < 100:
        margen_ganancia = 3.0
    elif gramos < 200:
        margen_ganancia = 2.5
    elif gramos < 300:
        margen_ganancia = 2.0
    else:
        margen_ganancia = 1.5   
    
    costo_material = gramos * precio_g
    costo_luz = horas * (consumo_w / 1000) * costo_kwh
    costo_desgaste = horas * (precio_repuestos / desgaste_horas)
    
    gastos_unitario = costo_luz + costo_desgaste + costo_material
    costo_error_unitario = gastos_unitario * margen_error
    precio_neto_unitario = gastos_unitario + costo_error_unitario
    precio_unitario_bruto = precio_neto_unitario * margen_ganancia
    
    tasa_iva = 0.16 if aplicar_iva else 0.0
    total_bruto = (precio_unitario_bruto * piezas) * (1 + tasa_iva)
    total_redondeado = math.ceil(total_bruto / 5.0) * 5.0
    
    subtotal_final = total_redondeado / (1 + tasa_iva)
    precio_unitario = subtotal_final / piezas
    iva_final = total_redondeado - subtotal_final
    
    gastos_totales = gastos_unitario * piezas
    fallos_totales = costo_error_unitario * piezas
    costo_base_total = precio_neto_unitario * piezas
    ganancia_neta = subtotal_final - costo_base_total
    
    return {
        'p_unitario': precio_unitario,
        'subtotal': subtotal_final,
        'iva': iva_final,
        'total': total_redondeado,
        'tasa_iva': tasa_iva,
        'gastos': gastos_totales,
        'fallos': fallos_totales,
        'ganancia': ganancia_neta
    }

# --- GENERADOR DE PDF ---
def generar_pdf(cliente, proyecto, material, piezas, dict_totales):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()
    pdf.set_fill_color(26, 26, 26) 
    pdf.rect(0, 0, 210, 35, 'F')
    
    if ruta_logo:
        try:
            pdf.image(ruta_logo, x=15, y=5, w=25)
        except Exception:
            pass 
        
    pdf.set_y(10)
    pdf.set_font('Arial', 'B', 22)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 10, 'COTIZACION', ln=True, align='R')
    pdf.set_font('Arial', '', 10)
    pdf.set_text_color(253, 242, 58) 
    pdf.cell(0, 5, 'IMPRIME TUS IDEAS - JAB 3D', ln=True, align='R')
    
    pdf.ln(20)
    fecha = datetime.date.today().strftime("%d/%m/%Y")
    pdf.set_font('Arial', 'B', 11)
    pdf.set_text_color(40, 40, 40)
    pdf.cell(120, 6, f'Atencion a: {cliente}', 0, 0, 'L')
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 6, f'Fecha: {fecha}', 0, 1, 'R')
    
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(120, 6, f'Producto(s): {proyecto}', 0, 0, 'L')
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 6, 'Vigencia: 15 dias habiles', 0, 1, 'R')
    pdf.ln(8)
    
    pdf.set_fill_color(40, 40, 40)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Arial', 'B', 10)
    
    pdf.cell(100, 9, ' Descripcion de Manufactura', 0, 0, 'L', fill=True)
    pdf.cell(20, 9, ' Cant.', 0, 0, 'C', fill=True)
    pdf.cell(35, 9, ' P. Unitario', 0, 0, 'R', fill=True)
    pdf.cell(35, 9, ' Importe', 0, 1, 'R', fill=True)
    
    pdf.set_text_color(30, 30, 30)
    y_start = pdf.get_y() + 2
    
    pdf.set_xy(10, y_start)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(100, 5, f'{proyecto}', 0, 1, 'L')
    
    pdf.set_font('Arial', '', 9)
    pdf.set_text_color(90, 90, 90)
    pdf.set_x(10)
    pdf.cell(100, 5, f'Tecnologia: Impresion 3D FDM', 0, 1, 'L')
    pdf.set_x(10)
    pdf.cell(100, 5, f'Material principal: {material}', 0, 1, 'L')
    
    pdf.set_xy(110, y_start + 4)
    pdf.set_font('Arial', '', 10)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(20, 5, f'{piezas}', 0, 0, 'C')
    pdf.cell(35, 5, f"${dict_totales['p_unitario']:,.2f}", 0, 0, 'R')
    pdf.cell(35, 5, f"${dict_totales['subtotal']:,.2f}", 0, 1, 'R')
    
    pdf.ln(8)
    pdf.set_draw_color(220, 220, 220)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)
    
    pdf.set_font('Arial', '', 11)
    pdf.cell(120, 7, '', 0, 0)
    pdf.cell(35, 7, 'Subtotal:', 0, 0, 'R')
    pdf.cell(35, 7, f"${dict_totales['subtotal']:,.2f}", 0, 1, 'R')
    
    pdf.cell(120, 7, '', 0, 0)
    texto_iva = 'IVA (16%):' if dict_totales['tasa_iva'] > 0 else 'IVA (0%):'
    pdf.cell(35, 7, texto_iva, 0, 0, 'R')
    pdf.cell(35, 7, f"${dict_totales['iva']:,.2f}", 0, 1, 'R')
    
    pdf.set_font('Arial', 'B', 12)
    pdf.set_fill_color(253, 242, 58) 
    pdf.cell(120, 9, '', 0, 0)
    pdf.cell(35, 9, 'TOTAL (MXN):', 0, 0, 'R')
    pdf.cell(35, 9, f"${dict_totales['total']:,.2f}", 0, 1, 'R', fill=True)
    
    pdf.set_y(260) 
    pdf.set_font('Arial', 'I', 8)
    pdf.set_text_color(130, 130, 130)
    pdf.cell(0, 4, 'Condiciones de servicio:', ln=True)
    pdf.cell(0, 4, 'El tiempo de fabricacion y entrega comenzara a transcurrir una vez confirmado el anticipo.', ln=True)
    pdf.cell(0, 4, 'Este documento constituye una estimacion comercial sujeta a los estandares de manufactura aditiva.', ln=True)
    
    temp_filename = "temp_cotizacion.pdf"
    pdf.output(temp_filename)
    with open(temp_filename, "rb") as pdf_file:
        PDFbyte = pdf_file.read()
    os.remove(temp_filename)
    return PDFbyte

# --- INTERFAZ WEB (STREAMLIT) ---
col1, col2, col3 = st.columns([1, 1.5, 1])
with col2:
    if ruta_logo:
        st.image(ruta_logo, use_container_width=True)

st.markdown("<h2 style='text-align: center; color: #FDF23A; margin-bottom: 30px;'>COTIZADOR WEB</h2>", unsafe_allow_html=True)

# Usamos HTML In-line para forzar el color de las etiquetas
st.markdown("<div style='color: #4BA1FF; font-weight: bold; font-size: 1.1em; margin-bottom: 5px;'>Cliente:</div>", unsafe_allow_html=True)
cliente = st.text_input("Cliente", label_visibility="collapsed")

st.markdown("<div style='color: #FF4B4B; font-weight: bold; font-size: 1.1em; margin-bottom: 5px;'>Descripción del Producto(s):</div>", unsafe_allow_html=True)
proyecto = st.text_input("Descripción", label_visibility="collapsed")

st.markdown("<div style='color: #2ECC71; font-weight: bold; font-size: 1.1em; margin-bottom: 5px;'>Tiempo (Ej. 3.5 o 90m o 2h30m):</div>", unsafe_allow_html=True)
tiempo_str = st.text_input("Tiempo", value="0", label_visibility="collapsed")

col_a, col_b = st.columns(2)
with col_a:
    st.markdown("<div style='color: #FDF23A; font-weight: bold; font-size: 1.1em; margin-bottom: 5px;'>Peso del material (g):</div>", unsafe_allow_html=True)
    gramos = st.number_input("Peso", min_value=0.0, value=0.0, step=1.0, label_visibility="collapsed")
with col_b:
    st.markdown("<div style='color: #4BA1FF; font-weight: bold; font-size: 1.1em; margin-bottom: 5px;'>Cantidad de productos:</div>", unsafe_allow_html=True)
    piezas = st.number_input("Cantidad", min_value=1, value=1, step=1, label_visibility="collapsed")

st.markdown("<div style='color: #FF4B4B; font-weight: bold; font-size: 1.1em; margin-bottom: 5px;'>Material Principal:</div>", unsafe_allow_html=True)
opciones_mat = [
    "PLA / PETG Estándar ($300/kg)",
    "PLA PRO / Seda ($350/kg)",
    "ABS / ASA (Alta Temp) ($350/kg)",
    "PLA-CF Fibra Carbono ($400/kg)",
    "TPU Flexible ($450/kg)",
    "Polímero Alta Gama ($600/kg)",
    "Costo Variable (Manual)"
]
material = st.selectbox("Material", opciones_mat, label_visibility="collapsed")

costo_manual = 0.0
if material == "Costo Variable (Manual)":
    st.markdown("<div style='color: #FDF23A; font-weight: bold; font-size: 1.1em; margin-bottom: 5px;'>Precio de 1kg ($):</div>", unsafe_allow_html=True)
    costo_manual = st.number_input("Precio Manual", min_value=0.0, value=300.0, step=10.0, label_visibility="collapsed")

aplicar_iva = st.checkbox("Aplicar IVA (16%)", value=False)

st.markdown("---")

# Tablero Financiero en Vivo
totales = calcular_totales(tiempo_str, gramos, piezas, material, costo_manual, aplicar_iva)

if totales:
    col_fin1, col_fin2, col_fin3 = st.columns(3)
    col_fin1.metric("Gastos Operativos", f"${totales['gastos']:,.2f}")
    col_fin2.metric("Fondo de Fallos", f"${totales['fallos']:,.2f}")
    col_fin3.metric("Ganancia Neta", f"${totales['ganancia']:,.2f}")
    
    texto_iva = "c/ IVA" if totales['tasa_iva'] > 0 else "s/ IVA"
    st.markdown(f"<h1 style='text-align: center; color: #2ECC71;'>PRECIO FINAL ({texto_iva}): ${totales['total']:,.2f}</h1>", unsafe_allow_html=True)
    
    # Lógica del botón de PDF (Siempre visible, pero requiere datos)
    if cliente and proyecto:
        nombre_mat_limpio = "Material de Ingeniería Custom" if material == "Costo Variable (Manual)" else material.split(" ($")[0]
        pdf_bytes = generar_pdf(cliente, proyecto, nombre_mat_limpio, piezas, totales)
        nombre_archivo = f"Cotizacion_{cliente.replace(' ', '_')}.pdf"
        
        st.download_button(
            label="📄 DESCARGAR COTIZACIÓN EN PDF",
            data=pdf_bytes,
            file_name=nombre_archivo,
            mime="application/pdf",
            type="primary",
            use_container_width=True
        )
    else:
        st.button("⚠️ INGRESA CLIENTE Y PRODUCTO PARA DESCARGAR PDF", disabled=True, type="primary", use_container_width=True)
else:
    st.markdown("<h4 style='text-align: center; color: #888888;'>Ingresa el tiempo y el peso para calcular...</h4>", unsafe_allow_html=True)