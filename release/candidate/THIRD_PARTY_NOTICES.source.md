# Avisos de fuente — candidato, no distribuible

Este repositorio no incorpora código fuente ni binarios de OpenOutreach, VICIdial, Node-RED, LangGraph, RabbitMQ, Kimi, DeepSeek, Evolution API o n8n. El Dockerfile de la imagen base sí declara la instalación futura de dependencias desde PyPI.

Dependencias runtime declaradas por RC5:

- psycopg 3.3.4 con extra `binary`: LGPL-3.0; requiere análisis de `psycopg-binary` y sus bibliotecas incluidas.
- Pika 1.4.4: BSD-3-Clause.
- LangGraph 1.2.11, biblioteca open source: MIT. Esto no incluye LangGraph Platform ni servicios comerciales.

Las versiones y hashes de artefactos PyPI, incluidas dependencias transitivas, están fijados en `deploy/proxmox/base/requirements-runtime.lock`. Los textos completos de licencia, digests de las imágenes finales y la attestation todavía deben incorporarse al paquete de distribución. No se consideran satisfechos por este aviso preliminar.

OpenOutreach se invoca exclusivamente como programa externo sin modificar. Si se distribuye una versión modificada, deben cumplirse íntegramente las obligaciones GPLv3 aplicables.
