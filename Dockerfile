FROM python:3.12-slim
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH HF_HOME=/home/user/.cache/huggingface FRESHMART_LOG_DIR=/tmp/freshmart_logs
WORKDIR /home/user/app
COPY --chown=user app/requirements.txt app/requirements.txt
RUN pip install --no-cache-dir --user -r app/requirements.txt
COPY --chown=user . .
RUN python app/fetch_models.py
EXPOSE 8501
CMD ["streamlit", "run", "app/app.py", "--server.port", "8501", "--server.address", "0.0.0.0", "--server.enableXsrfProtection", "false", "--server.enableCORS", "false"]
