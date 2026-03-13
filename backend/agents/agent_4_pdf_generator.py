"""Agent 4: PDF Generator - Create professional PDFs with filled form data"""
import logging
import io
import base64
from typing import Dict, List, Any
from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import HexColor, black, grey
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from datetime import datetime

from agents.base import Agent, AgentInput, AgentOutput

logger = logging.getLogger(__name__)


class PDFGeneratorAgent(Agent):
    """
    Agent 4: Generate professional government-style PDFs with filled data
    
    Inputs:
        - mappings: List of field mappings with values
        - profile: Identity profile with confidence scores
        - form_title: Title of the form (e.g., "DS-160 Visa Application")
    
    Outputs:
        - pdf_base64: Base64 encoded PDF for download
        - pdf_bytes: Raw PDF bytes
        - file_name: Suggested filename for PDF
    """
    
    def __init__(self):
        super().__init__(name="PDFGenerator")
    
    async def execute(self, input_data: AgentInput) -> AgentOutput:
        """Generate PDF from field mappings"""
        
        mappings = input_data.metadata.get("mappings", [])
        profile = input_data.metadata.get("profile", {})
        form_title = input_data.metadata.get("form_title", "Filled Form")
        
        if not mappings:
            return AgentOutput(
                status="error",
                data={},
                confidence=0,
                execution_time_ms=0,
                errors=["No mappings provided for PDF generation"]
            )
        
        try:
            pdf_bytes = self._generate_pdf(mappings, profile, form_title)
            pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
            
            file_name = f"{form_title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            
            return AgentOutput(
                status="success",
                data={
                    "pdf_base64": pdf_base64,
                    "pdf_bytes": pdf_bytes,
                    "file_name": file_name,
                    "file_size_bytes": len(pdf_bytes),
                    "generated_at": datetime.now().isoformat()
                },
                confidence=0.95
            )
        
        except Exception as e:
            logger.error(f"PDF generation failed: {str(e)}", exc_info=True)
            return AgentOutput(
                status="error",
                data={},
                confidence=0,
                execution_time_ms=0,
                errors=[str(e)]
            )
    
    def _generate_pdf(
        self, 
        mappings: List[Dict[str, Any]], 
        profile: Dict[str, Any], 
        form_title: str
    ) -> bytes:
        """Generate professional PDF document"""
        
        # Create in-memory PDF
        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            pdf_buffer,
            pagesize=letter,
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )
        
        # Container for PDF elements
        elements = []
        styles = getSampleStyleSheet()
        
        # Custom styles for government documents
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=HexColor('#1a1a1a'),
            spaceAfter=12,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=11,
            textColor=HexColor('#333333'),
            spaceAfter=8,
            fontName='Helvetica-Bold'
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=10,
            textColor=black,
            spaceAfter=4,
            fontName='Helvetica'
        )
        
        # Title
        elements.append(Paragraph(form_title, title_style))
        elements.append(Spacer(1, 0.2*inch))
        
        # Generation timestamp
        timestamp = datetime.now().strftime("%d %B %Y at %H:%M:%S")
        elements.append(Paragraph(
            f"<i>Generated on {timestamp}</i>",
            ParagraphStyle('Timestamp', parent=styles['Normal'], fontSize=8, textColor=grey)
        ))
        elements.append(Spacer(1, 0.15*inch))
        
        # Separator line
        elements.append(self._create_separator())
        elements.append(Spacer(1, 0.15*inch))
        
        # Personal Information Section
        elements.append(Paragraph("PERSONAL INFORMATION", heading_style))
        
        personal_mappings = [m for m in mappings if self._is_personal_field(m['formField'])]
        if personal_mappings:
            personal_table_data = self._create_table_data(personal_mappings)
            personal_table = Table(personal_table_data, colWidths=[2.5*inch, 3.5*inch])
            personal_table.setStyle(self._get_table_style())
            elements.append(personal_table)
            elements.append(Spacer(1, 0.2*inch))
        
        # Address Section
        address_mappings = [m for m in mappings if self._is_address_field(m['formField'])]
        if address_mappings:
            elements.append(Paragraph("ADDRESS", heading_style))
            address_table_data = self._create_table_data(address_mappings)
            address_table = Table(address_table_data, colWidths=[2.5*inch, 3.5*inch])
            address_table.setStyle(self._get_table_style())
            elements.append(address_table)
            elements.append(Spacer(1, 0.2*inch))
        
        # Document Information Section
        doc_mappings = [m for m in mappings if self._is_document_field(m['formField'])]
        if doc_mappings:
            elements.append(Paragraph("DOCUMENT INFORMATION", heading_style))
            doc_table_data = self._create_table_data(doc_mappings)
            doc_table = Table(doc_table_data, colWidths=[2.5*inch, 3.5*inch])
            doc_table.setStyle(self._get_table_style())
            elements.append(doc_table)
            elements.append(Spacer(1, 0.2*inch))
        
        # Other fields
        other_mappings = [m for m in mappings if not any([
            self._is_personal_field(m['formField']),
            self._is_address_field(m['formField']),
            self._is_document_field(m['formField'])
        ])]
        if other_mappings:
            elements.append(Paragraph("OTHER INFORMATION", heading_style))
            other_table_data = self._create_table_data(other_mappings)
            other_table = Table(other_table_data, colWidths=[2.5*inch, 3.5*inch])
            other_table.setStyle(self._get_table_style())
            elements.append(other_table)
            elements.append(Spacer(1, 0.2*inch))
        
        # Confidence scores
        elements.append(Spacer(1, 0.15*inch))
        elements.append(self._create_separator())
        elements.append(Spacer(1, 0.1*inch))
        elements.append(Paragraph("EXTRACTION CONFIDENCE", heading_style))
        
        if profile:
            overall_confidence = profile.get('overallConfidence', 0)
            elements.append(Paragraph(
                f"Overall Extraction Confidence: <b>{overall_confidence:.1%}</b>",
                normal_style
            ))
        
        # Build PDF
        doc.build(elements)
        
        pdf_buffer.seek(0)
        return pdf_buffer.getvalue()
    
    def _create_table_data(self, mappings: List[Dict[str, Any]]) -> List[List]:
        """Create table data from mappings"""
        data = [["Field", "Value"]]
        for mapping in mappings:
            field = mapping.get('formField', '').replace('_', ' ').title()
            value = str(mapping.get('value', ''))
            data.append([field, value])
        return data
    
    def _get_table_style(self) -> TableStyle:
        """Get consistent table styling"""
        return TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#E8E8E8')),
            ('TEXTCOLOR', (0, 0), (-1, 0), black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), HexColor('#FFFFFF')),
            ('TEXTCOLOR', (0, 1), (-1, -1), black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [HexColor('#FFFFFF'), HexColor('#F5F5F5')]),
            ('GRID', (0, 0), (-1, -1), 1, HexColor('#CCCCCC')),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ])
    
    def _create_separator(self):
        """Create a horizontal separator line"""
        data = [['_' * 80]]
        table = Table(data)
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('TEXTCOLOR', (0, 0), (-1, -1), grey),
        ]))
        return table
    
    def _is_personal_field(self, field_name: str) -> bool:
        """Check if field is personal information"""
        personal_keywords = ['name', 'firstName', 'lastName', 'dob', 'dateOfBirth', 'gender']
        return any(kw in field_name.lower() for kw in personal_keywords)
    
    def _is_address_field(self, field_name: str) -> bool:
        """Check if field is address information"""
        address_keywords = ['address', 'street', 'city', 'state', 'province', 'pincode', 'zipcode', 'postal']
        return any(kw in field_name.lower() for kw in address_keywords)
    
    def _is_document_field(self, field_name: str) -> bool:
        """Check if field is document information"""
        doc_keywords = ['document', 'id', 'passport', 'license', 'aadhaar']
        return any(kw in field_name.lower() for kw in doc_keywords)
