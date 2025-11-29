# app.py

# Importaciones necesarias para Flask, Base de Datos, CORS y tiempo
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
import time
from flask_cors import CORS 
import os # Importar para leer variables de entorno como PORT (de Render)
import sys

# --- 1. Configuración de la Aplicación ---
app = Flask(__name__)
# Configura el soporte de CORS
CORS(app) 

# Usaremos SQLite, que guarda el archivo 'boletos.db'. 
# Render utilizará una instancia temporal, suficiente para esta demostración.
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///boletos.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Duración de la reserva en segundos (30 segundos para probar)
RESERVA_DURACION_SEGUNDOS = 30 

# --- 2. Modelo de la Base de Datos (Tabla Boletos) ---
class Boleto(db.Model):
    # Identificador único del registro
    id = db.Column(db.Integer, primary_key=True)
    # Nombre del asiento (Ej: A1, B5). Debe ser único.
    asiento = db.Column(db.String(10), unique=True, nullable=False)
    # Estados posibles: 'DISPONIBLE', 'RESERVADO', 'VENDIDO'
    estado = db.Column(db.String(20), default='DISPONIBLE')
    # Marca de tiempo UNIX para saber cuándo liberar la reserva (0 si está libre)
    tiempo_limite = db.Column(db.Integer, default=0) 

    def to_dict(self):
        """Convierte el objeto a un diccionario JSON para el frontend."""
        return {
            'id': self.id,
            'asiento': self.asiento,
            'estado': self.estado
        }

# --- 3. Inicialización de la Base de Datos ---
# Se utiliza un contexto de aplicación para garantizar que la base de datos se configure correctamente
with app.app_context():
    try:
        db.create_all() # Crea la tabla 'Boleto' si no existe
    
        # Si la tabla está vacía, inserta los boletos (200 de prueba)
        if Boleto.query.count() == 0:
            for i in range(1, 201):
                db.session.add(Boleto(asiento=f'A{i}', estado='DISPONIBLE'))
            db.session.commit()
        print("Base de datos inicializada con 200 boletos de ejemplo (A1 a A200).")
    except Exception as e:
        # En entornos de despliegue, a veces hay problemas de permisos.
        print(f"Error al inicializar la DB: {e}", file=sys.stderr)


# --- 4. Función de Lógica de Negocio: Liberación de Reservas ---
def liberar_reservas_expiradas():
    """Libera boletos que superaron su tiempo límite de reserva."""
    ahora = int(time.time())
    
    # Consulta: Busca boletos 'RESERVADO' cuyo tiempo_limite ya pasó
    # Se usa app_context() porque esta función se llama desde los endpoints
    with app.app_context():
        boletos_expirados = Boleto.query.filter(
            Boleto.estado == 'RESERVADO',
            Boleto.tiempo_limite < ahora
        ).all()
        
        for boleto in boletos_expirados:
            boleto.estado = 'DISPONIBLE'
            boleto.tiempo_limite = 0
            print(f"Reserva expirada y liberada para el asiento: {boleto.asiento}")
            
        if boletos_expirados:
            db.session.commit()

# --- 5. ENDPOINTS (API REST) ---

@app.route('/api/boletos', methods=['GET'])
def get_boletos():
    """Endpoint para que el frontend obtenga el estado actual de todos los boletos."""
    # 1. Limpia reservas expiradas antes de responder (mantiene la base de datos actualizada)
    liberar_reservas_expiradas()
    
    # 2. Obtiene todos los boletos y los convierte a formato JSON
    boletos = Boleto.query.all()
    return jsonify([b.to_dict() for b in boletos])


@app.route('/api/reservar/<string:asiento_nombre>', methods=['POST'])
def reservar_boleto(asiento_nombre):
    """Endpoint para que el frontend intente reservar un asiento."""
    
    liberar_reservas_expiradas() # Limpieza preventiva
    boleto = Boleto.query.filter_by(asiento=asiento_nombre).first()

    if not boleto:
        return jsonify({'message': 'Asiento no encontrado.'}), 404

    # Lógica de RESERVA (Solo si está disponible)
    if boleto.estado == 'DISPONIBLE':
        try:
            # Calcula el tiempo límite para esta reserva
            tiempo_limite = int(time.time()) + RESERVA_DURACION_SEGUNDOS
            
            # 1. Realiza el cambio en la base de datos (Transacción Atómica)
            boleto.estado = 'RESERVADO'
            boleto.tiempo_limite = tiempo_limite
            db.session.commit()
            
            # 2. Respuesta de Éxito
            return jsonify({
                'message': f'Asiento {asiento_nombre} reservado exitosamente. Tienes {RESERVA_DURACION_SEGUNDOS} segundos para comprarlo.',
                'estado': 'RESERVADO'
            }), 200
        except Exception as e:
            # 3. Si hay un error, revierte la base de datos
            db.session.rollback()
            print(f"Error al reservar: {e}", file=sys.stderr)
            return jsonify({'message': 'Error interno del servidor al reservar.'}), 500
            
    else:
        # 4. Respuesta de Conflicto (ya reservado o vendido)
        return jsonify({
            'message': f'Asiento {asiento_nombre} ya está {boleto.estado}.',
            'estado': boleto.estado
        }), 409 # Código 409: Conflict


@app.route('/api/comprar/<string:asiento_nombre>', methods=['POST'])
def comprar_boleto(asiento_nombre):
    """Endpoint para confirmar la compra final de un asiento reservado."""
    
    boleto = Boleto.query.filter_by(asiento=asiento_nombre).first()

    if not boleto:
        return jsonify({'message': 'Asiento no encontrado.'}), 404

    # 1. Verificar si el asiento está en estado RESERVADO
    if boleto.estado == 'RESERVADO':
        try:
            # 2. Transacción de Venta: Cambiar a VENDIDO
            boleto.estado = 'VENDIDO'
            boleto.tiempo_limite = 0 # El límite ya no aplica
            db.session.commit()
            
            return jsonify({
                'message': f'¡Compra exitosa! Asiento {asiento_nombre} VENDIDO permanentemente.',
                'estado': 'VENDIDO'
            }), 200
        except Exception as e:
            db.session.rollback()
            print(f"Error al comprar: {e}", file=sys.stderr)
            return jsonify({'message': 'Error interno del servidor al comprar.'}), 500
            
    else:
        # Si el estado es DISPONIBLE o ya VENDIDO (o expiró la reserva)
        return jsonify({
            'message': f'El asiento {asiento_nombre} no está reservado o ya fue vendido.',
            'estado': boleto.estado
        }), 409 # Conflicto

# --- 6. EJECUCIÓN (Ajustado para Hosting en la Nube) ---
if __name__ == '__main__':
    # Obtiene el puerto de la variable de entorno, si existe (para hosting como Render)
    # o usa el puerto 5000 por defecto (para desarrollo local).
    port = int(os.environ.get('PORT', 5000))
    # Escucha en todas las IPs para ser accesible desde el exterior.
    # En Render, esto será ignorado ya que Gunicorn es el que inicia la aplicación.
    app.run(host='0.0.0.0', port=port, debug=True)