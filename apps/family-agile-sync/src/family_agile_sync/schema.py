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


ESTADO_PENDIENTE = "Pendiente"
ESTADO_HECHA = "Hecha"
ESTADO_FALLADA = "Fallada"

ORIGEN_HABITICA = "Habitica"
ORIGEN_MANUAL = "Manual"

MODALIDAD_PERSONAL = "Personal"
MODALIDAD_POOL = "Pool"
