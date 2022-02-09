FROM "python:3.9"

WORKDIR /app/src
ADD requirements.txt /app/src/
RUN python -m pip install --upgrade pip
RUN pip install -r requirements.txt

ADD main.py /app/src/

CMD python main.py