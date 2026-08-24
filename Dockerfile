FROM python:3.12-slim AS build
WORKDIR /app
COPY pyproject.toml ./
COPY tfguard ./tfguard
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim
WORKDIR /app
# A server that reads files should not run as root, and this one is
# explicitly designed to read only what it is pointed at.
RUN useradd --create-home --uid 10001 tfguard
COPY --from=build /install /usr/local
COPY tfguard ./tfguard
USER tfguard
ENV TFGUARD_PLAN_DIR=/plans
# stdio by default: the client starts this process and speaks over the pipe.
CMD ["python", "-m", "tfguard.server"]
