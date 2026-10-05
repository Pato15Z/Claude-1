# leadpipe no servidor: Python + Chromium do Playwright.
# A imagem traz o navegador porque qualificação, enriquecimento e sourcing abrem
# páginas de verdade — sem Chromium o app sobe e trava na primeira etapa.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    LEADPIPE_DATA=/data \
    LEADPIPE_UI_HOST=0.0.0.0

WORKDIR /app

# Dependências antes do código: pyproject muda pouco, então o build seguinte
# reaproveita a camada do Chromium (que é a cara, ~400 MB).
COPY pyproject.toml ./
COPY leadpipe ./leadpipe
RUN pip install . \
 && playwright install --with-deps chromium \
 && rm -rf /root/.cache/pip

EXPOSE 8090

# Porta aberta = processo vivo. O painel responde 401 sem senha, então checar o
# código HTTP daria falso negativo; o que importa é o socket estar escutando.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import socket,sys; s=socket.create_connection(('127.0.0.1',8090),3); s.close()" || exit 1

# --no-browser: não existe navegador de desktop aqui para abrir.
# Sem --public: o túnel sobe no container vizinho, não dentro deste.
CMD ["leadpipe", "ui", "--no-browser"]
