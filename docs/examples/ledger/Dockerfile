FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
RUN python -m pip install --no-cache-dir "requests>=2.28,<3"
COPY checkin.py update_streak.py ./
COPY docs/examples/ledger/demo.py ./
COPY tests/test_update_streak.py tests/
USER 65534:65534
CMD ["python", "demo.py"]
