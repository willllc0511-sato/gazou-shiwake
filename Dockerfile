FROM python:3.12-slim

# 学習済みモデル（ONNX Model Zoo の MobileNetV2）と分類名の一覧。照合値が合わなければ作るのを止める
ARG MODEL_URL=https://media.githubusercontent.com/media/onnx/models/main/validated/vision/classification/mobilenet/model/mobilenetv2-12.onnx
ARG MODEL_SHA256=c0c3f76d93fa3fd6580652a45618618a220fced18babf65774ed169de0432ad5
ARG LABELS_URL=https://raw.githubusercontent.com/pytorch/hub/master/imagenet_classes.txt
ARG LABELS_SHA256=1f386e0d1cb6e28b9c2dac651c3dea6801e98ad1b41a14ce6bb1a093d72069f5

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY requirements.txt requirements-dev.txt ./
ARG DEV=0
RUN pip install --no-cache-dir -r $( [ "$DEV" = "1" ] && echo requirements-dev.txt || echo requirements.txt )
ADD --checksum=sha256:${MODEL_SHA256} ${MODEL_URL} model/mobilenetv2-12.onnx
ADD --checksum=sha256:${LABELS_SHA256} ${LABELS_URL} model/imagenet_classes.txt
COPY app ./app
COPY tests ./tests
RUN useradd -r -u 10001 app && chown -R app /srv
USER app
EXPOSE 8000
CMD ["uvicorn", "app.asgi:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
