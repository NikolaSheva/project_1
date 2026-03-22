# =======================
# Builder stage
# =======================
FROM python:3.13-slim AS builder

SHELL ["/bin/bash", "-exo", "pipefail", "-c"]

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gcc g++ make libc6-dev libffi-dev libssl-dev wget \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --upgrade uv
# RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# Copy project metadata
COPY pyproject.toml uv.lock ./

# Create virtual environment
RUN uv venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Install dependencies defined in pyproject.toml
RUN uv sync --frozen

# Install playwright and browsers
RUN pip install playwright && playwright install chromium
# Install extra runtime packages
RUN pip install python-dotenv psycopg2-binary


# Copy application source
COPY manage.py ./manage.py
COPY config ./config
COPY watch ./watch
COPY static ./static
COPY templates /app/templates

# =======================
# Runtime stage
# =======================
FROM python:3.13-slim AS runtime

WORKDIR /app

# Install utilities + psql client + Chromium dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl iputils-ping iproute2 net-tools dnsutils postgresql-client-17 \
    # Базовые библиотеки
    libglib2.0-0 libnss3 libnspr4 libdbus-1-3 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    # Добавленные для X11
    libxfixes3 libxss1 libxtst6 libxcb-shm0 libxcb-xfixes0 \
    libxcb-util1 libxcb-image0 libxcb-keysyms1 libxcb-randr0 \
    libxcb-render0 libxcb-render-util0 libxcb-shape0 libxcb-sync1 \
    libxcb-xinerama0 libxcb-xkb1 libxcb-xv0 \
    && rm -rf /var/lib/apt/lists/*

# Copy environment from builder
# Copy application files
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/manage.py /app/
COPY --from=builder /app/config /app/config
COPY --from=builder /app/watch /app/watch
COPY --from=builder /app/static /app/static
COPY --from=builder /app/templates /app/templates 
COPY --from=builder /app/pyproject.toml /app/

# Python config
ENV PATH="/app/.venv/bin:$PATH" 
ENV PYTHONPATH="/app:/app/watch"
ENV DJANGO_SETTINGS_MODULE="config.settings"

# Create non-root user
ARG DEV_USER=devuser
RUN useradd --create-home --shell /bin/bash ${DEV_USER}

# Копируем кэш Playwright в ДОМАШНЮЮ директорию пользователя
COPY --from=builder /root/.cache/ms-playwright /home/${DEV_USER}/.cache/ms-playwright
RUN chown -R ${DEV_USER}:${DEV_USER} /home/${DEV_USER}/.cache

# Дай права на /app
RUN chown -R ${DEV_USER}:${DEV_USER} /app

USER ${DEV_USER}

# Установи переменную для playwright (чтобы знал где искать)
ENV PLAYWRIGHT_BROWSERS_PATH=/home/${DEV_USER}/.cache/ms-playwright


EXPOSE 10000
# Вместо простого "gunicorn" используйте полный путь к интерпретатору Python
# CMD ["/app/.venv/bin/gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:10000"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:10000"]
#CMD ["python", "manage.py", "runserver", "0.0.0.0:10000", "--settings=config.settings.dev"]