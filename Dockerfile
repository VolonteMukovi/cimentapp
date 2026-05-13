FROM python:3.12-slim

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

RUN mkdir /cimentapp
WORKDIR /cimentapp

# 🔥 INSTALL DEPENDANCES SYSTEME (IMPORTANT)
RUN apt-get update && apt-get install -y \
    gcc \
    pkg-config \
    default-libmysqlclient-dev \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /cimentapp/

RUN python -m venv /.venv
ENV PATH="/.venv/bin:$PATH"

RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . /cimentapp

RUN chmod +x /cimentapp/entrypoint.sh
ENTRYPOINT ["/cimentapp/entrypoint.sh"]
