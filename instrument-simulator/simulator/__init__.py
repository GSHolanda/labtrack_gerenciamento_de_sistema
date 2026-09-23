"""LabTrack Instrument Simulator.

Processo independente que se comporta como um equipamento de laboratório
conectado: consulta a worklist, "mede" as amostras e envia os resultados à API
do LabTrack. Comunica-se exclusivamente via REST, sem acesso ao banco, que é
como um driver de instrumento real se integraria ao LIMS.
"""

__version__ = "0.1.0"
