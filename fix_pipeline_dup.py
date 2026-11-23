import sys

p = r'D:\Nexora\src\parsers\pipeline.py'
with open(p, encoding='utf-8') as f:
    lineas = f.readlines()

# Líneas 54-116 (índices 53-115) son la primera definición duplicada.
# La segunda definición comienza en línea 119 (índice 118).
nuevas_lineas = lineas[:53] + lineas[118:]

with open(p, 'w', encoding='utf-8') as f:
    f.writelines(nuevas_lineas)

print(f'Archivo procesado: {len(lineas)} líneas originales -> {len(nuevas_lineas)} líneas finales')
print('Duplicación de _flags_for_item eliminada.')
