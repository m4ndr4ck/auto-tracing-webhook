FROM python:3.6-alpine

ENV PATH=/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

COPY requirements.txt requirements.txt
COPY webhook.py webhook.py
COPY webhook-server-tls.crt webhook-server-tls.crt
COPY webhook-server-tls.key webhook-server-tls.key

RUN pip3 install -r requirements.txt

ENTRYPOINT ["python", "webhook.py"]
