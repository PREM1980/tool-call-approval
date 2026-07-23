FROM node:22-bookworm AS ui-build
WORKDIR /ui
COPY tool-call-ui/package.json tool-call-ui/package-lock.json ./
RUN npm ci
COPY tool-call-ui/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY tool-call-api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY tool-call-api/ .
COPY --from=ui-build /ui/dist/tool-call-ui/browser ./static
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
