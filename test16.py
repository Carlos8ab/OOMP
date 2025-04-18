import os
import re
import xml.etree.ElementTree as ET
import textwrap
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

def format_unidad(unidad: str) -> str:
    """
    Convierte notaciones de exponentes en el texto, por ejemplo:
      "m^3" -> "m³"
      "m^2" -> "m²"
    Puede aplicarse tanto en la unidad como en otros textos (por ejemplo, en la descripción)
    que contengan notaciones similares.
    """
    mapping = {
        "0": "\u2070",  # ⁰
        "1": "\u00B9",  # ¹
        "2": "\u00B2",  # ²
        "3": "\u00B3",  # ³
        "4": "\u2074",  # ⁴
        "5": "\u2075",  # ⁵
        "6": "\u2076",  # ⁶
        "7": "\u2077",  # ⁷
        "8": "\u2078",  # ⁸
        "9": "\u2079",  # ⁹
    }
    def replace_func(match):
        digit = match.group(1)
        return mapping.get(digit, "")
    return re.sub(r'\^(\d)', replace_func, unidad)

def wrap_text(text, max_width, c, font_name, font_size):
    """
    Devuelve una lista de líneas de 'text' que no excedan 'max_width' en puntos.
    Se estima el número máximo de caracteres basándose en el ancho promedio de un carácter.
    """
    avg_char_width = c.stringWidth("M", font_name, font_size)
    if avg_char_width == 0:
        avg_char_width = 7  # valor por defecto
    max_chars = int(max_width // avg_char_width)
    lines = textwrap.wrap(text, width=max_chars)
    return lines

def draw_table_header(c, y, margen, header_x_cant, header_x_unidad, header_x_desc):
    """
    Dibuja el encabezado de la tabla de productos.
    """
    c.setFont("Helvetica-Bold", 10)
    c.drawString(header_x_cant, y, "CANT.")
    c.drawString(header_x_unidad, y, "UNIDAD")
    c.drawString(header_x_desc, y, "DESCRIPCIÓN")
    y -= 20
    return y

def draw_page_footer(c, width, margen):
    """
    Dibuja el pie de página, por ejemplo, mostrando el número de página.
    """
    c.setFont("Helvetica", 8)
    page_number = c.getPageNumber()
    c.drawCentredString(width / 2, margen / 2, f"Página {page_number}")

def generar_pdf_oc_desde_xml(xml_path, pdf_path, firma_image=None, logo_image="logo.jpg"):
    ns = {
       "cfdi": "http://www.sat.gob.mx/cfd/4",
       "tfd": "http://www.sat.gob.mx/TimbreFiscalDigital"
    }

    # Parsear el XML  
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # --- Datos extraídos del XML ---
    fecha_xml = root.attrib.get("Fecha", "Sin fecha")

    # Extraer los conceptos (productos/ítems)
    conceptos = []
    conceptos_node = root.find("cfdi:Conceptos", ns)
    if conceptos_node is not None:
        for concepto in conceptos_node.findall("cfdi:Concepto", ns):
            cantidad    = concepto.attrib.get("Cantidad", "")
            unidad      = concepto.attrib.get("Unidad", "")
            descripcion = concepto.attrib.get("Descripcion", "")
            # Se formatea la unidad que venga del XML (por ejemplo, "m^3" a "m³")
            unidad = format_unidad(unidad)
            # También se puede aplicar el formateo a la descripción para convertir exponentes
            descripcion = format_unidad(descripcion)
            conceptos.append((cantidad, unidad, descripcion))

    # --- Datos fijos (según el formato del Excel) ---
    titulo       = "ORDEN DE COMPRA"
    organismo    = "ORGANISMO OPERADOR MUNICIPAL DE AGUA POTABLE ALCANTARILLADO Y SANEAMIENTO"
    direccion    = "MAGDALENA DE KINO, SONORA."
    contacto     = "Matamoros s/n Col. Centro Teléfono (632) 32 23155"
    orden_compra = "2427516"
    bodega       = "BODEGA"  # Aunque existe, esta sección no se imprimirá

    # Datos dinámicos desde el usuario:
    departamento = input("Ingrese el Departamento que lo solicita: ").strip()
    persona = input("Ingrese la Persona que lo solicita: ").strip()
    proveedor = input("Ingrese el Proveedor: ").strip()

    # Opción para modificar "UNIDAD" si fuera necesario
    modificar_unidad = input("¿Desea modificar la información de 'UNIDAD' extraída del XML? (S/N): ").strip().lower()
    if modificar_unidad == 's':
        nuevos_conceptos = []
        for cantidad, unidad, descripcion in conceptos:
            nuevo_valor = input(f"Para el concepto con descripción '{descripcion}', la unidad es '{unidad}'. Ingrese nuevo valor (Enter para mantener): ").strip()
            if nuevo_valor != "":
                unidad = nuevo_valor
            # Se aplica el formateo, en caso de que el usuario ingrese una notación como m^3
            unidad = format_unidad(unidad)
            nuevos_conceptos.append((cantidad, unidad, descripcion))
        conceptos = nuevos_conceptos
    else:
        # Aseguramos que la unidad esté formateada
        conceptos = [(cantidad, format_unidad(unidad), descripcion) for cantidad, unidad, descripcion in conceptos]

    # Opción para modificar "DESCRIPCIÓN" si fuera necesario
    modificar_descripcion = input("¿Desea modificar la información de 'DESCRIPCIÓN' extraída del XML? (S/N): ").strip().lower()
    if modificar_descripcion == 's':
        nuevos_conceptos = []
        for cantidad, unidad, descripcion in conceptos:
            nuevo_texto = input(f"Para el concepto con cantidad '{cantidad}' y unidad '{unidad}', la descripción es '{descripcion}'. Ingrese nuevo valor (Enter para mantener): ").strip()
            if nuevo_texto != "":
                descripcion = nuevo_texto
            # Se aplica el formateo para la descripción, para convertir por ejemplo "m^2" a "m²"
            descripcion = format_unidad(descripcion)
            nuevos_conceptos.append((cantidad, unidad, descripcion))
        conceptos = nuevos_conceptos
    else:
        # Aseguramos el formateo en la descripción incluso si no se modifica
        conceptos = [(cantidad, unidad, format_unidad(descripcion)) for cantidad, unidad, descripcion in conceptos]

    # --- Datos para el pie de página extraídos del XML ---
    timbre = root.find(".//tfd:TimbreFiscalDigital", ns)
    folio_fiscal = timbre.attrib.get("UUID", "N/A") if timbre is not None else "N/A"

    serie = root.attrib.get("Serie", "")
    folio_attr = root.attrib.get("Folio", "")
    if not serie and not folio_attr:
        cfdi_no = "N/A"
    else:
        if serie and folio_attr:
            cfdi_no = f"{serie} {folio_attr}"
        elif serie:
            cfdi_no = serie
        else:
            cfdi_no = folio_attr

    formulado  = "Rodolfo Ochoa Ibarra"
    autorizado = "Maximino Leyva Soto"

    # --- Generación del PDF con ReportLab ---
    c = canvas.Canvas(pdf_path, pagesize=LETTER)
    width, height = LETTER
    margen = 50

    # --- Se dibuja el logotipo ---
    logo_width = 100
    logo_height = 50
    logo_x = margen
    if logo_image:
        if not os.path.exists(logo_image):
            c.rect(logo_x, height - logo_height, logo_width, logo_height)
            c.setFont("Helvetica-Oblique", 8)
            c.drawString(logo_x + 5, height - logo_height / 2, "Logo no encontrado")
        else:
            try:
                img = ImageReader(logo_image)
                c.drawImage(img, logo_x, height - logo_height, width=logo_width, height=logo_height, preserveAspectRatio=True)
            except Exception as e:
                c.rect(logo_x, height - logo_height, logo_width, logo_height)
                c.setFont("Helvetica-Oblique", 8)
                c.drawString(logo_x + 5, height - logo_height / 2, f"Error al cargar logo: {e}")
    else:
        c.rect(logo_x, height - logo_height, logo_width, logo_height)
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(logo_x + 5, height - logo_height / 2, "LOGO")

    # Ajustamos el encabezado para que no se superponga al logo.
    header_start_y = height - logo_height - 30
    y = header_start_y

    # Encabezado del documento (centrado)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2, y, titulo)
    y -= 20
    c.setFont("Helvetica", 12)
    c.drawCentredString(width / 2, y, organismo)
    y -= 20
    c.drawCentredString(width / 2, y, direccion)
    y -= 20
    c.drawCentredString(width / 2, y, contacto)
    y -= 30

    # Datos generales
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margen, y, "ORDEN DE COMPRA No:")
    c.setFont("Helvetica", 12)
    c.drawString(margen + 150, y, orden_compra)
    y -= 20

    c.setFont("Helvetica-Bold", 12)
    c.drawString(margen, y, "FECHA:")
    c.setFont("Helvetica", 12)
    c.drawString(margen + 150, y, fecha_xml)
    y -= 20

    c.setFont("Helvetica-Bold", 12)
    c.drawString(margen, y, "DEPARTAMENTO QUE LO SOLICITA:")
    c.setFont("Helvetica", 12)
    c.drawString(margen + 250, y, departamento)
    y -= 20

    c.setFont("Helvetica-Bold", 12)
    c.drawString(margen, y, "PERSONA QUE LO SOLICITA:")
    c.setFont("Helvetica", 12)
    c.drawString(margen + 250, y, persona)
    y -= 30

    # Posiciones para la tabla de productos
    header_x_cant   = margen
    header_x_unidad = margen + 100
    header_x_desc   = margen + 220
    max_width_desc = width - margen - header_x_desc

    # Dibuja la cabecera de la tabla
    y = draw_table_header(c, y, margen, header_x_cant, header_x_unidad, header_x_desc)

    # Imprimir cada concepto con ajuste (wrap) para la descripción
    c.setFont("Helvetica", 10)
    for item in conceptos:
        if y < 100:
            draw_page_footer(c, width, margen)
            c.showPage()
            y = height - margen
            # Reimprimir la cabecera en la nueva página.
            y = draw_table_header(c, y, margen, header_x_cant, header_x_unidad, header_x_desc)

        cantidad, unidad, desc = item
        row_start_y = y
        c.drawString(header_x_cant, row_start_y, str(cantidad))
        c.drawString(header_x_unidad, row_start_y, str(unidad))
        lines = wrap_text(desc, max_width_desc, c, "Helvetica", 10)
        for i, line in enumerate(lines):
            c.drawString(header_x_desc, row_start_y - i * 12, line)
        row_height = (len(lines) * 12) + 4
        y = row_start_y - row_height

    y -= 20
    c.line(margen, y, width - margen, y)
    y -= 20

    # Sección de observaciones: PROVEEDOR, Folio Fiscal y CFDI
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margen, y, "OBSERVACIONES:")
    y -= 20

    c.setFont("Helvetica-Bold", 12)
    c.drawString(margen, y, "PROVEEDOR:")
    c.setFont("Helvetica", 12)
    c.drawString(margen + 120, y, proveedor)
    y -= 20

    c.setFont("Helvetica-Bold", 12)
    c.drawString(margen, y, "Folio Fiscal:")
    c.setFont("Helvetica", 12)
    c.drawString(margen + 120, y, folio_fiscal)
    y -= 20

    c.setFont("Helvetica-Bold", 12)
    c.drawString(margen, y, "CFDI:")
    c.setFont("Helvetica", 12)
    c.drawString(margen + 120, y, cfdi_no)
    y -= 30

    c.setFont("Helvetica-Bold", 12)
    c.drawString(margen, y, "FORMULÓ")
    c.drawString(margen + 200, y, "AUTORIZÓ")
    y -= 20

    c.setFont("Helvetica", 12)
    c.drawString(margen, y, formulado)
    c.drawString(margen + 200, y, autorizado)
    y -= 40

    # Espacio para firma
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margen, y, "FIRMA:")
    firma_x = margen + 70
    firma_y = y - 40   # espacio vertical para la firma
    firma_width = 200
    firma_height = 50
    if firma_image:
        try:
            img_firma = ImageReader(firma_image)
            c.drawImage(img_firma, firma_x, firma_y, width=firma_width, height=firma_height, preserveAspectRatio=True)
        except Exception as e:
            c.rect(firma_x, firma_y, firma_width, firma_height)
            c.setFont("Helvetica-Oblique", 10)
            c.drawString(firma_x + 5, firma_y + firma_height/2, f"Error al cargar firma: {e}")
    else:
        c.rect(firma_x, firma_y, firma_width, firma_height)
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(firma_x + 5, firma_y + firma_height/2, "Firma digital o física")
    
    y = firma_y - 20

    # Dibuja el pie de página final antes de guardar el documento
    draw_page_footer(c, width, margen)
    
    c.save()
    print("PDF generado en:", pdf_path)

# Ejemplo de uso:
generar_pdf_oc_desde_xml("factura 4.xml", "Orden_Compra_Salida.pdf", firma_image=None, logo_image="logo.jpg")