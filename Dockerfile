# Python 3.10 기반 이미지 사용
FROM python:3.10-slim

# 작업 디렉토리 생성
WORKDIR /app

# 시스템 패키지 설치 (psycopg2 및 PostgreSQL 연동 필요)
RUN apt-get update && \
    apt-get install -y gcc libpq-dev curl && \
    apt-get clean

# requirements.txt 복사 및 설치
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 앱 소스 복사
COPY . .

# 포트 노출 (Django 개발 서버 기준)
EXPOSE 8000

# .env 포함 시 django-environ 등으로 읽기 가능
# 기본 커맨드는 dev 서버 실행, docker-compose에서 override 가능
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
