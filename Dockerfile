# 1. Usar una imagen base de Python. 
# Se recomienda una version 'slim' (ligera) para builds más rápidas.
FROM python:3.11-slim

# 2. Establecer el directorio de trabajo dentro del contenedor
WORKDIR /app

# 3. Copiar el archivo de dependencias primero para optimizar el caché de Docker
COPY requirements.txt .

# 4. Instalar todas las dependencias listadas en requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copiar el resto de los archivos de la aplicación (app.py, templates, etc.)
COPY . .

# 6. Especificar el puerto que usará Gunicorn (opcional, pero buena práctica)
EXPOSE 8080

# 7. Comando principal para ejecutar la aplicación con Gunicorn
# 'app:app' significa: archivo 'app.py' y la instancia Flask llamada 'app'
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]