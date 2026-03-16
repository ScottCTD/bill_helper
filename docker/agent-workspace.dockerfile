FROM python:3.13-slim

ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        coreutils \
        curl \
        file \
        findutils \
        gawk \
        grep \
        jq \
        less \
        procps \
        sed \
        tree \
        unzip \
        zip \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://code-server.dev/install.sh | sh

RUN mkdir -p /opt/code-server-preinstalled-vsix \
    && curl -fsSL \
      https://open-vsx.org/api/chocolatedesue/modern-pdf-preview/1.5.5/file/chocolatedesue.modern-pdf-preview-1.5.5.vsix \
      -o /opt/code-server-preinstalled-vsix/chocolatedesue.modern-pdf-preview-1.5.5.vsix

RUN pip install --no-cache-dir \
    matplotlib \
    numpy \
    openpyxl \
    pandas \
    pydantic \
    python-dateutil \
    requests

COPY pyproject.toml README.md /opt/bill-helper/
COPY backend /opt/bill-helper/backend
COPY telegram /opt/bill-helper/telegram
RUN pip install --no-cache-dir /opt/bill-helper

RUN useradd --create-home --shell /bin/bash app \
    && mkdir -p /workspace /data \
    && chown -R app:app /workspace /data /home/app /opt/code-server-preinstalled-vsix

COPY docker/agent-workspace-entrypoint.sh /usr/local/bin/agent-workspace-entrypoint
RUN chmod +x /usr/local/bin/agent-workspace-entrypoint

USER app
WORKDIR /workspace
EXPOSE 13337

ENTRYPOINT ["/usr/local/bin/agent-workspace-entrypoint"]
