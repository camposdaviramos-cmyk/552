FROM python:3.14-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home saude
COPY saude ./saude
COPY static ./static
COPY docs/aderencia.json ./docs/aderencia.json
COPY run.py seed.py backup.py manage.py ./
COPY TR.pdf ./TR.pdf
RUN mkdir -p instance && chown -R saude:saude /app
USER saude
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=4)"
CMD ["python", "run.py", "--host", "0.0.0.0"]
