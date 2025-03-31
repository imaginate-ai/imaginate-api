FROM python:3.12-slim
RUN pip install poetry==1.8.4
WORKDIR /api
COPY . .
RUN poetry install --without dev --sync
CMD ["poetry","run","python", "imaginate_api/app.py"]