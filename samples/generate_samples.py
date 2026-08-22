import os
from PIL import Image, ImageDraw

os.makedirs('samples', exist_ok=True)

# 1. Scanned Inspection Report Sample
img1 = Image.new('RGB', (800, 1000), color='#fafafa')
draw1 = ImageDraw.Draw(img1)

# Header
draw1.rectangle([(40, 30), (760, 90)], fill='#2d3748')
draw1.text((60, 50), 'PETROCHEM REFINERY - EQUIPMENT INSPECTION REPORT', fill='white')

# Metadata block
draw1.text((50, 120), 'Report ID: REP-2026-8891', fill='#1a202c')
draw1.text((450, 120), 'Date: 2026-08-23', fill='#1a202c')
draw1.text((50, 150), 'Facility: Unit 4 Catalyst Cracker', fill='#1a202c')
draw1.text((450, 150), 'Inspector: Eng. R. Sharma (ID: 4402)', fill='#1a202c')
draw1.line([(50, 185), (750, 185)], fill='#cbd5e1', width=2)

# Table Header
draw1.rectangle([(50, 210), (750, 245)], fill='#e2e8f0')
draw1.text((60, 220), 'Component Tag', fill='#334155')
draw1.text((220, 220), 'Operating Pressure', fill='#334155')
draw1.text((420, 220), 'Temp (C)', fill='#334155')
draw1.text((580, 220), 'Status / Flag', fill='#334155')

# Table Rows
rows = [
    ('V-101 (Main Feed Valve)', '142.5 PSI', '185 C', 'NORMAL - PASSED'),
    ('P-204A (High Pressure Pump)', '210.0 PSI', '215 C', 'NORMAL - PASSED'),
    ('PT-302 (Pressure Transmitter)', '142.2 PSI', '184 C', 'CALIBRATED'),
    ('TI-401 (Thermocouple Well)', 'N/A', '320 C', 'WARNING: HIGH TEMP'),
    ('PSV-501 (Safety Relief Valve)', 'Set @ 250 PSI', '180 C', 'INSPECTED & SEALED'),
]
y = 260
for row in rows:
    draw1.text((60, y), row[0], fill='#1e293b')
    draw1.text((220, y), row[1], fill='#1e293b')
    draw1.text((420, y), row[2], fill='#1e293b')
    draw1.text((580, y), row[3], fill='#b91c1c' if 'WARNING' in row[3] else '#15803d')
    y += 40
    draw1.line([(50, y-10), (750, y-10)], fill='#f1f5f9', width=1)

# Notes & Compliance
draw1.text((50, 520), 'COMPLIANCE & MAINTENANCE NOTES:', fill='#0f172a')
notes = (
    '1. High temperature reading on TI-401 requires secondary thermal scan within 48 hours.\n'
    '2. Valve V-101 packing gland adjusted and torqued to manufacturer specification (45 Nm).\n'
    '3. Pressure transmitter PT-302 zero-point recalibration verified against master gauge.\n'
    '4. Overall unit safety integrity level (SIL-2) maintained.'
)
draw1.multiline_text((50, 550), notes, fill='#334155', spacing=8)

# Signoff
draw1.line([(50, 780), (350, 780)], fill='#64748b', width=1)
draw1.text((50, 790), 'Lead Inspector Signature: R. Sharma', fill='#475569')
draw1.line([(450, 780), (750, 780)], fill='#64748b', width=1)
draw1.text((450, 790), 'Plant Safety Officer: M. Adhitya', fill='#475569')

img1.save('samples/sample_inspection_report.png')

# 2. P&ID Schematic Diagram Sample
img2 = Image.new('RGB', (1000, 650), color='#ffffff')
draw2 = ImageDraw.Draw(img2)

# Border & Title block
draw2.rectangle([(15, 15), (985, 635)], outline='#000000', width=2)
draw2.rectangle([(680, 520), (985, 635)], outline='#000000', width=2)
draw2.text((700, 535), 'PROJECT: KAVACH SOVEREIGN AI', fill='#000000')
draw2.text((700, 560), 'DWG TITLE: DISTILLATION FEED P&ID', fill='#000000')
draw2.text((700, 585), 'DWG NO: PID-2026-A101  REV: 03', fill='#000000')
draw2.text((700, 610), 'SCALE: NTS   DATE: 23-AUG-2026', fill='#000000')

# Equipment 1: Tank T-100
draw2.rectangle([(80, 180), (220, 420)], outline='#1e3a8a', width=3)
draw2.text((115, 290), 'FEED TANK\n  T-100', fill='#1e3a8a')

# Level Transmitter on Tank
draw2.ellipse([(120, 110), (180, 170)], outline='#0284c7', width=2)
draw2.text((135, 133), 'LT-101', fill='#0284c7')
draw2.line([(150, 170), (150, 180)], fill='#0284c7', width=2)

# Pipe from Tank to Pump
draw2.line([(220, 360), (360, 360)], fill='#000000', width=3)
draw2.text((250, 340), 'LINE: 4-HC-101', fill='#475569')

# Suction Valve V-101
draw2.polygon([(280, 350), (280, 370), (310, 360)], fill='#dc2626')
draw2.polygon([(340, 350), (340, 370), (310, 360)], fill='#dc2626')
draw2.text((295, 378), 'V-101', fill='#dc2626')

# Pump P-102
draw2.ellipse([(360, 320), (440, 400)], outline='#1e3a8a', width=3)
draw2.polygon([(400, 320), (435, 345), (400, 370)], fill='#1e3a8a')
draw2.text((385, 410), 'PUMP P-102', fill='#1e3a8a')

# Discharge Line & Instrumentation
draw2.line([(440, 360), (650, 360)], fill='#000000', width=3)
draw2.line([(650, 360), (650, 220)], fill='#000000', width=3)
draw2.line([(650, 220), (780, 220)], fill='#000000', width=3)
draw2.text((470, 340), 'LINE: 3-HC-102', fill='#475569')

# Pressure Transmitter PT-202
draw2.line([(510, 360), (510, 290)], fill='#0284c7', width=2)
draw2.ellipse([(480, 230), (540, 290)], outline='#0284c7', width=2)
draw2.text((493, 253), 'PT-202', fill='#0284c7')

# Flow Transmitter FT-303
draw2.line([(590, 360), (590, 290)], fill='#0284c7', width=2)
draw2.ellipse([(560, 230), (620, 290)], outline='#0284c7', width=2)
draw2.text((573, 253), 'FT-303', fill='#0284c7')

# Control Valve CV-404
draw2.polygon([(690, 210), (690, 230), (720, 220)], fill='#16a34a')
draw2.polygon([(750, 210), (750, 230), (720, 220)], fill='#16a34a')
draw2.ellipse([(705, 170), (735, 200)], outline='#16a34a', width=2)
draw2.line([(720, 200), (720, 220)], fill='#16a34a', width=2)
draw2.text((702, 238), 'CV-404', fill='#16a34a')

# Column C-200 Destination
draw2.rectangle([(780, 140), (920, 480)], outline='#1e3a8a', width=3)
draw2.text((810, 300), 'FRACTIONATOR\n    C-200', fill='#1e3a8a')

img2.save('samples/sample_pid_schematic.png')
print('Samples generated successfully!')
