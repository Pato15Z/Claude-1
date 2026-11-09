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
# ffmpeg duas vezes, de propósito: o do Playwright grava a tela (lp hero video)
# e o do sistema converte para MP4 H.264, o único formato que abre direto no
# iPhone. Sem o segundo, a gravação acontece e o vídeo não sai.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/* \
 && pip install . \
 && playwright install --with-deps chromium ffmpeg \
 && rm -rf /root/.cache/pip

EXPOSE 8090

# Porta aberta = processo vivo. O painel responde 401 sem senha, então checar o
# código HTTP daria falso negativo; o que importa é o socket estar escutando.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import socket,sys; s=socket.create_connection(('127.0.0.1',8090),3); s.close()" || exit 1

# --no-browser: não existe navegador de desktop aqui para abrir.
# Sem --public: o túnel sobe no container vizinho, não dentro deste.
CMD ["leadpipe", "ui", "--no-browser"]
