# BTC-notify-bot
이평선을 통한 매수-매도 타이밍을 텔레그램 봇으로 notify

## How to get started
#### Get started with docker
~~~~bash
docker build -t "mabot" .

docker run \
  -v ${PWD}/memory:/app/src/memory \
  -e bot-token="텔레그램 봇 토큰" \
  mabot
~~~~
