"""Notion property names, in one place.

Property names are also the labels Fer sees in the Notion UI, so they stay in
Spanish. Renaming a column in Notion breaks the sync; change it here too.
"""


class Miembros:
    NOMBRE = "Nombre"
    ROL = "Rol"
    HABITICA_USER_ID = "Habitica User ID"
    COLONES_POR_PUNTO = "Colones por punto"
    ACTIVO = "Activo"
    SUPERVISADO_POR = "Supervisado por"


class Rutinas:
    NOMBRE = "Nombre"
    MIEMBRO = "Miembro"
    ELEGIBLES = "Elegibles"
    TIPO = "Tipo"
    MODALIDAD = "Modalidad"
    PAGA = "Paga"
    DIFICULTAD = "Dificultad"
    PUNTOS_GANA = "Puntos gana"
    PUNTOS_FALLA = "Puntos falla"
    RECURRENCIA = "Recurrencia"
    DIAS = "Días"
    DIA_DEL_MES = "Día del mes"
    HORA = "Hora"
    CATEGORIA = "Categoría"
    HABITICA_TASK_ID = "Habitica Task ID"
    HABITICA_TIPO = "Habitica tipo"
    VIGENTE_DESDE = "Vigente desde"
    VIGENTE_HASTA = "Vigente hasta"


class Agenda:
    TITULO = "Título"
    MIEMBRO = "Miembro"
    # Dificultad, Tipo, Paga and Habitica Task ID are NOT columns on Agenda:
    # the sync reads them from the linked Rutina / Tarea (see ADR-32).
    RUTINA = "Rutina"
    TAREA = "Tarea"
    ESTADO = "Estado"
    INICIA = "Inicia"
    PUNTOS_APLICADOS = "Puntos aplicados"
    COLONES = "Colones"
    MARCADO_EN = "Marcado en"
    MARCADO_POR = "Marcado por"
    ORIGEN = "Origen"
    AJUSTADO = "Ajustado"
    MOTIVO = "Motivo del ajuste"
    TABLA = "Tabla"


class Tareas:
    TITULO = "Título"
    MIEMBRO = "Miembro"
    ESTADO = "Estado"
    DIFICULTAD = "Dificultad"
    PUNTOS_GANA = "Puntos gana"
    APROBADA = "Aprobada"
    ASIGNADA_POR = "Asignada por"
    HABITICA_TASK_ID = "Habitica Task ID"
    FECHA_LIMITE = "Fecha límite"


class Corte:
    CICLO = "Ciclo"
    MIEMBRO = "Miembro"
    DESDE = "Desde"
    HASTA = "Hasta"
    MANDATORY_ASIGNADAS = "Mandatory asignadas"
    MANDATORY_CUMPLIDAS = "Mandatory cumplidas"
    MANDATORY_FALLADAS = "Mandatory falladas"
    OPCIONALES = "Opcionales completadas"
    TODOS = "To-Dos completados"
    PUNTOS_GANADOS = "Puntos ganados"
    PUNTOS_RESTADOS = "Puntos restados"
    PUNTOS_NETOS = "Puntos netos"
    COLONES = "Colones a pagar"
    TOPE_APLICADO = "Tope aplicado"
    PISO_APLICADO = "Piso aplicado"
    PAGADO = "Pagado"


class Sobres:
    """💵 Sobres -- one virtual envelope per member per jar type (ADR-35)."""

    SOBRE = "Sobre"
    MIEMBRO = "Miembro"
    TIPO = "Tipo de sobre"
    SALDO = "Saldo"
    PCT_REPARTO = "% de reparto"
    META_ACTIVA = "Meta activa"


class Movimientos:
    """🔁 Movimientos -- the append-only ledger behind every sobre (ADR-35)."""

    MOVIMIENTO = "Movimiento"
    MIEMBRO = "Miembro"
    TIPO = "Tipo"
    MONTO = "Monto"
    FECHA = "Fecha"
    CATEGORIA = "Categoría"
    DESCRIPCION = "Descripción"
    SOBRE_ORIGEN = "Sobre origen"
    SOBRE_DESTINO = "Sobre destino"
    META_LIGADA = "Meta ligada"
    APROBADO_POR = "Aprobado por"
    REPORTADO_POR = "Reportado por"
    #: Relation back to the Corte quincenal row that produced this movement;
    #: added by the sync (ADR-013). Used to make the deposit idempotent.
    CORTE = "Corte"


TIPO_INGRESO_MESADA = "Ingreso mesada"
TIPO_TRANSFERENCIA_SOBRE = "Transferencia a sobre"


ESTADO_PENDIENTE = "Pendiente"
ESTADO_HECHA = "Hecha"
ESTADO_FALLADA = "Fallada"

ORIGEN_HABITICA = "Habitica"
ORIGEN_NOTION = "Notion"
ORIGEN_MANUAL = "Manual"

MODALIDAD_PERSONAL = "Personal"
MODALIDAD_POOL = "Pool"
