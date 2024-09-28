
FROM python:3.12.5


COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt
COPY . /app



WORKDIR /app
EXPOSE 8483 

CMD ["bash", "start.sh"]