# TG bot with Stripe.

A telegram bot that can process incoming requests in an asynchronous
mode, sells confectionery products downloaded from the database from
Stripe and receives payments using [Stripe](https://stripe.com/) 
platform and running with Docker.

### Environment variables

Create a `.env` file in the root folder with the code and write there:
```
TG_TOKEN=Your_telegram_tocken_received_in_BotFather.
STRIPE_KEY=Your_stripe_key_received_from_the_site stripe.com
```

### Program launch

You must already have [Python 3](https://www.python.org/downloads/release/python-379/) installed to run.

- Download the code.
- Install the dependencies with the command:
```
pip install -r requirements.txt
```
- Run the script with the command:
```
python payment_bot.py
```
or
- Run with docker-compose the script with the command:
```
docker-compose up --build
```