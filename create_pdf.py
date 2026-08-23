from fpdf import FPDF

pdf = FPDF()
pdf.add_page()
pdf.set_font('Arial', 'B', 16)
pdf.cell(200, 10, txt='V-101 Main Valve Standard Operating Procedure', ln=True, align='C')

pdf.set_font('Arial', '', 12)
pdf.ln(10)
pdf.multi_cell(0, 10, txt='''1. OVERVIEW
This document outlines the standard operating procedure (SOP) for the V-101 Main Valve used in the cooling system.

2. SPECIFICATIONS
- Maximum Operating Pressure: 150 PSI
- Normal Operating Pressure: 105 PSI
- Safe Temperature Range: -20C to 85C
- Default State: Normally Closed (NC)

3. MAINTENANCE PROTOCOL
- Weekly check: Verify pressure does not exceed 110 PSI.
- Monthly check: Inspect the O-ring seals for thermal degradation.
- Yearly check: Complete valve replacement if cycle count exceeds 10,000 operations.

4. EMERGENCY SHUTDOWN
In the event of a pressure spike exceeding 140 PSI, the system will automatically trigger a lockdown. Operators must manually reset the valve using the override key.
''')

pdf.output('/app/sample_manual.pdf')
print('PDF created successfully at sample_manual.pdf')
