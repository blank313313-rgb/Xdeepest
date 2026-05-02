FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p uploads

# HF Spaces يوفر PORT و SPACE_HOST تلقائياً
ENV PORT=7860

CMD ["python", "bot.py"]
