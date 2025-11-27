# -*- coding: utf-8 -*-
"""
Módulo de generación de reportes para el sistema de parqueadero
Incluye exportación a Excel y PDF
"""

from io import BytesIO
from datetime import datetime, timedelta
from django.http import HttpResponse
from django.db.models import Sum, Count, Avg, Q
from django.utils import timezone
import xlsxwriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

from .models import ParkingTicket, PaymentMethod, Mensualidad


def export_to_excel(parking_lot, start_date, end_date, tickets, payment_summary, category_stats, mensualidades=None):
    """
    Exporta el reporte a Excel con múltiples hojas
    Incluye tickets y mensualidades
    """
    if mensualidades is None:
        mensualidades = []
    
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output)
    
    # Formatos
    title_format = workbook.add_format({
        'bold': True,
        'font_size': 16,
        'align': 'center',
        'valign': 'vcenter',
        'bg_color': '#2563eb',
        'font_color': 'white'
    })
    
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#dbeafe',
        'border': 1,
        'align': 'center',
        'valign': 'vcenter'
    })
    
    cell_format = workbook.add_format({
        'border': 1,
        'align': 'left',
        'valign': 'vcenter'
    })
    
    number_format = workbook.add_format({
        'border': 1,
        'align': 'right',
        'num_format': '$#,##0.00'
    })
    
    date_format = workbook.add_format({
        'border': 1,
        'align': 'center',
        'num_format': 'dd/mm/yyyy hh:mm'
    })
    
    # Hoja 1: Resumen General
    worksheet1 = workbook.add_worksheet('Resumen General')
    worksheet1.set_column('A:A', 30)
    worksheet1.set_column('B:B', 20)
    
    row = 0
    worksheet1.merge_range(row, 0, row, 1, f'REPORTE DE PARQUEADERO - {parking_lot.empresa}', title_format)
    row += 2
    
    worksheet1.write(row, 0, 'Período:', header_format)
    worksheet1.write(row, 1, f'{start_date.strftime("%d/%m/%Y")} - {end_date.strftime("%d/%m/%Y")}', cell_format)
    row += 1
    
    worksheet1.write(row, 0, 'Fecha de Generación:', header_format)
    worksheet1.write(row, 1, datetime.now().strftime("%d/%m/%Y %H:%M"), cell_format)
    row += 2
    
    # Resumen por medio de pago
    worksheet1.write(row, 0, 'RESUMEN POR MEDIO DE PAGO', header_format)
    worksheet1.write(row, 1, '', header_format)
    row += 1
    
    worksheet1.write(row, 0, 'Medio de Pago', header_format)
    worksheet1.write(row, 1, 'Total Recaudado', header_format)
    row += 1
    
    total_general = 0
    for payment in payment_summary:
        worksheet1.write(row, 0, payment['payment_method__nombre'] or 'Sin especificar', cell_format)
        worksheet1.write(row, 1, float(payment['total'] or 0), number_format)
        total_general += float(payment['total'] or 0)
        row += 1
    
    worksheet1.write(row, 0, 'TOTAL GENERAL', header_format)
    worksheet1.write(row, 1, total_general, number_format)
    row += 2
    
    # Resumen por categoría
    worksheet1.write(row, 0, 'RESUMEN POR CATEGORÍA', header_format)
    worksheet1.write(row, 1, '', header_format)
    row += 1
    
    worksheet1.write(row, 0, 'Categoría', header_format)
    worksheet1.write(row, 1, 'Total Recaudado', header_format)
    row += 1
    
    for cat in category_stats:
        worksheet1.write(row, 0, cat['category__name'], cell_format)
        worksheet1.write(row, 1, float(cat['revenue'] or 0), number_format)
        row += 1
    
    # Hoja 2: Detalle de Tickets
    worksheet2 = workbook.add_worksheet('Detalle de Tickets')
    worksheet2.set_column('A:A', 12)
    worksheet2.set_column('B:B', 18)
    worksheet2.set_column('C:C', 18)
    worksheet2.set_column('D:D', 15)
    worksheet2.set_column('E:E', 12)
    worksheet2.set_column('F:F', 15)
    worksheet2.set_column('G:G', 15)
    
    row = 0
    worksheet2.merge_range(row, 0, row, 6, 'DETALLE DE TICKETS', title_format)
    row += 1
    
    headers = ['Placa', 'Entrada', 'Salida', 'Categoría', 'Horas', 'Monto', 'Medio de Pago']
    for col, header in enumerate(headers):
        worksheet2.write(row, col, header, header_format)
    row += 1
    
    for ticket in tickets:
        worksheet2.write(row, 0, ticket.placa, cell_format)
        worksheet2.write_datetime(row, 1, ticket.entry_time, date_format)
        if ticket.exit_time:
            worksheet2.write_datetime(row, 2, ticket.exit_time, date_format)
        else:
            worksheet2.write(row, 2, 'En parqueadero', cell_format)
        worksheet2.write(row, 3, ticket.category.name, cell_format)
        worksheet2.write(row, 4, ticket.get_duration(), cell_format)
        worksheet2.write(row, 5, float(ticket.amount_paid or 0), number_format)
        worksheet2.write(row, 6, ticket.payment_method.nombre if ticket.payment_method else 'No especificado', cell_format)
        row += 1
    
    # Hoja 3: Detalle de Mensualidades
    if mensualidades:
        worksheet3 = workbook.add_worksheet('Mensualidades')
        worksheet3.set_column('A:A', 20)
        worksheet3.set_column('B:B', 12)
        worksheet3.set_column('C:C', 15)
        worksheet3.set_column('D:D', 18)
        worksheet3.set_column('E:E', 12)
        worksheet3.set_column('F:F', 15)
        
        row = 0
        worksheet3.merge_range(row, 0, row, 5, 'DETALLE DE MENSUALIDADES', title_format)
        row += 1
        
        headers = ['Cliente', 'Placa', 'Categoría', 'Fecha de Pago', 'Monto', 'Medio de Pago']
        for col, header in enumerate(headers):
            worksheet3.write(row, col, header, header_format)
        row += 1
        
        for mensualidad in mensualidades:
            worksheet3.write(row, 0, mensualidad.cliente.nombre, cell_format)
            worksheet3.write(row, 1, mensualidad.cliente.placa, cell_format)
            worksheet3.write(row, 2, mensualidad.category.name, cell_format)
            if mensualidad.fecha_pago:
                worksheet3.write_datetime(row, 3, mensualidad.fecha_pago, date_format)
            else:
                worksheet3.write(row, 3, 'Sin pago', cell_format)
            worksheet3.write(row, 4, float(mensualidad.monto or 0), number_format)
            worksheet3.write(row, 5, mensualidad.payment_method.nombre if mensualidad.payment_method else 'No especificado', cell_format)
            row += 1
    
    workbook.close()
    output.seek(0)
    
    return output


def export_to_pdf(parking_lot, start_date, end_date, tickets, payment_summary, category_stats, mensualidades=None):
    """
    Exporta el reporte a PDF
    Incluye tickets y mensualidades
    """
    if mensualidades is None:
        mensualidades = []
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=18)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Estilo personalizado para el título
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#2563eb'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    # Título
    title = Paragraph(f'REPORTE DE PARQUEADERO<br/>{parking_lot.empresa}', title_style)
    elements.append(title)
    elements.append(Spacer(1, 12))
    
    # Información del período
    info_data = [
        ['Período:', f'{start_date.strftime("%d/%m/%Y")} - {end_date.strftime("%d/%m/%Y")}'],
        ['Fecha de Generación:', datetime.now().strftime("%d/%m/%Y %H:%M")],
        ['Total de Tickets:', str(len(tickets))],
        ['Total de Mensualidades:', str(len(mensualidades))]
    ]
    
    info_table = Table(info_data, colWidths=[2*inch, 4*inch])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#dbeafe')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey)
    ]))
    
    elements.append(info_table)
    elements.append(Spacer(1, 20))
    
    # Resumen por medio de pago
    elements.append(Paragraph('RESUMEN POR MEDIO DE PAGO', styles['Heading2']))
    elements.append(Spacer(1, 12))
    
    payment_data = [['Medio de Pago', 'Cantidad', 'Total Recaudado']]
    total_general = 0
    
    for payment in payment_summary:
        payment_data.append([
            payment['payment_method__nombre'] or 'Sin especificar',
            str(payment['count']),
            f"${payment['total']:,.2f}"
        ])
        total_general += float(payment['total'] or 0)
    
    payment_data.append(['TOTAL GENERAL', '', f'${total_general:,.2f}'])
    
    payment_table = Table(payment_data, colWidths=[3*inch, 1.5*inch, 2*inch])
    payment_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#dbeafe')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey)
    ]))
    
    elements.append(payment_table)
    elements.append(Spacer(1, 20))
    
    # Resumen por categoría
    elements.append(Paragraph('RESUMEN POR CATEGORÍA', styles['Heading2']))
    elements.append(Spacer(1, 12))
    
    category_data = [['Categoría', 'Cantidad', 'Total Recaudado']]
    
    for cat in category_stats:
        category_data.append([
            cat['category__name'],
            str(cat['count']),
            f"${cat['revenue']:,.2f}"
        ])
    
    category_table = Table(category_data, colWidths=[3*inch, 1.5*inch, 2*inch])
    category_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#059669')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey)
    ]))
    
    elements.append(category_table)
    
    # Construir PDF
    doc.build(elements)
    buffer.seek(0)
    
    return buffer


def generate_chart_data(tickets, start_date, end_date):
    """
    Genera datos para los gráficos de Chart.js
    """
    import json
    from collections import defaultdict
    
    # Datos para gráfico de ocupación por hora
    ocupacion_por_hora = defaultdict(int)
    for ticket in tickets:
        if ticket.entry_time:
            hora = ticket.entry_time.hour
            ocupacion_por_hora[hora] += 1
    
    ocupacion_labels = [f"{h:02d}:00" for h in range(24)]
    ocupacion_data = [ocupacion_por_hora.get(h, 0) for h in range(24)]
    
    # Datos para gráfico de categorías
    categorias_count = defaultdict(int)
    for ticket in tickets:
        if ticket.category:
            categorias_count[ticket.category.name] += 1
    
    categorias_labels = list(categorias_count.keys())
    categorias_data = list(categorias_count.values())
    
    # Datos para gráfico de métodos de pago
    pagos_count = defaultdict(int)
    for ticket in tickets:
        if ticket.payment_method:
            pagos_count[ticket.payment_method.nombre] += 1
        else:
            pagos_count['Sin especificar'] += 1
    
    pagos_labels = list(pagos_count.keys())
    pagos_data = list(pagos_count.values())
    
    chart_data = {
        'ocupacion_labels': ocupacion_labels,
        'ocupacion_data': ocupacion_data,
        'categorias_labels': categorias_labels,
        'categorias_data': categorias_data,
        'pagos_labels': pagos_labels,
        'pagos_data': pagos_data,
    }
    
    return json.dumps(chart_data)
