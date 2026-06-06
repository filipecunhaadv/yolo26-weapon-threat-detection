# Doc: https://huggingface.co/docs/hub/spaces-sdks-docker

FROM python:3.11-slim

RUN useradd -m -u 1000 user

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

USER user
ENV PATH="/home/user/.local/bin:$PATH"
WORKDIR /app

COPY --chown=user requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY --chown=user app/ ./app/
COPY --chown=user model/ ./model/
COPY --chown=user metrics/ ./metrics/
COPY --chown=user app.py .

ENV MODEL_PATH=/app/model/best.pt
ENV PYTHONUNBUFFERED=1

EXPOSE 7860

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
