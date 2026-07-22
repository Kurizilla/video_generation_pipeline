"""video-pipeline — pipeline generalizado de generación de video por etapas, parametrizable por proyecto.

Etapas: anchors (personajes+sets) → keyframes → shots (video) → [GO] assemble (unificación+VO+subs+master).
El front (web/) opera todo vía la API de pipeline.server. Cada etapa lee un proyecto (projects/<nombre>/).
"""
__version__ = "1.0.0"
