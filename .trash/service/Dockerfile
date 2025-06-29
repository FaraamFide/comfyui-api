# service/Dockerfile
ARG CUDA_VERSION="12.4.1" # Используйте стабильную версию CUDA
ARG OS_VERSION="ubuntu22.04"
FROM nvidia/cuda:${CUDA_VERSION}-devel-${OS_VERSION}

ENV DEBIAN_FRONTEND=noninteractive
ENV BENTOML_HOME=/home/bentoml/
WORKDIR ${BENTOML_HOME}

# 1. Устанавливаем системные зависимости, включая Python 3.11
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    libgl1 \
    libglib2.0-0 \
    python3.11 \
    python3.11-venv \
    python3-pip \
    aria2 && \
    rm -rf /var/lib/apt/lists/*

# Делаем python3.11 основным
RUN ln -s /usr/bin/python3.11 /usr/bin/python

# 2. Создаем пользователя bentoml и виртуальное окружение
RUN useradd -m -U -s /bin/bash bentoml
USER bentoml
RUN python -m venv /home/bentoml/venv
ENV PATH="/home/bentoml/venv/bin:$PATH"

# 3. Копируем собранный Bento
# Эту часть BentoML выполнит автоматически при запуске `bentoml containerize`.
# Этот Dockerfile служит как шаблон, который можно кастомизировать.
# COPY --chown=bentoml:bentoml ./bento /home/bentoml/bento

# 4. Устанавливаем точку входа и открываем порт
EXPOSE 3000
# CMD будет автоматически добавлен командой `bentoml containerize`.
# Пример: CMD ["bentoml", "serve", "comfyui-prod-svc:latest", "--production"]
